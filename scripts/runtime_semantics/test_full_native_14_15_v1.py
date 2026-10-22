"""OFFLINE synthetic/admission regression tests; never device calibration."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from . import full_native_14_15_guard_v1 as guard
from . import full_native_14_15_runner_v1 as runner
from . import task14_full_native_packaging_v5 as p14
from . import task15_full_native_v7 as p15
from .test_task14_actual_routes_guard_v4 import fixture as routes_fixture
from .test_task15_page_owner_v5 import fixture as owner_fixture


def route(number):
    episode, spec, profile = routes_fixture(number)
    episode['protocol'] = guard.P14
    def update(value):
        if isinstance(value, list):
            for child in value:
                update(child)
        elif isinstance(value, dict):
            if 'resolverRequests' in value:
                value['boundaryProtocol'] = guard.BOUNDARY
                for request in value['resolverRequests']:
                    request.update(bridgeCallId=1, externalLeaf='DemoRoomGateway.resolveAlias')
                call = {'id': 1, 'alias': value['address'], 'calledOriginal': True, 'returned': True,
                    'receiverIsPageResolver': True, 'leafIsOriginalGateway': True}
                if number == 5:
                    call.update(settlement='fulfilled', value=value['resolvedRoom'])
                value['originalBridgeCalls'] = [call]
            if value.get('method') == 'Task14.externalResolverResolved':
                value['response'] = {'roomId': value['response']['roomId']}
            for child in value.values():
                update(child)
    update(episode)
    if number == 6:
        after = episode['transition']['frames'][-1]
        for state in (after['samePageOwnerState'], after['frame']['stateBefore'], after['frame']['stateAfter']):
            state['resolverRequests'][0]['settled'] = True
            state['originalBridgeCalls'][0].update(settlement='fulfilled', value={
                'roomId': spec['event']['roomId'], 'servers': spec['event']['servers']})
    return episode, spec, profile


def original_owner(number):
    data, profile = owner_fixture(number)
    data['native']['pageOwnerProtocol'] = guard.P15
    for frame in data['native']['frames']:
        frame['pageOwner']['protocol'] = guard.P15
        frame['bracketEnd'] = {key: copy.deepcopy(frame[key]) for key in ('nativeTree', 'windowIdentity', 'windowAndIme', 'pageOwner')}
    return data, profile


class FullNativeGuardTests(unittest.TestCase):
    def test_three_route_assertions_reconstruct_from_original_bridge_and_real_route(self):
        for number in (5, 6, 9):
            with self.subTest(number=number):
                episode, spec, profile = route(number)
                row = guard.inspect_task14_routes(episode, spec, profile)
                self.assertEqual('pass', row['status'])
                self.assertEqual(spec['expected'], row['observed'])
                self.assertEqual(spec['invariants'], [item['description'] for item in row['invariantChecks']])

    def test_hardcoded_demo_server_cannot_be_replaced_by_external_fixture(self):
        episode, spec, profile = route(5)
        episode['transition']['frames'][1]['samePageOwnerState']['originalBridgeCalls'][0]['value']['servers'] = ['demo.local']
        with self.assertRaisesRegex(ValueError, 'Original bridge did not produce'):
            guard.inspect_task14_routes(episode, spec, profile)

    def test_new_bridge_bypass_and_modified_leaf_are_not_eligible(self):
        for field in ('calledOriginal', 'returned', 'receiverIsPageResolver', 'leafIsOriginalGateway'):
            episode, spec, profile = route(9)
            episode['transition']['frames'][1]['samePageOwnerState']['originalBridgeCalls'][0][field] = False
            with self.subTest(field=field), self.assertRaises(ValueError):
                guard.inspect_task14_routes(episode, spec, profile)

    def test_unknown_alternate_control_and_intent_only_navigation_fail_closed(self):
        episode, spec, profile = route(9)
        frame = episode['transition']['frames'][-1]['frame']
        frame['tree']['$children'].append({'$type': 'Button', '$attrs': {'id': 'unknown'}, '$children': []})
        frame['bracketEnd']['tree'] = copy.deepcopy(frame['tree'])
        with self.assertRaises(ValueError):
            guard.inspect_task14_routes(episode, spec, profile)

    def test_five_previously_host_cases_require_each_own_original_native_owner(self):
        for number in (2, 3, 4, 7, 10):
            with self.subTest(number=number):
                data, profile = original_owner(number)
                row = guard.inspect_task15(data, profile)
                self.assertEqual('pass', row['status'])
                self.assertEqual(data['spec']['expected'], row['observed'])
                self.assertFalse(row['presenterGetterUsedAsUiVerdict'])

    def test_native_disabled_submit_remains_real_fail_despite_true_domain_getter(self):
        data, profile = original_owner(3)
        after = data['native']['frames'][-1]
        guard.transport._control(after, 'submit')['enabled'] = False
        after['nativeTree']['$children'][5]['$attrs']['enabled'] = False
        after['bracketEnd']['nativeTree'] = copy.deepcopy(after['nativeTree'])
        self.assertEqual('fail', guard.inspect_task15(data, profile)['status'])

    def test_own_episode_not_borrowed005_or_a_new_domain_presenter(self):
        for mutation in ('episode', 'owner', 'extra_control', 'ime'):
            data, profile = original_owner(3)
            after = data['native']['frames'][-1]
            if mutation == 'episode':
                after['sessionId'] = 'borrowed005'
            elif mutation == 'owner':
                after['pageOwner']['observerMode'] = 'new_host_presenter'
            elif mutation == 'ime':
                after['windowAndIme']['keyboardVisible'] = True
            else:
                after['nativeTree']['$children'].append({'$type': 'Button', '$attrs': {'id': 'unbound'}, '$children': []})
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                guard.inspect_task15(data, profile)

    def test_unapproved_profile_cannot_score_synthetic_or_old_raw(self):
        self.assertEqual({}, guard.REVIEWED_PROFILES)
        for task in (p14.TASK, p15.TASK):
            with self.subTest(task=task), self.assertRaisesRegex(ValueError, 'No externally reviewed'):
                guard.admit(task, {}, {}, profile_key='invented')


class PackagingAndBudgetTests(unittest.TestCase):
    def temporary(self):
        directory = tempfile.TemporaryDirectory(prefix='full-native-offline-unit-', dir=runner.ROOT / 'experiment_results')
        self.addCleanup(directory.cleanup)
        return Path(directory.name)

    def test_all_nine_and_ten_cases_are_native_not_host_selected(self):
        self.assertEqual(9, len(p14.CASES))
        self.assertEqual(10, len(p15.CASES))
        engine = p15.engine_source()
        for case in runner.core.load(p15.CONTRACT)['cases']:
            self.assertIn(case['key'], engine)
        self.assertNotIn('tasks12_15.cjs', engine)
        self.assertNotIn('new AccountDeactivationPresenter', engine)
        self.assertIn('modal_physical_input', engine)
        self.assertIn('waitHeld(2)', engine)
        observer = p15.observer_source()
        self.assertNotIn('receiver.canSubmit()', observer)
        self.assertIn(p15.PROTOCOL, observer)

    def test_generated_native_javascript_syntax_without_any_sdk_build(self):
        for code in (p15.engine_source(), p15.observer_source()):
            result = subprocess.run(['node', '--input-type=module', '--check'], input=code,
                capture_output=True, text=True, timeout=10)
            self.assertEqual(0, result.returncode, result.stderr)

    def test_fixture_inventory_has_single_pass_through_observer_and_full_case_dispatch(self):
        records = p14.expected_fixtures()
        self.assertEqual(len(records), len({item['name'] for item in records}))
        indexed = {item['name']: item for item in records}
        self.assertIn('Task14ScalarCasesV5.js', indexed)
        self.assertIn('Task14FullNativeV5.adapter.js', indexed)
        self.assertNotIn('Task14RealRoutesV4.adapter.js', indexed)

    def test_offline_ns_reports_directly_pass_current_public_validator(self):
        from scripts.run_runtime_transition_matrix import validate_report
        for task, count in ((p14.TASK, 9), (p15.TASK, 10)):
            report = runner.unavailable(task, '.', 'not executed', compile_passed=True, compile_command='retained independent app build')
            validate_report(report, runner.core.load(runner.ROOT / 'benchmark_tasks' / task / 'transitions.json'))
            self.assertEqual((0, 0, count), tuple(report['semantic'][name] for name in ('passed', 'failed', 'notScored')))
            self.assertTrue(report['compile']['passed'])
            self.assertIsNone(report['runtimeCompile']['passed'])

    def test_no_hardware_without_explicit_release_and_old_deadline_cannot_reset(self):
        for arguments in ({}, {'execute': True, 'original_deadline_epoch': time.time() - 1}):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                runner.evaluate(task=p14.TASK, source='.', output='never-created', **arguments)
        self.assertFalse(Path('never-created').exists())

    def test_missing_given_or_action_cannot_be_a_semantic_failure(self):
        episode, spec, profile = route(9)
        episode['transition']['eventExecuted'] = False
        with self.assertRaises(ValueError):
            guard.inspect_task14_routes(episode, spec, profile)

    def test_full_ten_real_source_preparation_and_installer_without_sdk_or_device(self):
        directory = self.temporary()
        source = runner.ROOT / 'final_dev_nodes/15_account_deactivation_final_0_6_3'
        before = runner.core.directory_digest(source)
        for case_id in sorted(p15.CASES):
            p15.prepare(source=source, case_id=case_id, output=directory / case_id,
                deadline=time.monotonic() + 3600)
        self.assertEqual(before, runner.core.directory_digest(source))
        script = """const fs=require('node:fs'),path=require('node:path');
const root=process.argv[1],directory=process.argv[2],work=process.argv[3],plan=JSON.parse(fs.readFileSync(path.join(directory,'plan.json')));
fs.cpSync(plan.source,work,{recursive:true,filter:file=>!['.git','build','.hvigor','oh_modules','node_modules'].includes(path.basename(file))});
fs.mkdirSync(path.join(work,'entry/src/test'),{recursive:true});const evidence=path.join(work,'bundle-evidence');fs.mkdirSync(evidence);
require(path.join(root,'scripts/runtime_semantics/arkts_native_bundle.cjs')).generate(work,evidence,'15_account_deactivation','agent',plan.source,true,{device:true,caseId:plan.caseId});
const report=require(path.join(directory,'native-environment-fixtures/Task15NativeUi.install.cjs')).install(work);
const crypto=require('node:crypto');for(const item of report.fixtures)if(crypto.createHash('sha256').update(fs.readFileSync(path.join(work,item.installedPath))).digest('hex')!==item.sha256)throw Error('Compiled fixture identity mismatch');
process.stdout.write(JSON.stringify({productionUnchanged:report.productionUnchanged,binding:report.binding}));"""
        selected = sorted(p15.CASES)[2]
        result = subprocess.run([p15.previous.NODE, '-e', script, str(runner.ROOT),
            str(directory / selected), str(directory / 'work')], capture_output=True, text=True, timeout=30, check=True)
        value = json.loads(result.stdout)
        self.assertTrue(value['productionUnchanged'])
        self.assertIn('retry', value['binding']['controlSelectors'])
        self.assertEqual(before, runner.core.directory_digest(source))

    def test_hash_cleanup_preserves_unique_compiler_log_and_never_claims_remote_cleanup(self):
        root = self.temporary()
        build = root / 'native/own-case/native-e2e/build'
        build.mkdir(parents=True)
        (build / 'compile.log').write_text('unique inner compiler failure')
        (build / 'own.hap').write_bytes(b'UNIT SYNTHETIC BINARY NOT A REAL HAP')
        result = runner._cleanup(root, time.monotonic() + 10)
        data = json.loads(runner.artifacts.bound(result))
        self.assertFalse(build.exists())
        self.assertEqual(1, len(data['files']))
        self.assertTrue(data['files'][0]['removed'])
        self.assertFalse(data['remoteCleanupInferred'])
        self.assertTrue(data['intermediateTrees'][0]['removed'])
        retained = next(item['retainedText'] for item in data['intermediateTrees'][0]['files'] if item['path'].endswith('compile.log'))
        self.assertEqual(b'unique inner compiler failure', runner.artifacts.bound(retained))


if __name__ == '__main__':
    unittest.main()
