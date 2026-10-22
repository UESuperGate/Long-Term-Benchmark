"""Offline review tests. No device, model, or mutation of accepted formal scorers."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from . import task15_arkts_action_eligibility as action
from scripts import run_runtime_transition_matrix as public


class ActionEligibilityReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = action.PROFILE.parent.parent / 'candidate-ui-ime-onecase-v6'
        cls.inputs = {
            'raw': json.loads((directory / 'native-e2e/execution/native-result.json').read_text()),
            'provider': json.loads((directory / 'native-e2e/execution/provider-transcript.json').read_text()),
            'build': json.loads((directory / 'retained-build-text/device-build-report.json').read_text()),
            'inputs': action.profile()['inputFiles'],
            'contract': json.loads((action.ROOT / 'benchmark_tasks/15_account_deactivation/transitions.json').read_text()),
        }

    def test_real_review_preserves_every_original_obligation_without_a_score(self):
        result = action.inspect_evidence(**self.inputs)
        spec = next(row for row in self.inputs['contract']['cases'] if row['caseId'] == action.CASE)
        self.assertEqual('proven_visible_disabled_required_action', result['classification'])
        self.assertEqual({key: spec[key] for key in ('given', 'event', 'expected', 'invariants', 'traceDigest')},
                         result['canonicalObligations'])
        self.assertIsNone(result['observedPostState'])
        self.assertEqual([], result['evaluatedInvariants'])
        self.assertFalse(result['transitionExecuted'])
        self.assertFalse(result['scoringApplied'])
        self.assertFalse(result['publicAdmissionReady'])

    def test_presenter_getter_disagreement_is_not_the_failure_criterion(self):
        for value in (False, None):
            kwargs = copy.deepcopy(self.inputs)
            native = next(row['nativePageTransition'] for row in kwargs['raw']['evidence'] if 'nativePageTransition' in row)
            native['failure']['presenter']['submitEnabledRead'] = {'value': value}
            self.assertEqual('proven_visible_disabled_required_action',
                             action.inspect_evidence(**kwargs)['classification'])

    def test_unknown_missing_alternate_or_changed_control_cannot_fail(self):
        for mutation in ('no_tree', 'extra_button', 'extra_gesture_text', 'rename_button', 'missing_selector',
                         'enabled', 'ime_visible', 'window_changed', 'unsettled', 'no_input', 'no_setter',
                         'changed_given', 'direct_presenter', 'request_sent', 'compile_error', 'extra_source',
                         'source_changed', 'different_case', 'environment_error'):
            with self.subTest(mutation=mutation):
                kwargs = copy.deepcopy(self.inputs)
                native = next(row['nativePageTransition'] for row in kwargs['raw']['evidence'] if 'nativePageTransition' in row)
                frame = native['imeDiagnostic']['frames'][1]
                if mutation == 'no_tree':
                    frame.pop('nativeTree')
                elif mutation in ('extra_button', 'extra_gesture_text'):
                    frame['nativeTree']['$children'].append({'$type': 'Button' if mutation == 'extra_button' else 'Text',
                        '$attrs': {'id': 'alternate_deactivate', 'touchable': True, 'enabled': True}, '$children': []})
                elif mutation == 'rename_button':
                    action.unique(frame['nativeTree'], 'deactivation_submit')['$attrs']['id'] = 'renamed_submit'
                elif mutation == 'missing_selector':
                    next(row for row in frame['controls'] if row['name'] == 'submit')['present'] = False
                elif mutation == 'enabled':
                    action.unique(frame['nativeTree'], 'deactivation_submit')['$attrs']['enabled'] = True
                elif mutation == 'ime_visible':
                    frame['windowAndIme']['keyboardVisible'] = True
                elif mutation == 'window_changed':
                    frame['windowAndIme']['nativeWindow']['id'] = -1
                elif mutation == 'unsettled':
                    action.unique(frame['nativeTree'], 'deactivation_submit')['$attrs']['hasPendingRequest'] = True
                elif mutation == 'no_input':
                    native['actions'] = [row for row in native['actions'] if row['kind'] != 'input']
                elif mutation == 'no_setter':
                    native['failure']['presenter']['calls'] = []
                elif mutation == 'changed_given':
                    native['failure']['presenter']['action'] = 'loading'
                elif mutation == 'direct_presenter':
                    native['failure']['presenter']['calls'].append({'method': 'deactivateAccount'})
                elif mutation == 'request_sent':
                    kwargs['provider']['deactivationCount'] = 1
                elif mutation == 'compile_error':
                    kwargs['build']['runtimeCompile']['passed'] = False
                elif mutation == 'extra_source':
                    kwargs['inputs'].append(copy.deepcopy(kwargs['inputs'][0]))
                elif mutation == 'source_changed':
                    kwargs['inputs'][0]['sha256'] = '0' * 64
                elif mutation == 'different_case':
                    kwargs['raw']['caseId'] = 'ad_state_003_password_enables_submit'
                else:
                    native['failure']['stage'] = 'transport_timeout'
                with self.assertRaises(ValueError):
                    action.inspect_evidence(**kwargs)

    def test_random_input_snapshot_directory_is_not_a_role_or_filename_selector(self):
        with tempfile.TemporaryDirectory(dir=action.PROFILE.parent) as temporary:
            kwargs = copy.deepcopy(self.inputs)
            for item in kwargs['inputs']:
                data = action.artifacts.bound(item['snapshot'])
                path = Path(temporary) / item['path']
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                item['snapshot'] = {'path': str(path), 'bytes': len(data), 'sha256': item['sha256']}
            self.assertEqual(action.profile()['rootSha256'], action.inspect_evidence(**kwargs)['candidateRootSha256'])

    def test_public_rejects_staged_policy_without_central_modification(self):
        self.assertNotIn(action.POLICY_ID, public.SOURCE_BOUND_ENTRY_POLICIES)
        contract = self.inputs['contract']
        spec = next(row for row in contract['cases'] if row['caseId'] == action.CASE)
        cases = [{'caseId': row['caseId'], 'traceDigest': row['traceDigest'], 'status': 'not_scored'}
                 for row in contract['cases']]
        target = next(row for row in cases if row['caseId'] == action.CASE)
        target.update(key=spec['key'], status='fail', observed=None, invariantChecks=[], transitionExecuted=False,
            unevaluatedExpected=copy.deepcopy(spec['expected']), unevaluatedInvariants=copy.deepcopy(spec['invariants']),
            entryFailureEvidence={'policyId': action.POLICY_ID})
        report = {'taskId': action.TASK, 'platform': 'arkts', 'role': 'agent',
                  'observationMode': 'runtime_state_transition', 'semantic': {'cases': cases}}
        with self.assertRaisesRegex(ValueError, 'Unreviewed runtime entry assertion'):
            public.validate_report(report, contract)

    def test_historical_diagnostic_cannot_be_upgraded_by_relabeling(self):
        raw_record = action.profile()['profileOriginRaw']
        row = {'entryFailureEvidence': {'policyId': action.POLICY_ID, 'raw': raw_record}}
        report = {'taskId': action.TASK, 'platform': 'arkts', 'role': 'agent'}
        with self.assertRaisesRegex(ValueError, 'Historical diagnostic lacks reviewed fresh producer protocol'):
            action.validate_entry_failure(row, report, set(), contract=self.inputs['contract'])


if __name__ == '__main__':
    unittest.main()
