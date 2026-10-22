"""Versioned exact native observation projection; canonical assertions unchanged."""
import json
from .task15_fresh_admission_v2 import require, read, _window, _control, closure


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
        require(state['calls'][:len(prior['calls'])] == prior['calls'],
                'Not the same cumulative production handler observer')
        prefix = state['serviceCalls'][:len(prior['serviceCalls'])]
        require(len(prefix) == len(prior['serviceCalls']), 'Original service call disappeared')
        for before_call, after_call in zip(prior['serviceCalls'], prefix):
            # An actual HTTP failure settles the SAME async service call. Only
            # settlement metadata may advance; call identity/args never change.
            require({k: v for k, v in before_call.items() if k != 'settlement'} ==
                    {k: v for k, v in after_call.items() if k != 'settlement'},
                    'Original service call identity/payload changed')
            if before_call.get('settlement') != after_call.get('settlement'):
                require(key == 'failure_preserves_form' and 'settlement' not in before_call and
                        after_call.get('settlement', {}).get('status') == 'rejected' and
                        action.get('kind') == 'https_response' and action.get('status') == 503,
                        'Unbound async settlement metadata change')
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
