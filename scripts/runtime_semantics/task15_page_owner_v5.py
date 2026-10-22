"""STAGED native admission for the five formerly host-only Task15 cases.

No runtime/public registration is supplied here. Raw transport remains the
reviewed v2 envelope; v5 additionally binds a packaged passive observer and
each case's own physical episode. A standalone presenter is never admissible.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from . import task15_fresh_admission_v2 as transport
from . import task14_15_formal_core as core

PROTOCOL = 'task15.arkts.same-original-page-owner.v5'
TASK = '15_account_deactivation'
CASES = {'default_form_blocks_submit', 'password_enables_submit', 'erase_data_option',
         'success_completes', 'close_dialog_resets_action'}
DIRECTORY = Path(__file__).with_name('task15_page_owner_v5')
require = transport.require

# No profile is approved by this offline staging change. Registration requires
# real native/source closure review, not a caller-supplied "approved" boolean.
APPROVED_PROFILES = {}


def layout_signature(tree, profile):
    rows = []
    dynamic = profile['dynamicAttributes']
    allowed = {'text', 'content', 'enabled', 'focused', 'isOn', 'isLayoutDirtyMarked',
               'isRenderDirtyMarked', 'hasPendingRequest', 'isFirstBuilding'}
    require(all(set(fields) <= allowed for fields in dynamic.values()), 'Layout cannot wildcard IDs/types/unknown controls')
    def visit(node, path):
        require(isinstance(node, dict) and isinstance(node.get('$children', []), list), 'Incomplete full native tree')
        attrs = copy.deepcopy(node.get('$attrs', {}))
        for key in dynamic.get(attrs.get('id'), []):
            if key in attrs:
                attrs[key] = '$actual_dynamic_value'
        rows.append({'path': path, 'type': node.get('$type'), 'attrs': attrs, 'children': len(node.get('$children', []))})
        for index, child in enumerate(node.get('$children', [])):
            visit(child, path + '/' + str(index))
    visit(tree, 'root')
    return rows


def _node(tree, path):
    require(path == 'root' or path.startswith('root/'), 'Unbound native node path')
    node = tree
    for part in path.split('/')[1:]:
        node = node['$children'][int(part)]
    return node


def _control(frame, name, profile):
    value = transport._control(frame, name)
    require(value.get('present') is True and value.get('visible') is True, 'Missing/unknown UI remains NS, not disabled')
    binding = profile['controls'][name]
    require(value['id'] == binding['id'] and value['treePath'] == binding['treePath'], 'Unbound or renamed native control')
    node = _node(frame['nativeTree'], value['treePath'])
    attrs = node['$attrs']
    require(node['$type'] == binding['type'] and attrs.get('id', '') == value['id'] and
        attrs.get('visibility') == 'Visibility.Visible' and type(attrs.get('enabled')) is bool and
        value.get('enabled') is attrs['enabled'], 'Native tree/query enabled/type disagree')
    bounds, viewport = value['bounds'], frame['windowIdentity']['bounds']
    require(json.loads('[' + node['$rect'] + ']') == [[bounds['left'], bounds['top']], [bounds['right'], bounds['bottom']]] and
        viewport['left'] <= bounds['left'] < bounds['right'] <= viewport['right'] and
        viewport['top'] <= bounds['top'] < bounds['bottom'] <= viewport['bottom'], 'Unproven geometry/occlusion')
    if name == 'password':
        require(type(attrs.get('text')) is str and value.get('text') == attrs['text'], 'Actual native password value missing')
    if name == 'erase':
        require(attrs.get('isOn') in ('true', 'false') and type(value.get('checked')) is bool and
            value['checked'] == (attrs['isOn'] == 'true'), 'Actual native toggle state missing')
    return value


def _owner(frame, native, profile):
    transport._window(frame, native)
    require(layout_signature(frame['nativeTree'], profile) in profile['closedLayouts'],
            'Unknown/extra/renamed native control: NS')
    p = frame['pageOwner']
    require(p.get('protocol') == PROTOCOL and p.get('available') is True and p.get('instanceCount') == 1 and
        p.get('observerMode') == 'pass_through_original_page_owner' and
        p.get('readScope') == 'original_receiver_fields_only' and p.get('originalService') is True,
        'No actual original page owner; standalone domain presenter is ineligible')
    require(p['binding'] == profile['ownerBinding'] and p['episodeId'] == native['sessionId'], 'Other source/page/episode owner')
    acquisition = p['acquisition']
    renders = [call for call in p['ownerCalls'] if call['sequence'] == acquisition['ownerCallSequence']]
    require(len(renders) == 1 and renders[0]['instanceId'] == p['instanceId'] and renders[0]['returned'] is True and
        acquisition['kind'] == 'production_page_lifecycle_or_render' and
        renders[0]['method'] in profile['ownerAcquisitionMethods'] and
        any(symbol in renders[0]['stack'] for symbol in profile['pageOwnerSymbols']),
        'Getter value/metadata is not a production page receiver acquisition')
    require(frame['sessionId'] == p['episodeId'] == native['sessionId'] and
        type(p['state']['requestCount']) is int and p['state']['requestCount'] >= 0 and
        p['state']['requestCount'] == len([call for call in p['serviceCalls'] if call['instanceId'] == p['serviceId']]),
        'Unbound receiver/request effect ledger')
    require(not p.get('evaluatorConstructedReceiver') and not p.get('evaluatorAssignedFields') and
        not p.get('forcedRender') and not p.get('directPresenterEvent'), 'Fixture manufactured production state/event')
    return p


def inspect_same_page_owner(data, profile):
    """Pure admission/projection boundary; tests use explicitly synthetic data.

    Only admit() binds this to actual HAP/AA/nonce/source/removal artifacts.
    Every UI expectation uses native controls; pure domain/effect expectations
    may use only the same captured native page owner's fields/call ledger.
    """
    native, spec = data['native'], data['spec']
    require(spec['taskId'] == TASK and spec['key'] in CASES and native['caseId'] == spec['caseId'] and
        native['traceDigest'] == spec['traceDigest'] and native.get('pageOwnerProtocol') == PROTOCOL and
        native.get('outcome') == 'transition_observed' and native.get('eventExecuted') is True and
        native.get('failure') is None, 'Old/borrowed/failed/host episode is not native v5 evidence')
    require(native.get('entryExecuted') is True and data['provider']['nonce'] == native['nonce'] and
        native['sessionId'] == native['nonce'] + ':' + spec['caseId'] and data['provider']['loginCount'] == 1 and
        len([request for request in data['provider']['requests'] if request.get('kind') == 'login' and
             request.get('secure') is True and request.get('responseStatus') == 200]) == 1,
        'Actual own authenticated native common prefix unavailable')
    require(profile['sourceRootSha256'] == data['inputs']['rootSha256'] and
        profile['compiledProduction'] == data['build']['production'], 'Unknown/mutated production binding: NS')
    frames, actions = native['frames'], native['actions']
    require(len({item['sequence'] for item in frames + actions}) == len(frames + actions), 'Reused episode/action')
    require(all(item['sessionId'] == native['sessionId'] for item in frames) and all(
        item['sessionId'] == native['sessionId'] or (item.get('phase') == 'setup' and
        item['sessionId'] == native.get('launchSetupSessionId')) for item in actions), 'Other case receiver/event reused')
    before = [frame for frame in frames if frame['label'] == 'before_event']
    after = [frame for frame in frames if frame['label'] == 'after_event']
    events = [action for action in actions if action.get('phase') == 'event']
    require(len(before) == len(after) == len(events) == 1, 'Own before/event/after required')
    before, after, event = before[0], after[0], events[0]
    prefixes = [frame for frame in frames if frame['label'] == 'common_start']
    require(len(prefixes) == 1 and prefixes[0]['sequence'] < before['sequence'], 'Own native common prefix missing')
    prefix = prefixes[0]
    transport._window(prefix, native)
    require(layout_signature(prefix['nativeTree'], profile) in profile['closedLayouts'], 'Unknown common prefix UI')
    for name in ('settings', 'notifications', 'entry'):
        _control(prefix, name, profile)
    require(prefix['windowAndIme']['nativeWindow']['id'] == before['windowAndIme']['nativeWindow']['id'] ==
        after['windowAndIme']['nativeWindow']['id'], 'Physical event switched original native window')
    for back in [action for action in actions if action['kind'] == 'system_back']:
        ime_frames = [frame for frame in frames if frame['sequence'] < back['sequence'] and
                      frame.get('windowAndIme') == back.get('observedImeBefore')]
        require(back.get('executed') is True and len(ime_frames) == 1 and
            ime_frames[0]['windowAndIme'].get('visibilitySource') == 'native_window_keyboard_avoid_area' and
            ime_frames[0]['windowAndIme'].get('keyboardVisible') is True and
            any(rect['width'] > 0 and rect['height'] > 0 for rect in
                ime_frames[0]['windowAndIme']['keyboardAvoidArea'].values()), 'Unconditioned/fabricated IME Back')
    if spec['key'] != 'default_form_blocks_submit':
        require(any(action['kind'] == 'click' and action['target'] == 'entry' and action['executed'] is True and
            action['sessionId'] == native['sessionId'] and prefix['sequence'] < action['sequence'] < before['sequence']
            for action in actions), 'Own physical original form entry not established')
    require(before['sequence'] < event['sequence'] < after['sequence'] and event.get('executed') is True,
            'Own physical/external event not executed')
    prior, current = _owner(before, native, profile), _owner(after, native, profile)
    require((prior['instanceId'], prior['serviceId']) == (current['instanceId'], current['serviceId']) and
        core._contains(prior['state'], spec['given']), 'Canonical given or same actual page owner unavailable')
    require(current['calls'][:len(prior['calls'])] == prior['calls'], 'Borrowed/replaced original call history')
    if spec['key'] != 'default_form_blocks_submit':
        if 'password' in spec['given']:
            require(_control(before, 'password', profile)['text'] == spec['given']['password'], 'Physical password given not established')
        if 'eraseData' in spec['given']:
            require(_control(before, 'erase', profile)['checked'] == spec['given']['eraseData'], 'Physical toggle given not established')
    require(len(current['serviceCalls']) >= len(prior['serviceCalls']) and all(
        {key: value for key, value in old.items() if key != 'settlement'} ==
        {key: value for key, value in new.items() if key != 'settlement'}
        for old, new in zip(prior['serviceCalls'], current['serviceCalls'])), 'Replaced service call receiver/payload history')
    require(event['callStart'] == len(prior['calls']) and len(prior['calls']) <= event['callEnd'] <= len(current['calls']),
            'Native action not bound to its own production call span')
    new_calls = current['calls'][event['callStart']:event['callEnd']]
    require(all(call['instanceId'] == current['instanceId'] for call in new_calls), 'Action reached another receiver')
    field_evidence, invariant = {}, False
    key = spec['key']
    def physical(kind, target):
        require(event['kind'] == kind and event['target'] == target and event.get('injected') is not True,
                'Not the canonical physical native action')
        control = _control(before, target, profile)
        require(control['enabled'] is True and event.get('nativeControl') == control,
                'Not an eligible actual native action; never force-click')
    def handler(method, args=None):
        found = [call for call in new_calls if call['method'] == method and call['returned'] is True]
        require(len(found) == 1 and (args is None or found[0]['args'] == args), 'No same-page production callback')
    if key == 'default_form_blocks_submit':
        physical('click', 'entry')
        require(not any(call['method'] in ('setPassword', 'setEraseData', 'deactivateAccount') for call in current['calls']),
                'Default values setter-repaired rather than observed')
    elif key == 'password_enables_submit':
        physical('input', 'password')
        require(event.get('value') == spec['event']['value'] and
            event.get('driverArguments') == [spec['event']['value']], 'Literal newline replaced before native input')
        handler('setPassword')
    elif key == 'erase_data_option':
        physical('click', 'erase')
        handler('setEraseData', [spec['event']['value']])
    elif key == 'success_completes':
        require(event['kind'] == 'https_response' and event['target'] == 'own_pending_deactivation' and
            event['status'] == 200 and type(event.get('requestId')) is int, 'No actual external success response')
        matching = [request for request in data['provider']['requests'] if request.get('kind') == 'deactivation' and
            request.get('number') == event['requestId'] and request.get('responseStatus') == 200 and request.get('secure') is True]
        require(len(matching) == 1 and prior['state']['requestCount'] == 1 and
            len(prior['serviceCalls']) == 1 and len(current['serviceCalls']) >= 1 and
            current['serviceCalls'][0].get('settlement', {}).get('status') == 'fulfilled' and
            {k: v for k, v in prior['serviceCalls'][0].items() if k != 'settlement'} ==
            {k: v for k, v in current['serviceCalls'][0].items() if k != 'settlement'},
            'Success is not settlement of this native owner\'s pending production request')
    else:
        physical('click', 'close')
        handler('closeDialogs', [])
    state = current['state']
    if key in ('default_form_blocks_submit', 'password_enables_submit'):
        password = _control(after, 'password', profile)['text']
        submit = _control(after, 'submit', profile)['enabled']
        field_evidence.update(password=[('native_input', password), ('same_page_owner_domain', state['password'])],
            submitEnabled=[('native_button_enabled', submit)])
        if key == 'default_form_blocks_submit':
            erase = _control(after, 'erase', profile)['checked']
            field_evidence['eraseData'] = [('native_toggle', erase), ('same_page_owner_domain', state['eraseData'])]
            invariant = state['requestCount'] == 0 and not current['serviceCalls'] and data['provider']['deactivationCount'] == 0
        else:
            invariant = all('\n' not in value and '\r' not in value for value in (password, state['password']))
    elif key == 'erase_data_option':
        field_evidence['eraseData'] = [('native_toggle', _control(after, 'erase', profile)['checked']),
                                     ('same_page_owner_domain', state['eraseData'])]
        invariant = (_control(before, 'password', profile)['text'] == _control(after, 'password', profile)['text'] ==
                     prior['state']['password'] == state['password'])
    elif key == 'success_completes':
        field_evidence = {name: [('same_native_page_owner_domain' if name == 'action' else 'same_owner_production_service_ledger', state[name])]
                          for name in ('action', 'requestCount')}
        invariant = (state['requestCount'] == prior['state']['requestCount'] == 1 and len(current['serviceCalls']) == 1 and
            after['provider']['deactivationCount'] == before['provider']['deactivationCount'] == data['provider']['deactivationCount'])
    else:
        field_evidence = {'action': [('same_native_page_owner_domain', state['action'])],
            'password': [('native_input', _control(after, 'password', profile)['text']), ('same_page_owner_domain', state['password'])],
            'eraseData': [('native_toggle', _control(after, 'erase', profile)['checked']), ('same_page_owner_domain', state['eraseData'])]}
        invariant = (state['requestCount'] == prior['state']['requestCount'] and
            len(current['serviceCalls']) == len(prior['serviceCalls']) and
            after['provider']['deactivationCount'] == before['provider']['deactivationCount'] and
            not any(call['method'] == 'deactivateAccount' for call in new_calls))
    require(set(field_evidence) == set(spec['expected']) and len(spec['invariants']) == 1, 'Original obligations changed')
    checks = [{'description': spec['invariants'][0], 'passed': invariant,
        'observed': {'before': prior['state'], 'after': state, 'nativeFrameSequences': [before['sequence'], after['sequence']]}}]
    passed = invariant and all(value == spec['expected'][name] for name, values in field_evidence.items() for scope, value in values)
    return {'caseId': spec['caseId'], 'key': spec['key'], 'traceDigest': spec['traceDigest'],
        'status': 'pass' if passed else 'fail', 'observed': {name: values[0][1] for name, values in field_evidence.items()},
        'fieldEvidence': {name: [{'scope': scope, 'value': value} for scope, value in values] for name, values in field_evidence.items()},
        'invariantChecks': checks, 'canonicalObligations': {name: copy.deepcopy(spec[name]) for name in ('given', 'event', 'expected', 'invariants')},
        'episodeId': native['sessionId'], 'sameOriginalPageOwner': {'instanceId': current['instanceId'], 'serviceId': current['serviceId']},
        'checkpoints': [copy.deepcopy(before), copy.deepcopy(after)], 'transitionExecuted': True,
        'runtime': 'openharmony_api23_original_page_owner_v5', 'presenterGetterUsedAsUiVerdict': False}


def admit(bundle, contract, *, profile_key):
    """Fail closed by default. No old raw/host report acquires native provenance."""
    require(profile_key in APPROVED_PROFILES, 'No reviewed native v5 source/layout/owner profile approved yet')
    profile = transport.read(APPROVED_PROFILES[profile_key])
    data = transport.envelope(bundle, contract)
    require(data['plan'].get('pageOwnerProtocol') == PROTOCOL and
        data['native'].get('pageOwnerProtocol') == PROTOCOL, 'Old host/native raw cannot be upgraded')
    require(any(Path(record['path']) == Path(__file__) and record['sha256'] == core.sha256(Path(__file__))
                for record in data['plan']['evaluator']['files']), 'Independent native owner guard not source-version bound')
    for name in ('Task15FreshActionsV2.js', 'Task15PageOwnerObserverV5.js'):
        source = DIRECTORY / name
        planned = [record for record in data['plan']['derivedFiles'] if Path(record['path']).name == name]
        compiled = [record for record in data['build']['nativeUIObserver']['fixtures'] if Path(record['installedPath']).name == name]
        require(len(planned) == len(compiled) == 1 and planned[0]['sha256'] == compiled[0]['sha256'] == core.sha256(source),
                'New passive observer/physical producer was not actually packaged')
    result = inspect_same_page_owner(data, profile)
    return {**result, 'rawEpisode': bundle, 'productionSources': data['build']['production']}
