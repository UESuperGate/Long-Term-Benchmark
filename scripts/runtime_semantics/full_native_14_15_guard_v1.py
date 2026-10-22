"""Independent full-native successor review. NOT registered in public dispatch.

No caller-supplied profile, producer summary, source absence, or compile error
can turn into a semantic result. Empty reviewed registries deliberately keep
the default unavailable until actual captures and matched controls are reviewed.
Synthetic inspect_* functions are test-only projections, never formal admission.
"""
from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path
import types

from . import task14_15_arkts_artifacts as artifacts
from . import task14_15_formal_core as core
from . import task14_actual_routes_guard_v4 as routes
from . import task15_fresh_admission_v2 as transport
from . import task15_page_owner_v5 as owner

P14 = 'task14.full-nine-original-owner.v5'
P15 = 'task15.full-ten-original-owner.v7'
BOUNDARY = 'task14.original-bridge-legacy-leaf.v6'
REVIEWED_PROFILES = {}
require = artifacts.require


def _clone(function, **changes):
    value = types.FunctionType(function.__code__, {**function.__globals__, **changes},
        name=function.__name__, argdefs=function.__defaults__, closure=function.__closure__)
    value.__kwdefaults__ = function.__kwdefaults__
    return value


def task14_envelope(bundle, contract):
    # Reuse all original source/nonce/AA/compiler/cleanup checks, changing only
    # the explicitly versioned producer module and raw envelope key.
    from . import task14_full_native_packaging_v5 as packaging
    text = packaging.old.replace_once(inspect.getsource(routes.envelope),
        'from . import task14_actual_routes_packaging_v4 as packaging',
        'from . import task14_full_native_packaging_v5 as packaging')
    text = text.replace("'actualRouteEpisodeV4'", "'fullNativeEpisodeV5'")
    scope = {**routes.envelope.__globals__, 'PROTOCOL': P14}
    exec(compile(text, str(Path(__file__)) + ':versioned_transport_only', 'exec'), scope)
    return scope['envelope'](bundle, contract)


def original_bridge(state, *, settled=None, expected=None):
    require(state.get('available') is True and state.get('instanceCount') == 1 and
        state.get('boundaryProtocol') == BOUNDARY, 'Not the original page/bridge observer')
    requests, calls = state['resolverRequests'], state['originalBridgeCalls']
    require(requests and len({item['id'] for item in requests}) == len(requests), 'No own actual legacy leaf request')
    for request in requests:
        matching = [item for item in calls if item['id'] == request['bridgeCallId']]
        require(len(matching) == 1 and request.get('samePageResolver') is True and
            request.get('externalLeaf') == 'DemoRoomGateway.resolveAlias', 'Unknown/mocked new bridge boundary')
        call = matching[0]
        require(call.get('calledOriginal') is True and call.get('returned') is True and
            call.get('receiverIsPageResolver') is True and call.get('leafIsOriginalGateway') is True and
            call['alias'] == request['alias'], 'New application bridge body did not execute')
    matching = [item for item in requests if item['alias'] == state['address']]
    require(len(matching) == 1, 'Ambiguous own alias request')
    request = matching[0]
    call = next(item for item in calls if item['id'] == request['bridgeCallId'])
    if settled is not None:
        require(request['settled'] is settled, 'Own legacy boundary settlement missing')
    if expected is not None:
        require(call.get('settlement') == 'fulfilled' and call.get('value') == expected,
            'Original bridge did not produce the canonical external response; never inject its mapped value')
    return call


def inspect_task14_routes(episode, spec, profile):
    require(episode.get('protocol') == P14, 'Wrong full-native producer')
    frames = episode['transition']['frames']
    states = {item['label']: item['samePageOwnerState'] for item in frames}
    before, after = states['before:event'], states['after:event']
    if spec['key'] == 'found_then_continue_navigates':
        original_bridge(before, settled=True, expected={
            'roomId': spec['given']['roomId'], 'servers': spec['given']['servers']})
    else:
        original_bridge(before, settled=False)
    if spec['key'] == 'continue_waits_for_resolution':
        original_bridge(after, settled=True, expected={
            'roomId': spec['event']['roomId'], 'servers': spec['event']['servers']})
    # The original raw receipt now records only the immutable string-valued
    # leaf response. The independently observed original bridge return above
    # binds server names; no synthetic server field is added to raw evidence.
    text = inspect.getsource(routes.inspect_episode)
    text = text.replace("resolved[0][1]['response'] == prior['resolvedRoom']",
        "resolved[0][1]['response'] == {'roomId': prior['resolvedRoom']['roomId']}")
    text = text.replace("responses[0][1]['response'] == {'roomId': spec['event']['roomId'], 'servers': spec['event']['servers']}",
        "responses[0][1]['response'] == {'roomId': spec['event']['roomId']}")
    scope = {**routes.inspect_episode.__globals__, 'PROTOCOL': P14}
    exec(compile(text, str(Path(__file__)) + ':original_route_assertions', 'exec'), scope)
    return scope['inspect_episode'](episode, spec, profile)


def _task14_frames(episode, profile):
    require(episode.get('protocol') == P14 and episode.get('entryExecuted') is True and
        episode.get('released') is True and not episode.get('failure') and
        episode['finishedAt'] <= episode['deadlineEpochMs'], 'Incomplete original native episode')
    for frame in episode['samples']:
        routes._frame(frame, episode, profile)
    transition = episode['transition']
    require(not transition.get('failure') and transition.get('eventExecuted') is True,
        'Setup/environment/unknown action remains NS')
    def one(label):
        items = [item for item in transition['frames'] if item['label'] == label]
        require(len(items) == 1, 'Missing own scalar frame: ' + label)
        item = items[0]
        require(item['frame'] in episode['samples'] and item['frame']['stateBefore'] ==
            item['frame']['stateAfter'] == item['state'] and item['state']['instanceCount'] == 1,
            'Detached/unstable page-owner state')
        return item
    return one


def _row(spec, observed, invariant, checkpoints, runtime, evidence):
    require(set(observed) == set(spec['expected']) and len(spec['invariants']) == 1,
        'Original expected/invariant obligations incomplete')
    return {'caseId': spec['caseId'], 'key': spec['key'], 'traceDigest': spec['traceDigest'],
        'status': 'pass' if observed == spec['expected'] and invariant else 'fail',
        'observed': observed, 'invariantChecks': [{'description': spec['invariants'][0],
            'passed': bool(invariant), 'observed': evidence}], 'checkpoints': copy.deepcopy(checkpoints),
        'canonicalObligations': {key: copy.deepcopy(spec[key]) for key in ('given', 'event', 'expected', 'invariants')},
        'transitionExecuted': True, 'runtime': runtime}


def inspect_task14_scalar(episode, spec, profile):
    one = _task14_frames(episode, profile)
    before, after = one('before:event'), one('after:event')
    prior, current = before['state'], after['state']
    require(prior['instanceId'] == current['instanceId'] and
        before['frame']['windowId'] == after['frame']['windowId'] and
        core._contains(prior, spec['given']), 'Own complete given/window/receiver missing')
    common = [frame for frame in episode['samples'] if frame['label'] == 'scalar:common']
    require(len(common) == 1 and common[0]['routeName'] == profile['entryRoute'], 'Own reachable root missing')
    for name in ('search', 'join'):
        routes._control(common[0], name, profile)
    actions = episode['actions']
    setup = [item for item in actions if common[0]['acquisition']['endSequence'] < item['beginSequence'] <
        before['frame']['acquisition']['beginSequence']]
    require(setup and setup[0]['kind'] == 'click' and setup[0]['executed'] is True and
        setup[0]['control'] == common[0]['controls']['join'].get('actionAncestor', common[0]['controls']['join']),
        'Original root-to-form physical prefix missing')
    routes._control(common[0], 'join', profile, action=True)
    for frame in (before['frame'], after['frame']):
        routes._control(frame, 'input', profile)
    clocks = [before['clock'], after['clock']]
    require(all(clock.get('protocol') == 'task14.same-native-owner-sdk-clock.v5' and
        clock.get('ownerObserved') is True and clock.get('ownerCount') == 1 and
        clock.get('globalTimersOutsideOwnerUnchanged') is True for clock in clocks), 'No own actual SDK clock')
    lower, upper = before['frame']['acquisition']['endSequence'], after['frame']['acquisition']['beginSequence']
    events = [item for item in actions if lower < item['beginSequence'] < item['endSequence'] < upper]
    records = [item for item in episode['records'] if lower < item['sequence'] < upper]
    request_events = [item for item in records if item['event'].get('method') == 'Task14.externalResolverRequested']
    key = spec['key']
    if key == 'update_trims_and_debounces':
        require(len(events) == 1 and events[0]['kind'] == 'input' and events[0]['executed'] is True and
            events[0]['value'] == spec['event']['value'] and events[0]['sessionId'] == episode['sessionId'],
            'Own literal physical input event missing')
        at299, edited, stale = one('boundary:299'), one('invariant:second-edit'), one('invariant:stale-response')
        require(at299['clock']['now'] - clocks[0]['now'] == 299 and len(request_events) == 1,
            'Unobserved debounce boundary/request')
        original_bridge(current, settled=False)
        callbacks = [call for call in clocks[1]['calls'][len(clocks[0]['calls']):] if call['method'] == 'timerCallback']
        require(len(callbacks) >= 1 and request_events[0].get('clockAt') == callbacks[0]['at'],
            'Requested duration cannot replace actual resolver callback time')
        observed = {'address': current['address'], 'addressStateBefore300ms': at299['state']['addressState'],
            'resolveAfterMs': request_events[0]['clockAt'] - clocks[0]['now']}
        edits = [item for item in actions if after['frame']['acquisition']['endSequence'] < item['beginSequence'] <
            edited['frame']['acquisition']['beginSequence'] and item['kind'] == 'input' and item['executed'] is True]
        require(len(edits) == 1 and edits[0]['value'] == '#other:example.org', 'Own invalidation physical edit missing')
        invariant = (edited['state']['address'] == stale['state']['address'] == '#other:example.org' and
            stale['state'].get('resolvedRoom') is None and stale['state']['addressState'] != 'room_found')
    elif key == 'valid_address_resolves':
        original_bridge(current, settled=False)
        invalid = one('invariant:invalid')
        invalid_actions = [item for item in actions if after['frame']['acquisition']['endSequence'] < item['beginSequence'] <
            invalid['frame']['acquisition']['beginSequence'] and item['kind'] == 'input' and item['executed'] is True]
        require(len(invalid_actions) == 1 and invalid_actions[0]['value'] == 'not-a-room' and
            clocks[1]['now'] - clocks[0]['now'] == spec['event']['elapsedMs'] and not events,
            'Own debounce or invalid syntax action missing')
        observed = {'addressState': current['addressState'], 'effect': 'resolve_room_alias' if request_events else None,
            'alias': request_events[0]['event']['alias'] if len(request_events) == 1 else None}
        invariant = (len(invalid['state']['resolverRequests']) == len(current['resolverRequests']) and
            invalid['state']['address'] == 'not-a-room')
    elif key == 'timeout_recovers':
        original_bridge(prior, settled=False)
        retry = one('invariant:retry-edit')
        require(not events and clocks[1]['now'] - clocks[0]['now'] == spec['event']['elapsedSeconds'] * 1000 and
            any(call['method'] == 'timerCallback' and clocks[0]['now'] <= call['at'] <= clocks[1]['now']
                for call in clocks[1]['calls'][len(clocks[0]['calls']):]), 'No actual own timeout callback')
        retries = [item for item in actions if after['frame']['acquisition']['endSequence'] < item['beginSequence'] <
            retry['frame']['acquisition']['beginSequence'] and item['kind'] == 'input' and item['executed'] is True]
        require(len(retries) == 1 and retries[0]['value'] == '#retry:example.org', 'Own physical retry unavailable')
        observed = {'addressState': current['addressState'], 'navigationCount': current['navigationCount'],
            'retryByEditing': retry['state']['address'] == '#retry:example.org' and
                routes._control(retry['frame'], 'input', profile)['enabled'] is True}
        invariant = (routes._control(before['frame'], 'resolving', profile)['visible'] is True and
            after['frame']['controls']['resolving']['visible'] is False and current['addressState'] != 'resolving')
    else:
        raise ValueError('Unknown scalar semantic case')
    return _row(spec, observed, invariant, [before['frame'], after['frame']], P14, {'before': before, 'after': after})


def inspect_task14_device(episode, spec, profile):
    """001/003/007 must retain own physical production chain, not trust summary."""
    require(spec['key'] in ('entry_opens_address_flow', 'invalid_after_continue', 'not_found_recovers'), 'Wrong device case')
    require(episode.get('protocol') == P14 and episode.get('entryExecuted') is True and
        episode.get('released') is True and not episode.get('failure') and
        episode['finishedAt'] <= episode['deadlineEpochMs'], 'Incomplete original UI episode')
    for frame in episode['samples']:
        routes._frame(frame, episode, profile)
    samples = episode['samples']
    def one(label):
        matches = [frame for frame in samples if frame['label'] == label or frame['label'].startswith(label + ':')]
        require(len(matches) == 1, 'Own stable full native frame missing/ambiguous: ' + label)
        return matches[0]
    def control(frame, name, action=False):
        phase = frame['label'].rsplit(':', 1)[0] if frame['label'].rsplit(':', 1)[-1].isdigit() else frame['label']
        return routes._control(frame, name, {**profile, 'controls': profile['frameControls'][phase]}, action=action)
    actions = episode['actions']
    def physical(before, after, name, kind='click', value=None):
        target = control(before, name, action=True)
        items = [item for item in actions if before['acquisition']['endSequence'] < item['beginSequence'] <
            item['endSequence'] < after['acquisition']['beginSequence'] and item['kind'] == kind and
            item['control'] == target.get('actionAncestor', target)]
        require(len(items) == 1 and items[0]['executed'] is True and items[0]['sessionId'] == episode['sessionId'] and
            (kind != 'input' or items[0]['value'] == value), 'Own eligible original UI action missing')
        return items[0]
    before, after = one('setup:root' if spec['key'] == 'entry_opens_address_flow' else 'before:event'), one('after:event')
    require(before['windowId'] == after['windowId'], 'Canonical action switched window')
    prior, current = before['pageOwner'], after['pageOwner']
    require(current.get('available') is True and current.get('instanceCount') == 1 and
        current.get('boundaryProtocol') == BOUNDARY and current.get('nativeReceiverId'), 'No original page receiver')
    if spec['key'] == 'entry_opens_address_flow':
        physical(before, after, 'join')
        search = control(before, 'search')
        require(before['routeName'] == profile['entryRoute'] and search['text'] == '' and search['focused'] is False,
            'Complete canonical start-chat given missing')
        observed = {'addressFlowVisible': control(after, 'input')['visible'],
            'address': control(after, 'input')['text'],
            'addressState': current.get('visibleAddressState', current['addressState'])}
        require(observed['address'] == current['address'], 'Rendered address differs from same original owner')
        create_before, named, created = one('create:configuration'), one('create:named'), one('create:room')
        returned, dm_root, dm_room = one('returned:root'), one('dm:root'), one('dm:room')
        physical(after, returned, 'cancel')
        physical(returned, create_before, 'create')
        physical(create_before, named, 'name', 'input', 'Task14 Native Room')
        require(control(named, 'name')['text'] == 'Task14 Native Room', 'Actual create name input not rendered')
        physical(named, created, 'submit')
        physical(created, dm_root, 'back')
        physical(dm_root, dm_room, 'dm')
        def calls_between(first, last):
            return [item['event']['call'] for item in episode['records'] if first['acquisition']['endSequence'] <
                item['sequence'] < last['acquisition']['beginSequence'] and
                item['event'].get('method') == 'Task14.realFlowProductionCall']
        def unique(calls, class_name, method, phase, tag=None):
            matches = [call for call in calls if call['owner'] == class_name and call['method'] == method and
                call['phase'] == phase and (tag is None or call.get('receiverTags', {}).get(tag) is True)]
            require(len(matches) == 1, 'Own original production action chain incomplete: ' + class_name + '.' + method)
            return matches[0]
        def settlement(calls, start):
            matches = [call for call in calls if call.get('originSequence') == start['sequence'] and
                call.get('receiverId') == start['receiverId'] and call['phase'] == 'fulfilled']
            require(len(matches) == 1, 'Original async result missing or different receiver')
            return matches[0]
        def route_identity(calls, frame):
            opened = unique(calls, 'RouterChatNavigator', 'openRoom', 'call', 'exportedChatNavigator')
            route = unique(calls, 'HarmonyRoutePort', 'replace', 'call', 'navigatorRoutePort')
            load = unique(calls, 'RoomPresenter', 'load', 'call', 'ownsExportedGateway')
            get = unique(calls, 'DemoRoomGateway', 'getRoom', 'call', 'exportedRoomGateway')
            room = settlement(calls, get)['value']
            room_id = frame['routeParams']['roomId']
            require(frame['routeName'] == 'pages/Room' and control(frame, 'roomId')['text'] == room_id and
                opened['args'][0] == room_id and route['args'] == ['pages/Room', frame['routeParams']] and
                load['args'] == get['args'] == [room_id] and room['roomId'] == room_id,
                'Actual routed/rendered/stored room identities disagree')
            return room
        create_calls, dm_calls = calls_between(named, created), calls_between(dm_root, dm_room)
        create_start = unique(create_calls, 'DemoRoomGateway', 'createRoom', 'call', 'exportedRoomGateway')
        create_result = settlement(create_calls, create_start)['value']
        created_room = route_identity(create_calls, created)
        select = unique(dm_calls, 'StartChatPresenter', 'selectPerson', 'call', 'exportedStartChatPresenter')
        execute = unique(dm_calls, 'StartDMService', 'execute', 'call', 'exportedStartDMService')
        dm_create = unique(dm_calls, 'DemoRoomGateway', 'createDirectRoom', 'call', 'exportedRoomGateway')
        dm_id = settlement(dm_calls, execute)['value']
        stored_dm = route_identity(dm_calls, dm_room)
        invariant = (created_room['direct'] is False and create_result == created['routeParams']['roomId'] and
            stored_dm['direct'] is True and select['args'] == execute['args'] == ['@alice:demo.local'] and
            settlement(dm_calls, dm_create)['value'] == dm_id == dm_room['routeParams']['roomId'] and
            '@alice:demo.local' in stored_dm['memberIds'] and '@me:demo.local' in stored_dm['memberIds'])
    else:
        require(prior.get('available') is True and prior.get('instanceCount') == 1 and
            prior['nativeReceiverId'] == current['nativeReceiverId'] and core._contains(prior, spec['given']) and
            control(before, 'input')['text'] == prior['address'], 'Complete same-owner canonical given missing')
        if spec['key'] == 'invalid_after_continue':
            physical(before, after, 'continue')
            observed = {'addressState': current.get('visibleAddressState', current['addressState']),
                'errorVisible': control(after, 'invalid')['visible'], 'navigationCount': current['navigationCount']}
            invariant = before['controls']['invalid']['visible'] is False and prior['validationRequested'] is False
        else:
            records = [item for item in episode['transition']['evidence'] if item.get('label') == 'before:event']
            require(len(records) == 1, 'Own exact inner page-owner before frame missing')
            inner_before = records[0]['data']['state']
            original_bridge(inner_before, settled=False)
            require(inner_before['nativeReceiverId'] == prior['nativeReceiverId'], 'Nested probe acquired another owner')
            failures = [item for item in episode['records'] if before['acquisition']['endSequence'] < item['sequence'] <
                after['acquisition']['beginSequence'] and item['event'].get('method') == 'Task14.externalResolverRejectedV6']
            require(len(failures) == 1, 'Own original bridge/leaf failure event missing')
            observed = {'addressState': current['internalAddressState'], 'errorVisible': control(after, 'notFound')['visible'],
                'navigationCount': current['navigationCount'], 'editingEnabled': control(after, 'input')['enabled']}
            invariant = (before['routeName'] == after['routeName'] and control(after, 'input')['visible'] and
                control(after, 'continue')['visible'] and current.get('addressFlowVisible') is True)
    return _row(spec, observed, bool(invariant), [before, after], P14,
        {'sameOriginalPageOwner': current['nativeReceiverId'], 'physicalSamples': episode['samples']})


def _task15_owner(frame, native, profile):
    return _clone(owner._owner, PROTOCOL=P15)(frame, native, profile)


def _native_visibility(frame, name, profile):
    value = transport._control(frame, name)
    if value.get('present') is True:
        return owner._control(frame, name, profile)['visible']
    require(value.get('present') is False and value.get('visible') is False and
        owner.layout_signature(frame['nativeTree'], profile) in profile.get('absentControlLayouts', {}).get(name, []),
        'Selector absence alone is not actual modal absence')
    binding = profile['controls'][name]
    def walk(node):
        yield node
        for child in node.get('$children', []):
            yield from walk(child)
    if binding['id']:
        require(not any(node.get('$attrs', {}).get('id') == binding['id'] and
            node.get('$attrs', {}).get('visibility') == 'Visibility.Visible' for node in walk(frame['nativeTree'])),
            'Native full tree contradicts control absence')
    return False


def inspect_task15(data, profile):
    native, spec = data['native'], data['spec']
    for frame in native['frames']:
        end = frame['bracketEnd']
        require(frame['nativeTree'] == end['nativeTree'] and frame['windowIdentity'] == end['windowIdentity'] and
            frame['windowAndIme'] == end['windowAndIme'], 'Native frame/window/IME changed during observation bracket')
        for field in ('protocol', 'episodeId', 'binding', 'instanceCount', 'available', 'instanceId', 'serviceId', 'state'):
            require(frame['pageOwner'].get(field) == end['pageOwner'].get(field), 'Original owner changed during native bracket')
    if spec['key'] in owner.CASES:
        return _clone(owner.inspect_same_page_owner, PROTOCOL=P15, _owner=_task15_owner)(data, profile)
    require(native.get('pageOwnerProtocol') == P15 and native.get('failure') is None and
        native.get('outcome') == 'transition_observed' and native.get('eventExecuted') is True and
        native.get('entryExecuted') is True and native['caseId'] == spec['caseId'] and
        native['traceDigest'] == spec['traceDigest'], 'Incomplete/borrowed/host episode')
    require(profile['sourceRootSha256'] == data['inputs']['rootSha256'] and
        profile['compiledProduction'] == data['build']['production'] and native['nonce'] == data['provider']['nonce'] and
        native['sessionId'] == native['nonce'] + ':' + spec['caseId'] and data['provider']['loginCount'] == 1,
        'Unknown original owner/source/own authenticated prefix')
    frames, actions = native['frames'], native['actions']
    require(len({item['sequence'] for item in frames + actions}) == len(frames + actions), 'Duplicated raw episode')
    def one(label):
        matches = [frame for frame in frames if frame['label'] == label]
        require(len(matches) == 1, 'Own native given/event/post missing')
        frame = matches[0]
        require(frame['sessionId'] == native['sessionId'], 'Frame borrowed from other case')
        _task15_owner(frame, native, profile)
        return frame
    prefix, before, after = one('common_start'), one('before_event'), one('after_event')
    prior, current = before['pageOwner'], after['pageOwner']
    require(prior['instanceId'] == current['instanceId'] and prior['serviceId'] == current['serviceId'] and
        prefix['sequence'] < before['sequence'] < after['sequence'] and
        prefix['windowAndIme']['nativeWindow']['id'] == before['windowAndIme']['nativeWindow']['id'] ==
            after['windowAndIme']['nativeWindow']['id'], 'Original owner/window continuity missing')
    for name in ('settings', 'notifications', 'entry'):
        owner._control(prefix, name, profile)
    events = [item for item in actions if item.get('phase') == 'event']
    require(len(events) == 1, 'No unique own canonical event')
    event = events[0]
    require(before['sequence'] < event['sequence'] < after['sequence'] and event.get('executed') is True and
        event['sessionId'] == native['sessionId'] and current['calls'][:len(prior['calls'])] == prior['calls'] and
        event['callStart'] == len(prior['calls']) and event['callStart'] <= event['callEnd'] <= len(current['calls']),
        'Action not bound to actual original receiver calls')
    key = spec['key']
    if key == 'capability_gates_entry':
        require(prior['state'].get('serverCanDeactivateAccount') is spec['given']['serverCanDeactivateAccount'],
        'Actual same-page capability given missing')
        raise ValueError('Own unsupported-capability native/closed-layout negative bundle pending; invariant not invented')
    require(core._contains(prior['state'], spec['given']), 'Complete canonical native-owner given missing')
    require(any(item['kind'] == 'click' and item['target'] == 'entry' and item['executed'] is True and
        prefix['sequence'] < item['sequence'] < before['sequence'] for item in actions), 'Own physical form entry missing')
    for name, field in (('password', 'password'), ('erase', 'eraseData')):
        if field in spec['given']:
            value = owner._control(before, name, profile)
            require(value['text' if name == 'password' else 'checked'] == spec['given'][field], 'Rendered given missing')
    calls = current['calls'][event['callStart']:event['callEnd']]
    state = current['state']
    require(len(current['serviceCalls']) >= len(prior['serviceCalls']) and all(
        {key: value for key, value in old.items() if key != 'settlement'} ==
        {key: value for key, value in new.items() if key != 'settlement'}
        for old, new in zip(prior['serviceCalls'], current['serviceCalls'])), 'Production SDK call history changed')
    def physical(target):
        control = owner._control(before, target, profile)
        require(event['kind'] == 'click' and event['target'] == target and event.get('injected') is not True and
            event.get('nativeControl') == control and control['enabled'] is True,
            'Missing/unknown/disabled action remains NS, never force-click')
        matching = [call for call in calls if call['method'] == 'deactivateAccount' and call['returned'] is True and
            call['instanceId'] == current['instanceId'] and call['args'] == [spec['event']['isRetry']]]
        require(len(matching) == 1, 'Original same-page submit callback missing')
    if key == 'first_submit_confirms':
        physical('submit')
        visible = owner._control(after, 'confirmation', profile)['visible']
        observed = {'action': state['action'], 'requestCount': state['requestCount'], 'confirmationVisible': visible}
        invariant = (not current['serviceCalls'] and data['provider']['deactivationCount'] == 0)
    elif key == 'confirm_sends_payload':
        physical('confirm')
        new = current['serviceCalls'][len(prior['serviceCalls']):]
        require(len(new) == 1 and new[0]['instanceId'] == current['serviceId'], 'Actual new production SDK request missing')
        external = [item for item in data['provider']['requests'] if item.get('kind') == 'deactivation']
        require(external and all(item.get('secure') is True for item in external), 'Actual HTTPS SDK leaf request missing')
        request = external[-1]
        payload = {'password': new[0]['args'][0], 'eraseData': new[0]['args'][1]}
        require(request['body'].get('erase') == payload['eraseData'] and
            request['body'].get('auth', {}).get('password') == payload['password'],
            'Original new SDK bridge authenticated HTTP payload differs')
        observed = {'action': state['action'], 'effect': 'deactivate_account', 'payload': payload}
        modal = owner._control(after, 'loading', profile)
        probe = native['modalProbe']
        after_modal = one('after_modal_input')
        attempts = [item for item in actions if item['kind'] == 'modal_physical_input' and item['executed'] is True]
        password_bounds = owner._control(after, 'password', profile)['bounds']
        require(len(attempts) == 1 and probe['beforeSequence'] == after['sequence'] and
            probe['afterSequence'] == after_modal['sequence'] and after['sequence'] < attempts[0]['sequence'] <
            after_modal['sequence'] and attempts[0]['target'] == 'password_coordinates' and
            attempts[0]['attemptedText'] == 'tampered' and attempts[0]['geometry'] == [
                [password_bounds['left'], password_bounds['top']], [password_bounds['right'], password_bounds['bottom']]],
            'Own real loading modal hit-routing probe missing')
        invariant = (modal['visible'] is True and after_modal['pageOwner']['state']['password'] == state['password'] ==
            prior['state']['password'] and after_modal['pageOwner']['state']['eraseData'] == state['eraseData'] ==
            prior['state']['eraseData'] and after_modal['pageOwner']['serviceCalls'] == current['serviceCalls'] and
            owner._control(after_modal, 'password', profile)['text'] == state['password'])
    elif key == 'failure_preserves_form':
        require(event['kind'] == 'https_response' and event['target'] == 'own_pending_deactivation' and
            event['status'] == 503 and len(prior['serviceCalls']) == 1 and len(current['serviceCalls']) == 1 and
            current['serviceCalls'][0].get('settlement', {}).get('status') == 'rejected', 'Own production request failure missing')
        matches = [request for request in data['provider']['requests'] if request.get('kind') == 'deactivation' and
            request.get('number') == event['requestId'] and request.get('responseStatus') == 503 and request.get('secure') is True]
        require(len(matches) == 1, 'Failure borrowed from another SDK request')
        observed = {'action': state['action'], 'password': owner._control(after, 'password', profile)['text'],
            'eraseData': owner._control(after, 'erase', profile)['checked'],
            'retryEnabled': owner._control(after, 'retry', profile)['enabled']}
        invariant = state['action'] != 'success' and state.get('accountSessionActive') is True
    elif key == 'retry_bypasses_confirmation':
        physical('retry')
        new = current['serviceCalls'][len(prior['serviceCalls']):]
        require(len(new) == 1, 'Own new retry SDK service call missing')
        observed = {'action': state['action'], 'requestCount': state['requestCount'],
            'confirmationVisible': _native_visibility(after, 'confirmation', profile)}
        invariant = new[0]['args'][:2] == [prior['state']['password'], prior['state']['eraseData']]
    else:
        raise ValueError('Unknown native task15 semantic case')
    return _row(spec, observed, invariant, [before, after], P15, {'before': prior, 'after': current})


def admit(task, bundle, contract, *, profile_key):
    require((task, profile_key) in REVIEWED_PROFILES, 'No externally reviewed source/layout/whole-owner profile; NS')
    profile = transport.read(REVIEWED_PROFILES[(task, profile_key)])
    if task == '14_join_room_by_address':
        data, episode, spec = task14_envelope(bundle, contract)
        require(profile['sourceRootSha256'] == data['inputs']['rootSha256'] and
            profile['compiledProduction'] == data['build']['production'], 'Unknown original production/layout binding')
        if spec['key'] in routes.KEYS:
            row = inspect_task14_routes(episode, spec, profile)
        elif spec['key'] in ('update_trims_and_debounces', 'valid_address_resolves', 'timeout_recovers'):
            row = inspect_task14_scalar(episode, spec, profile)
        else:
            row = inspect_task14_device(episode, spec, profile)
    elif task == '15_account_deactivation':
        data = transport.envelope(bundle, contract)
        require(data['plan'].get('fullNativeProtocol') == P15 and data['plan'].get('pageOwnerProtocol') == P15,
            'Old detached host packaging cannot become native original-owner proof')
        bindings = transport.read(data['plan']['actualSourceBindings'])
        require(profile['ownerBinding'] == bindings['ownerBinding'] and
            data['build']['nativeUIObserver']['binding']['ownerBinding'] == bindings['ownerBinding'] and
            data['build']['nativeUIObserver']['binding']['controlSelectors'] == bindings['controlSelectors'],
            'Actual compiled owner/control bindings differ')
        compiled = {Path(item['installedPath']).name: item['sha256'] for item in data['build']['nativeUIObserver']['fixtures']}
        derived = {Path(item['path']).name: item['sha256'] for item in data['plan']['derivedFiles']}
        require(compiled.get('Task15PageOwnerObserverV5.js') == derived.get('Task15PageOwnerObserverV5.js') and
            derived.get('Task15PageOwnerObserverV5.js') is not None, 'Original owner observer not compiled')
        row = inspect_task15(data, profile)
    else:
        raise ValueError('Only Task14/15 ArkTS owned by this module')
    return {**row, 'rawEpisode': bundle, 'productionSources': data['build']['production']}
