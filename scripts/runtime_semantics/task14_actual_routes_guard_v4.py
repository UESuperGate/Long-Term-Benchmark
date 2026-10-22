"""Independent admission for fresh physical Task14 route cases, never host rows.

inspect_episode is a pure projection for explicitly synthetic unit fixtures.
admit additionally binds the full candidate, compiled fixtures, nonce, native
transport, cleanup and a separately reviewed closed-layout profile.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from . import task14_15_arkts_artifacts as artifacts
from . import task15_fresh_admission_v2 as inputs
from . import task15_page_owner_v5 as layout

TASK = '14_join_room_by_address'
PROTOCOL = 'task14.arkts.actual-route-envelope.v4'
KEYS = {'found_then_continue_navigates', 'continue_waits_for_resolution', 'dismiss_closes_flow'}
require = artifacts.require
# Approval needs actual native captures and source/layout review. Offline
# fixtures and a caller-provided source hash cannot create such an approval.
REVIEWED_PROFILES = {}


def _control(frame, name, profile, *, action=False):
    control = frame['controls'][name]
    require(control.get('present') is True and control.get('visible') is True and
            control.get('inspectorMatches') == 1, 'Missing/unknown native control remains NS')
    binding = profile['controls'][name]
    require(control['id'] == binding['id'] and control['type'] == binding['type'],
            'Unknown/renamed action binding')
    matches = []
    def visit(node, path='root'):
        attrs = node.get('$attrs', {})
        if path == binding['treePath']:
            matches.append(node)
        for number, child in enumerate(node.get('$children', [])):
            visit(child, path + '/' + str(number))
    visit(frame['tree'])
    require(len(matches) == 1, 'Native node path is not bound')
    node = matches[0]
    attrs, bounds, viewport = node['$attrs'], control['bounds'], frame['viewport']
    require(node['$type'] == binding['type'] and attrs.get('id', '') == binding['id'] and
        attrs.get('visibility') == 'Visibility.Visible' and float(attrs.get('opacity', 0)) > 0 and
        type(attrs.get('enabled')) is bool and attrs['enabled'] is control['enabled'],
        'Inspector and Driver identity/visibility/enabled disagree')
    require(json.loads('[' + node['$rect'] + ']') == [[bounds['left'], bounds['top']], [bounds['right'], bounds['bottom']]] and
        viewport['left'] <= bounds['left'] < bounds['right'] <= viewport['right'] and
        viewport['top'] <= bounds['top'] < bounds['bottom'] <= viewport['bottom'], 'Unproven native geometry')
    if action:
        target = control.get('actionAncestor', control)
        require(target.get('enabled') is True and target.get('clickable') is True,
                'Physical event not eligible; no force-click')
        # No caller-supplied unknown parent can redirect a genuine control.
        require(target == control or target == binding.get('reviewedActionAncestor'), 'Unbound action ancestor')
    return control


def _frame(frame, episode, profile):
    end = frame['bracketEnd']
    require(frame.get('available') is True and type(frame.get('windowId')) is int and
        frame['windowId'] == end['windowId'] and frame['routeName'] == end['routeName'] and
        frame.get('routeParams') == end.get('routeParams') and frame['tree'] == end['tree'],
        'Mixed/unknown complete native frame')
    require(layout.layout_signature(frame['tree'], profile) in profile['closedLayouts'],
            'Unknown/extra/renamed interactive layout remains NS')
    acquisition = frame['acquisition']
    require(acquisition['sessionId'] == episode['sessionId'] and
        0 < acquisition['beginSequence'] < acquisition['endSequence'] and
        sum(sample == frame for sample in episode['samples']) == 1, 'Frame is not from this original native episode')


def inspect_episode(episode, spec, profile):
    require(episode.get('protocol') == PROTOCOL and spec['taskId'] == TASK and spec['key'] in KEYS and
        episode.get('taskId') == TASK and episode.get('caseId') == spec['caseId'] and
        episode.get('traceDigest') == spec['traceDigest'] and
        re.fullmatch('[a-f0-9]{32}', episode.get('nonce', '')) is not None and
        episode.get('sessionId') == episode['nonce'] + ':' + spec['caseId'], 'Borrowed/old/host case identity')
    transition = episode['transition']
    require(episode.get('entryExecuted') is True and episode.get('released') is True and not episode.get('failure') and
        transition.get('protocol') == 'task14.arkts.actual-navigation-routes.v3' and
        transition.get('eventExecuted') is True and not transition.get('failure') and
        transition.get('outcome') == 'native_transition_observed_pending_independent_admission',
        'Environment/setup/action failure remains NS')
    require(episode['finishedAt'] <= episode['deadlineEpochMs'], 'Native cleanup exceeded original deadline')
    frames = transition['frames']
    def unique(label):
        matches = [item for item in frames if item['label'] == label]
        require(len(matches) == 1, 'Own complete given/event/post frame required')
        item = matches[0]
        _frame(item['frame'], episode, profile)
        return item['frame'], item['samePageOwnerState']
    root, _ = unique('common:root')
    before, prior = unique('before:event')
    after, current = unique('after:event')
    require(root['routeName'] == profile['entryRoute'] and
        before['routeName'] == profile['addressRoute'] and
        root['windowId'] == before['windowId'] == after['windowId'], 'Original common-prefix/window lineage missing')
    for name in ('search', 'join', 'create'):
        _control(root, name, profile)
    for name in ('input', 'continue', 'cancel'):
        _control(before, name, profile)
    setup = [action for action in episode['actions'] if action['beginSequence'] > root['acquisition']['endSequence'] and
             action['endSequence'] < before['acquisition']['beginSequence']]
    require(len(setup) == 2 and setup[0]['kind'] == 'click' and setup[1]['kind'] == 'input' and
        all(action['executed'] is True and action['sessionId'] == episode['sessionId'] for action in setup) and
        setup[0]['control'] == root['controls']['join'].get('actionAncestor', root['controls']['join']) and
        setup[1]['control']['selector'] == before['controls']['input']['selector'] and setup[1]['value'] == prior['address'],
        'Original native join entry and physical address-input prefix not established')
    _control(root, 'join', profile, action=True)
    require(all(state.get('available') is True and state.get('instanceCount') == 1 for state in (prior, current)) and
        prior['instanceId'] == current['instanceId'] and before['stateBefore'] == before['stateAfter'] == prior and
        after['stateBefore'] == after['stateAfter'] == current, 'Standalone/replaced/mixed original page owner')
    require(current['calls'][:len(prior['calls'])] == prior['calls'] and
        prior['address'] == before['controls']['input']['text'], 'Original owner/rendered given mismatch')
    own = [request for request in prior['resolverRequests'] if request['samePageResolver'] and
           request['alias'] == prior['address']]
    require(len(own) == 1, 'Own actual external pending/resolved request missing')
    records = episode['records']
    require([item['sequence'] for item in records] == sorted({item['sequence'] for item in records}), 'Duplicated evidence sequence')
    events = [(item['sequence'], item['event']) for item in records]
    request = own[0]
    require(sum(event.get('method') == 'Task14.externalResolverRequested' and event.get('requestId') == request['id'] and
        event.get('alias') == prior['address'] for _, event in events) == 1, 'No actual resolver request boundary')
    if spec['key'] == 'found_then_continue_navigates':
        require(prior['addressState'] == spec['given']['addressState'] and prior['resolvedRoom'] ==
            {'roomId': spec['given']['roomId'], 'servers': spec['given']['servers']} and request['settled'] is True,
            'Full canonical resolved-room given missing')
        resolved = [(number, event) for number, event in events if event.get('method') == 'Task14.externalResolverResolved']
        require(len(resolved) == 1 and resolved[0][0] < before['acquisition']['beginSequence'] and
            resolved[0][1]['requestId'] == request['id'] and resolved[0][1]['samePageResolver'] is True and
            resolved[0][1]['response'] == prior['resolvedRoom'], 'Resolved given not established by own external boundary')
    else:
        require(prior['addressState'] == 'resolving' and request['settled'] is False and all(
            prior.get(name) == value for name, value in spec['given'].items()), 'Complete canonical pending given missing')
    lower, upper = before['acquisition']['endSequence'], after['acquisition']['beginSequence']
    actions = [item for item in episode['actions'] if item['beginSequence'] > lower and item['endSequence'] < upper]
    require(len(actions) == 1, 'Missing/borrowed canonical physical event')
    action = actions[0]
    name = 'cancel' if spec['key'] == 'dismiss_closes_flow' else 'continue'
    control = _control(before, name, profile, action=True)
    require(action.get('executed') is True and action['kind'] == 'click' and
        action['sessionId'] == episode['sessionId'] and action['control'] == control.get('actionAncestor', control),
        'Not this own case eligible physical action')
    handler = 'dismiss' if name == 'cancel' else 'continue'
    require(any(call['instanceId'] == current['instanceId'] and call['method'] == handler and call.get('returned') is True
        for call in current['calls'][len(prior['calls']):]), 'Physical event did not reach original handler')
    physical = [event for number, event in events if lower < number < upper and event.get('method') == 'Task14.uiAction']
    require(len(physical) == 1 and physical[0]['kind'] == 'click' and physical[0]['selector'] == action['control']['selector'],
            'Driver action receipt missing')
    # Reconstruct effects from the original observer ledger, never the summary
    # actualRouteOutcomeV3 or producer observed/invariantChecks objects.
    route_calls = [event['call'] for number, event in events if lower < number < upper and
        event.get('method') == 'Task14.realFlowProductionCall']
    routes = [call for call in route_calls if call['owner'] == 'HarmonyRoutePort' and
        call['method'] == 'replace' and call['phase'] == 'call']
    loads = [call for call in route_calls if call['owner'] == 'RoomPresenter' and call['method'] == 'load' and call['phase'] == 'call']
    nav_prefix = prior['navigationCalls']
    require(current['navigationCalls'][:len(nav_prefix)] == nav_prefix, 'Navigator history changed')
    navigations = [call for call in current['navigationCalls'][len(nav_prefix):] if call['method'] == 'openRoom']
    room = after['routeName'] == 'pages/Room'
    root_visible = (after['routeName'] == profile['entryRoute'] and after['controls']['search'].get('present') is True and
        after['controls']['input'].get('present') is False)
    address = after['routeName'] == profile['addressRoute'] and after['controls']['input'].get('present') is True
    require(room or root_visible or address, 'Unknown actual post-event surface')
    if room:
        _control(after, 'roomBack', profile)
        room_id = after.get('routeParams', {}).get('roomId')
        require(room_id and any(call.get('receiverTags', {}).get('navigatorRoutePort') is True and
            call['args'] == ['pages/Room', after['routeParams']] for call in routes) and any(
            call['args'] == [room_id] and call.get('receiverTags', {}).get('ownsExportedGateway') is True for call in loads),
            'Actual Room route lacks original router/RoomPresenter ownership and params')
    if root_visible:
        _control(after, 'search', profile)
        # A Driver "missing" result alone is not evidence that the old address
        # input is absent. The same complete inspector must agree.
        def all_nodes(node):
            yield node
            for child in node.get('$children', []):
                yield from all_nodes(child)
        require(not any(node.get('$attrs', {}).get('id') == profile['controls']['input']['id']
            for node in all_nodes(after['tree'])), 'Address input remains in inspector despite Driver absence')
    if address:
        for name in ('input', 'continue', 'cancel'):
            _control(after, name, profile)
    if spec['key'] == 'continue_waits_for_resolution':
        pending, pending_state = unique('after:continue-before-resolution')
        require(pending_state['instanceId'] == prior['instanceId'] and pending_state['addressState'] == 'resolving' and
            pending['acquisition']['beginSequence'] > action['endSequence'], 'Own intermediate pending event missing')
        responses = [(number, event) for number, event in events if event.get('method') == 'Task14.externalResolverResolved']
        require(len(responses) == 1 and pending['acquisition']['endSequence'] < responses[0][0] < upper and
            responses[0][1]['requestId'] == request['id'] and responses[0][1]['samePageResolver'] is True and
            responses[0][1]['response'] == {'roomId': spec['event']['roomId'], 'servers': spec['event']['servers']},
            'Compound event is not its own actual external response')
        observed = {'validationRequested': current['validationRequested'], 'dismissAddressFlow': room,
                    'navigationCount': len(routes)}
        invariant = len(current['resolverRequests']) == len(prior['resolverRequests'])
    elif spec['key'] == 'found_then_continue_navigates':
        observed = {'dismissAddressFlow': room, 'openRoom': {'roomIdOrAlias': after['routeParams']['roomId'],
            'serverNames': navigations[-1]['args'][1] if len(navigations[-1]['args']) > 1 else None} if room and navigations else None}
        invariant = len(navigations) == len(routes) == 1
    else:
        observed = {'addressFlowVisible': not root_visible, 'openRoomCount': len(routes)}
        invariant = not navigations and not routes and not loads
    require(set(observed) == set(spec['expected']) and len(spec['invariants']) == 1, 'Original obligations missing/changed')
    checks = [{'description': spec['invariants'][0], 'passed': bool(invariant),
        'observed': {'actualRouteCalls': routes, 'actualRoomLoads': loads,
            'originalNavigatorCalls': navigations, 'beforeRequests': prior['resolverRequests'], 'afterRequests': current['resolverRequests']}}]
    return {'caseId': spec['caseId'], 'key': spec['key'], 'traceDigest': spec['traceDigest'],
        'status': 'pass' if observed == spec['expected'] and invariant else 'fail', 'observed': observed,
        'invariantChecks': checks, 'checkpoints': [copy.deepcopy(before), copy.deepcopy(after)],
        'canonicalObligations': {key: copy.deepcopy(spec[key]) for key in ('given', 'event', 'expected', 'invariants')},
        'episodeId': episode['sessionId'], 'transitionExecuted': True, 'runtime': PROTOCOL}


def envelope(bundle, contract):
    data = {key: json.loads(artifacts.bound(bundle[key])) for key in
            ('plan', 'inputs', 'build', 'execution', 'raw', 'retention')}
    plan, build, execution, raw = (data[key] for key in ('plan', 'build', 'execution', 'raw'))
    require(plan['protocol'] == PROTOCOL and json.loads(artifacts.bound(plan['contract'])) == contract,
            'Wrong pre-execution plan/contract')
    manifest = json.loads(artifacts.bound(plan['immutableTaskManifest']))
    require(manifest.get('taskId') == TASK and all(re.fullmatch('[0-9a-f]{40}', manifest['android'][key])
        for key in ('baseCommit', 'finalCommit')), 'Immutable upstream commit identities unavailable')
    from . import task14_actual_routes_packaging_v4 as packaging
    require(plan['implementation'] == packaging.implementation() and plan['packagedFixtures'] == packaging.expected_fixtures(),
        'Not the reviewed exact route producer/guard implementation')
    require(plan['source'] == data['inputs']['source'] == build['source'], 'Candidate path differs')
    inputs._input_closure(data['inputs'], build)
    require(all(build.get(key) is True for key in ('productionUnchanged', 'copiedProductionUnchanged', 'temporaryProjectRemoved')) and
        build.get('runtimeCompile', {}).get('passed') is True and build.get('compile', {}).get('passed') is None,
        'Environment or runtime packaging failure is never a semantic failure')
    require(build['taskId'] == execution['taskId'] == raw['taskId'] == TASK and
        build['caseId'] == execution['caseId'] == raw['caseId'] and build['role'] == execution['role'] == raw['role'] == 'agent',
        'Executed case/role/source is not the plan')
    spec = next(item for item in contract['cases'] if item['caseId'] == raw['caseId'])
    require(spec['caseId'] in plan['selectedCases'] and raw['traceDigest'] == spec['traceDigest'], 'Canonical raw identity differs')
    native = [item['actualRouteEpisodeV4'] for item in raw.get('evidence', []) if 'actualRouteEpisodeV4' in item]
    require(len(native) == 1, 'Projected ArkVM/old row cannot be native route evidence')
    native = native[0]
    nonce = execution['executionNonce']
    require(native['nonce'] == nonce == raw['nativeBridge']['capabilities']['execution']['nonce'] and
        execution.get('transportCompleted') is True and execution.get('status') == 'transport_completed' and
        execution.get('candidateAbsentBeforeInstall') is True and not execution.get('error') and
        execution.get('cleanup', {}).get('ownedAppUninstalled') is True and execution['rows'] == [raw], 'Fresh transport/cleanup mismatch')
    require(execution['rowArtifact']['sha256'] == bundle['raw']['sha256'] and
        execution['rowArtifact']['bytes'] == bundle['raw']['bytes'] and
        execution['rowArtifact']['processLogMarker']['executionNonce'] == nonce, 'Raw bytes/nonce not bound to pulled device result')
    aa = [item for item in execution['commands'] if item.get('log') == 'aa-test.log']
    require(len(aa) == 1 and aa[0]['exitCode'] == 0 and not aa[0].get('error') and not aa[0].get('signal') and
        sum(aa[0]['args'][pos:pos + 3] == ['-s', 'ltbExecutionNonce', nonce] for pos in range(len(aa[0]['args']))) == 1,
        'No own completed nonce-bound AA command')
    transcript = artifacts.bound(bundle['aaLog']).decode()
    require(bundle['aaLog']['sha256'] == aa[0]['sha256'] and re.search(r'TestFinished-ResultCode: 0\b', transcript) and
        'Failure: 0, Error: 0' in transcript, 'Native transport log missing/failed')
    require(build['nativeUIObserver']['protocol'] == PROTOCOL and build['nativeUIObserver']['production'] == build['production'] and
        native['productionSources'] == build['nativeUIObserver']['config']['productionSources'], 'Actual production provenance differs')
    packaged = {Path(item['path']).name: item['sha256'] for item in build['nativeUIObserver']['fixtures']}
    require(len(packaged) == len(build['nativeUIObserver']['fixtures']) == len(plan['packagedFixtures']),
            'Missing/extra/ambiguous compiled route fixture')
    for item in plan['packagedFixtures']:
        require(packaged.get(item['name']) == item['sha256'], 'Fresh route producer was not compiled: ' + item['name'])
    for item in plan['implementation']['files']:
        path = Path(item['path'])
        require(path.is_file() and not path.is_symlink() and artifacts.digest(path) == item['sha256'] and
            path.stat().st_size == item['bytes'], 'Evaluator implementation changed since pre-execution plan')
    require(artifacts.row_digest(plan['implementation']['files']) == plan['implementation']['sha256'], 'Evaluator inventory digest differs')
    retention = data['retention']
    require(retention.get('binariesRetained') is False and retention.get('temporaryBuildRemoved') is True,
        'Missing runtime hash/removal evidence')
    removed = retention['removedBinaryArtifacts']
    for hap in build['haps']:
        require(any(item['sha256'] == hap['sha256'] and item['bytes'] == hap['bytes'] for item in removed) and
            not Path(hap['path']).exists(), 'HAP has no matching hash/removal record')
    require(len(build['haps']) >= 2 and native['deadlineEpochMs'] <= plan['deadlineEpochMs'], 'Incomplete packaging/deadline')
    return data, native, spec


def admit(bundle, contract, *, profile_key):
    require(profile_key in REVIEWED_PROFILES, 'No actual source/layout route profile reviewed yet; NS')
    profile = json.loads(artifacts.bound(REVIEWED_PROFILES[profile_key]))
    data, episode, spec = envelope(bundle, contract)
    require(profile['sourceRootSha256'] == data['inputs']['rootSha256'] and
        profile['compiledProduction'] == data['build']['production'], 'Unknown production source/layout eligibility')
    return {**inspect_episode(episode, spec, profile), 'rawEpisode': bundle,
            'productionSources': data['build']['production']}
