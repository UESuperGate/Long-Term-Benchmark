"""Independent, fail-closed review of Task15 fresh physical action evidence.

This module does not execute a device, register a public policy, or promote
readiness. Diagnostic v6 is not a fresh execution. A blocked prefix has no
post-state or evaluated invariants; admission requires four current controls.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
from datetime import datetime

from . import task14_15_arkts_artifacts as artifacts
from . import task15_arkts_action_eligibility as closure

PROTOCOL = 'task15.arkts.fresh-physical-actions.v2'
POLICY_ID = 'task15.arkts.fresh-blocked-required-action.v2'
TASK = closure.TASK
CASE = closure.CASE
require = artifacts.require


def read(record):
    return json.loads(artifacts.bound(record))


def spec_for(contract, case_id):
    require(contract.get('taskId') == TASK, 'Wrong canonical task')
    matches = [row for row in contract['cases'] if row['caseId'] == case_id]
    require(len(matches) == 1, 'Unknown or duplicate canonical case')
    return matches[0]


def identity(value):
    files = value.get('files', [])
    require(files and len({item['path'] for item in files}) == len(files), 'Ambiguous evaluator source inventory')
    for item in files:
        path = Path(item['path'])
        require(path.is_file() and not path.is_symlink(), 'Evaluator source unavailable')
        data = path.read_bytes()
        require(len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'],
                'Evaluator source version changed; use a new version, not old pins')
    require(value['protocol'] == PROTOCOL and artifacts.row_digest(files) == value['sha256'],
            'Unbound evaluator implementation')
    return value['sha256']


def envelope(bundle, contract):
    """Bind actual packaged fixtures, source, nonce, transport and hash cleanup.

    Required records are explicit retained artifacts, not path guesses. In
    particular an old diagnostic plus a new JSON protocol field cannot pass
    the compiled-fixture and AA-command checks.
    """
    required = {'plan', 'raw', 'provider', 'build', 'run', 'cleanup', 'aaLog'}
    require(required <= bundle.keys(), 'Incomplete fresh execution bundle')
    plan, raw, provider, build, run, cleanup = (read(bundle[key]) for key in
        ('plan', 'raw', 'provider', 'build', 'run', 'cleanup'))
    require(plan.get('protocol') == PROTOCOL and plan.get('taskId') == TASK, 'No reviewed fresh plan')
    spec = spec_for(contract, plan['caseId'])
    require(read(plan['contract']) == contract and plan['canonicalCase'] == spec,
            'Fresh producer contract/given/event/obligations changed')
    evaluator = identity(plan['evaluator'])
    require(raw.get('taskId') == TASK and raw.get('role') == 'agent' and
            raw.get('caseId') == spec['caseId'] and raw.get('traceDigest') == spec['traceDigest'],
            'Raw is not its own source-parameterized canonical case')
    native = [item['nativePageTransition'] for item in raw.get('evidence', []) if 'nativePageTransition' in item]
    require(len(native) == 1, 'Missing/ambiguous native raw')
    native = native[0]
    require(native.get('protocol') == PROTOCOL and native.get('taskId') == TASK and
            native.get('caseId') == spec['caseId'] and native.get('traceDigest') == spec['traceDigest'],
            'Historical diagnostic or projected case is not fresh evidence')
    require(native.get('failure') is None and native.get('entryExecuted') is True and
            native.get('outcome') in ('transition_observed', 'blocked_required_physical_action'),
            'Runtime/transport/setup error remains NOT_SCORED')
    require(build.get('runtimeCompile', {}).get('passed') is True and
            all(build.get(key) is True for key in
                ('productionUnchanged', 'copiedProductionUnchanged', 'temporaryProjectRemoved')),
            'Packaging/source/environment failure cannot be semantic fail')
    require(build.get('compile', {}).get('passed') is None,
            'Runtime packaging must not be mislabeled application compile')
    inputs = read(plan['inputInventory'])
    require(inputs['source'] == plan['source'] == run.get('source') == build.get('source'),
            'Executed candidate/source inventory differs')
    _input_closure(inputs, build)
    require(native.get('productionSources') == build['nativeUIObserver']['sources'] and
            build['nativeUIObserver'].get('production') == build['production'] and
            run.get('sourceHashes') == build['production'], 'Actual productionSources differ')
    production = {item['path']: item['sha256'] for item in build['production']}
    registered = raw.get('productionSources', [])
    require(registered and len({item['path'] for item in registered}) == len(registered) and
            any(item['path'] == 'entry/src/main/ets/pages/Index.ets' for item in registered) and
            all(production.get(item['path']) == item['sha256'] for item in registered),
            'Native row has no actual source-bound original page execution')
    observed_calls = [item.get('observation', {}) for item in raw.get('calls', [])
                      if item.get('method') == 'Task15.originalPageTransition' and item.get('nativeUI') is True]
    require(len(observed_calls) == 1 and observed_calls[0].get('caseId') == spec['caseId'] and
            observed_calls[0].get('traceDigest') == spec['traceDigest'] and
            observed_calls[0].get('sessionId') == native['sessionId'] and
            observed_calls[0].get('frames') == native['frames'] and
            observed_calls[0].get('actions') == native['actions'] and
            observed_calls[0].get('productionSources') == native['productionSources'],
            'Original page observation recorder did not execute')
    derived = plan['derivedFiles']
    require(len({item['path'] for item in derived}) == len(derived), 'Duplicate derived fixture')
    for item in derived:
        artifacts.bound(item)
    indexed = {Path(item['path']).name: item for item in derived}
    engine = indexed.get('Task15FreshActionsV2.js')
    reviewed_engine = next((item for item in plan['evaluator']['files']
                            if Path(item['path']).name == 'Task15FreshActionsV2.js'), None)
    require(engine and reviewed_engine and engine['sha256'] == reviewed_engine['sha256'],
            'Fresh engine not bound to reviewed source')
    fixtures = build['nativeUIObserver'].get('fixtures', [])
    for name in ('Task15FreshActionsV2.js', 'Task15NativeUi.js', 'Task15NativeUiSuite.ets',
                 'Task15NativeE2E.js', 'Task15NativeUiBridge.js', 'Task15Launch.js'):
        require(name in indexed, 'Fresh fixture absent from plan')
        matches = [item for item in fixtures if Path(item['installedPath']).name == name]
        require(len(matches) == 1 and matches[0]['sha256'] == indexed[name]['sha256'] and
                Path(matches[0]['file']) == Path(indexed[name]['path']),
                'Not actually packaged fresh fixture: ' + name)
    nonce = run.get('nonce', '')
    require(re.fullmatch('[0-9a-f]{32}', nonce) is not None and native.get('nonce') == nonce and
            native.get('sessionId') == nonce + ':' + spec['caseId'] and
            native.get('integration', {}).get('nonce') == nonce and provider.get('nonce') == nonce,
            'Execution/session nonce mismatch')
    marker = run.get('resultMarker', {})
    require(marker.get('executionNonce') == nonce and marker.get('caseId') == spec['caseId'] and
            marker.get('role') == 'agent' and marker.get('taskId') == TASK and
            marker.get('bytes') == bundle['raw']['bytes'] and
            run.get('nativeResult', {}).get('sha256') == bundle['raw']['sha256'] and
            run.get('providerTranscript', {}).get('sha256') == bundle['provider']['sha256'],
            'No fresh nonce-bound device result/provider bytes')
    commands = run.get('commands', [])
    aa = [item for item in commands if item.get('log') == 'aa-test.log']
    require(len(aa) == 1 and aa[0].get('exitCode') == 0 and aa[0].get('timedOut') is False,
            'No completed fresh physical test command')
    arguments = aa[0]['args']
    for name, value in (('ltbExecutionNonce', nonce), ('task15Nonce', nonce),
                        ('task15DeadlineEpochMs', str(native['deadlineEpochMs']))):
        require(sum(arguments[pos:pos + 3] == ['-s', name, value] for pos in range(len(arguments))) == 1,
                'AA command is not bound to fresh nonce/deadline')
    log = artifacts.bound(bundle['aaLog']).decode()
    require(bundle['aaLog']['sha256'] == aa[0]['logSha256'] and
            re.search(r'TestFinished-ResultCode: 0\b', log) and 'Failure: 0, Error: 0' in log,
            'Fresh transport log missing, changed or failed')
    require(not run.get('error') and run.get('deviceCertificateCleanupConfirmed') is True and
            native['integration'].get('certificate', {}).get('cleanupConfirmed') is True and
            run.get('status') == 'fresh_raw_pending_independent_admission' and
            all(run.get('cleanup', {}).get(key) is True for key in
                ('appUninstalled', 'reverseRemoved', 'serverClosed', 'privateKeysRemoved')),
            'Incomplete device/transport cleanup')
    require(cleanup == run.get('binaryCleanup') and cleanup.get('removedAfterRecordingHashes') is True and
            cleanup.get('buildDirectoryRemoved') is True and cleanup.get('certificatesRemoved') is True,
            'No actual hash-bound build/certificate cleanup')
    files = cleanup.get('files', [])
    for hap in run.get('haps', []):
        require(any(all(item.get(key) == hap.get(key) for key in ('path', 'bytes', 'sha256')) and
                    item.get('removed') is True for item in files) and not Path(hap['path']).exists(),
                'HAP retained or missing independent hash-removal inventory')
    require(len(run.get('haps', [])) >= 2 and all(item.get('removed') is True and
            not Path(item['path']).exists() for item in files), 'Incomplete binary/intermediate removal')
    deadline = native.get('deadlineEpochMs')
    require(type(deadline) is int and deadline <= plan['deadlineEpochMs'] and native['finishedAt'] <= deadline and
            120 < plan['remainingAtPreparationSeconds'] <= 3600, 'Scorer deadline changed/exhausted')
    require(datetime.fromisoformat(run['finishedAt'].replace('Z', '+00:00')).timestamp() * 1000 <= plan['deadlineEpochMs'],
            'Cleanup exceeded the same scorer deadline')
    return {'plan': plan, 'raw': raw, 'native': native, 'provider': provider, 'build': build,
            'inputs': inputs, 'spec': spec, 'evaluatorSha256': evaluator}


def _input_closure(inventory, build):
    files = inventory['files']
    require(files and [item['path'] for item in files] == sorted({item['path'] for item in files}),
            'Ambiguous full input inventory')
    digest = hashlib.sha256()
    index = {}
    for item in files:
        relative = Path(item['path'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'Escaping source input')
        data = artifacts.bound(item['snapshot'])
        require(len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'],
                'Candidate snapshot changed')
        name = item['path'].encode()
        digest.update(len(name).to_bytes(8, 'big')); digest.update(name)
        digest.update(len(data).to_bytes(8, 'big')); digest.update(data)
        index[item['path']] = item
    require(digest.hexdigest() == inventory['rootSha256'], 'Full candidate root digest differs')
    production = {item['path']: item['sha256'] for item in build['production']}
    require(len(production) == len(build['production']) and production == {
        path: item['sha256'] for path, item in index.items() if path.startswith('entry/src/main/')},
        'Packaged production closure missing/extra/changed')


def _control(frame, name):
    matches = [item for item in frame['controls'] if item['name'] == name]
    require(len(matches) == 1, 'Unknown native control inventory')
    return matches[0]


def _window(frame, native):
    view, ime = frame['windowIdentity'], frame['windowAndIme']
    require(view.get('hostVerified') is True and view.get('focused') is True and
            view.get('bundleName') == native['bundleName'] and
            view.get('stageMainWindowId') == view.get('lastWindowId') == ime['nativeWindow']['id'] and
            type(view.get('stageMainWindowId')) is int and
            ime.get('nativeWindowShowing') is True and ime['activeWindow']['focused'] is True and
            ime['activeWindow']['bundleName'] == native['bundleName'] and
            ime.get('visibilitySource') == 'native_window_keyboard_avoid_area' and
            ime.get('keyboardVisible') is False and all(
                ime['keyboardAvoidArea'][key]['width'] == ime['keyboardAvoidArea'][key]['height'] == 0
                for key in ('topRect', 'bottomRect', 'leftRect', 'rightRect')),
            'Unknown window/occlusion/IME: NOT_SCORED')


def inspect_blocked_prefix(data):
    """Pure raw review, not a public score. Only fresh case005 is eligible."""
    native, spec, provider = data['native'], data['spec'], data['provider']
    require(spec['caseId'] == CASE and native.get('protocol') == PROTOCOL and
            native.get('caseId') == CASE and native.get('traceDigest') == spec['traceDigest'] and
            native.get('outcome') == 'blocked_required_physical_action' and native.get('failure') is None and
            native.get('entryExecuted') is True and native.get('eventExecuted') is False,
            'Not a fresh, complete own-case blocked action prefix')
    require(spec['given'] == {'password': 'secret', 'eraseData': True, 'action': 'uninitialized'} and
            spec['event'] == {'name': 'deactivate_account', 'isRetry': False}, 'Unsupported physical action boundary')
    binding = closure.profile()
    closure.source_closure(data['inputs']['files'], data['build'], binding)
    login = native['integration']['login']
    logins = [item for item in provider['requests'] if item['kind'] == 'login']
    require(provider['loginCount'] == login['providerLoginCount'] == len(logins) == 1 and
            logins[0]['secure'] is True and logins[0]['responseStatus'] == 200 and
            login['expectedUserId'] == '@' + logins[0]['body']['user'] + ':task15.test',
            'Actual authenticated HTTPS login positive control missing')
    require(all(native['settings'][name].get('present') is True and
                native['settings'][name].get('visible') is True for name in ('settings', 'notifications', 'entry')),
            'Common settings/form positive control missing')
    frames, actions = native['frames'], native['actions']
    sequences = [item['sequence'] for item in frames + actions]
    require(len(set(sequences)) == len(sequences), 'Reused action/frame sequence')
    samples = [frame for frame in frames if frame['sequence'] in native['submitSamples']]
    require(len(samples) >= 2 and [frame['sequence'] for frame in samples] == native['submitSamples'] and
            native['blockedAction']['sampleSequences'] == native['submitSamples'] and
            native['blockedAction']['frameSequence'] == samples[-1]['sequence'] and
            native['blockedAction']['requiredEvent'] == spec['event'] and
            samples[-1]['at'] - native['submitReadinessStartedAt'] >= 2000,
            'No stable bounded native action readiness observation')
    first = next(frame for frame in frames if frame['label'] == 'after_password_before_ime_action')
    backs = [item for item in actions if item['kind'] == 'system_back']
    if first['windowAndIme'].get('keyboardVisible') is True:
        require(len(backs) == 1 and backs[0]['executed'] is True and
                backs[0]['observedImeBefore'] == first['windowAndIme'] and
                first['sequence'] < backs[0]['sequence'] < samples[0]['sequence'] and
                any(first['windowAndIme']['keyboardAvoidArea'][key]['height'] > 0 and
                    first['windowAndIme']['keyboardAvoidArea'][key]['width'] > 0
                    for key in ('topRect', 'bottomRect', 'leftRect', 'rightRect')),
                'No actually visible IME-conditioned physical Back')
    else:
        require(first['windowAndIme'].get('keyboardVisible') is False and not backs,
                'Unknown IME or unconditioned Back')
        _window(first, native)
    owner = binding['sourceBinding']
    receiver = None
    for frame in samples:
        require(frame['sessionId'] == native['sessionId'] and frame['at'] <= native['finishedAt'],
                'Other session/reused frame')
        _window(frame, native)
        require(frame['windowAndIme']['nativeWindow']['id'] == first['windowAndIme']['nativeWindow']['id'],
                'Back left original form/window')
        require(closure.inventory(frame['nativeTree'], login['expectedUserId']) == binding['postImeClosedInventory'],
                'Unknown/extra/renamed code or native control: NOT_SCORED')
        button = closure.unique(frame['nativeTree'], owner['actionControlId'])
        actual = _control(frame, 'submit')
        require(button['$type'] == owner['actionControlType'] and
                button['$attrs']['visibility'] == 'Visibility.Visible' and button['$attrs']['enabled'] is False and
                all(button['$attrs'].get(key) is False for key in
                    ('isLayoutDirtyMarked', 'isRenderDirtyMarked', 'hasPendingRequest')) and
                actual.get('present') is True and actual.get('visible') is True and actual.get('enabled') is False and
                actual.get('id') == owner['actionControlId'], 'Not a proven settled visible disabled native action')
        bounds, viewport = actual['bounds'], frame['windowIdentity']['bounds']
        require(json.loads('[' + button['$rect'] + ']') == [[bounds['left'], bounds['top']], [bounds['right'], bounds['bottom']]] and
                viewport['left'] <= bounds['left'] < bounds['right'] <= viewport['right'] and
                viewport['top'] <= bounds['top'] < bounds['bottom'] <= viewport['bottom'],
                'Inspector/UiTest/window geometry mismatch')
        require(closure.unique(frame['nativeTree'], owner['passwordControlId'])['$attrs']['text'] == 'secret' and
                closure.unique(frame['nativeTree'], owner['eraseControlId'])['$attrs']['isOn'] == 'true' and
                _control(frame, 'erase').get('checked') is True, 'Physical original givens incomplete')
        state = frame['presenter']
        require(state.get('available') is True and state.get('originalService') is True and
                state.get('accountSessionActive') is True and state.get('instanceCount') == 1 and
                all(state.get(key) == value for key, value in spec['given'].items()),
                'Original receiver/givens unavailable')
        current = (state['instanceId'], state['serviceId'])
        require(receiver is None or receiver == current, 'Receiver/service replaced')
        receiver = current
        require(state['binding']['presenterSourcePath'] == owner['presenterModule'] and
                state['binding']['importCompleted'] is True and
                state['binding']['importPhase'] == 'after_original_page_ready_before_fixture',
                'Not observing original production page after readiness')
        for method, arg in (('setPassword', 'secret'), ('setEraseData', True)):
            require(any(call.get('method') == method and call.get('args') == [arg] and call.get('returned') is True and
                        call.get('instanceId') == state['instanceId'] for call in state['calls']),
                    'No same original receiver physical setter')
        require(state['requestCount'] == 0 and state['serviceCalls'] == [] and
                not any(call.get('method') == 'deactivateAccount' for call in state['calls']),
                'Not blocked before canonical destructive event')
    for kind, target in (('input', 'password'), ('click', 'erase'), ('click', 'entry')):
        require(any(item['kind'] == kind and item['target'] == target and item['executed'] is True and
                    item['sessionId'] == native['sessionId'] and item['sequence'] < samples[0]['sequence']
                    for item in actions), 'Incomplete physical common prefix')
    require(not any(item.get('phase') == 'event' or item.get('target') in ('submit', 'confirm')
                    for item in actions) and provider['deactivationCount'] == 0,
            'Event/request actually executed or unbound direct intervention')
    return {'caseId': CASE, 'traceDigest': spec['traceDigest'], 'classification': 'blocked_required_physical_action',
        'canonicalObligations': copy.deepcopy({key: spec[key] for key in ('given', 'event', 'expected', 'invariants')}),
        'transitionExecuted': False, 'observed': None, 'invariantChecks': [],
        'proposedStatus': 'fail', 'scoringApplied': False, 'publicAdmissionReady': False,
        'presenterCanSubmitGetterUsedForVerdict': False}


def inspect_transition(data, *, capability=None):
    """Derive observations from this case's own production event, not case005.

    Missing evidence raises (NS). Wrong observed state after an established
    given and real event yields FAIL. Getter values are never UI verdicts.
    """
    native, spec = data['native'], data['spec']
    require(native['outcome'] == 'transition_observed' and native['eventExecuted'] is True,
            'No actual canonical physical event')
    frames = native['frames']
    after = [frame for frame in frames if frame['label'] == 'after_event']
    require(len(after) == 1, 'No unique own-case post-event frame')
    after = after[0]
    require(after['sessionId'] == native['sessionId'] and isinstance(after['nativeTree'], dict),
            'No own-session complete native tree')
    _window(after, native)
    actions = [item for item in native['actions'] if item.get('phase') == 'event']
    require(len(actions) == 1 and actions[0]['executed'] is True and
            actions[0]['sessionId'] == native['sessionId'] and actions[0]['sequence'] < after['sequence'],
            'Event is missing, injected or reused')
    action = actions[0]
    key = spec['key']
    visible = lambda frame, name: _control(frame, name).get('present') is True and _control(frame, name).get('visible') is True
    checks = []
    if key == 'capability_gates_entry':
        from . import task15_capability_probe as probe
        require(capability is not None, 'Authenticated unsupported-capability own probe required')
        negative = read(capability)
        require(negative.get('candidateRootSha256') == data['inputs']['rootSha256'] and
                negative.get('source') == data['plan']['source'], 'Capability probe belongs to another production source')
        require(action['kind'] == 'ability_start' and action['target'] == 'original_settings',
                'Settings event was not actual ability lifecycle')
        login = native['integration']['login']
        require(login['providerLoginCount'] == data['provider']['loginCount'] == 1,
                'Authenticated positive capability given missing')
        color = login['entryInspector']['$attrs'].get('foregroundColor')
        observed = {'deactivateEntryVisible': visible(after, 'entry'),
                    'entryStyle': 'destructive' if color in ('#FFB42318', '#b42318', '#ffb42318') else color}
        observation = read(negative['observation'])
        require(negative.get('productionUnchanged') is True and negative.get('ownedAppUninstalled') is True and
                negative.get('build', {}).get('runtimeCompile', {}).get('passed') is True,
                'Capability runtime/source/cleanup incomplete')
        passed = probe.validate_observation(observation, data['build']['nativeUIObserver']['binding']['entryId'])
        checks.append({'description': spec['invariants'][0], 'passed': passed, 'observed': observation})
    else:
        before = [frame for frame in frames if frame['label'] == 'before_event']
        require(len(before) == 1, 'No unique own canonical given frame')
        before = before[0]
        _window(before, native)
        prior, state = before['presenter'], after['presenter']
        require(before['sessionId'] == native['sessionId'] and before['sequence'] < action['sequence'] and
                all(prior.get(name) == value for name, value in spec['given'].items()) and
                all(item.get('available') is True and item.get('originalService') is True and
                    item.get('instanceCount') == 1 and item.get('accountSessionActive') is True
                    for item in (prior, state)) and
                (prior['instanceId'], prior['serviceId']) == (state['instanceId'], state['serviceId']),
                'Own canonical given/original receiver not established')
        require(state['calls'][:len(prior['calls'])] == prior['calls'] and
                state['serviceCalls'][:len(prior['serviceCalls'])] == prior['serviceCalls'],
                'Not the same cumulative pass-through observer')
        new_calls = state['calls'][len(prior['calls']):]
        service = [item for item in state['serviceCalls'] if item['instanceId'] == state['serviceId']]
        if key in ('first_submit_confirms', 'confirm_sends_payload', 'retry_bypasses_confirmation'):
            target = {'first_submit_confirms': 'submit', 'confirm_sends_payload': 'confirm',
                      'retry_bypasses_confirmation': 'retry'}[key]
            require(action['kind'] == 'click' and action['target'] == target and
                    action['nativeControl'].get('present') is True and
                    action['nativeControl'].get('visible') is True and action['nativeControl'].get('enabled') is True,
                    'Not an eligible real native control action')
            calls = [item for item in new_calls if item['method'] == 'deactivateAccount']
            require(len(calls) == 1 and calls[0]['instanceId'] == prior['instanceId'] and
                    calls[0]['args'] == [spec['event']['isRetry']] and calls[0]['returned'] is True,
                    'Original handler was not called by this case event')
        if key == 'first_submit_confirms':
            observed = {'action': state['action'], 'requestCount': state['requestCount'],
                        'confirmationVisible': visible(after, 'confirmation') and visible(after, 'confirm')}
            checks.append({'description': spec['invariants'][0], 'passed': not service and
                           data['provider']['deactivationCount'] == 0, 'observed': {'serviceCalls': service,
                           'httpsRequests': data['provider']['deactivationCount']}})
        elif key == 'confirm_sends_payload':
            observed = {'action': state['action'], 'effect': 'deactivate_account' if service else None,
                        'payload': {'password': service[-1]['args'][0], 'eraseData': service[-1]['args'][1]} if service else None}
            modal = native.get('modalProbe')
            routed = False
            if modal is not None:
                sampled = {frame['sequence']: frame for frame in frames}
                start, end = sampled[modal['beforeSequence']], sampled[modal['afterSequence']]
                inputs = [item for item in native['actions'] if item['kind'] == 'modal_physical_input' and
                          item.get('phase') == 'invariant' and start['sequence'] < item['sequence'] < end['sequence']]
                require(len(inputs) == 1 and inputs[0]['executed'] is True and inputs[0]['attemptedText'] == 'tampered',
                        'No actual modal pointer/input routing attempt')
                require(modal.get('inputError') is None, 'Modal input transport error is not proof of blocked interaction')
                require(isinstance(end['nativeTree'], dict), 'No full post-input native tree')
                password = closure.unique(start['nativeTree'], 'deactivation_password')
                require(inputs[0]['geometry'] == json.loads('[' + password['$rect'] + ']'),
                        'Physical modal probe targeted unrelated coordinates')
                after_password = closure.unique(end['nativeTree'], 'deactivation_password')
                require('text' in password['$attrs'] and 'text' in after_password['$attrs'],
                        'Actual native form value observation unavailable')
                routed = (visible(start, 'loading') and visible(end, 'loading') and all(
                    end['presenter'].get(name) == prior[name] for name in ('password', 'eraseData')) and
                    end['presenter']['requestCount'] == state['requestCount'] == prior['requestCount'] + 1 and
                    password['$attrs']['text'] == after_password['$attrs']['text'] == prior['password'])
            else:
                require(not visible(after, 'loading'), 'Known modal without physical routing remains unscored')
            checks.append({'description': spec['invariants'][0], 'passed': routed,
                           'observed': {'physicalModalProbe': modal, 'serviceCalls': service}})
        elif key == 'failure_preserves_form':
            require(action['kind'] == 'https_response' and action.get('deactivationNumber') == 2 and
                    action.get('status') == 503 and action['target'] == 'deactivation:2',
                    'Not this case actual failure response')
            require(any(item.get('kind') == 'deactivation' and item.get('responseStatus') == 503
                        for item in data['provider']['requests']), 'Provider did not emit actual failure')
            observed = {name: state[name] for name in ('action', 'password', 'eraseData')}
            retry = _control(after, 'retry')
            observed['retryEnabled'] = visible(after, 'retry') and retry.get('enabled') is True
            checks.append({'description': spec['invariants'][0], 'passed': state['action'] != 'success' and
                           state.get('accountSessionActive') is True,
                           'observed': {'action': state['action'], 'accountSessionActive': state.get('accountSessionActive')}})
        elif key == 'retry_bypasses_confirmation':
            observed = {'action': state['action'], 'requestCount': state['requestCount'],
                        'confirmationVisible': visible(after, 'confirmation') and visible(after, 'confirm')}
            checks.append({'description': spec['invariants'][0], 'passed': bool(service) and
                           service[-1]['args'] == [prior['password'], prior['eraseData']],
                           'observed': {'retryServiceCalls': service}})
        else:
            raise ValueError('Own host runtime required; never project native005 onto another case')
    require([item['description'] for item in checks] == spec['invariants'], 'Original invariant obligations lost')
    passed = all(observed.get(name) == value for name, value in spec['expected'].items()) and all(item['passed'] for item in checks)
    return {'caseId': spec['caseId'], 'traceDigest': spec['traceDigest'], 'observed': observed,
            'invariantChecks': checks, 'status': 'pass' if passed else 'fail'}


def verify_controls(index, contract, *, evaluator_sha):
    """Re-run public AND independent raw verification, never trust receipt booleans."""
    from scripts import run_runtime_transition_matrix as public
    from . import task14_15_arkts_formal_verify as independent
    from . import task14_15_formal_core as core
    require(set(index) == {'base', 'final', 'base_copy_agent', 'final_copy_agent'}, 'Four controls required')
    reports, roots, raw_paths, nonces, source_paths, retained_paths = {}, {}, set(), set(), set(), set()
    for pole, reference in index.items():
        report = read(reference)
        role = pole if pole in ('base', 'final') else 'agent'
        require(report.get('taskId') == TASK and report.get('platform') == 'arkts' and report.get('role') == role,
                'Wrong control identity')
        provenance = report.get('provenance', {}).get('freshPhysicalProtocol', {})
        require(provenance.get('protocol') == PROTOCOL and provenance.get('evaluatorSha256') == evaluator_sha,
                'Old/mixed evaluator controls do not calibrate fresh protocol')
        core.validate_report(report, task_id=TASK, platform='arkts',
            source=Path(report['provenance']['candidateSource']).resolve(), contract=contract, expected=None)
        retained = report['provenance']['retainedEvidence']
        source_path = Path(report['provenance']['candidateSource']).resolve()
        require(str(source_path) not in source_paths and retained['path'] not in retained_paths,
                'Control copies require independent source directories and runtime evidence roots')
        source_paths.add(str(source_path)); retained_paths.add(retained['path'])
        for item in retained['files']:
            artifacts.bound({**item, 'path': str(Path(retained['path']) / item['path'])})
        for item in report['provenance']['productionSources']:
            snapshot = report['provenance']['productionSourceSnapshots'][item['path']]
            data = artifacts.bound(snapshot)
            require(len(data) == item['bytes'] and snapshot['sha256'] == item['sha256'],
                    'Control source differs from actual compiled production')
        public.validate_report(report, contract)
        rows = report['semantic']['cases']
        expected = 'fail' if pole in ('base', 'base_copy_agent') else 'pass'
        require(len(rows) == len(contract['cases']) and all(row['status'] == expected for row in rows),
                'Four controls require 0 NOT_SCORED and exact polarity')
        bundles = provenance.get('caseBundles', {})
        native_ids = {spec['caseId'] for spec in contract['cases'] if spec['key'] in
                      ('capability_gates_entry', 'first_submit_confirms', 'confirm_sends_payload',
                       'failure_preserves_form', 'retry_bypasses_confirmation')}
        # Base absence uses the separately reviewed, actual UI common-prefix policy.
        if expected == 'pass':
            require(set(bundles) == native_ids, 'Fresh final controls must execute each own native case')
            for case_id, bundle in bundles.items():
                data = envelope(bundle, contract)
                require(data['spec']['caseId'] == case_id and data['evaluatorSha256'] == evaluator_sha and
                        data['native']['eventExecuted'] is True, 'Case005 projection or mixed producer control')
                require(bundle['raw']['path'] not in raw_paths, 'Reused native session across controls/cases')
                raw_paths.add(bundle['raw']['path'])
                require(data['native']['nonce'] not in nonces, 'Reused native execution nonce across cases/controls')
                nonces.add(data['native']['nonce'])
                actual = inspect_transition(data, capability=provenance.get('capability'))
                row = next(row for row in rows if row['caseId'] == case_id)
                for name in ('status', 'observed', 'invariantChecks'):
                    require(row.get(name) == actual[name], 'Control differs from independently derived native observations')
            host = read(provenance['host'])
            independent.bound_source(host, Path(report['provenance']['candidateSource']).resolve())
            for row in rows:
                if row['caseId'] not in native_ids:
                    raw = independent.runtime_row(host, row['caseId'])
                    production = {item['path']: item['sha256'] for item in report['provenance']['productionSources']}
                    require(raw.get('productionSources') and raw.get('calls') and len(raw.get('checkpoints', [])) >= 2 and
                            all(production.get(item['path']) == item['sha256'] for item in raw['productionSources']),
                            'Host row has no executed source-bound production event/checkpoints')
                    independent.same_runtime_row(row, raw)
        else:
            independent.verify_report(Path(reference['path']), contract=contract)
        roots[pole] = report['provenance']['candidateRootSha256']
        reports[pole] = reference
    require(roots['base'] == roots['base_copy_agent'] and roots['final'] == roots['final_copy_agent'] and
            roots['base'] != roots['final'], 'Base/final copy controls differ from source identity')
    manifest = core.load(artifacts.ROOT / 'benchmark_tasks' / TASK / 'task.json')
    require(roots['base'] == core.directory_digest(artifacts.ROOT / manifest['arkts']['basePath']) and
            roots['final'] == core.directory_digest(artifacts.ROOT / manifest['arkts']['finalPath']),
            'Calibration controls are not the approved task base/final inputs')
    return {'verified': True, 'reports': reports, 'evaluatorSha256': evaluator_sha,
            'publicRevalidated': True, 'independentRawRevalidated': True}


def admit_blocked_candidate(bundle, contract, controls):
    """No candidate verdict until the same producer's four actual controls pass."""
    data = envelope(bundle, contract)
    review = inspect_blocked_prefix(data)
    calibration = verify_controls(controls, contract, evaluator_sha=data['evaluatorSha256'])
    return {'caseId': CASE, 'traceDigest': data['spec']['traceDigest'], 'status': 'fail',
        'observed': None, 'invariantChecks': [], 'transitionExecuted': False,
        'unevaluatedExpected': copy.deepcopy(data['spec']['expected']),
        'unevaluatedInvariants': copy.deepcopy(data['spec']['invariants']),
        'entryFailureEvidence': {'policyId': POLICY_ID, 'bundle': bundle, 'controls': controls},
        'actionEligibilityReview': review, 'calibration': calibration}


def validate_entry_failure(row, report, used_observation_ids, contract=None):
    """Proposed public hook; intentionally not added to the public registry here."""
    require(contract is not None and report.get('taskId') == TASK and report.get('platform') == 'arkts' and
            report.get('role') == 'agent', 'Wrong blocked action report identity')
    evidence = row.get('entryFailureEvidence', {})
    require(evidence.get('policyId') == POLICY_ID, 'Unknown action eligibility policy')
    admitted = admit_blocked_candidate(evidence['bundle'], contract, evidence['controls'])
    for key in ('caseId', 'traceDigest', 'status', 'observed', 'invariantChecks', 'transitionExecuted',
                'unevaluatedExpected', 'unevaluatedInvariants'):
        require(row.get(key) == admitted[key], 'Invented post-state/invariant or changed blocked action row')
    token = 'task15-fresh:' + evidence['bundle']['raw']['sha256']
    require(token not in used_observation_ids, 'Reused blocked raw evidence')
    used_observation_ids.add(token)
