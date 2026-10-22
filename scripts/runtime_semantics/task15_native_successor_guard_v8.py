"""Independent Task15 V8 raw admission; no central/public registration here."""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
import types
from pathlib import Path

from . import task15_native_successor_v8 as producer
from . import full_native_14_15_guard_v1 as previous
from . import task15_page_owner_v5 as owner
from . import task15_fresh_admission_v2 as transport

PROTOCOL = producer.PROTOCOL
REVIEWED_PROFILES = {}
require = transport.require
digest = lambda value: hashlib.sha256(str(value).encode()).hexdigest()


def stable_window(first, last):
    require(set(first) == set(last) and type(first.get('checkedAt')) is int and type(last.get('checkedAt')) is int and
        first['checkedAt'] <= last['checkedAt'], 'Window acquisition timestamps/fields unavailable')
    return {key: value for key, value in first.items() if key != 'checkedAt'} == {
        key: value for key, value in last.items() if key != 'checkedAt'}


def page_owner(frame, native, profile):
    return producer.clone(owner._owner, PROTOCOL=PROTOCOL)(frame, native, profile)


def control(frame, name, profile):
    actual = transport._control(frame, name)
    bindings = profile['controls'][name]
    bindings = bindings if isinstance(bindings, list) else [bindings]
    matching = [binding for binding in bindings if binding['id'] == actual.get('id') and
        binding['treePath'] == actual.get('treePath')]
    require(len(matching) == 1, 'Unknown/renamed/ambiguous original native control path')
    return owner._control(frame, name, {**profile, 'controls': {**profile['controls'], name: matching[0]}})


def visibility(frame, name, profile):
    actual = transport._control(frame, name)
    if actual.get('present') is True:
        return control(frame, name, profile)['visible']
    require(actual.get('present') is False and actual.get('visible') is False and
        owner.layout_signature(frame['nativeTree'], profile) in profile.get('absentControlLayouts', {}).get(name, []),
        'Private selector absence is not capability/UI closure')
    bindings = profile['controls'][name]
    bindings = bindings if isinstance(bindings, list) else [bindings]
    ids = {binding['id'] for binding in bindings if binding['id']}
    def walk(node):
        yield node
        for child in node.get('$children', []):
            yield from walk(child)
    require(not any(node.get('$attrs', {}).get('id') in ids and node.get('$attrs', {}).get('visibility') ==
        'Visibility.Visible' for node in walk(frame['nativeTree'])), 'Native tree contradicts private selector absence')
    return False


def bracket(frame):
    end = frame['bracketEnd']
    require(frame['nativeTree'] == end['nativeTree'] and stable_window(frame['windowIdentity'], end['windowIdentity']) and
        frame['windowAndIme'] == end['windowAndIme'], 'Mixed original native tree/window/IME bracket')
    for name in ('protocol', 'episodeId', 'binding', 'instanceCount', 'available', 'instanceId', 'serviceId',
                 'bridgeReceiverId', 'sessionIdentity', 'state'):
        require(frame['pageOwner'].get(name) == end['pageOwner'].get(name), 'Original owner changed within frame')


def ledger_calls(value):
    require(value.get('protocol') == 'task15.changed-body-ledger.v8' and value.get('allWrappersPassOriginal') is True and
        value.get('controlledBoundary') == 'external HTTPS server only' and value.get('systemHttpReplaced') is False,
        'New application-owned bridge was mocked/replaced')
    calls = value['calls']
    require([call['id'] for call in calls] == list(range(1, len(calls) + 1)), 'Ambiguous bridge call ledger')
    for call in calls:
        require(call.get('calledOriginal') is True and type(call.get('returned')) is bool and
            type(call.get('receiverId')) is int and call['receiverId'] > 0 and call.get('stack') and
            (call.get('parentCallId') is None or 0 < call['parentCallId'] < call['id']), 'Original bridge call/receiver missing')
        require(call['returned'] is True or call.get('settlement', {}).get('status') == 'threw', 'Unexecuted bridge body')
    return calls


def _post_matches(call, request):
    args = call['args']
    require(len(args) == 4 and args[1] == request['path'] and request.get('secure') is True and
        request.get('method') == 'POST' and args[0].startswith('https://'), 'Original transport/server path or TLS differs')
    body = json.loads(args[3])
    seen = request['body']
    if request['kind'] == 'login':
        require(body.get('type') == seen['type'] and body.get('identifier', {}).get('user') == seen['user'] and
            digest(body.get('password', '')) == seen['passwordSha256'] and args[2] == '', 'Original login HTTP mapping differs')
    else:
        auth = body.get('auth')
        require(body.get('erase') is seen['erase'] and bool(auth) is seen['hasAuth'] and
            digest('Bearer ' + args[2]) == request['authorizationSha256'], 'Original erase/token mapping differs')
        if auth:
            require(auth.get('type') == seen['authType'] and auth.get('identifier', {}).get('user') == seen['user'] and
                digest(auth.get('password', '')) == seen['passwordSha256'] and auth.get('session') == seen.get('session'),
                'Original UIA auth/password/challenge mapping differs')
    if request.get('responseStatus') is not None:
        settlement = call.get('settlement', {})
        require(settlement.get('status') == 'fulfilled' and settlement.get('value', {}).get('status') == request['responseStatus'],
            'Original NativeAccountTransport response mapping unavailable/different')


def changed_body(data):
    native, provider = data['native'], data['provider']
    label = 'capability:restored_positive' if data['spec']['key'] == 'capability_gates_entry' else (
        'after_modal_input' if data['spec']['key'] == 'confirm_sends_payload' else 'after_event')
    snapshots = [frame for frame in native['frames'] if frame['label'] == label]
    require(len(snapshots) == 1, 'Own canonical bridge post-event boundary missing')
    snapshot = snapshots[0]
    calls = ledger_calls(snapshot['bridgeLedger'])
    owners = {frame['pageOwner'].get('bridgeReceiverId') for frame in native['frames'] if frame.get('pageOwner', {}).get('available')}
    require(owners and None not in owners, 'No original page-owned AccountClient receiver identity')
    clients = [call for call in calls if call['className'] == 'AccountClient' and call['receiverId'] in owners]
    require(clients and any(call['method'] == 'login' and call.get('settlement', {}).get('status') == 'fulfilled'
        for call in clients), 'Own actual page login body did not execute')
    transports = {call['before']['transportId'] for call in clients}
    posts = [call for call in calls if call['className'] == 'NativeAccountTransport' and call['method'] == 'post' and
        call['receiverId'] in transports]
    counts = snapshot['provider']
    requests = [item for item in provider['requests'] if item.get('kind') == 'login' or
        (item.get('kind') == 'deactivation' and item['number'] <= counts['deactivationCount'])]
    require(counts['loginCount'] == 1 and len(requests) == 1 + counts['deactivationCount'], 'Own server snapshot/request count mismatch')
    require(len(posts) == len(requests) and provider['nonce'] == native['nonce'], 'SDK HTTP effects differ from external server')
    for call, request in zip(posts, requests):
        _post_matches(call, request)
    service = [call for call in clients if call['method'] == 'deactivateAccount']
    if service:
        sends = [call for call in clients if call['method'] == 'sendDeactivation']
        require(len(sends) == len([request for request in requests if request['kind'] == 'deactivation']) and all(
            any(post['parentCallId'] == send['id'] and post['receiverId'] == send['before']['transportId'] for post in posts)
            for send in sends), 'Original deactivate/sendDeactivation/transport bridge chain missing')
        for send in sends:
            matching = [post for post in posts if post['parentCallId'] == send['id']]
            require(len(matching) == 1 and json.loads(matching[0]['args'][3]) == send['args'][1],
                'New app-owned sendDeactivation mapping was not actually exercised')
    if data['spec']['key'] == 'success_completes':
        success = [call for call in service if call.get('settlement', {}).get('status') == 'fulfilled']
        require(len(success) == 1, 'Original successful deactivation wrapper did not settle')
        client = success[0]
        cleanup = [call for call in clients if call['method'] == 'completeCleanup' and call['receiverId'] == client['receiverId'] and
            call.get('settlement', {}).get('status') == 'fulfilled']
        require(len(cleanup) == 1 and cleanup[0]['after'].get('closed') is True and cleanup[0]['after'].get('session') is None,
            'Original production completion/cleanup missing')
        store_id = cleanup[0]['before']['storeId']
        clears = [call for call in calls if call['className'] == 'NativeAccountSessionStore' and call['method'] == 'clear' and
            call['receiverId'] == store_id and call.get('settlement', {}).get('status') == 'fulfilled']
        require(len(clears) == 1 and clears[0]['startedAt'] >= cleanup[0]['startedAt'],
            'Fixture cleanup cannot substitute original session store clear')
    return {'protocol': 'task15.changed-body-admission.v8', 'originalCallIds': [call['id'] for call in calls],
        'originalPageClientIds': sorted(owners), 'originalTransportIds': sorted(transports),
        'serverRequestSequences': [request['sequence'] for request in requests],
        'mockedApplicationBridges': False, 'systemHttpControlled': False,
        'canonicalFrameSequence': snapshot['sequence'], 'fixtureTeardownIsNotCanonicalEvent': True}


def inspect_capability(data, profile):
    native, spec = data['native'], data['spec']
    require(spec['key'] == 'capability_gates_entry' and native.get('pageOwnerProtocol') == PROTOCOL and
        native.get('eventExecuted') is True and native.get('outcome') == 'transition_observed' and not native.get('failure'),
        'Incomplete fresh own capability event')
    require(native.get('entryExecuted') is True and native['caseId'] == spec['caseId'] and
        native['traceDigest'] == spec['traceDigest'] and native['nonce'] == data['provider']['nonce'] and
        native['sessionId'] == native['nonce'] + ':' + spec['caseId'] and data['provider']['loginCount'] == 1,
        'Borrowed capability episode or absent own authenticated prefix')
    require(len({item['sequence'] for item in native['frames'] + native['actions']}) ==
        len(native['frames'] + native['actions']), 'Duplicated capability frame/action')
    require(all(frame['sessionId'] == native['sessionId'] for frame in native['frames']), 'Other capability frame episode')
    pair = native['capabilityPair']
    require(pair.get('protocol') == 'task15.capability-cold-original-owner.v8' and pair.get('complete') is True and
        pair.get('restored') is True and pair['parentEpisodeId'] == native['sessionId'], 'Capability negative/restored positive incomplete')
    require(profile['sourceRootSha256'] == data['inputs']['rootSha256'] and profile['compiledProduction'] == data['build']['production'],
        'Unknown source capability closure')
    frames = native['frames']
    def one(label):
        found = [frame for frame in frames if frame['label'] == label]
        require(len(found) == 1, 'Own capability full native frame missing')
        frame = found[0]
        bracket(frame)
        p = page_owner(frame, native, profile)
        for name in ('settings', 'notifications', 'session', 'signOut'):
            control(frame, name, profile)
        require(control(frame, 'session', profile)['text'] == p['sessionIdentity']['userId'],
            'Actual signed-in account positive control differs from original page client')
        session = control(frame, 'session', profile)
        require(owner._node(frame['nativeTree'], session['treePath'])['$attrs'].get('text') == session['text'],
            'Session positive control query/full-tree text mismatch')
        return frame
    before, after, negative, restored = [one(label) for label in
        ('before_event', 'after_event', 'capability:unsupported_after', 'capability:restored_positive')]
    require(before['pageOwner']['state']['serverCanDeactivateAccount'] is spec['given']['serverCanDeactivateAccount'],
        'Complete supported given missing')
    phases = pair['phases']
    require([phase['label'] for phase in phases] == ['after_event', 'capability:unsupported_after', 'capability:restored_positive'],
        'Own supported/negative/restored cold epochs missing')
    client_ids = []
    for phase, frame in zip(phases, (after, negative, restored)):
        require(phase['frameSequence'] == frame['sequence'], 'Capability phase borrowed another frame')
        events = phase['lifecycle']['events']
        prior_events = phase['previousLifecycle']['events']
        require(events[:len(prior_events)] == prior_events, 'Original lifecycle history changed')
        fresh = events[len(prior_events):]
        names = [event['method'] for event in fresh]
        require(all(name in names for name in ('coldRestartRequested', 'abilityDestroy', 'windowStageDestroy',
            'abilityCreate', 'windowStageCreate', 'abilityForeground', 'coldRestartReturned')) and
            names.index('abilityDestroy') < names.index('abilityCreate') and
            names.index('windowStageDestroy') < names.index('windowStageCreate'), 'No actual original cold app lifecycle/window')
        p = frame['pageOwner']; client_ids.append(p['bridgeReceiverId'])
        lifecycle = [call for call in p['ownerCalls'] if call['method'] in ('loadCapability', 'refreshAvailability') and
            call['returned'] is True and call['instanceId'] == p['instanceId']]
        require(lifecycle, 'Capability read from a detached client instead of original page lifecycle')
        calls = ledger_calls(phase['bridgeLedger'])
        capabilities = [call for call in calls if call['className'] == 'AccountClient' and call['method'] == 'canDeactivateAccount' and
            call['receiverId'] == p['bridgeReceiverId'] and call.get('settlement', {}).get('status') == 'fulfilled']
        restores = [call for call in calls if call['className'] == 'AccountClient' and call['method'] == 'restore' and
            call['receiverId'] == p['bridgeReceiverId'] and call.get('settlement', {}).get('status') == 'fulfilled']
        require(capabilities and restores and capabilities[-1]['settlement']['value'] is p['state']['serverCanDeactivateAccount'],
            'Cold original page client capability/restore body unobserved')
        actions = [action for action in native['actions'] if action['sequence'] == phase['eventSequence']]
        require(len(actions) == 1 and actions[0]['kind'] == 'cold_settings_load' and actions[0]['target'] == 'original_settings' and
            actions[0]['executed'] is True and actions[0]['sessionId'] == native['sessionId'] and
            actions[0]['sequence'] < frame['sequence'], 'Canonical cold settings SDK action missing')
    require(len(set(client_ids)) == 3, 'Cold phases reused a detached/disposed original client')
    require([fixture['kind'] for fixture in pair['fixtures']] == [
        'system_persisted_unsupported_session', 'system_persisted_matrix_restore'], 'Own SDK persisted input/restore missing')
    calls = ledger_calls(pair['bridgeLedger'])
    for fixture, mode in zip(pair['fixtures'], ('oidc', 'matrix')):
        span = calls[fixture['bridgeCallStart']:fixture['bridgeCallEnd']]
        saves = [call for call in span if call['className'] == 'NativeAccountSessionStore' and call['method'] == 'save' and
            call.get('settlement', {}).get('status') == 'fulfilled']
        reads = [call for call in span if call['className'] == 'NativeAccountSessionStore' and call['method'] == 'read' and
            call.get('settlement', {}).get('status') == 'fulfilled']
        require(len(saves) == len(reads) == 1 and saves[0]['args'][0]['authMode'] ==
            reads[0]['settlement']['value']['authMode'] == mode, 'Fixture given not actually persisted/read by original system store')
    require(negative['pageOwner']['sessionIdentity']['authMode'] == 'oidc' and
        restored['pageOwner']['sessionIdentity']['authMode'] == 'matrix' and
        all(frame['pageOwner']['sessionIdentity']['userId'] == before['pageOwner']['sessionIdentity']['userId']
            for frame in (after, negative, restored)), 'Unsupported/restored input did not reach original page client')
    visible = visibility(after, 'entry', profile)
    negative_visible = visibility(negative, 'entry', profile)
    positive_visible = visibility(restored, 'entry', profile)
    entry = control(after, 'entry', profile) if visible else None
    color = None
    if entry:
        node = owner._node(after['nativeTree'], entry['treePath'])
        color = node['$attrs'].get('fontColor')
        require(type(color) is str and color in profile['reviewedEntryColors'], 'Native destructive style unobserved/unknown')
    observed = {'deactivateEntryVisible': visible, 'entryStyle': profile['reviewedEntryColors'][color] if color else None}
    invariant = (negative['pageOwner']['state']['serverCanDeactivateAccount'] is False and not negative_visible and
        restored['pageOwner']['state']['serverCanDeactivateAccount'] is True and positive_visible)
    return previous._row(spec, observed, invariant, [before, after, negative, restored], PROTOCOL,
        {'actualColdPageClientIds': client_ids, 'unsupportedInput': pair['fixtures'][0], 'restoredPositiveControl': positive_visible})


def inspect_obligations(data, profile):
    """Pure native-schema projection, not the artifact/default admission API."""
    require(data['native'].get('pageOwnerProtocol') == PROTOCOL, 'Wrong original page protocol')
    if data['spec']['key'] == 'capability_gates_entry':
        row = inspect_capability(data, profile)
    else:
        text = inspect.getsource(previous.inspect_task15)
        text = producer.prior.transport.replace(text,
            "frame['windowIdentity'] == end['windowIdentity']", "stable_window(frame['windowIdentity'], end['windowIdentity'])")
        text = producer.prior.transport.replace(text,
            "request['body'].get('auth', {}).get('password') == payload['password']",
            "request['body'].get('passwordSha256') == digest(payload['password'])")
        facade = types.SimpleNamespace(**{**vars(owner), '_control': control,
            'inspect_same_page_owner': producer.clone(owner.inspect_same_page_owner, _control=control)})
        scope = {**previous.inspect_task15.__globals__, 'P15': PROTOCOL, '_task15_owner': page_owner,
            'owner': facade, '_native_visibility': visibility, 'stable_window': stable_window, 'digest': digest}
        exec(compile(text, str(Path(__file__)) + ':original-native-obligations', 'exec'), scope)
        row = scope['inspect_task15'](data, profile)
    return row


def inspect_native(data, profile):
    row = inspect_obligations(data, profile)
    row['changedBodyEvidence'] = changed_body(data)
    return row


def admit(bundle, contract, *, profile_key):
    require(profile_key in REVIEWED_PROFILES, 'No reviewed V8 complete native/source/SDK profile; NS')
    profile = transport.read(REVIEWED_PROFILES[profile_key])
    data = transport.envelope(bundle, contract)
    plan, build = data['plan'], data['build']
    require(plan.get('fullNativeProtocol') == PROTOCOL and plan.get('pageOwnerProtocol') == PROTOCOL,
        'Old host/producer cannot acquire full original-owner provenance')
    bindings = transport.read(plan['actualSourceBindings'])
    require(profile['ownerBinding'] == bindings['ownerBinding'] and
        build['nativeUIObserver']['binding']['ownerBinding'] == bindings['ownerBinding'] and
        build['nativeUIObserver']['binding']['controlSelectors'] == bindings['controlSelectors'], 'Unbound original native controls/owner')
    fixtures = {Path(item['installedPath']).name: item['sha256'] for item in build['nativeUIObserver']['fixtures']}
    planned = {Path(item['path']).name: item['sha256'] for item in plan['derivedFiles']}
    for name in ('Task15PageOwnerObserverV5.js', 'Task15BridgeLedgerV8.js', 'Task15CapabilityPairV8.js', 'Task15Launch.js'):
        require(name in fixtures and fixtures[name] == planned.get(name), 'New original-owner/bridge/lifecycle fixture not actually compiled')
    scope = transport.read(plan['changedBodySourceLedger'])
    production = {item['path']: item['sha256'] for item in build['production']}
    for item in scope['records']:
        require(production.get(item['path']) == item['sourceSha256'], 'App-owned bridge scope differs from actual compiled source')
    immutable = transport.read(plan['immutableTaskManifest'])
    import re
    require(immutable['taskId'] == producer.TASK and all(re.fullmatch('[a-f0-9]{40}', immutable['android'][name])
        for name in ('baseCommit', 'finalCommit')), 'Immutable upstream source identity missing')
    row = inspect_native(data, profile)
    row['changedBodySourceScope'] = plan['changedBodySourceLedger']
    return {**row, 'rawEpisode': bundle, 'productionSources': build['production']}
