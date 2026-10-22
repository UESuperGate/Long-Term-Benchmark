"""Offline protocol fixtures are NOT fresh device evidence or four-pole proof."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from datetime import datetime, timezone

from . import task15_fresh_protocol_v2 as producer
from . import task15_fresh_admission_v2 as admission
from . import task15_arkts_action_eligibility as old
from scripts import run_runtime_transition_matrix as public

ROOT = producer.ROOT
OLD = old.PROFILE.parent.parent / 'candidate-ui-ime-onecase-v6'
SOURCE = old.PROFILE.parent.parent / 'sources/15_account_deactivation/candidate'


def unit_prefix():
    """Synthetic NEW-shape unit input; old build cannot pass envelope()."""
    raw = json.loads((OLD / 'native-e2e/execution/native-result.json').read_text())
    native = next(item['nativePageTransition'] for item in raw['evidence'] if 'nativePageTransition' in item)
    prior, ready = copy.deepcopy(native['imeDiagnostic']['frames'])
    presenter = copy.deepcopy(native['failure']['presenter'])
    sid = native['integration']['nonce'] + ':' + old.CASE
    native.update(protocol=admission.PROTOCOL, failure=None, outcome='blocked_required_physical_action',
                  sessionId=sid, nonce=native['integration']['nonce'])
    native['settings'] = {name: {'present': True, 'visible': True} for name in ('settings', 'notifications', 'entry')}
    prior.update(sequence=20, label='after_password_before_ime_action', sessionId=sid)
    samples = []
    for sequence, at in ((22, ready['at']), (23, ready['at'] + 2100)):
        frame = copy.deepcopy(ready)
        frame.update(sequence=sequence, at=at, sessionId=sid, presenter=presenter,
                     windowIdentity=copy.deepcopy(native['frames'][-1]['windowIdentity']))
        samples.append(frame)
    for i, action in enumerate(native['actions']):
        action.update(sequence=i + 1, sessionId=sid, phase='setup')
        if action['target'] == 'deactivation_entry':
            action['target'] = 'entry'
        if action['kind'] == 'system_back':
            action['sequence'] = 21
    native['frames'] = [prior] + samples
    native.update(submitSamples=[22, 23], submitReadinessStartedAt=ready['at'], finishedAt=ready['at'] + 2200,
        blockedAction={'sampleSequences': [22, 23], 'frameSequence': 23,
                       'requiredEvent': {'name': 'deactivate_account', 'isRetry': False}})
    spec = producer.core.load(producer.CONTRACT)['cases'][4]
    return {'native': native, 'spec': spec,
            'provider': producer.core.load(OLD / 'native-e2e/execution/provider-transcript.json'),
            'build': producer.core.load(OLD / 'retained-build-text/device-build-report.json'),
            'inputs': {'files': old.profile()['inputFiles']}}


def unit_transition(number):
    value = unit_prefix()
    native = value['native']
    spec = producer.core.load(producer.CONTRACT)['cases'][number - 1]
    value['spec'] = spec
    native.update(caseId=spec['caseId'], traceDigest=spec['traceDigest'], outcome='transition_observed', eventExecuted=True)
    before = copy.deepcopy(native['frames'][-1])
    before.update(label='before_event', sequence=30)
    before['presenter'].update(spec['given'])
    after = copy.deepcopy(before)
    after.update(label='after_event', sequence=32)
    state = after['presenter']
    state.update({name: val for name, val in spec['expected'].items() if name in state})
    for frame in (before, after):
        for name in ('confirmation', 'confirm', 'loading', 'retry'):
            frame['controls'].append({'name': name, 'present': False, 'visible': False, 'enabled': True})
    target = {5: 'submit', 6: 'confirm', 8: 'deactivation:2', 9: 'retry'}[number]
    event = {'sequence': 31, 'phase': 'event', 'sessionId': native['sessionId'], 'executed': True,
        'kind': 'https_response' if number == 8 else 'click', 'target': target,
        'nativeControl': {'present': True, 'visible': True, 'enabled': True}}
    if number == 8:
        event.update(status=503, deactivationNumber=2)
        value['provider']['requests'].append({'kind': 'deactivation', 'responseStatus': 503})
        admission._control(after, 'retry').update(present=True, visible=True)
    else:
        state['calls'].append({'method': 'deactivateAccount', 'instanceId': state['instanceId'],
            'args': [spec['event']['isRetry']], 'returned': True})
    if number == 5:
        for name in ('confirmation', 'confirm'):
            admission._control(after, name).update(present=True, visible=True)
    if number in (6, 9):
        state['serviceCalls'].append({'instanceId': state['serviceId'], 'method': 'deactivateAccount',
                                     'args': ['secret', True], 'returned': True})
    if number == 6:
        state['requestCount'] = before['presenter']['requestCount'] + 1
        admission._control(after, 'loading').update(present=True, visible=True)
        end = copy.deepcopy(after); end.update(label='after_modal_input', sequence=34)
        native['modalProbe'] = {'beforeSequence': 32, 'afterSequence': 34, 'inputError': None}
        node = old.unique(after['nativeTree'], 'deactivation_password')
        native['actions'].append({'kind': 'modal_physical_input', 'phase': 'invariant', 'sequence': 33,
            'executed': True, 'attemptedText': 'tampered', 'geometry': json.loads('[' + node['$rect'] + ']')})
        native['frames'] = [before, after, end]
    else:
        native['frames'] = [before, after]
    native['actions'].append(event)
    return value


def unit_bundle(output):
    """Synthetic envelope fixture in a disposable unit directory. Not an execution."""
    plan = producer.prepare_case(source=SOURCE, case_id=old.CASE, output=output,
                                 deadline=time.monotonic() + 3500)
    prefix = unit_prefix()
    native = prefix['native']
    native.update(deadlineEpochMs=plan['deadlineEpochMs'] - 120000,
                  finishedAt=plan['deadlineEpochMs'] - 121000)
    raw = {'taskId': old.TASK, 'role': 'agent', 'caseId': old.CASE,
           'traceDigest': prefix['spec']['traceDigest'], 'evidence': [{'nativePageTransition': native}],
           'productionSources': prefix['build']['nativeUIObserver']['sources']}
    native['productionSources'] = raw['productionSources']
    raw['calls'] = [{'method': 'Task15.originalPageTransition', 'nativeUI': True, 'observation': {
        'caseId': old.CASE, 'traceDigest': prefix['spec']['traceDigest'], 'sessionId': native['sessionId'],
        'frames': copy.deepcopy(native['frames']), 'actions': copy.deepcopy(native['actions']),
        'productionSources': native['productionSources']}}]
    raw['productionSources'] = [item for item in raw['productionSources'] if item['path'] == 'entry/src/main/ets/pages/Index.ets']
    build = prefix['build']
    build['nativeUIObserver']['fixtures'] = [{'file': item['path'], 'installedPath': 'entry/src/test/' + Path(item['path']).name,
        'sha256': item['sha256']} for item in plan['derivedFiles']]
    removed = [{'path': str(output / ('unit-not-real-' + str(i) + '.hap')), 'bytes': 0,
                'sha256': '0' * 64, 'removed': True} for i in range(2)]
    cleanup = {'files': removed, 'removedAfterRecordingHashes': True, 'buildDirectoryRemoved': True,
               'certificatesRemoved': True}
    def put(name, data):
        path = output / (name + '.json')
        producer.core.write(path, data)
        return producer.artifacts.artifact(path)
    bundle = {'plan': producer.artifacts.artifact(output / 'plan.json'), 'raw': put('raw-unit-fixture', raw),
        'build': put('build-unit-fixture', build), 'provider': put('provider-unit-fixture', prefix['provider']),
        'cleanup': put('cleanup-unit-fixture', cleanup)}
    log = output / 'aa-unit-fixture.log'
    log.write_text('TestFinished-ResultCode: 0\nFailure: 0, Error: 0\n')
    bundle['aaLog'] = producer.artifacts.artifact(log)
    run = {'source': str(SOURCE.resolve()), 'nonce': native['nonce'], 'sourceHashes': build['production'],
        'status': 'fresh_raw_pending_independent_admission',
        'finishedAt': datetime.now(timezone.utc).isoformat(),
        'nativeResult': bundle['raw'], 'providerTranscript': bundle['provider'],
        'haps': [{key: item[key] for key in ('path', 'bytes', 'sha256')} for item in removed],
        'resultMarker': {'executionNonce': native['nonce'], 'taskId': old.TASK, 'role': 'agent',
                         'caseId': old.CASE, 'bytes': bundle['raw']['bytes']},
        'deviceCertificateCleanupConfirmed': True, 'binaryCleanup': cleanup,
        'cleanup': {key: True for key in ('appUninstalled', 'reverseRemoved', 'serverClosed', 'privateKeysRemoved')},
        'commands': [{'log': 'aa-test.log', 'exitCode': 0, 'timedOut': False, 'logSha256': bundle['aaLog']['sha256'],
                      'args': ['-s', 'ltbExecutionNonce', native['nonce'], '-s', 'task15Nonce', native['nonce'],
                               '-s', 'task15DeadlineEpochMs', str(native['deadlineEpochMs'])]}]}
    bundle['run'] = put('run-unit-fixture', run)
    return bundle


class FreshProducerTests(unittest.TestCase):
    def test_preparation_only_derives_all_five_own_cases_and_removes_unit_temporaries(self):
        with tempfile.TemporaryDirectory(dir=producer.REVIEW.parent) as temporary:
            for case_id in sorted(producer.NATIVE_CASES):
                with self.subTest(case_id=case_id):
                    output = Path(temporary) / case_id
                    plan = producer.prepare_case(source=SOURCE, case_id=case_id, output=output,
                        deadline=time.monotonic() + 3500)
                    self.assertTrue(plan['preparedOnly'])
                    self.assertFalse(plan['deviceOrModelStarted'])
                    self.assertEqual(case_id, plan['canonicalCase']['caseId'])
                    self.assertEqual(producer.core.load(producer.CONTRACT), admission.read(plan['contract']))
                    self.assertEqual(plan['evaluator']['sha256'], admission.identity(plan['evaluator']))
                    host = (output / 'fresh-host.cjs').read_text()
                    self.assertIn('8GiB disk guard', host)
                    self.assertIn('cleanup-manifest.json', host)
                    self.assertIn('task15DeadlineEpochMs', host)
                    bridge = (output / 'native-environment-fixtures/Task15NativeUiBridge.js').read_text()
                    self.assertNotIn('prerequisite?.rootConfirmed', bridge)
                    self.assertIn('frame.windowIdentity?.hostVerified', bridge)
                    self.assertIn('refuses to release a foreign canonical device lease', host)
                    self.assertNotIn("'--role', 'final'", host)
                    self.assertNotIn('lockWaitStartedAt + taskTimeoutMs', host)
                    self.assertIn('fresh_raw_pending_independent_admission', host)
                    checked = subprocess.run(['node', '--check', str(output / 'fresh-host.cjs')],
                        capture_output=True, text=True, timeout=10)
                    self.assertEqual(0, checked.returncode, checked.stderr)
            self.assertEqual([], list(Path(temporary).rglob('*.hap')))

    def test_one_budget_and_no_overwrite_or_case003_projection(self):
        with tempfile.TemporaryDirectory(dir=producer.REVIEW.parent) as temporary:
            output = Path(temporary) / 'case'
            for delta in (-1, 30, 3601):
                with self.assertRaises(ValueError):
                    producer.prepare_case(source=SOURCE, case_id=old.CASE, output=output,
                        deadline=time.monotonic() + delta)
            with self.assertRaises(ValueError):
                producer.prepare_case(source=SOURCE, case_id='ad_state_003_password_enables_submit',
                    output=output, deadline=time.monotonic() + 3500)
            output.mkdir()
            with self.assertRaises(ValueError):
                producer.prepare_case(source=SOURCE, case_id=old.CASE, output=output,
                    deadline=time.monotonic() + 3500)


class IndependentFreshAdmissionTests(unittest.TestCase):
    def test_disposable_synthetic_envelope_checks_packaged_fixtures_transport_and_cleanup(self):
        with tempfile.TemporaryDirectory(dir=producer.REVIEW.parent) as temporary:
            output = Path(temporary) / 'unit-bundle'
            bundle = unit_bundle(output)
            contract = producer.core.load(producer.CONTRACT)
            self.assertEqual(old.CASE, admission.envelope(bundle, contract)['spec']['caseId'])
            for key, mutation in (
                ('build', lambda v: v['nativeUIObserver']['fixtures'].pop(0)),
                ('build', lambda v: v['runtimeCompile'].update(passed=False)),
                ('build', lambda v: v['compile'].update(passed=True)),
                ('raw', lambda v: v['evidence'][0]['nativePageTransition'].pop('protocol')),
                ('run', lambda v: v.update(nonce='b' * 32)),
                ('run', lambda v: v['commands'][0].update(timedOut=True)),
                ('run', lambda v: v['commands'][0].update(args=[])),
                ('run', lambda v: v['cleanup'].update(appUninstalled=False)),
                ('run', lambda v: v['binaryCleanup'].update(buildDirectoryRemoved=False)),
            ):
                with self.subTest(key=key, mutation=mutation):
                    original = producer.artifacts.bound(bundle[key])
                    altered = json.loads(original)
                    mutation(altered)
                    path = Path(bundle[key]['path'])
                    producer.core.write(path, altered)
                    changed = {**bundle, key: producer.artifacts.artifact(path)}
                    try:
                        with self.assertRaises((ValueError, KeyError)):
                            admission.envelope(changed, contract)
                    finally:
                        path.write_bytes(original)

    def test_own_native_transition_observations_preserve_original_assertions(self):
        for number in (5, 6, 8, 9):
            with self.subTest(number=number):
                value = unit_transition(number)
                row = admission.inspect_transition(value)
                self.assertEqual('pass', row['status'])
                self.assertEqual(value['spec']['expected'], row['observed'])
                self.assertEqual(value['spec']['invariants'], [item['description'] for item in row['invariantChecks']])
                value['native']['frames'][1]['presenter']['action'] = 'wrong_actual_poststate'
                self.assertEqual('fail', admission.inspect_transition(value)['status'])

    def test_modal_transport_error_is_not_a_passing_invariant(self):
        value = unit_transition(6)
        value['native']['modalProbe']['inputError'] = 'permission or transport failure'
        with self.assertRaisesRegex(ValueError, 'transport error'):
            admission.inspect_transition(value)

    def test_reused_case005_and_incomplete_given_or_action_stay_unscored(self):
        for mutation in ('event_false', 'no_before', 'wrong_given', 'disabled_event', 'no_handler', 'wrong_receiver'):
            with self.subTest(mutation=mutation):
                value = unit_transition(6)
                native = value['native']
                if mutation == 'event_false': native['eventExecuted'] = False
                elif mutation == 'no_before': native['frames'].pop(0)
                elif mutation == 'wrong_given': native['frames'][0]['presenter']['action'] = 'uninitialized'
                elif mutation == 'disabled_event': native['actions'][-1]['nativeControl']['enabled'] = False
                elif mutation == 'no_handler': native['frames'][1]['presenter']['calls'].pop()
                else: native['frames'][1]['presenter']['serviceId'] = -1
                with self.assertRaises((ValueError, KeyError)):
                    admission.inspect_transition(value)

    def test_synthetic_prefix_is_only_unscored_review_preserving_all_obligations(self):
        value = unit_prefix()
        result = admission.inspect_blocked_prefix(value)
        self.assertEqual('fail', result['proposedStatus'])
        self.assertFalse(result['scoringApplied'])
        self.assertFalse(result['publicAdmissionReady'])
        self.assertIsNone(result['observed'])
        self.assertEqual([], result['invariantChecks'])
        self.assertEqual({key: value['spec'][key] for key in ('given', 'event', 'expected', 'invariants')},
                         result['canonicalObligations'])

    def test_can_submit_getter_does_not_determine_result(self):
        for getter in (None, False, True):
            value = unit_prefix()
            for frame in value['native']['frames'][1:]:
                frame['presenter']['submitEnabledRead'] = {'value': getter}
            self.assertFalse(admission.inspect_blocked_prefix(value)['presenterCanSubmitGetterUsedForVerdict'])

    def test_mutations_fail_closed(self):
        mutations = ('old_protocol', 'wrong_case', 'wrong_trace', 'extra_button', 'renamed_button',
                     'no_selector', 'enabled', 'unsettled', 'ime_visible', 'unknown_ime', 'back_left_form',
                     'not_enough_samples', 'no_stable_wait', 'given_wrong', 'no_physical_input',
                     'request_sent', 'handler_called', 'event_executed', 'extra_source', 'packaging_failed',
                     'wrong_user', 'getter_only', 'no_positive_ui', 'duplicate_sequence')
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                value = unit_prefix()
                native = value['native']; frame = native['frames'][-1]
                if mutation == 'old_protocol': native.pop('protocol')
                elif mutation == 'wrong_case': native['caseId'] = 'ad_state_006_confirm_sends_payload'
                elif mutation == 'wrong_trace': native['traceDigest'] = '0' * 64
                elif mutation == 'extra_button':
                    frame['nativeTree']['$children'].append({'$type': 'Button', '$attrs': {'id': 'unknown', 'enabled': True}})
                elif mutation == 'renamed_button': old.unique(frame['nativeTree'], 'deactivation_submit')['$attrs']['id'] = 'alternate'
                elif mutation == 'no_selector': admission._control(frame, 'submit')['present'] = False
                elif mutation == 'enabled': admission._control(frame, 'submit')['enabled'] = True
                elif mutation == 'unsettled': old.unique(frame['nativeTree'], 'deactivation_submit')['$attrs']['hasPendingRequest'] = True
                elif mutation == 'ime_visible': frame['windowAndIme']['keyboardVisible'] = True
                elif mutation == 'unknown_ime': frame['windowAndIme']['visibilitySource'] = 'heuristic'
                elif mutation == 'back_left_form': frame['windowAndIme']['nativeWindow']['id'] = -1
                elif mutation == 'not_enough_samples': native['submitSamples'] = [23]
                elif mutation == 'no_stable_wait': native['submitReadinessStartedAt'] = frame['at']
                elif mutation == 'given_wrong': frame['presenter']['action'] = 'loading'
                elif mutation == 'no_physical_input': native['actions'] = [a for a in native['actions'] if a['target'] != 'password']
                elif mutation == 'request_sent': value['provider']['deactivationCount'] = 1
                elif mutation == 'handler_called': frame['presenter']['calls'].append({'method': 'deactivateAccount'})
                elif mutation == 'event_executed': native['eventExecuted'] = True
                elif mutation == 'extra_source': value['inputs']['files'].append(copy.deepcopy(value['inputs']['files'][0]))
                elif mutation == 'packaging_failed': value['build']['runtimeCompile']['passed'] = False
                elif mutation == 'wrong_user': native['integration']['login']['expectedUserId'] = '@wrong:task15.test'
                elif mutation == 'getter_only': frame['nativeTree'] = {}
                elif mutation == 'no_positive_ui': native['settings']['notifications']['present'] = False
                else: native['actions'][0]['sequence'] = frame['sequence']
                with self.assertRaises((ValueError, KeyError, StopIteration)):
                    admission.inspect_blocked_prefix(value)

    def test_actual_v6_has_no_fresh_compiled_fixture_and_cannot_be_retagged(self):
        native_row = producer.core.load(OLD / 'native-e2e/execution/native-result.json')
        build = producer.core.load(OLD / 'retained-build-text/device-build-report.json')
        self.assertNotIn('Task15FreshActionsV2.js', [Path(item['installedPath']).name for item in build['nativeUIObserver']['fixtures']])
        native = next(item['nativePageTransition'] for item in native_row['evidence'] if 'nativePageTransition' in item)
        self.assertNotIn('protocol', native)
        with self.assertRaisesRegex(ValueError, 'Incomplete fresh execution bundle'):
            admission.envelope({'raw': producer.artifacts.artifact(OLD / 'native-e2e/execution/native-result.json')},
                               producer.core.load(producer.CONTRACT))

    def test_no_four_poles_no_candidate_acceptance_and_no_public_registration(self):
        with self.assertRaisesRegex(ValueError, 'Four controls required'):
            admission.verify_controls({}, producer.core.load(producer.CONTRACT), evaluator_sha='0' * 64)
        self.assertNotIn(admission.POLICY_ID, public.SOURCE_BOUND_ENTRY_POLICIES)
        contract = producer.core.load(producer.CONTRACT)
        rows = [{'caseId': spec['caseId'], 'traceDigest': spec['traceDigest'], 'status': 'not_scored'}
                for spec in contract['cases']]
        rows[4].update(status='fail', entryFailureEvidence={'policyId': admission.POLICY_ID})
        report = {'taskId': old.TASK, 'platform': 'arkts', 'role': 'agent',
                  'observationMode': 'runtime_state_transition', 'semantic': {'cases': rows}}
        with self.assertRaisesRegex(ValueError, 'Unreviewed runtime entry assertion'):
            public.validate_report(report, contract)


if __name__ == '__main__':
    unittest.main()
