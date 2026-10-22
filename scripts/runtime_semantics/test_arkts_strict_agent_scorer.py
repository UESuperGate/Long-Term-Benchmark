#!/usr/bin/env python3
import subprocess
import sys
import time
import unittest
import json
import tempfile
import copy
from contextlib import contextmanager
import shutil
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arkts_strict_agent_scorer as scorer


CASE = {"caseId": "case_001", "key": "one", "traceDigest": "a" * 64}


class ArktsStrictAgentScorerTest(unittest.TestCase):
    def test_storage_guard_is_unscored_without_starting_a_build(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            contract = root / 'contract.json'
            contract.write_text(json.dumps({'taskId': '16_identity_reset', 'cases': [CASE]}))
            with patch.object(scorer.shutil, 'disk_usage', return_value=SimpleNamespace(free=1)), \
                    patch.object(scorer.subprocess, 'run') as execute:
                report = scorer.score(task_id='16_identity_reset', source=root,
                                      output=root / 'report.json', deadline=time.monotonic() + 3600,
                                      contract_path=contract, build_script=root / 'builder.cjs')
            execute.assert_not_called()
            self.assertEqual('not_scored', report['semantic']['cases'][0]['status'])
            self.assertIn('Storage protection', report['diagnostics']['reason'])
            self.assertFalse(report['diagnostics']['publishableWithoutApplicationCompile'])

    def test_extracts_only_exact_fresh_transport_row(self):
        execution = {"status": "transport_completed", "transportCompleted": True,
                     "candidateAbsentBeforeInstall": True,
                     "cleanup": {"ownedAppUninstalled": True},
                     "rows": [{**CASE, "status": "pass"}]}
        self.assertEqual(scorer.extract_row(execution, CASE)["status"], "pass")
        for mutate in (
            lambda value: value.update(transportCompleted=False),
            lambda value: value.update(candidateAbsentBeforeInstall=False),
            lambda value: value["cleanup"].update(ownedAppUninstalled=False),
            lambda value: value["rows"][0].update(traceDigest="b" * 64),
        ):
            candidate = {"status": "transport_completed", "transportCompleted": True,
                         "candidateAbsentBeforeInstall": True,
                         "cleanup": {"ownedAppUninstalled": True},
                         "rows": [{**CASE, "status": "pass"}]}
            mutate(candidate)
            with self.assertRaises(RuntimeError):
                scorer.extract_row(candidate, CASE)

    def test_build_validation_rejects_role_and_production_mutations(self):
        report = {"taskId": "17_pinned_messages", "role": "agent", "caseId": CASE["caseId"],
                  "status": "built_not_executed", "runtimeCompile": {"passed": True},
                  "productionUnchanged": True, "copiedProductionUnchanged": True,
                  "nativeUIObserver": {"productionUnchanged": True}}
        scorer.validate_build(report, "17_pinned_messages", CASE)
        for field, value in (("role", "final"), ("productionUnchanged", False)):
            candidate = {**report, field: value}
            with self.assertRaises(RuntimeError):
                scorer.validate_build(candidate, "17_pinned_messages", CASE)

    def test_environment_failure_rows_are_all_not_scored(self):
        contract = {"cases": [CASE, {"caseId": "case_002", "key": "two", "traceDigest": "b" * 64}]}
        rows = scorer.unavailable_rows(contract, "device offline")
        self.assertEqual([row["status"] for row in rows], ["not_scored", "not_scored"])

    def test_single_absolute_deadline_expires(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            scorer.remaining(time.monotonic() - 1, "whole score")

    def test_only_cleaned_preflight_transport_failure_is_retryable(self):
        cleaned = {"error": "SyntaxError: Unexpected end of JSON input",
                   "cleanup": {"ownedAppUninstalled": True}}
        self.assertTrue(scorer.retryable_environment_failure(cleaned))
        cleaned["cleanup"]["ownedAppUninstalled"] = False
        self.assertFalse(scorer.retryable_environment_failure(cleaned))
        semantic = {"error": "canonical assertion failed", "cleanup": {"ownedAppUninstalled": True}}
        self.assertFalse(scorer.retryable_environment_failure(semantic))


class ProspectiveHookTest(unittest.TestCase):
    """Isolated synthetic transport controls, never counted as device/model results."""

    @contextmanager
    def fixture(self, *, role='base', before_source=None, after_execution=None, capture_hook=None,
                seal_hook=None, task_id='16_identity_reset', case_count=1):
        historical = scorer.ROOT / 'experiment_results/runtime_transition_20261020'
        fixture_task=task_id if task_id in {'16_identity_reset','17_pinned_messages'} else '16_identity_reset'
        folder = historical / ('task16_arkts_entry_controls_v3_'+role if fixture_task=='16_identity_reset' else
                               'task17_arkts_entry_controls_'+('v2' if role=='base' else 'v1'))
        original = json.loads((folder/(role+'-as-agent.json')).read_text())
        original_inputs = json.loads((folder/(role+'-input.json')).read_text())
        root = Path(original['provenance']['strictEvidence']['path'])
        run = original['provenance']['executions'][0]
        execution_path = root/run['report']
        build_template = json.loads((execution_path.parent.parent/'device-build-report.json').read_text())
        native_template = json.loads((execution_path.parent/'native-result.json').read_text())
        actual_contract = json.loads((scorer.ROOT/'benchmark_tasks'/fixture_task/'transitions.json').read_text())
        spec = actual_contract['cases'][0]
        specs=actual_contract['cases'][:case_count]
        entry = sys.modules[scorer.attach_entries.__module__]
        actual_capture = scorer.input_guard.capture_inputs
        actual_seal = scorer.input_guard.seal_inputs
        with tempfile.TemporaryDirectory(prefix='ltb-prospective-hook-test-') as directory:
            workspace = Path(directory).resolve()
            source = workspace/'random-project'
            source.mkdir()
            for item in original_inputs['files']:
                path = source/item['path']
                path.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(Path(original_inputs['copiedFrom'])/item['path'],path)
            if before_source:
                before_source(source)
            output = workspace/'experiment_results'/'isolated'/'report.json'
            output.parent.mkdir(parents=True)
            contract = workspace/'contract.json'
            contract.write_text(json.dumps({'taskId':task_id,'cases':specs}))
            events, locks, deadlines = [], [], []
            deadline = time.monotonic()+60

            def capture(*args,**kwargs):
                phase=kwargs['phase']
                events.append(phase)
                deadlines.append(kwargs['deadline'])
                result=actual_capture(*args,**kwargs)
                if capture_hook:
                    result=capture_hook(source,phase,Path(args[1]),result)
                return result

            def execute(command,**kwargs):
                self.assertLessEqual(kwargs['timeout'],60)
                if '--output-dir' in command:
                    events.append('build')
                    case_root=Path(command[command.index('--output-dir')+1])
                    case_root.mkdir(parents=True)
                    report=copy.deepcopy(build_template)
                    report.update(source=str(source),taskId=task_id,caseId=command[command.index('--case')+1])
                    production=[{'path':p.relative_to(source).as_posix(),'sha256':scorer.sha256(p)}
                                for p in sorted((source/'entry/src/main').rglob('*')) if p.is_file()]
                    report['production']=production
                    report['nativeUIObserver']['production']=production
                    for fixture in report['nativeUIObserver']['fixtures']:
                        old=Path(fixture['file'])
                        path=workspace/'state_tests/runtime/arkts/native'/old.name
                        path.parent.mkdir(parents=True,exist_ok=True)
                        if not path.exists():
                            shutil.copyfile(old,path)
                        fixture['file']=str(path)
                    (case_root/'device-build-report.json').write_text(json.dumps(report))
                    (case_root/'owned-test.hap').write_bytes(b'synthetic test artifact')
                else:
                    events.append('device')
                    self.assertEqual('1',kwargs['env']['LTB_DEVICE_LOCK_PREACQUIRED'])
                    build_path=Path(command[2])
                    destination=Path(command[4])
                    destination.mkdir()
                    raw=copy.deepcopy(native_template)
                    actual_build=json.loads(build_path.read_text())
                    current_spec=next(item for item in specs if item['caseId']==actual_build['caseId'])
                    raw.update(taskId=task_id,caseId=current_spec['caseId'],traceDigest=current_spec['traceDigest'])
                    raw_path=destination/'native-result.json'
                    raw_path.write_text(json.dumps(raw))
                    transport={'status':'transport_completed','transportCompleted':True,
                        'candidateAbsentBeforeInstall':True,'cleanup':{'ownedAppUninstalled':True},
                        'executionNonce':'synthetic-isolated-nonce-'+current_spec['caseId'],'pid':123,'rows':[raw],
                        'buildReport':scorer.input_guard.record(build_path),
                        'rowArtifact':scorer.input_guard.record(raw_path),'commands':[]}
                    (destination/'device-execution.json').write_text(json.dumps(transport))
                    if after_execution:
                        after_execution(source)
                return SimpleNamespace(returncode=0)

            def acquire(serial,passed_deadline):
                self.assertEqual(deadline,passed_deadline)
                lock=workspace/'isolated-lease'
                lock.mkdir()
                locks.append(lock)
                return lock

            def seal(*args,**kwargs):
                if seal_hook:
                    return seal_hook(*args,**kwargs)
                return actual_seal(*args,**kwargs)

            with patch.object(scorer.input_guard,'ROOT',workspace),patch.object(entry,'ROOT',workspace), \
                    patch.object(scorer.shutil,'disk_usage',return_value=SimpleNamespace(free=9*1024**3)), \
                    patch.object(scorer.subprocess,'run',side_effect=execute), \
                    patch.object(scorer,'discover_device',return_value='isolated-not-a-real-device'), \
                    patch.object(scorer,'acquire_device',side_effect=acquire), \
                    patch.object(scorer.input_guard,'capture_inputs',side_effect=capture), \
                    patch.object(scorer.input_guard,'seal_inputs',side_effect=seal):
                if task_id not in {'16_identity_reset','17_pinned_messages'}:
                    with patch.object(scorer,'attach_entries'):
                        report=scorer.score(task_id=task_id,source=source,output=output,deadline=deadline,
                            contract_path=contract,build_script=workspace/'synthetic-builder.cjs')
                else:
                    report=scorer.score(task_id=task_id,source=source,output=output,deadline=deadline,
                        contract_path=contract,build_script=workspace/'synthetic-builder.cjs')
                self.assertTrue(all(not lock.exists() for lock in locks))
                yield report,source,output,events,deadlines,deadline,entry,spec

    def assert_ns(self,report):
        self.assertEqual('not_scored',report['semantic']['cases'][0]['status'])
        self.assertNotIn('entryFailureEvidence',report['semantic']['cases'][0])
        self.assertFalse(report['diagnostics']['publishableWithoutApplicationCompile'])

    def test_actual_before_build_then_execution_after_order_and_same_overall_deadline(self):
        with self.fixture() as (report,source,output,events,deadlines,deadline,entry,spec):
            self.assertEqual(['before_runtime','build','device','after_runtime'],events)
            self.assertEqual([deadline,deadline],deadlines)
            self.assertEqual('fail',report['semantic']['cases'][0]['status'])
            self.assertTrue(report['diagnostics']['publishableWithoutApplicationCompile'])
            self.assertEqual({},report['diagnostics']['prospectiveInputIssues'])
            binding=report['provenance']['entryInputBindings'][spec['caseId']]
            root=Path(report['provenance']['strictEvidence']['path'])
            data=scorer.input_guard.bound(binding)
            for item in (binding,data['before'],data['after'],data['build']):
                self.assertTrue(Path(item['path']).is_relative_to(root))
                self.assertTrue(Path(item['path']).is_file())
            manifest=json.loads(Path(report['provenance']['strictEvidence']['manifest']).read_text())
            inventory={item['path'] for item in manifest['files']}
            for item in (binding,data['before'],data['after'],data['build']):
                self.assertIn(str(Path(item['path']).relative_to(root)),inventory)
            self.assertFalse(list(root.rglob('*.hap')))
            shutil.rmtree(source)
            entry.validate_entry_failure(report['semantic']['cases'][0],report,set(),
                contract={'taskId':'16_identity_reset','cases':[spec]})

    def test_real_canonical_final_row_does_not_need_base_only_missing_entry_binding(self):
        with self.fixture(role='final') as (report,*_):
            self.assertEqual('pass',report['semantic']['cases'][0]['status'])
            self.assertTrue(report['diagnostics']['publishableWithoutApplicationCompile'])
            self.assertEqual(1,len(report['provenance']['entryInputBindings']))

    def test_task17_base_and_final_paths_also_receive_prospective_capture(self):
        for role,status in [('base','fail'),('final','pass')]:
            with self.subTest(role=role),self.fixture(task_id='17_pinned_messages',role=role) as \
                    (report,_,_,events,*_):
                self.assertEqual(['before_runtime','build','device','after_runtime'],events)
                self.assertEqual(status,report['semantic']['cases'][0]['status'])
                self.assertTrue(report['diagnostics']['publishableWithoutApplicationCompile'])

    def test_each_case_captures_and_seals_independently_without_reusing_first_case_binding(self):
        with self.fixture(case_count=2) as (report,_,_,events,deadlines,deadline,*_):
            self.assertEqual(['before_runtime','build','device','after_runtime']*2,events)
            self.assertEqual([deadline]*4,deadlines)
            mapping=report['provenance']['entryInputBindings']
            self.assertEqual(2,len(mapping))
            build_paths=[]
            for case_id,item in mapping.items():
                data=scorer.input_guard.bound(item)
                self.assertIn(case_id,data['build']['path'])
                build_paths.append(data['build']['path'])
            self.assertEqual(2,len(set(build_paths)))
            self.assertEqual(['fail','fail'],[row['status'] for row in report['semantic']['cases']])

    def test_changed_inputs_after_execution_are_ns_not_a_semantic_failure(self):
        with self.fixture(after_execution=lambda source:(source/'unknown.json').write_text('{}')) as (report,*_):
            self.assert_ns(report)
            self.assertTrue(report['runtimeCompile']['passed'])
            self.assertIn('changed during',str(report['diagnostics']['prospectiveInputIssues']))

    def test_added_production_control_with_old_positive_prefix_is_ns(self):
        def added(source):
            (source/'entry/src/main/ets/pages/AnotherEntry.ets').write_text('export const alternate = true')
        with self.fixture(before_source=added) as (report,*_):
            self.assert_ns(report)
            guard=report['semantic']['cases'][0]['entryBindingGuard']
            self.assertIn('unbound_compiled_production_closure',guard['reasonCodes'])

    def test_stable_unknown_enclosing_config_with_unchanged_old_ui_is_ns(self):
        with self.fixture(before_source=lambda source:(source/'another-profile.json5').write_text('{}')) as (report,*_):
            self.assert_ns(report)
            self.assertIn('unbound_complete_enclosing_inputs',report['semantic']['cases'][0]['entryBindingGuard']['reasonCodes'])

    def test_before_inventory_failure_starts_no_build_and_cannot_use_legacy_defaults(self):
        with self.fixture(before_source=lambda source:(source/'.env').write_text('synthetic fixture only')) as (report,_,_,events,*_):
            self.assert_ns(report)
            self.assertEqual(['before_runtime'],events)
            self.assertEqual({},report['provenance']['entryInputBindings'])
            self.assertEqual('not_run',report['diagnostics']['transport'])

    def test_missing_before_inventory_after_runtime_is_ns(self):
        def hook(source,phase,path,result):
            if phase=='after_runtime':
                (path.parent/'before.json').unlink()
            return result
        with self.fixture(capture_hook=hook) as (report,*_):
            self.assert_ns(report)
            self.assertEqual({},report['provenance']['entryInputBindings'])

    def test_bad_phase_or_incomplete_after_inventory_is_ns(self):
        for field,value in [('phase','before_runtime'),('complete',False),('producer',{})]:
            def hook(source,phase,path,result):
                if phase=='after_runtime':
                    data=json.loads(path.read_text())
                    data[field]=value
                    path.write_text(json.dumps(data))
                    return scorer.input_guard.record(path)
                return result
            with self.subTest(field=field),self.fixture(capture_hook=hook) as (report,*_):
                self.assert_ns(report)

    def test_sealer_missing_receipt_never_falls_back_to_legacy(self):
        with self.fixture(seal_hook=lambda *args,**kwargs:None) as (report,*_):
            self.assert_ns(report)
            self.assertEqual({},report['provenance']['entryInputBindings'])

    def test_retained_capture_tamper_is_detected_by_independent_validator_after_cleanup(self):
        with self.fixture() as (report,source,_,_,_,_,entry,spec):
            shutil.rmtree(source)
            binding=scorer.input_guard.bound(report['provenance']['entryInputBindings'][spec['caseId']])
            Path(binding['after']['path']).write_text('{}')
            with self.assertRaisesRegex(ValueError,'bytes changed'):
                entry.validate_entry_failure(report['semantic']['cases'][0],report,set(),
                    contract={'taskId':'16_identity_reset','cases':[spec]})

    def test_hook_not_invoked_for_other_tasks(self):
        with self.fixture(task_id='12_report_room') as (report,_,_,events,*_):
            self.assertEqual(['build','device'],events)
            self.assertNotIn('entryInputBindings',report['provenance'])


if __name__ == "__main__":
    unittest.main()
