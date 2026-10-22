"""Canonical recomputation from connected-v3 raw. Not a public admission/scoring route.

Owner/source/compiled-input authenticity is a separate prerequisite. This module
does not trust producer verdicts or an `observed` map and never selects by role.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / 'benchmark_tasks/17_pinned_messages/transitions.json'
PROTOCOL = 'task17.android.connected-roomflow.v3'
MESSAGES = 'io.element.android.features.messages.impl.MessagesNode'
LIST = 'io.element.android.features.messages.impl.pinned.list.PinnedMessagesListNode'
PARENT = 'io.element.android.appnav.LoggedInFlowNode'
FLOW = 'io.element.android.features.messages.impl.MessagesFlowNode'
ROOM_DETAILS = 'io.element.android.features.roomdetails.impl.RoomDetailsNode'
REQUIRED_ANCESTORS = (
    PARENT, 'io.element.android.appnav.room.RoomFlowNode',
    'io.element.android.appnav.room.joined.JoinedRoomFlowNode',
    'io.element.android.appnav.room.joined.JoinedRoomLoadedFlowNode', FLOW,
)


class EvidenceGap(ValueError):
    """Unavailable observation/given/binding; not semantic failure."""


def need(value, reason):
    if not value:
        raise EvidenceGap(reason)


def integer(value):
    return type(value) is int and value > 0


def exact(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(exact(a, b) for a, b in zip(actual, expected))
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(exact(actual[k], expected[k]) for k in expected)
    return actual == expected


def _owner(frame, raw):
    need(frame.get('episode') == raw['episode'] and frame.get('activityId') == raw['activityId'],
         'Cross-episode/activity frame')
    need(isinstance(frame.get('semanticsTree'), str) and frame['semanticsTree'].strip(), 'Missing original UI tree')
    nodes = frame.get('nodes', [])
    need(nodes and len({n.get('nodeId') for n in nodes}) == len(nodes), 'Ambiguous original node tree')
    by_id = {n['nodeId']: n for n in nodes}
    for node in nodes:
        need(integer(node.get('nodeId')) and isinstance(node.get('class'), str), 'Invalid original node identity')
        cursor, visited = node, set()
        while cursor.get('parentId') is not None:
            need(cursor['nodeId'] not in visited and cursor['parentId'] in by_id, 'Detached/cyclic parent chain')
            visited.add(cursor['nodeId'])
            cursor = by_id[cursor['parentId']]
    owner = frame.get('owner', {})
    need(owner.get('nodeClass') in {MESSAGES, LIST} and owner.get('nodeId') in by_id and
         by_id[owner['nodeId']]['class'] == owner['nodeClass'], 'Unknown or detached actual page')
    need(by_id[owner['nodeId']].get('lifecycle') == 'RESUMED', 'Actual page not resumed')
    need(integer(owner.get('presenterId')) and owner.get('pagePresenterId') == owner['presenterId'],
         'Detached presenter')
    need(owner.get('readback') == 'actual_composition_parameter' and owner.get('renderFunction') ==
         ('MessagesView' if owner['nodeClass'] == MESSAGES else 'PinnedMessagesListView'), 'No original rendered state')
    ancestry, ancestors_by_class, cursor = [], {}, by_id[owner['nodeId']]
    while cursor.get('parentId') is not None:
        cursor = by_id[cursor['parentId']]
        ancestry.append(cursor['class'])
        ancestors_by_class.setdefault(cursor['class'], cursor['nodeId'])
    need(all(path in ancestry for path in REQUIRED_ANCESTORS), 'Original RoomFlow ancestry missing')
    records = frame.get('dependencyReadback', [])

    def dependencies(identity):
        selected = [r for r in records if r.get('instanceId') == identity]
        need(len(selected) == 1 and selected[0].get('readback') == 'original_instance_fields_no_constructor_replay',
             'Actual original dependency field readback missing')
        pairs = selected[0].get('dependencies', [])
        need(len({p.get('name') for p in pairs}) == len(pairs), 'Duplicate original dependency fields')
        return {p['name']: p['instanceId'] for p in pairs}

    dep = dependencies(owner['presenterId'])
    need(dep.get('navigator') == owner['nodeId'] and dep.get('room') == owner.get('roomId'),
         'Original presenter not bound to mounted navigator/SDK room')
    if owner['nodeClass'] == LIST:
        need(dep.get('timelineProvider') == owner.get('providerId'), 'Detached pinned provider')
    else:
        banner = dependencies(dep.get('pinnedMessagesBannerPresenter'))
        need(banner.get('pinnedEventsTimelineProvider') == owner.get('providerId'), 'Detached original banner provider')
        timeline = dependencies(dep.get('timelinePresenter'))
        need(timeline.get('navigator') == owner['nodeId'] and timeline.get('room') == owner.get('roomId'),
             'Original TimelinePresenter not owned by actual MessagesNode')
    components = frame.get('productionComponents', {})
    need(components.get('roomId') == owner.get('roomId') and integer(components.get('clientId')),
         'SDK boundary component mismatch')
    bridge = frame.get('bridgeEvidence', {})
    need(bridge.get('sdkNamespace') == 'org.matrix.rustcomponents.sdk' and
         bridge.get('roomClass') == 'io.element.android.libraries.matrix.impl.room.RustMatrixRoom' and
         bridge.get('roomId') == owner.get('roomId') and bridge.get('leafRoomId') == components.get('leafRoomId') and
         integer(bridge.get('leafRoomId')) and
         components.get('clientClass') == 'io.element.android.libraries.matrix.impl.RustMatrixClient',
         'Original application Rust SDK bridges bypassed')
    if bridge.get('providerStateClass', '').endswith('$Success'):
        need(bridge.get('pinnedTimelineClass') == 'io.element.android.libraries.matrix.impl.timeline.RustTimeline' and
             bridge.get('pinnedTimelineRoomId') == owner.get('roomId') and integer(bridge.get('pinnedTimelineId')) and
             integer(bridge.get('leafPinnedTimelineId')) and
             bridge.get('leafPinnedTimelineId') == bridge.get('expectedLeafPinnedTimelineId'),
             'Original pinned RustTimeline not bound to actual room and lower SDK timeline')
    need(components.get('actualRootClientId') == components['clientId'] and
         components.get('actualRoomInputId') == owner.get('roomId') and
         components.get('actualFlowProviderId') == owner.get('providerId') and
         components.get('loadedRoomOwnerId') == ancestors_by_class[REQUIRED_ANCESTORS[3]] and
         integer(components.get('roomComponentId')) and 'RoomComponent' in components.get('roomComponentClass', ''),
         'Actual original RoomScope/root SDK/provider binding absent')
    need(isinstance(components.get('appClass'), str) and components['appClass'].startswith('io.element.android.x.di.Dagger')
         and isinstance(components.get('sessionClass'), str) and 'Session' in components['sessionClass'],
         'Original generated app/session component proof absent')
    factories = components.get('nodeFactories', [])
    need(any(f.get('node') == PARENT and f.get('factory') for f in factories), 'Original root factory not retained')
    callbacks = frame.get('callbackReadback', [])
    need(len({item.get('nodeId') for item in callbacks}) == len(callbacks), 'Duplicate callback readback node')
    for node_id, enclosing in ((owner['nodeId'], FLOW),
                               (ancestors_by_class[REQUIRED_ANCESTORS[3]], PARENT)):
        selected = [item for item in callbacks if item.get('nodeId') == node_id]
        need(len(selected) == 1 and selected[0].get('callbacks'), 'Actual original callback chain absent')
        need(all(item.get('enclosingClass') == enclosing and
                 any(outer.get('nodeId') == ancestors_by_class[enclosing] and outer.get('nodeClass') == enclosing
                     for outer in item.get('outerNodes', [])) for item in selected[0]['callbacks']),
             'Callback does not capture actual original parent flow')
    calls = frame.get('sdkCalls')
    need(isinstance(calls, list) and calls == raw['sdkCalls'][:len(calls)], 'SDK checkpoint prefix mismatch')
    need(isinstance(frame.get('state'), dict), 'Actual state snapshot missing')
    need(frame['state'].get('screen') == ('room_timeline' if owner['nodeClass'] == MESSAGES else 'pinned_messages'),
         'Screen observation inconsistent with mounted owner')
    return owner


def _list(state, name):
    value = state.get(name)
    need(isinstance(value, list), 'Actual list observation absent: ' + name)
    return value


def _result(case, actual, invariant_values):
    need(set(actual) == set(case['expected']) and len(invariant_values) == len(case['invariants']),
         'Incomplete original assertion recomputation')
    for field in case['expected']:
        need(actual[field] is not None, 'Actual canonical observation missing: ' + field)
    checks = [{'kind': 'expected', 'field': field, 'expected': expected, 'actual': actual[field],
               'passed': exact(actual[field], expected)} for field, expected in case['expected'].items()]
    checks += [{'kind': 'invariant', 'statement': statement, 'passed': passed}
               for statement, passed in zip(case['invariants'], invariant_values)]
    return {'caseId': case['caseId'], 'traceDigest': case['traceDigest'], 'actual': actual, 'checks': checks,
            'assertionCount': len(checks), 'allAssertionsPass': all(check['passed'] for check in checks),
            'sourceAndCompilerAdmission': 'not_checked', 'benchmarkAccepted': False, 'diagnosticOnly': True}


def _feature_unavailable_result(raw, case, frames, calls):
    need(len(frames) == 3 and [frame.get('name') for frame in frames] ==
         ['common_room_timeline', 'before', 'after'], 'Unavailable-feature checkpoint shape changed')
    common, before, after = frames
    expected_classes = (MESSAGES, ROOM_DETAILS, ROOM_DETAILS)
    room_ids, leaf_ids = set(), set()
    for frame, expected_class in zip(frames, expected_classes):
        need(frame.get('episode') == raw['episode'] and frame.get('activityId') == raw['activityId'],
             'Cross-episode unavailable-feature frame')
        need(isinstance(frame.get('semanticsTree'), str) and frame['semanticsTree'].strip(),
             'Missing unavailable-feature UI tree')
        nodes = frame.get('nodes', [])
        by_id = {node.get('nodeId'): node for node in nodes}
        owner = frame.get('owner', {})
        need(nodes and len(by_id) == len(nodes) and owner.get('nodeClass') == expected_class and
             owner.get('nodeId') in by_id and by_id[owner['nodeId']].get('class') == expected_class and
             by_id[owner['nodeId']].get('lifecycle') == 'RESUMED', 'Unavailable-feature mounted owner absent')
        need(owner.get('readback') == 'actual_mounted_node_fields' and owner.get('featureAvailable') is False and
             integer(owner.get('presenterId')) and integer(owner.get('roomId')), 'Unavailable-feature owner not observed')
        state, bridge, components = frame.get('state', {}), frame.get('bridgeEvidence', {}), frame.get('productionComponents', {})
        need(state.get('featureAvailable') is False and state.get('missingControlDisplayed') is False and
             isinstance(state.get('missingControl'), str) and state['missingControl'], 'Missing-control probe unavailable')
        need(bridge.get('sdkNamespace') == 'org.matrix.rustcomponents.sdk' and
             bridge.get('roomClass') == 'io.element.android.libraries.matrix.impl.room.RustMatrixRoom' and
             bridge.get('roomId') == owner['roomId'] and integer(bridge.get('leafRoomId')) and
             bridge.get('leafRoomId') == components.get('leafRoomId') and
             components.get('roomId') == owner['roomId'] and components.get('actualRootClientId') == components.get('clientId'),
             'Unavailable-feature original Rust room/root binding absent')
        need(isinstance(components.get('appClass'), str) and components['appClass'].startswith('io.element.android.x.di.Dagger') and
             isinstance(components.get('sessionClass'), str) and 'Session' in components['sessionClass'],
             'Unavailable-feature generated component proof absent')
        need(frame.get('sdkCalls') == calls[:len(frame.get('sdkCalls', []))], 'Unavailable-feature SDK prefix mismatch')
        room_ids.add(owner['roomId'])
        leaf_ids.add(bridge['leafRoomId'])
    need(common['state'].get('screen') == 'room_timeline' and
         before['state'].get('screen') == after['state'].get('screen') == 'room_details',
         'Unavailable feature not probed from common runtime path')
    need(len(room_ids) == len(leaf_ids) == 1 and common['parentRoute'].get('nodeId') == before['parentRoute'].get('nodeId') ==
         after['parentRoute'].get('nodeId'), 'Unavailable-feature room/root identity changed')
    actions = [action for action in raw.get('actions', []) if action.get('phase') != 'environment_setup']
    need(len(actions) == 2 and actions[0].get('phase') == 'prefix' and
         actions[0].get('dispatch') == 'compose_original_control' and actions[0].get('eligible') is True and
         integer(actions[0].get('semanticsNodeId')) and actions[0].get('sequence') < before['sequence'],
         'Real common-to-details operation prefix absent')
    need(actions[1].get('phase') == 'event' and actions[1].get('dispatch') == 'missing_original_control_probe' and
         actions[1].get('eligible') is False and before['sequence'] < actions[1].get('sequence') < after['sequence'] and
         actions[1].get('selectorText') == before['state'].get('missingControl') and actions[1].get('semanticsBefore'),
         'Canonical missing control was not probed in the original UI')
    pinned_calls = [call for call in calls if call.get('method') == 'sdk.Room.pinnedEventsTimeline']
    need(all(call.get('sdkRoomId') in leaf_ids for call in pinned_calls) and
         not any(call.get('method') == 'sdk.Timeline.unpinEvent' for call in calls),
         'Unavailable list feature bypassed the existing banner room or fabricated an unpin')

    def unavailable(field, expected):
        if field == 'screen':
            return 'room_details'
        if isinstance(expected, list):
            return []
        if isinstance(expected, bool):
            return False
        if isinstance(expected, int):
            return -1
        if isinstance(expected, str):
            return 'feature_unavailable'
        raise EvidenceGap('Unsupported unavailable-feature expected type: ' + field)

    actual = {field: unavailable(field, expected) for field, expected in case['expected'].items()}
    return _result(case, actual, [False] * len(case['invariants']))


def recompute(raw, *, contract=None):
    """Compute every original assertion. Raises EvidenceGap for missing inputs.

    Returns diagnostic recomputation, NOT an accepted benchmark report. No raw,
    source, compiler, UI authenticity or cleanup claim can be created by this API.
    """
    contract = contract or json.loads(CONTRACT.read_bytes())
    need(raw.get('protocol') == PROTOCOL and raw.get('taskId') == contract['taskId'], 'Task/protocol mismatch')
    need(raw.get('role') in {'base', 'final', 'agent'} and integer(raw.get('activityId')) and raw.get('episode'),
         'Invalid identity')
    cases = [c for c in contract['cases'] if c['caseId'] == raw.get('caseId') and c['traceDigest'] == raw.get('traceDigest')]
    need(len(cases) == 1, 'Original canonical case/digest mismatch')
    case = cases[0]
    need(raw.get('canonicalAssertions') == {'expected': case['expected'], 'invariants': case['invariants']},
         'Original canonical assertions changed')
    need(not raw.get('bindingErrors') and not raw.get('asyncErrors'), 'Production/harness binding failure')
    calls = raw.get('sdkCalls')
    need(raw.get('sdkBoundaryVersion') == 'org.matrix.rustcomponents.sdk-only.v1' and
         raw.get('leafSdkAudit') and raw['leafSdkAudit'][-1].get('operation') == 'strict_sdk_call_audit' and
         raw['leafSdkAudit'][-1].get('unboundMethods') == [], 'Strict lower SDK audit absent or unbound')
    need(isinstance(calls, list) and all(c.get('episode') == raw['episode'] and c.get('boundary') == 'org.matrix.rustcomponents.sdk'
         and c.get('sequence') == i for i, c in enumerate(calls)), 'Unbound SDK trace')
    frames = raw.get('frames', [])
    need(frames and [f.get('sequence') for f in frames] == sorted({f.get('sequence') for f in frames})
         and all(integer(f.get('sequence')) for f in frames), 'Unordered runtime checkpoints')
    need(len({f.get('name') for f in frames}) == len(frames), 'Duplicate checkpoint')
    by_name = {f['name']: f for f in frames}
    need('before' in by_name and 'after' in by_name and 'common_room_timeline' in by_name, 'Required checkpoints missing')
    if raw.get('featureUnavailable') is True:
        return _feature_unavailable_result(raw, case, frames, calls)
    for frame in frames:
        _owner(frame, raw)
    before, after = by_name['before'], by_name['after']
    need(before['sequence'] < after['sequence'], 'Reversed primary window')
    actions = raw.get('actions', [])
    need(actions and len({a.get('sequence') for a in actions + frames}) == len(actions + frames), 'Duplicate action/checkpoint sequence')
    for action in actions:
        need(action.get('episode') == raw['episode'], 'Cross-episode action')
        if action.get('dispatch') == 'compose_original_control':
            need(action.get('activityId') == raw['activityId'] and action.get('eligible') is True and
                 integer(action.get('semanticsNodeId')) and action.get('semanticsBefore'), 'Ineligible original UI action')
        else:
            need(action.get('dispatch') == 'external_sdk_completion' and action.get('boundary') == 'org.matrix.rustcomponents.sdk',
                 'Internal callback/state injection')
    events = [a for a in actions if a.get('phase') == 'event']
    need(events and all(before['sequence'] < a['sequence'] < after['sequence'] for a in events), 'Event outside primary window')
    sdk_case = case['key'] in {'load_failure', 'empty_success', 'filled_list'}
    need(all(a['dispatch'] == ('external_sdk_completion' if sdk_case else 'compose_original_control') for a in events),
         'Canonical event boundary replaced')
    if case['key'] != 'open_loading':
        need(any(a.get('phase') == 'prefix' and a['dispatch'] == 'compose_original_control' and
                 a['sequence'] < before['sequence'] for a in actions), 'No real original UI entry prefix')
    same_parent = before['parentRoute']['nodeId'] == after['parentRoute']['nodeId']
    need(same_parent and before['bridgeEvidence']['leafRoomId'] == after['bridgeEvidence']['leafRoomId'],
         'Changed root/lower SDK room identity')
    if case['key'] not in {'open_loading', 'view_in_timeline'}:
        need(all(before['owner'][k] == after['owner'][k] for k in ('nodeId', 'presenterId', 'providerId', 'roomId')),
             'Disconnected transition owner')
    b, a = before['state'], after['state']
    delta = calls[len(before['sdkCalls']):len(after['sdkCalls'])]
    sdk = lambda method: [c for c in delta if c.get('method') == method]
    key = case['key']
    actual = {}
    invariant_values = []
    if key == 'open_loading':
        need(b.get('screen') == 'room_timeline', 'Canonical common timeline given unavailable')
        # Original provider starts in MessagesFlow.onBuilt, BEFORE opening the list.
        # The effect remains tied to this actual room/provider and held completion;
        # do not invent a second request solely to fit an event-local expectation.
        opened = [c for c in after['sdkCalls'] if c.get('method') == 'sdk.Room.pinnedEventsTimeline'
                  and c.get('sdkRoomId') == after['bridgeEvidence']['leafRoomId']]
        need(not any(c.get('method') == 'server.pinnedTimelineComplete' for c in before['sdkCalls']), 'SDK given not held')
        actual = {'screen': a['screen'], 'listState': a.get('listState'),
                  'effects': ['open_pinned_timeline'] if opened else []}
        invariant_values = [after.get('timelineParentNodeId') == before['owner']['nodeId'] and
                            any(n['nodeId'] == before['owner']['nodeId'] for n in after['nodes'])]
    elif key in {'load_failure', 'empty_success', 'filled_list'}:
        need(b.get('listState') == 'loading', 'Canonical loading given unavailable')
        completions = sdk('server.pinnedTimelineComplete')
        need(len(completions) == 1 and completions[0].get('failure') is (key == 'load_failure'), 'Wrong incoming SDK completion')
        if key == 'load_failure':
            actual = {field: a.get(field) for field in ('listState', 'emptyStateVisible', 'errorVisible')}
            invariant_values = [a.get('listState') == 'failed' and a.get('emptyStateVisible') is False]
        elif key == 'empty_success':
            need(_list(b, 'sdkCacheEventIds') == [], 'Canonical empty SDK input unavailable')
            actual = {'listState': a.get('listState'), 'loadedPinnedMessagesCount': a.get('loadedPinnedMessagesCount'),
                      'failureVisible': a.get('errorVisible')}
            invariant_values = [a.get('listState') == 'empty' and a.get('errorVisible') is False and
                                completions[0]['failure'] is False]
        else:
            expected_ids = [item['eventId'] for item in case['given']['pinnedTimelineItems']]
            need(list(reversed(_list(b, 'sdkCacheEventIds'))) == expected_ids, 'Canonical server cache/order given unavailable')
            actual = {'listState': a.get('listState'), 'visibleEventIds': _list(a, 'renderedEventIds'),
                      'loadedPinnedMessagesCount': a.get('loadedPinnedMessagesCount')}
            invariant_values = [_list(a, 'loadedEventIds') == expected_ids == actual['visibleEventIds'] and
                                _list(a, 'displayedBodies') == [item['body'] for item in case['given']['pinnedTimelineItems']]]
    elif key in {'unpin_permission_denied', 'unpin_permission_allowed'}:
        need(b.get('listState') == 'filled' and b.get('canPinUnpin') is case['given']['canPinUnpin'] and
             case['given']['eventId'] in _list(b, 'loadedEventIds'), 'Canonical permissions/item given unavailable')
        visible = _list(a, 'actionsVisible')
        need(a.get('selectedEventId') == case['given']['eventId'], 'Action target not the canonical given')
        actual = {'actionsVisible': visible}
        if 'actionsHidden' in case['expected']:
            actual['actionsHidden'] = [name for name in case['expected']['actionsHidden'] if name not in visible]
            invariant_values = [_list(b, 'productionPinnedEventIds') == _list(a, 'productionPinnedEventIds') and
                                _list(b, 'loadedEventIds') == _list(a, 'loadedEventIds') and not sdk('sdk.Timeline.unpinEvent')]
        else:
            permission_calls = [c for c in after['sdkCalls'] if c.get('method') == 'sdk.Room.canUserPinUnpin']
            need(permission_calls, 'No actual SDK permission observation')
            invariant_values = [permission_calls[-1].get('allowed') is True and a.get('canPinUnpin') is True
                                and not sdk('sdk.Timeline.unpinEvent')]
    elif key == 'view_in_timeline':
        target = case['given']['eventId']
        need(b.get('screen') == 'pinned_messages' and b.get('selectedEventId') == target and
             'view_in_timeline' in _list(b, 'actionsVisible'), 'Canonical selected pinned event given unavailable')
        focus = a.get('focus', {})
        before_route = before['parentRoute']
        after_route = after['parentRoute']
        before_target = str(before_route.get('target', ''))
        after_target = str(after_route.get('target', ''))
        # In this canonical fixture the selected event is already indexed by the
        # live timeline. Upstream therefore focuses it in memory and does not
        # create a detached timeline via Room.timelineFocusedOnEvent.
        effect = (target in _list(b, 'loadedEventIds') and
                  before_route.get('focusedEventId') is None and
                  after_route.get('focusedEventId') == target and
                  before_target != after_target and
                  'trigger=null' in before_target and
                  'initialElement=Messages(focusedEventId=null)' in before_target and
                  'trigger=Timeline' in after_target and
                  f'initialElement=Messages(focusedEventId={target})' in after_target and
                  not sdk('sdk.Room.timelineFocusedOnEvent') and
                  focus.get('eventId') == target and focus.get('rendered') is True and
                  focus.get('targetControlDisplayed') is True)
        actual = {'screen': a['screen'], 'focusedEventId': focus.get('eventId'),
                  'effects': ['navigate_to_event'] if effect else []}
        invariant_values = [target in _list(a, 'productionPinnedEventIds') and
                            _list(a, 'productionPinnedEventIds') == _list(b, 'productionPinnedEventIds') and not sdk('sdk.Timeline.unpinEvent')]
    elif key in {'unpin_success', 'unpin_failure_recovery'}:
        need(b.get('canPinUnpin') is True and _list(b, 'renderedEventIds') == case['given']['visibleEventIds'] and
             b.get('selectedEventId') == case['event']['eventId'] and 'unpin' in _list(b, 'actionsVisible'),
             'Canonical eligible unpin given unavailable')
        pending = by_name.get('pending')
        need(pending and before['sequence'] < pending['sequence'] < after['sequence'], 'Held SDK pending checkpoint absent')
        request, response = sdk('sdk.Timeline.unpinEvent'), sdk('server.unpinComplete')
        need(len(request) == len(response) == 1 and request[0].get('eventId') == response[0].get('eventId') == case['event']['eventId']
             and response[0].get('failure') is (key == 'unpin_failure_recovery'), 'Actual request/completion missing')
        need(request[0].get('sdkTimelineId') == before['bridgeEvidence'].get('leafPinnedTimelineId'),
             'Unpin bypasses page-owned production RustTimeline lower SDK')
        need(any(c.get('method') == 'sdk.Timeline.unpinEvent' for c in pending['sdkCalls']) and
             not any(c.get('method') == 'server.unpinComplete' for c in pending['sdkCalls']), 'Pending window not held')
        actual = {'visibleEventIds': _list(a, 'renderedEventIds')}
        if key == 'unpin_success':
            persisted = sdk('server.pinnedItems')
            actual.update(effects=['unpin_event'] + (['persist_pinned_state'] if persisted and
                case['event']['eventId'] not in _list(a, 'productionPinnedEventIds') else []), errorVisible=a.get('errorVisible'))
            invariant_values = [_list(a, 'loadedEventIds') == case['expected']['visibleEventIds'] == actual['visibleEventIds'] and
                                [item for item in b['loadedEventIds'] if item != case['event']['eventId']] == a['loadedEventIds']]
        else:
            need(isinstance(a.get('snackbarMessageResIds'), list) and integer(a.get('errorSnackbarResId')), 'Actual snackbar effect not observed')
            retry = by_name.get('retry_pending')
            need(retry and retry['sequence'] > after['sequence'], 'Actual enabled retry not observed')
            retry_calls = calls[len(after['sdkCalls']):len(retry['sdkCalls'])]
            retry_actions = [event for event in actions if event.get('phase') == 'invariant' and
                             after['sequence'] < event['sequence'] < retry['sequence']]
            actual.update(effects=['show_error'] if a['errorSnackbarResId'] in a['snackbarMessageResIds'] else [],
                          retryEnabled=bool(retry_actions and any(c.get('method') == 'sdk.Timeline.unpinEvent' and
                              c.get('eventId') == case['event']['eventId'] for c in retry_calls)))
            invariant_values = [all(_list(frame['state'], 'loadedEventIds') == case['given']['visibleEventIds'] and
                                _list(frame['state'], 'productionPinnedEventIds') == _list(b, 'productionPinnedEventIds')
                                for frame in (pending, after)) and not sdk('server.pinnedItems')]
    else:
        raise EvidenceGap('Unimplemented original canonical case')
    return _result(case, actual, invariant_values)
