"""Synthetic guard mutation fixtures, never claimed as device calibration."""
import copy
import json
from pathlib import Path
import unittest

from . import task14_actual_routes_guard_v4 as guard
from . import task15_page_owner_v5 as layout

ROOT = Path(__file__).resolve().parents[2]


def fixture(number=5, wrong_intent=False):
    spec = json.loads((ROOT / 'benchmark_tasks/14_join_room_by_address/transitions.json').read_text())['cases'][number - 1]
    names = {'search': ('search', 'TextInput', 0), 'join': ('join', 'Button', 1), 'create': ('create', 'Button', 2),
        'input': ('input', 'TextInput', 0), 'continue': ('continue', 'Button', 1), 'cancel': ('cancel', 'Button', 2),
        'roomBack': ('roomBack', 'Button', 0)}
    profile = {'entryRoute': 'pages/Index', 'addressRoute': 'pages/JoinRoomByAddress', 'dynamicAttributes': {}, 'closedLayouts': [],
        'controls': {name: {'id': id_, 'type': type_, 'treePath': 'root/' + str(index)} for name, (id_, type_, index) in names.items()}}
    window = {'left': 0, 'top': 0, 'right': 300, 'bottom': 400}
    owner = {'available': True, 'instanceCount': 1, 'instanceId': 1, 'address': '#team:example.org',
        'addressState': 'room_found' if number == 5 else 'resolving', 'validationRequested': False,
        'addressFlowVisible': True, 'calls': [], 'navigationCalls': [],
        'resolverRequests': [{'id': 1, 'alias': '#team:example.org', 'samePageResolver': True, 'settled': number == 5}]}
    if number == 5:
        owner['resolvedRoom'] = {'roomId': spec['given']['roomId'], 'servers': spec['given']['servers']}
    nonce = 'a' * 32
    session = nonce + ':' + spec['caseId']
    def frame(label, route, visible, sequence, state, params=None):
        children, controls = [], {}
        for index, name in enumerate(visible):
            id_, type_, _ = names[name]
            text = owner['address'] if name == 'input' else name
            children.append({'$type': type_, '$rect': '[10,10],[90,40]', '$attrs': {
                'id': id_, 'enabled': True, 'visibility': 'Visibility.Visible', 'opacity': 1, 'text': text}})
            controls[name] = {'id': id_, 'type': type_, 'selector': {'id': id_}, 'present': True, 'visible': True,
                'enabled': True, 'clickable': True, 'inspectorMatches': 1, 'text': text,
                'bounds': {'left': 10, 'top': 10, 'right': 90, 'bottom': 40}}
        for name in names:
            controls.setdefault(name, {'present': False, 'visible': False, 'inspectorMatches': 0})
        tree = {'$type': 'Column', '$attrs': {}, '$children': children}
        result = {'available': True, 'label': label, 'tree': tree, 'controls': controls, 'windowId': 1, 'viewport': window,
            'routeName': route, 'routeParams': params or {}, 'stateBefore': copy.deepcopy(state), 'stateAfter': copy.deepcopy(state),
            'acquisition': {'sessionId': session, 'beginSequence': sequence, 'endSequence': sequence + 1},
            'bracketEnd': {'tree': copy.deepcopy(tree), 'windowId': 1, 'routeName': route, 'routeParams': params or {}}}
        profile['closedLayouts'].append(layout.layout_signature(tree, profile))
        return result
    root = frame('common:root:1', 'pages/Index', ['search', 'join', 'create'], 1, {})
    before = frame('before:event', 'pages/JoinRoomByAddress', ['input', 'continue', 'cancel'], 10, owner)
    current = copy.deepcopy(owner)
    current['calls'].append({'instanceId': 1, 'method': 'dismiss' if number == 9 else 'continue', 'returned': True})
    if number == 6:
        current['validationRequested'] = True
    if number != 9:
        current['navigationCalls'] = [{'method': 'openRoom', 'args': ['!team:example.org', ['example.org']]}]
    if number == 9:
        after = frame('after:event', 'pages/Index', ['search', 'join', 'create'], 30, current)
    elif wrong_intent:
        after = frame('after:event', 'pages/JoinRoomByAddress', ['input', 'continue', 'cancel'], 30, current)
    else:
        after = frame('after:event', 'pages/Room', ['roomBack'], 30, current, {'roomId': '!team:example.org'})
    events = [{'sequence': 5, 'event': {'method': 'Task14.externalResolverRequested', 'requestId': 1, 'alias': owner['address']}},
        {'sequence': 15, 'event': {'method': 'Task14.uiAction', 'kind': 'click', 'selector': {'id': 'cancel' if number == 9 else 'continue'}}}]
    if number == 5:
        events.append({'sequence': 8, 'event': {'method': 'Task14.externalResolverResolved', 'requestId': 1,
            'samePageResolver': True, 'response': copy.deepcopy(owner['resolvedRoom'])}})
    if number != 9 and not wrong_intent:
        for sequence, owner_, method, args, tags in [(25, 'HarmonyRoutePort', 'replace', ['pages/Room', {'roomId': '!team:example.org'}], {'navigatorRoutePort': True}),
                (26, 'RoomPresenter', 'load', ['!team:example.org'], {'ownsExportedGateway': True})]:
            events.append({'sequence': sequence, 'event': {'method': 'Task14.realFlowProductionCall',
                'call': {'owner': owner_, 'method': method, 'args': args, 'phase': 'call', 'receiverTags': tags}}})
    frames = [{'label': 'common:root', 'frame': root, 'samePageOwnerState': None},
        {'label': 'before:event', 'frame': before, 'samePageOwnerState': owner}]
    samples = [root, before]
    if number == 6:
        pending_state = copy.deepcopy(current); pending_state['addressState'] = 'resolving'
        pending = frame('pending:continue', 'pages/JoinRoomByAddress', ['input', 'continue', 'cancel'], 20, pending_state)
        samples.append(pending); frames.append({'label': 'after:continue-before-resolution', 'frame': pending, 'samePageOwnerState': pending_state})
        events.append({'sequence': 23, 'event': {'method': 'Task14.externalResolverResolved', 'requestId': 1,
            'samePageResolver': True, 'response': {'roomId': '!team:example.org', 'servers': ['example.org']}}})
    samples.append(after); frames.append({'label': 'after:event', 'frame': after, 'samePageOwnerState': current})
    episode = {'protocol': guard.PROTOCOL, 'taskId': guard.TASK, 'caseId': spec['caseId'], 'traceDigest': spec['traceDigest'],
        'nonce': nonce, 'sessionId': session, 'entryExecuted': True, 'released': True, 'finishedAt': 100, 'deadlineEpochMs': 200,
        'records': sorted(events, key=lambda item: item['sequence']), 'samples': samples,
        'actions': [{'beginSequence': 3, 'endSequence': 4, 'sessionId': session, 'kind': 'click', 'executed': True,
            'control': root['controls']['join']},
            {'beginSequence': 6, 'endSequence': 7, 'sessionId': session, 'kind': 'input', 'executed': True,
            'control': before['controls']['input'], 'value': owner['address']},
            {'beginSequence': 14, 'endSequence': 16, 'sessionId': session, 'kind': 'click', 'executed': True,
            'control': before['controls']['cancel' if number == 9 else 'continue']}],
        'transition': {'protocol': 'task14.arkts.actual-navigation-routes.v3', 'eventExecuted': True,
            'outcome': 'native_transition_observed_pending_independent_admission', 'frames': frames,
            'observed': {'INVENTED': 'guard must ignore'}, 'invariantChecks': [{'passed': True}]}}
    return episode, spec, profile


class GuardTests(unittest.TestCase):
    def test_three_own_actual_transitions(self):
        for number in (5, 6, 9):
            with self.subTest(number=number):
                episode, spec, profile = fixture(number)
                row = guard.inspect_episode(episode, spec, profile)
                self.assertEqual(row['status'], 'pass')
                self.assertEqual(row['observed'], spec['expected'])

    def test_intent_without_route_is_failure_not_projection(self):
        episode, spec, profile = fixture(wrong_intent=True)
        row = guard.inspect_episode(episode, spec, profile)
        self.assertEqual(row['status'], 'fail')
        self.assertIsNone(row['observed']['openRoom'])

    def test_no_approved_profile_cannot_admit_offline_fixture(self):
        with self.assertRaisesRegex(ValueError, 'No actual'):
            guard.admit({}, {}, profile_key='unit')

    def test_unknown_or_borrowed_boundary_mutations_fail_closed(self):
        def post(episode):
            return episode['transition']['frames'][-1]['frame']
        mutations = {
            'old_protocol': lambda e: e.update(protocol='native_previewer_arkvm_production_module'),
            'other_case': lambda e: e.update(caseId='jr_state_003_invalid_after_continue'),
            'no_entry': lambda e: e.update(entryExecuted=False),
            'no_cleanup': lambda e: e.update(released=False),
            'past_deadline': lambda e: e.update(finishedAt=201),
            'missing_event': lambda e: e['actions'].clear(),
            'forced_disabled': lambda e: e['actions'][-1]['control'].update(enabled=False),
            'no_physical_prefix': lambda e: e['actions'].pop(0),
            'unknown_button': lambda e: post(e)['tree']['$children'].append({'$type': 'Button', '$attrs': {'id': 'alternateJoin'}, '$children': []}),
            'renamed_button': lambda e: post(e)['tree']['$children'][0]['$attrs'].update(id='new-room-back'),
            'missing_room_load': lambda e: e['records'].__setitem__(slice(None), [item for item in e['records'] if item['event'].get('call', {}).get('owner') != 'RoomPresenter']),
            'intent_port': lambda e: e['records'][-2]['event']['call'].update(receiverTags={'navigatorRoutePort': False}),
            'other_owner': lambda e: e['transition']['frames'][-1]['samePageOwnerState'].update(instanceId=2),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                episode, spec, profile = fixture()
                mutation(episode)
                with self.assertRaises((ValueError, KeyError)):
                    guard.inspect_episode(episode, spec, profile)


if __name__ == '__main__':
    unittest.main()
