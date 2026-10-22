"""Offline default-guard/host-production tests. No device/calibration claim."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
import os
import subprocess
import sys
from unittest import mock

from . import task15_full_report_v3 as full
from . import task15_full_report_verify_v3 as guard
from . import test_task15_fresh_protocol_v2 as fixtures
from . import task15_native_transition_v3 as native_projection

FINAL = full.ROOT / 'final_dev_nodes/15_account_deactivation_final_0_6_3'
CANDIDATE = fixtures.SOURCE


def run_hosts(source, output):
    index, deadline = full.prepare_index(source=source, output=output, timeout=120)
    for case_id in sorted(full.HOST_CASES):
        directory = output / 'host' / case_id
        plan = full.prepare_host(source=source, case_id=case_id, output=directory, deadline=deadline,
                                 inputs=index['inputInventory'])
        full.command(plan['command'], log=directory / 'host.log', deadline=deadline)
        index['host'][case_id] = {key: full.raw.artifacts.artifact(path) for key, path in {
            'plan': directory / 'plan.json', 'raw': directory / 'raw.json',
            'command': directory / 'host.command.json'}.items()}
    index['finishedAtEpochMs'] = int(time.time() * 1000)
    full.core.write(output / 'episode-index.json', index)
    return index


class FullHostDefaultGuardTests(unittest.TestCase):
    def test_work_deadline_reserves_cleanup_without_starting_sdk_or_device(self):
        from . import task15_prefix_v3 as prefix
        from . import task15_capability_v3 as capability
        with tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as temporary:
            root = Path(temporary)
            deadline = time.monotonic() + 3500
            evidence = root / 'prefix'; evidence.mkdir()
            build = {'hap': {'path': str(root / 'not-created.hap')}}
            with mock.patch.object(prefix.core, 'build_arkts_application', return_value=build) as builder, \
                 mock.patch.object(full, 'command', side_effect=RuntimeError('UNIT stop before device')):
                with self.assertRaisesRegex(RuntimeError, 'UNIT stop'):
                    prefix.evaluate(source=FINAL, evidence=evidence, deadline=deadline, device_serial='127.0.0.1:5555')
                self.assertEqual(deadline - 120, builder.call_args.kwargs['deadline'])
            generated = evidence / 'task15-base-source-parameterized.cjs'
            self.assertIn('Whole base probe deadline exhausted', generated.read_text())
            self.assertIn("args[0] === 'uninstall'", generated.read_text())
            checked = subprocess.run(['node', '--check', str(generated)], capture_output=True, timeout=10)
            self.assertEqual(0, checked.returncode, checked.stderr)
            with mock.patch.object(capability, 'compile_fixture', side_effect=RuntimeError('UNIT stop before SDK')) as compiler, \
                 mock.patch.object(capability.lease, 'task_scope') as lease:
                with self.assertRaisesRegex(RuntimeError, 'UNIT stop'):
                    capability.evaluate(source=FINAL, output=root / 'cap', deadline=deadline, device_serial='127.0.0.1:5555')
                self.assertEqual(deadline - 120, compiler.call_args.kwargs['deadline'])
                lease.assert_not_called()
            self.assertFalse(list(root.rglob('*.hap')))

    def test_owned_process_group_timeout_is_stopped_not_left_running(self):
        with tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as temporary:
            result = full.command([sys.executable, '-c', 'import time; time.sleep(30)'],
                log=Path(temporary) / 'timeout.log', deadline=time.monotonic() + 0.1)
            self.assertTrue(result['timedOut'])
            self.assertTrue(result['ownedProcessGroupStopped'])
            with self.assertRaises(ProcessLookupError):
                os.kill(result['pid'], 0)

    def test_real_final_and_exact_candidate_have_five_own_host_production_episodes(self):
        with tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as temporary:
            for name, source in (('final', FINAL), ('candidate', CANDIDATE)):
                with self.subTest(source=name):
                    output = Path(temporary) / name
                    index = run_hosts(source, output)
                    report = full.assemble(full.raw.artifacts.artifact(output / 'episode-index.json'),
                                           output=output / 'report.json')
                    self.assertEqual((5, 0, 5), tuple(report['semantic'][key] for key in ('passed', 'failed', 'notScored')))
                    self.assertIsNone(report['compile']['passed'])
                    self.assertFalse(report['runtimeCompile']['passed'])
                    receipt = guard.verify_report(output / 'report.json')
                    self.assertTrue(receipt['publicValidatorPassed'])
                    self.assertFalse(receipt['publicationEligible'])
                    with self.assertRaisesRegex(ValueError, 'NS controls'):
                        reference = full.raw.artifacts.artifact(output / 'report.json')
                        guard.verify_controls({pole: reference for pole in
                            ('base', 'final', 'base_copy_agent', 'final_copy_agent')},
                            evaluator_sha=index['evaluator']['sha256'])
                    episodes = [row['episodeId'] for row in report['semantic']['cases'] if row['status'] == 'pass']
                    self.assertEqual(5, len(set(episodes)))
                    spec = full.core.load(full.native.CONTRACT)['cases'][2]
                    raw = full.raw.read(index['host'][spec['caseId']]['raw'])
                    event = next(action for action in raw['actions'] if action['phase'] == 'event')
                    self.assertEqual(['secret\n'], event['args'])
                    self.assertEqual(spec, raw['canonicalCase'])
                    for mutation in ('wrong_verdict', 'invented_invariant', 'missing_case', 'app_runtime_conflation'):
                        changed = copy.deepcopy(report)
                        if mutation == 'wrong_verdict': changed['semantic']['cases'][1]['status'] = 'fail'
                        elif mutation == 'invented_invariant': changed['semantic']['cases'][1]['invariantChecks'][0]['passed'] = False
                        elif mutation == 'missing_case': changed['semantic']['cases'].pop()
                        else: changed['compile']['passed'] = True
                        with self.assertRaises(ValueError):
                            guard.verify_value(changed, full.core.load(full.native.CONTRACT))

    def test_mutated_default_production_is_fail_not_setter_repaired_or_environment_ns(self):
        with tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as temporary:
            source = Path(temporary) / 'random-source'
            full.core._copy_project(FINAL, source)
            feature = source / 'entry/src/main/ets/features/AccountDeactivationFeature.ets'
            original = feature.read_text()
            self.assertEqual(1, original.count("password: string = '';"))
            feature.write_text(original.replace("password: string = '';", "password: string = 'unexpected-default';"))
            output = Path(temporary) / 'run'
            index = run_hosts(source, output)
            contract = full.core.load(full.native.CONTRACT)
            row = guard.host_row(index['host'][contract['cases'][1]['caseId']], index, contract['cases'][1])
            self.assertEqual('fail', row['status'])
            self.assertEqual('unexpected-default', row['observed']['password'])
            self.assertEqual('', row['canonicalObligations']['expected']['password'])
            raw = full.raw.read(index['host'][row['caseId']]['raw'])
            self.assertFalse(any(action['method'] in ('setPassword', 'setEraseData') for action in raw['actions']))

    def test_old_v2_fingerprint_and_public_registry_are_untouched(self):
        audit = full.core.load(full.native.REVIEW / 'review.json')
        for pair in audit['implementationSources']:
            self.assertEqual(pair['original']['sha256'], full.core.sha256(Path(pair['original']['path'])))
        from scripts import run_runtime_transition_matrix as public
        self.assertNotIn(full.POLICY, public.SOURCE_BOUND_ENTRY_POLICIES)
        self.assertEqual(5, len(full.HOST_CASES))
        self.assertEqual(5, len(full.native.NATIVE_CASES))

    def test_native_case001_has_own_before_event_in_new_version_only(self):
        new = full.ENGINE.read_text()
        old = (full.native.NATIVE / 'Task15FreshActionsV2.js').read_text()
        section = "      stage = 'load_settings';\n"
        self.assertIn(section + "      await capture('before_event');", new)
        self.assertNotIn(section + "      await capture('before_event');", old)

    def test_offline_native_preparation_binds_actual_successor_engine_not_v2_relabeling(self):
        with tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as temporary:
            directory = Path(temporary) / 'new-native-episode'
            plan = full.prepare_native(source=FINAL, case_id='ad_state_001_capability_gates_entry',
                output=directory, deadline=time.monotonic() + 3500, serial='127.0.0.1:5555')
            self.assertTrue(plan['preparedOnly'])
            self.assertFalse(plan['deviceOrModelStarted'])
            self.assertEqual(full.PROTOCOL, plan['reportProtocol'])
            self.assertEqual(full.implementation(), plan['evaluator'])
            source = next(item for item in plan['evaluator']['files']
                          if Path(item['path']).name == 'Task15FreshActionsV2.js')
            engine = directory / 'native-environment-fixtures/Task15FreshActionsV2.js'
            self.assertEqual(full.core.sha256(full.ENGINE), source['sha256'])
            self.assertEqual(source['sha256'], full.core.sha256(engine))
            self.assertNotEqual(full.core.sha256(full.native.NATIVE / engine.name), source['sha256'])
            self.assertTrue((directory / 'v2-preparation-plan.json').is_file())
            self.assertFalse(list(directory.rglob('*.hap')))


class FullCompositionFixtureTests(unittest.TestCase):
    def test_four_control_driver_is_explicit_serial_single_budget_and_hash_cleans_copies(self):
        with tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as temporary:
            output = Path(temporary) / 'no-execution'
            with self.assertRaisesRegex(ValueError, 'explicit coordinator release'):
                full.run_four_controls(base_source=full.ROOT / '15_account_deactivation_base_0_6_1',
                    final_source=FINAL, output=output)
            self.assertFalse(output.exists())
            seen = []
            def fake_evaluate(**kwargs):
                # Driver-only fixture; never a production/control evidence claim.
                seen.append(kwargs)
                directory = kwargs['output']; directory.mkdir(parents=True)
                full.core.write(directory / 'report.json', {'UNIT_DRIVER_FIXTURE': True})
            with mock.patch.object(full, 'evaluate', side_effect=fake_evaluate), \
                 mock.patch.object(guard, 'verify_controls', return_value={'UNIT_DRIVER_FIXTURE': True}):
                result = full.run_four_controls(base_source=full.ROOT / '15_account_deactivation_base_0_6_1',
                    final_source=FINAL, output=Path(temporary) / 'fixture-group', timeout=120, execute=True)
            self.assertEqual(['base', 'final', 'base_copy_agent', 'final_copy_agent'],
                             [value['control_label'] for value in seen])
            self.assertEqual(1, len({value['deadline'] for value in seen}))
            self.assertTrue(all(value['timeout'] == 120 for value in seen))
            self.assertFalse((Path(temporary) / 'fixture-group/sources').exists())
            self.assertEqual(4, len(result['cleanup']['trees']))
            self.assertTrue(all(not value['source'].exists() for value in seen))

    def test_all_ten_rows_are_composed_and_independently_checked_not_005_projected(self):
        # Native data below is explicitly synthetic; no device/HAP is built.
        # The envelope boundary has separate real-schema mutation tests in v2.
        with tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as temporary:
            output = Path(temporary) / 'synthetic-composition'
            index = run_hosts(FINAL, output)
            contract = full.core.load(full.native.CONTRACT)
            snapshot = full.raw.read(index['inputInventory'])
            production = [{key: item[key] for key in ('path', 'bytes', 'sha256')} for item in snapshot['files']
                          if item['path'].startswith('entry/src/main/')]
            build = output / 'unit-not-a-real-device-build.json'
            full.core.write(build, {'runtimeCompile': {'passed': True}})
            cap = output / 'unit-not-a-real-capability.json'
            full.core.write(cap, {'build': {'runtimeCompile': {'passed': True}}})
            index['capability'] = full.raw.artifacts.artifact(cap)
            native_data = {}
            for spec in contract['cases']:
                if spec['caseId'] not in full.native.NATIVE_CASES:
                    continue
                case_id = spec['caseId']
                bundle = {'build': full.raw.artifacts.artifact(build), 'caseId': case_id}
                index['native'][case_id] = bundle
                frames = [{'label': 'before_event', 'sequence': 10, 'sessionId': case_id},
                          {'label': 'after_event', 'sequence': 20, 'sessionId': case_id}]
                data = {'plan': {'reportProtocol': full.PROTOCOL, 'evaluator': index['evaluator'], 'source': index['source'],
                                'deadlineEpochMs': index['deadlineEpochMs']}, 'spec': spec,
                    'inputs': snapshot, 'build': {'production': production},
                    'native': {'outcome': 'transition_observed', 'sessionId': 'unit-only:' + case_id, 'frames': frames}}
                native_data[case_id] = data
            # Test composition, not physical/native admission (which remains separately fail-closed).
            def row(bundle, current_index, spec):
                data = native_data[bundle['caseId']]
                self.assertEqual(spec, data['spec'])
                return guard._row(spec, observed=copy.deepcopy(spec['expected']),
                    checks=[{'description': text, 'passed': True, 'observed': {'UNIT_FIXTURE_NOT_DEVICE': True}}
                            for text in spec['invariants']], checkpoints=data['native']['frames'], sources=production,
                    runtime='openharmony_api23_device_https_arkui', raw_evidence=bundle,
                    episode_id=data['native']['sessionId'])
            full.core.write(output / 'episode-index.json', index)
            with mock.patch.object(guard, '_native_row', side_effect=row):
                report = full.assemble(full.raw.artifacts.artifact(output / 'episode-index.json'), output=output / 'report.json')
                self.assertEqual((10, 0, 0), tuple(report['semantic'][key] for key in ('passed', 'failed', 'notScored')))
                self.assertEqual([spec['caseId'] for spec in contract['cases']],
                                 [row['caseId'] for row in report['semantic']['cases']])
                self.assertEqual(10, len({row['episodeId'] for row in report['semantic']['cases']}))
                self.assertTrue(guard.verify_report(output / 'report.json')['independentDefaultGuardPassed'])
                for row in report['semantic']['cases']:
                    spec = next(spec for spec in contract['cases'] if spec['caseId'] == row['caseId'])
                    self.assertEqual(guard._obligations(spec), row['canonicalObligations'])
                report['semantic']['cases'][5]['rawEpisode'] = report['semantic']['cases'][4]['rawEpisode']
                with self.assertRaises(ValueError):
                    guard.verify_value(report, contract)
            # The synthetic native fixture must NOT pass the production guard
            # once the composition-only mock boundary is removed.
            with self.assertRaises(ValueError):
                guard.verify_report(output / 'report.json')

    def test_four_controls_required_before_candidate005_and_no_role_verdict_selection(self):
        with self.assertRaisesRegex(ValueError, 'Four fresh controls required'):
            guard.verify_controls({}, evaluator_sha='0' * 64)
        with tempfile.TemporaryDirectory(dir=full.REVIEW.parent) as temporary:
            index, _ = full.prepare_index(source=CANDIDATE, output=Path(temporary) / 'agent-copy',
                                          timeout=120, control_label='base')
            # A label cannot manufacture a base FAIL: absent raw evidence stays ten NS.
            rows, _ = guard.derive_rows(index, full.core.load(full.native.CONTRACT))
            self.assertEqual({'passed': 0, 'failed': 0, 'notScored': 10, 'total': 10}, guard.counts(rows))

    def test_async_failure_settlement_advances_same_call_without_changing_original_obligations(self):
        value = fixtures.unit_transition(8)
        prior = value['native']['frames'][0]['presenter']
        after = value['native']['frames'][1]['presenter']
        call = {'instanceId': prior['serviceId'], 'sequence': 1, 'method': 'deactivateAccount',
                'args': ['secret', True], 'returned': True}
        prior['serviceCalls'] = [copy.deepcopy(call)]
        after['serviceCalls'] = [{**call, 'settlement': {'status': 'rejected'}}]
        self.assertEqual('pass', native_projection.inspect_transition(value)['status'])
        self.assertNotIn('settlement', prior['serviceCalls'][0])
        for mutation in ('wrong_payload', 'different_receiver', 'fulfilled', 'not_actual503'):
            changed = copy.deepcopy(value)
            call = changed['native']['frames'][1]['presenter']['serviceCalls'][0]
            if mutation == 'wrong_payload': call['args'] = ['other', False]
            elif mutation == 'different_receiver': call['instanceId'] = -1
            elif mutation == 'fulfilled': call['settlement']['status'] = 'fulfilled'
            else: changed['native']['actions'][-1]['status'] = 200
            with self.assertRaises(ValueError):
                native_projection.inspect_transition(changed)


if __name__ == '__main__':
    unittest.main()
