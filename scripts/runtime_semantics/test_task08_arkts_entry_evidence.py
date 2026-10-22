import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

DIRECTORY = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('task08_entry_under_test', DIRECTORY / 'task08_arkts_entry_evidence.py')
target = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(target)


class EntryEvidenceTests(unittest.TestCase):
    def fixture(self, spec):
        payload = 'task08-positive-control:' + spec['caseId']
        sources = [{'path': 'entry/src/main/ets/pages/Index.ets', 'sha256': 'a' * 64}]
        build = {'role': 'agent', 'bundleName': 'arbitrary.candidate', 'nativeUIObserver': {'sources': sources}}
        window = {'focused': True, 'hostVerified': True, 'routeName': 'pages/Index', 'bundleName': build['bundleName']}
        state = {'events': ['$root'], 'composerText': payload, 'sendState': 'idle', 'gatewayLastBody': ''}
        after = {**state, 'events': ['$root', payload], 'composerText': '', 'sendState': 'success', 'gatewayLastBody': payload}
        frames = [{'label': label, 'windowIdentity': window,
            'controls': [{'name': 'roomComposer', 'visible': True}, {'name': 'roomRoot', 'present': False}],
            'inventory': [{'id': 'room_composer', 'type': 'TextInput'}, {'id': 'room_send', 'type': 'Button'},
                          {'id': '', 'text': payload if index else '$root', 'type': 'Text'}],
            'pageObserver': {'available': True, 'instanceCount': 1, 'state': value,
                'calls': [{'owner': 'RoomTimelineGateway', 'method': 'sendMessage', 'args': [payload],
                           'completed': True, 'result': True}] if index else []}}
            for index, (label, value) in enumerate([('before_event', state), ('after_event', after)])]
        raw = {'taskId': '08_threads', 'caseId': spec['caseId'], 'traceDigest': spec['traceDigest'],
            'role': build['role'], 'bundleName': build['bundleName'], 'productionVariant': 'base',
            'entryExecuted': True, 'prefixExecuted': True, 'eventExecuted': False,
            'entryFailure': {'classification': 'required_feature_entry_missing', 'requestedAction': 'open_thread',
                'positiveControlBody': payload, 'canonicalEventExecuted': False},
            'basePositiveControl': {'roomRendered': True, 'roomSendCompleted': True, 'requestedAction': 'open_thread', 'routeAvailable': False},
            'verifiedWindow': window, 'launchEvidence': {'created': True, 'destroyed': True},
            'productionSources': sources, 'frames': frames,
            'actions': [{'kind': 'click', 'target': 'roomSend', 'executed': True}]}
        row = {'caseId': spec['caseId'], 'traceDigest': spec['traceDigest'], 'status': 'not_scored',
               'observed': {}, 'invariantChecks': [], 'evidence': [raw], 'productionSources': sources,
               'nativeBridge': {'candidateUIVerified': True, 'applicationContextAvailable': True,
                   'capabilities': {'execution': {'nonce': 'nonce'}}},
               'reason': 'Adapter did not observe every canonical expectation and invariant'}
        return row, build

    def test_all_nine_keep_later_states_unknown_and_artifact_bound(self):
        contract = json.loads((target.ROOT / 'benchmark_tasks/08_threads/transitions.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            for spec in contract['cases']:
                row, build = self.fixture(spec)
                path = Path(directory) / (spec['caseId'] + '.json')
                path.write_text(json.dumps(row))
                normalized = target.normalize(row, spec, build, 'nonce', target.record(path))
                self.assertIsNone(normalized['observed'])
                self.assertEqual([], normalized['invariantChecks'])
                self.assertEqual(spec['invariants'], normalized['unevaluatedInvariants'])
                self.assertFalse(normalized['transitionExecuted'])
                self.assertEqual(row, target.verify_normalized(normalized, spec, build, 'nonce'))
                normalized['observed'] = {'threadRootId': None}
                with self.assertRaises(ValueError):
                    target.verify_normalized(normalized, spec, build, 'nonce')

    def test_projection_environment_entry_and_positive_control_mutations_rejected(self):
        spec = json.loads((target.ROOT / 'benchmark_tasks/08_threads/transitions.json').read_text())['cases'][0]
        mutations = [
            lambda row: row.update(observed={'threadRootId': None}),
            lambda row: row.update(invariantChecks=[{'passed': False}]),
            lambda row: row.update(reason='transport failed'),
            lambda row: row['evidence'][0].update(eventExecuted=True),
            lambda row: row['evidence'][0]['verifiedWindow'].update(hostVerified=False),
            lambda row: row['evidence'][0]['launchEvidence'].update(destroyed=False),
            lambda row: row['evidence'][0]['frames'][1]['pageObserver']['state'].update(gatewayLastBody='wrong'),
            lambda row: row['evidence'][0]['frames'][1]['inventory'].append({'id': 'thread_open', 'type': 'Button'}),
            lambda row: row['evidence'][0]['frames'][1].update(inventory=[]),
            lambda row: row['evidence'][0]['actions'][0].update(executed=False),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                row, build = self.fixture(spec)
                row = copy.deepcopy(row)
                mutate(row)
                with self.assertRaises(ValueError):
                    target.validate_raw(row, spec, build, 'nonce')

    def test_nested_entry_requires_stable_inventory_and_real_preceding_actions(self):
        spec = json.loads((target.ROOT / 'benchmark_tasks/08_threads/transitions.json').read_text())['cases'][6]
        row, build = self.fixture(spec)
        raw = row['evidence'][0]
        raw['productionVariant'] = 'timeline'
        window = {**raw['verifiedWindow'], 'stageMainWindowId': 4}
        sample = {'windowIdentity': window, 'target': {'id': 'thread_open_poll', 'present': None},
                  'pollTextCount': 0, 'inventory': [{'id': 'thread_composer'}, {'id': 'thread_open_location'}, {'id': ''}]}
        raw['entryFailure'] = {'classification': 'required_nested_entry_unreachable',
                               'target': 'thread_open_poll', 'samples': [copy.deepcopy(sample), copy.deepcopy(sample)]}
        state = {'rootEvent': {'id': '$root'}, 'composerText': 'draft', 'replyTargetId': '$reply'}
        raw['frames'] = [{'label': label, 'state': {'thread': {**state, 'surface': surface}}}
                         for label, surface in [('before_event', 'attachment'), ('after_event', 'thread'),
                                                ('before_event', 'location'), ('after_event', 'thread')]]
        raw['actions'] = [{'kind': 'click', 'target': control, 'executed': True} for control in
                          ['thread_open_attachment', 'attachment_discard', 'thread_open_location', 'location_discard']]
        target.validate_raw(row, spec, build, 'nonce')
        for mutate in [
            lambda value: value['entryFailure']['samples'][1].update(pollTextCount=1),
            lambda value: value['entryFailure']['samples'][1]['target'].update(present=True),
            lambda value: value['entryFailure']['samples'][0].update(inventory=[]),
            lambda value: value['actions'][0].update(executed=False),
            lambda value: value['frames'][0]['state']['thread'].update(composerText='lost'),
        ]:
            changed = copy.deepcopy(row)
            mutate(changed['evidence'][0])
            with self.assertRaises(ValueError):
                target.validate_raw(changed, spec, build, 'nonce')


if __name__ == '__main__':
    unittest.main()
