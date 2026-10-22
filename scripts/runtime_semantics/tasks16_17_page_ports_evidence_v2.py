"""Independent prospective owner/SDK verifier. Never changes public admission."""
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[2]


def require(value, message):
    if not value:
        raise ValueError('Page SDK evidence unavailable: ' + message)


def record(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def checked(item):
    path = Path(item['path']).resolve()
    require(any(path.is_relative_to(ROOT / name) for name in ('experiment_results', 'eval_runs')),
            'artifact outside audit roots')
    require(record(path) == item, 'artifact bytes differ')
    return json.loads(path.read_text())


def frame(raw, label):
    matches = [value for value in raw['frames'] if value['label'] == label]
    require(len(matches) == 1, 'missing/ambiguous frame ' + label)
    return matches[0]


def state(value):
    current = value['owner']['current']
    require(current and current['sdkPortMatches'], 'owner does not use external SDK port')
    return current


def ui(value, control):
    return [item for item in value['inventory'] if item.get('id') == control]


def calls(raw, kind):
    return [value for value in raw['externalSdk'] if value['kind'] == kind]


def bootstrap_facts(raw):
    """Explicit unavailable warm-up and real framework remount, never hidden owners."""
    boot=raw.get('bootstrap',{})
    require(boot.get('version')=='original-ability-first-remount.v2' and raw.get('sdkSetupOrder')==
        'original_ability_profile_ready_then_original_module_then_external_ports', 'original Ability-first setup missing')
    events=boot.get('setupEvents',[])
    require([item['name'] for item in events]==['ability_started','original_page_ready','original_module_imported',
        'unconfigured_owner_observed','external_ports_connected','original_page_remounted'], 'module/port setup order differs')
    require(all(a['sequence']<b['sequence'] for a,b in zip(events,events[1:])), 'setup events reordered')
    frames=boot.get('frames',[])
    require([item['label'] for item in frames]==['initial_unconfigured_original_page',
        'unconfigured_original_owner_unavailable','ports_bound_original_page_remounted'], 'setup checkpoints incomplete')
    initial,unavailable,mounted=frames
    require(events[0]['sequence']<initial['sequence']<events[1]['sequence']<events[2]['sequence']<
        unavailable['sequence']<events[3]['sequence']<events[4]['sequence']<events[5]['sequence']<mounted['sequence'],
        'page readiness/import/port/remount checkpoints not ordered')
    require(initial.get('owner') is None and not initial['externalSdk'] and not unavailable['externalSdk'],
        'unconfigured page already had evaluator SDK effects or guessed owner')
    for value in frames:
        window=value['windowIdentity']
        require(window.get('hostVerified') and window.get('focused') and window.get('bundleName')==raw['bundleName'] and
            value.get('inventory'), 'bootstrap original page/window not actually observed')
    warmup=unavailable['owner']['current']
    require(unavailable['owner']['ownerCount']==1 and warmup['ownerId']==boot.get('warmupOwnerId') and
        warmup['serviceAvailable'] is False and warmup['sdkPortId'] is None and warmup['sdkPortMatches'] is False and
        not warmup['disposed'] and 'SDK service unavailable' in warmup['errorMessage'], 'warm-up unavailable owner not real')
    require(any('SDK service unavailable' in item.get('text','') for item in unavailable['inventory']),
        'unconfigured service unavailable state not rendered')
    identity=raw['taskId']=='16_identity_reset'
    expected=['identity_reset_continue','identity_reset_confirm'] if identity else ['open_pinned_messages']
    actions=boot.get('actions',[])
    require([item.get('id') for item in actions[:-1]]==expected and
        all(item.get('completed') and item.get('kind')=='click' for item in actions[:-1]) and
        events[2]['sequence']<actions[0]['sequence']<unavailable['sequence'], 'warm-up genuine UI probe missing')
    remount=actions[-1]
    require(remount.get('kind')=='framework_navigation' and remount.get('route')=='pages/Index' and remount.get('completed') and
        events[4]['sequence']<remount['sequence']<events[5]['sequence'], 'real framework remount missing')
    owners=mounted['owner']['owners']
    require(mounted['owner']['ownerCount']==2 and len(owners)==2 and owners[0]['ownerId']==warmup['ownerId'] and
        owners[0]['disposed'] and owners[0]['sdkPortId'] is None and owners[0]['serviceAvailable'] is False and
        owners[1]['ownerId']==boot.get('primaryOwnerId') and owners[1]['ownerId']!=warmup['ownerId'] and
        owners[1]['sdkPortMatches'] and owners[1]['serviceAvailable'] and not owners[1]['disposed'],
        'warm-up not disposed or remounted original owner not port-bound')
    disposal=[call for call in mounted['owner']['calls'] if call['method']=='dispose' and
        call['before']['ownerId']==warmup['ownerId']]
    subscriptions=[call for call in mounted['owner']['calls'] if call['method']=='subscribe' and
        call['before']['ownerId']==boot['primaryOwnerId']]
    require(len(disposal)==1 and disposal[0].get('stack') and disposal[0]['afterReturn']['disposed'] and
        len(subscriptions)==1 and subscriptions[0].get('stack'), 'original disposal/subscription callback proof missing')
    if identity:
        require(warmup['handleState']=='uninitialized' and warmup['completionCount']==0 and
            'failure' in warmup['cleanupHistory'] and owners[0]['completionCount']==0 and owners[0]['handleId'] is None,
            'unconfigured identity owner manufactured success')
    else:
        require(warmup['listState']=='failed' and not warmup['eventIds'] and not warmup['canPinUnpin'] and
            owners[0]['eventIds']==[], 'unconfigured room owner manufactured items/permissions')
    for item in mounted['owner'].get('managerInvocations',[]):
        if item['managerId']==warmup.get('managerId'):
            require(item['scope']=='bootstrap_ui' and item['sdkPortId'] is None and item['settled'] and
                item.get('returnedHandleId') is None, 'warm-up manager used a handle/default SDK success')
    return dict(warmupOwnerId=warmup['ownerId'],warmupManagerId=warmup.get('managerId'),primaryOwnerId=boot['primaryOwnerId'])


def case003_facts(raw, before, after):
    """Native primary event; separately witnessed original-owner domain invariant."""
    require(raw.get('domainInvariant') == dict(version='same-page-owner-callback-reentry.v1',
        scope='domain_invariant', primaryEvent='native_ui_single_confirm',
        successContinuation='same_manager_public_getResetHandle'), 'case003 domain scope missing')
    pending = frame(raw, 'domain_invariant_pending_reentry')
    success = frame(raw, 'domain_invariant_handle_success')
    cached = frame(raw, 'domain_invariant_cached_success')
    require(before['sequence'] < after['sequence'] < pending['sequence'] < success['sequence'] < cached['sequence'],
            'case003 canonical/domain checkpoints mixed or reordered')
    current = state(after)
    for value in raw['frames']:
        require(all(state(value)[key] == current[key] for key in
                    ('ownerId','managerId','serviceId','sdkPortId')), 'case003 original receiver identity changed')
    confirmation = ui(before, 'identity_reset_confirm')
    require(state(before)['confirmationVisible'] is True and state(before)['handleState'] == 'uninitialized' and
            len(confirmation) == 1 and confirmation[0].get('enabled') and confirmation[0].get('clickable'),
            'case003 real confirmation given not reached')
    require(not current['confirmationVisible'] and not ui(after, 'identity_reset_confirm') and
            current['handleState'] == 'loading' and ui(after,'identity_reset_progress'),
            'case003 actual post-confirm loading/modal missing')
    actions = raw['actions']
    require([(action['kind'], action.get('id')) for action in actions] ==
            [('click','identity_reset_continue'),('click','identity_reset_confirm')] and
            actions[0]['sequence'] < before['sequence'] < actions[1]['sequence'] < after['sequence'],
            'case003 primary transition is not actual single UI confirmation')
    primary = [call for call in after['owner']['calls'] if call['method']=='confirmReset' and call['before']['ownerId']==current['ownerId']]
    callbacks = [call for call in cached['owner']['calls'] if call['method']=='confirmReset' and call['before']['ownerId']==current['ownerId']]
    require(len(primary)==1 and len(callbacks)==2 and
            [call.get('scope') for call in callbacks] == ['primary_ui','domain_invariant_loading'],
            'case003 two original callbacks with explicit scopes missing')
    for call in callbacks:
        require(call.get('stack') and call['before']['ownerId']==current['ownerId'] and
                call['before']['managerId']==current['managerId'], 'case003 detached callback receiver')
    require(callbacks[0].get('originalMethodId') and callbacks[0].get('publicMethodId') and
            all(call[key]==callbacks[0][key] for call in callbacks for key in ('originalMethodId','publicMethodId')),
            'case003 public production callback changed')
    require('startConfirmedReset' in callbacks[0]['stack'], 'case003 native primary callback provenance missing')
    primary_log=lambda value:[item for item in value['owner'].get('managerInvocations',[]) if item['managerId']==current['managerId']]
    primary_managers,held,settled,all_calls=map(primary_log,(after,pending,success,cached))
    require([len(rows) for rows in (primary_managers,held,settled,all_calls)] == [1,2,2,3],
            'case003 original manager enter/return records incomplete')
    require([call.get('scope') for call in all_calls] ==
            ['primary_ui','domain_invariant_loading','domain_invariant_cached_success'], 'case003 manager scope differs')
    require([call.get('parentInvocationId') for call in all_calls] ==
            [callbacks[0]['invocationId'], callbacks[1]['invocationId'],None], 'case003 callback did not invoke original manager')
    for call in all_calls:
        require(call.get('method')=='getResetHandle' and call.get('stack') and call.get('returnOperationId') and
                all(call[key]==current[key] for key in ('managerId','serviceId','sdkPortId')),
                'case003 original manager method/receiver/return binding missing')
    require(all_calls[0].get('originalMethodId') and all_calls[0].get('publicMethodId') and
            all(call[key]==all_calls[0][key] for call in all_calls for key in ('originalMethodId','publicMethodId')),
            'case003 original manager method changed')
    require([call['stateAtEntry'] for call in all_calls] == ['uninitialized','loading','success'] and
            all(not call['settled'] for call in held) and primary_managers[0]['settled'] is False and
            all(call['settled'] and not call.get('error') and call.get('settlementSequence') for call in all_calls),
            'case003 actual pending/settled phases missing')
    # Earlier checkpoints must be prefixes of the same original invocation log;
    # settled results cannot be fabricated retroactively into the held checkpoint.
    for rows in (primary_managers,held,settled):
        for index,call in enumerate(rows):
            require(all(call[key]==all_calls[index][key] for key in ('invocationId','managerId',
                'serviceId','sdkPortId','scope','parentInvocationId','stateAtEntry','returnOperationId',
                'pendingAtEntryId','pendingAfterReturnId','stateAfterReturn','handleAtEntryId','stack',
                'originalMethodId','publicMethodId')),
                'case003 invocation history changed')
            if call['settled']:
                require(call==all_calls[index], 'case003 settled result changed')
    require(all(call['settlementSequence']>all_calls[1]['invocationId'] for call in all_calls[:2]) and
            all_calls[2]['invocationId']>max(call['settlementSequence'] for call in all_calls[:2]),
            'case003 reentry was not pending before settlement')
    primary_starts = [call for call in after['externalSdk'] if call['kind']=='start_identity_reset']
    held_starts = [call for call in pending['externalSdk'] if call['kind']=='start_identity_reset']
    starts = calls(raw,'start_identity_reset')
    responses = calls(raw,'external_response')
    require(len(primary_starts)==1 and primary_starts[0]['delivered'] is False and held_starts and
            all(call['delivered'] is False for call in held_starts) and
            [call['sequence'] for call in responses]==[call['deliverySequence'] for call in starts] and
            [call['requestSequence'] for call in responses]==[call['sequence'] for call in starts] and
            all(call['delivered'] for call in starts), 'case003 actual SDK request/response boundary incomplete')
    require(all(call['kind'] in ('subscribe_verification','start_identity_reset','external_response')
                for call in raw['externalSdk']), 'case003 unexpected SDK effect; not a reusable-handle probe')
    require(cached['externalSdk']==raw['externalSdk'] and success['externalSdk']==cached['externalSdk'] and
            state(success)['handleState']==state(cached)['handleState']=='success' and
            ui(success,'identity_reset_password') and ui(cached,'identity_reset_password'),
            'case003 same original page did not consume delivered handle')
    first,second,third=all_calls
    reused=(len(starts)==1 and len(held_starts)==1 and
        bool(first['pendingAfterReturnId']) and first['pendingAfterReturnId']==second['pendingAtEntryId']==second['pendingAfterReturnId'] and
        bool(first.get('returnedHandleId')) and first['returnedHandleId']==second.get('returnedHandleId')==third.get('returnedHandleId')==state(cached)['handleId'] and
        first.get('returnedSdkHandleId')==second.get('returnedSdkHandleId')==third.get('returnedSdkHandleId')==state(cached)['sdkHandleId'] and
        state(cached)['sdkHandleMatches'] and state(cached)['sdkHandleOrdinal']==1 and
        third['handleAtEntryId']==state(cached)['handleId'])
    return dict(confirmationVisible=current['confirmationVisible'],handleState=current['handleState'],
                effect='start_identity_reset'), [bool(reused)]


def verify_execution_bytes(execution_root, execution, build_ref, task_id, case_id):
    execution_root = Path(execution_root).resolve()
    require(execution_root.is_relative_to(ROOT / 'experiment_results'), 'execution outside audit root')
    require(execution.get('candidateAbsentBeforeInstall') and execution.get('executionNonce') and
            execution.get('pid') and execution.get('transportCompleted') and
            execution.get('cleanup', {}).get('ownedAppUninstalled') and
            execution['buildReport']['sha256'] == build_ref['sha256'], 'execution does not bind actual fresh build')
    raw_path = execution_root/'native-result.json'
    artifact = execution['rowArtifact']
    actual = record(raw_path)
    require(all(actual[key] == artifact[key] for key in ('bytes', 'sha256')), 'native row bytes differ')
    row = json.loads(raw_path.read_text())
    require(execution['rows'] == [row] and row['caseId'] == case_id and row['taskId'] == task_id,
            'execution embeds another native row')
    marker = artifact.get('processLogMarker', {})
    require(marker.get('taskId') == task_id and marker.get('caseId') == case_id and
            marker.get('executionNonce') == execution['executionNonce'], 'original process marker differs')
    require(execution.get('commands'), 'native command receipts empty')
    for command in execution['commands']:
        log = (execution_root/command['log']).resolve()
        require(log.is_relative_to(execution_root) and record(log)['sha256'] == command['sha256'],
                'native command log changed or escapes evidence root')
    return row


def derive(case, raw):
    """Recompute clauses from owner snapshots, physical UI and boundary receipts."""
    require(not raw.get('failure') and raw.get('eventExecuted'), 'runtime did not complete')
    require(raw.get('integrationTier') == 'actual_page_controlled_external_sdk' and
            raw.get('liveMatrixSdkOrServerVerified') is False, 'wrong/unqualified integration tier')
    require(all(raw.get(key) == case[key] for key in ('caseId', 'key', 'traceDigest')), 'case identity differs')
    before, after = frame(raw, 'before_event'), frame(raw, 'after_event')
    require(before['sequence'] < after['sequence'], 'checkpoints reversed')
    require(raw.get('actions') and all(action.get('completed') for action in raw['actions']), 'physical actions incomplete')
    require(all(action['kind'] in ('click', 'double_click', 'input', 'native_back', 'framework_navigation')
                for action in raw['actions']), 'direct feature calls cannot replace UI/framework events')
    bootstrap=bootstrap_facts(raw) if raw.get('bootstrap') else None
    for value in raw['frames']:
        require(value['windowIdentity'].get('hostVerified') and value['windowIdentity'].get('focused') and
                value['windowIdentity'].get('bundleName') == raw['bundleName'], 'wrong/unfocused original page')
        require(value.get('inventory'), 'complete native component inventory missing')
        require(value['owner']['ownerCount'] == (len(value['owner']['owners'])), 'owner inventory incomplete')
        for owner in value['owner']['owners']:
            if bootstrap and owner['ownerId']==bootstrap['warmupOwnerId']:
                require(owner['disposed'] and owner['sdkPortId'] is None and owner['serviceAvailable'] is False,
                    'retired warm-up owner changed after primary mounted')
            else:
                require(owner['sdkPortMatches'], 'detached owner or wrong SDK port')
        if bootstrap:
            require(all(item['managerId'] in (bootstrap['warmupManagerId'],value['owner']['current'].get('managerId'))
                for item in value['owner'].get('managerInvocations',[])), 'unknown manager invocation hidden by bootstrap')
    current = state(after)
    key = case['key']
    require(after['owner']['ownerCount'] == (4 if key == 'cancel_cleans_up' else 1)+(1 if bootstrap else 0), 'unbound extra owner')
    subscribed = [call for call in after['owner']['calls'] if call['method'] == 'subscribe']
    require(subscribed and all(call.get('stack') for call in subscribed), 'original page subscription provenance missing')
    starts = calls(raw, 'start_identity_reset')
    invariants = []
    if key in ('continue_requests_confirmation', 'dismiss_confirmation'):
        observed = dict(confirmationVisible=current['confirmationVisible'], startResetCount=len(starts))
        invariants = [not starts]
        require(bool(ui(after, 'identity_reset_confirm')) == current['confirmationVisible'], 'confirmation not actually rendered')
    elif key == 'confirm_starts_handle':
        observed,invariants=case003_facts(raw,before,after)
    elif key == 'password_handle_routes':
        require(state(before)['handleState'] == 'loading', 'SDK-loading given not reached')
        observed = {name: current[name] for name in ('handleState', 'screen', 'password')}
        invariants = [bool(current['sdkHandleMatches'] and current['sdkHandleOrdinal'] == 1 and
                           ui(after, 'identity_reset_password'))]
    elif key == 'oidc_handle_routes_and_resets':
        require(state(before)['handleState'] == 'loading', 'SDK-loading given not reached')
        observed = dict(handleState=current['handleState'], effect='open_oidc_approval',
                        url=current['approvalUrl'], pollEffect='reset_oidc' if calls(raw, 'reset_oidc') else None)
        labels = ui(after, 'identity_reset_oidc_url')
        invariants = [bool(current['sdkHandleMatches'] and current['approvalSurface'] == 'embedded_webview' and
                           ui(after, 'identity_reset_oidc_webview') and len(labels) == 1 and
                           labels[0]['text'] == current['approvalUrl'])]
    elif key == 'handle_failure_recovers':
        from scripts.runtime_semantics.task16_case006_native_successor_v2 import derive_case006
        scoped = derive_case006(case, raw)
        observed = scoped['observed']
        invariants = [item['passed'] for item in scoped['invariantChecks']]
    elif key == 'password_submit_calls_handle':
        empty = frame(raw, 'empty_password_submit_control')
        submit = ui(empty, 'identity_reset_password_submit')
        resets = calls(raw, 'reset_password')
        require(len(resets) == 1 and not resets[0]['delivered'], 'external password operation not held')
        observed = dict(resetAction=current['resetAction'], effect='reset_password',
                        password=resets[0]['password'], progressVisible=current['progressVisible'])
        invariants = [len(submit) == 1 and submit[0]['enabled'] is False and state(empty)['password'] == '' and
                      state(empty)['handleId'] == current['handleId'] and current['sdkHandleMatches']]
        require(ui(after, 'identity_reset_progress'), 'loading is not rendered as a modal')
    elif key == 'password_failure_clears_on_edit':
        failed = state(frame(raw, 'password_failure'))
        observed = dict(resetAction=current['resetAction'], password=current['password'],
                        errorVisible=bool(current['errorMessage']),
                        retryEnabled=any(item['enabled'] for item in ui(after, 'identity_reset_password_submit')))
        invariants = [failed['resetAction'] == 'failure' and bool(failed['errorMessage']) and
                      failed['handleId'] == current['handleId'] and current['sdkHandleMatches']]
    elif key == 'success_waits_for_verification':
        waiting_frame = frame(raw, 'awaiting_verification_callback')
        waiting = state(waiting_frame)
        observed = dict(resetAction=waiting['resetAction'], progressVisibleUntilVerified=waiting['progressVisible'],
                        completionCount=current['completionCount'])
        require(ui(waiting_frame, 'identity_reset_progress'), 'waiting progress modal not rendered')
        invariants = [waiting['parentCompletionCount'] == 0 and current['parentCompletionCount'] == 1 and
                      current['parentCompleted'] and len(calls(raw, 'verification_status')) == 2]
    elif key == 'cancel_cleans_up':
        episodes = raw.get('lifecycleEpisodes', [])
        require([item['reason'] for item in episodes] == ['cancel', 'oidc_return', 'node_destroy'],
                'actual independent lifecycle episodes missing')
        require(len({item['state']['ownerId'] for item in episodes}) == 3, 'lifecycle reuses already-cleaned owner')
        require(any(action['kind'] == 'native_back' for action in raw['actions']) and
                sum(action['kind'] == 'framework_navigation' for action in raw['actions']) == 3,
                'native lifecycle events not exercised')
        last = episodes[-1]['state']
        observed = dict(effect='cancel_reset_handle', handleState=last['handleState'],
                        resetJobActive=last['resetJobActive'], completionWatcherActive=last['completionWatcherActive'])
        invariants = [all(item['reason'] in item['state']['cleanupHistory'] and
                          item['state']['handleState'] == 'uninitialized' and
                          not item['state']['resetJobActive'] and not item['state']['completionWatcherActive']
                          for item in episodes) and
                      [item['handleOrdinal'] for item in calls(raw, 'cancel_reset_handle')] == [1, 2, 3] and
                      [item['handleOrdinal'] for item in calls(raw, 'destroy_reset_handle')] == [1, 2, 3] and
                      all(item['delivered'] and item.get('cancelled') for item in calls(raw, 'reset_oidc'))]
    else:
        require(current['providerRepositoryMatches'], 'list bypasses original room provider')
        if key == 'open_loading':
            loading = frame(raw, 'held_sdk_rendered_loading')
            held = state(loading)
            opening = [call for call in loading['externalSdk'] if call['kind'] == 'open_pinned_timeline']
            require(len(opening) == 1 and not opening[0]['delivered'] and ui(loading, 'pinned_messages_loading'),
                    'SDK pending/rendered loading not actually held')
            observed = dict(screen='pinned_messages', listState=held['listState'], effects=['open_pinned_timeline'])
            invariants = [held['parentTimelineId'] == current['parentTimelineId'] and bool(ui(after, 'open_pinned_messages'))]
        elif key in ('load_failure', 'empty_success', 'filled_list'):
            if key == 'load_failure':
                observed = dict(listState=current['listState'], emptyStateVisible=bool(ui(after, 'pinned_messages_empty')),
                                errorVisible=bool(ui(after, 'pinned_messages_failed')))
                invariants = [current['listState'] == 'failed' and not observed['emptyStateVisible']]
            elif key == 'empty_success':
                observed = dict(listState=current['listState'], loadedPinnedMessagesCount=len(current['eventIds']),
                                failureVisible=bool(ui(after, 'pinned_messages_failed')))
                invariants = [current['listState'] == 'empty' and not current['errorMessage']]
            else:
                observed = dict(listState=current['listState'], visibleEventIds=current['eventIds'],
                                loadedPinnedMessagesCount=len(current['eventIds']))
                actual_rows = [item['id'][len('message_actions_'):] for item in after['inventory']
                               if item['id'].startswith('message_actions_')]
                invariants = [current['eventIds'] == calls(raw, 'sdk_timeline_items')[-1]['eventIds'] == actual_rows]
        elif key in ('unpin_permission_denied', 'unpin_permission_allowed'):
            menu = frame(raw, 'message_actions_opened')
            visible = (['view_in_timeline'] if ui(menu, 'view_in_timeline_$a') else []) + (['unpin'] if ui(menu, 'unpin_$a') else [])
            observed = dict(actionsVisible=visible)
            if key == 'unpin_permission_denied':
                observed['actionsHidden'] = [] if ui(menu, 'unpin_$a') else ['unpin']
                invariants = [not calls(raw, 'unpin_event') and current['eventIds'] == state(before)['eventIds']]
            else:
                invariants = [bool(ui(menu, 'unpin_$a')) and not ui(after, 'unpin_$a') and
                              not current['canPinUnpin'] and calls(raw, 'can_pin_unpin')[-1]['allowed'] is False]
        elif key == 'view_in_timeline':
            event_id = case['given']['eventId']
            require(current['focusedIndex'] >= 0 and current['parentEventIds'][current['focusedIndex']] == event_id and
                    ui(after, 'room_event_' + event_id) and ui(after, 'open_pinned_messages'), 'no real parent timeline focus')
            require(any(call.get('focusedEventId') == event_id for call in calls(raw, 'room_timeline')),
                    'parent did not consume focus SDK request')
            observed = dict(screen='room_timeline', focusedEventId=current['focusedEventId'], effects=['navigate_to_event'])
            invariants = [state(before)['eventIds'] == current['eventIds'] and
                          before['nativePreferences']['raw'] == after['nativePreferences']['raw']]
        elif key in ('unpin_success', 'unpin_failure_recovery'):
            unpin = calls(raw, 'unpin_event')
            require(len(unpin) == 1 and unpin[0]['eventId'] == case['event']['eventId'] and unpin[0]['completed'],
                    'wrong/missing active SDK unpin result')
            ack = frame(raw, 'after_sdk_unpin_before_item_flow')
            require(state(ack)['eventIds'] == state(before)['eventIds'], 'unpin acknowledgement filtered list optimistically')
            require(ack['nativePreferences']['raw'] == before['nativePreferences']['raw'], 'unpin acknowledgement wrote cache')
            persisted = frame(raw, 'actual_native_preferences_after_unpin')['nativePreferences']
            require(persisted['sameAbilityContext'] and [row['eventId'] for row in persisted['rows']] == current['eventIds'],
                    'native cache differs from SDK-authoritative list')
            observed = dict(visibleEventIds=current['eventIds'], errorVisible=bool(current['errorMessage']),
                            retryEnabled=current['retryEnabled'], effects=['show_error'] if unpin[0]['failed'] else
                            ['unpin_event', 'persist_pinned_state'])
            if key == 'unpin_success':
                invariants = [not unpin[0]['failed'] and unpin[0].get('returned') is True and
                              current['eventIds'] == calls(raw, 'sdk_timeline_items')[-1]['eventIds'] and
                              current['eventIds'] == [value for value in state(before)['eventIds'] if value != case['event']['eventId']]]
            else:
                invariants = [unpin[0]['failed'] and current['eventIds'] == state(before)['eventIds'] and
                              bool(ui(after, 'unpin_error')) and any(item['enabled'] for item in ui(after, 'unpin_$a'))]
        else:
            raise ValueError('Page SDK evidence unavailable: unknown transition')
    require(raw.get('observed') == observed, 'declared observations differ from independently derived facts')
    require(len(invariants) == len(case['invariants']) and
            [item['description'] for item in raw['invariantChecks']] == case['invariants'], 'invariant binding incomplete')
    require([item['passed'] for item in raw['invariantChecks']] == invariants, 'invariant claims differ from facts')
    return dict(observed=observed, invariantChecks=[dict(description=description, passed=bool(value))
                for description, value in zip(case['invariants'], invariants)])


def verify_probe(root, case, reviewed_inputs):
    """Explicit reviewed full-input manifest required; a self-signed marker is insufficient."""
    root = Path(root).resolve()
    require(root.is_relative_to(ROOT / 'experiment_results'), 'report outside audit root')
    receipt = json.loads((root / 'receipt.json').read_text())
    require(receipt.get('taskId') in ('16_identity_reset', '17_pinned_messages'), 'wrong task')
    canonical = ROOT / 'benchmark_tasks' / receipt['taskId'] / 'transitions.json'
    require(receipt['canonicalContract'] == record(canonical) and
            case in json.loads(canonical.read_text())['cases'], 'canonical assertions changed or not bound')
    require(receipt.get('candidateRemoved') and not receipt.get('error') and receipt.get('transportCompleted') and
            receipt.get('ownedAppUninstalled'), 'incomplete native execution/cleanup')
    require(reviewed_inputs and len({item['path'] for item in reviewed_inputs}) == len(reviewed_inputs),
            'explicit complete reviewed inputs required')
    before, after = checked(receipt['before']), checked(receipt['after'])
    require(before['phase'] == 'before_runtime' and after['phase'] == 'after_runtime' and
            before['files'] == after['files'] == reviewed_inputs, 'source closure not bound to reviewed inputs')
    from scripts.runtime_semantics import tasks16_17_arkts_entry_binding_v2 as guard
    require(before['producer'] == after['producer'] == record(guard.__file__), 'unreviewed input-capture producer')
    binding = checked(receipt['inputBinding'])
    require(binding['before'] == receipt['before'] and binding['after'] == receipt['after'], 'wrong actual build input seal')
    build = checked(binding['build'])
    require(Path(before['candidateSource']).resolve() == Path(after['candidateSource']).resolve() ==
            Path(build['source']).resolve(), 'wrong candidate source')
    production = [dict(path=item['path'], sha256=item['sha256']) for item in reviewed_inputs
                  if item['path'].startswith('entry/src/main/')]
    order = lambda items: sorted(items, key=lambda item: item['path'])
    require(order(production) == order(build['production']) == order(build['nativeUIObserver']['production']),
            'packaged production differs from complete reviewed inputs')
    encoded = json.dumps(build, sort_keys=True, separators=(',', ':')).encode()
    require(binding['buildRecordHash'] == hashlib.sha256(encoded).hexdigest(), 'actual build seal differs')
    require(build['productionUnchanged'] and build['copiedProductionUnchanged'] and build['temporaryProjectRemoved'] and
            build['runtimeCompile']['passed'], 'production packaging incomplete')
    require(build['nativeUIObserver']['fixtures'], 'empty evaluator closure')
    from scripts.runtime_semantics import task16_case006_native_successor_v2 as successor
    wrapper = ROOT/'scripts/runtime_semantics/tasks16_17_arkts_page_ports_build_v2.cjs'
    require(build.get('prospectivePagePorts', {}).get('wrapper') == record(wrapper), 'actual reviewed v2 packaging producer missing')
    derivation = build['nativeUIObserver'].get('case006Derivation', {})
    installer = ROOT/'state_tests/runtime/arkts/native/Tasks16_17PagePortsV2.install.cjs'
    expected_code = successor.compose_ui_text().encode()
    require(derivation == dict(version='case006.actual-canonical-manager.v2',
        originalUi=record(successor.UI), scopeModule=record(successor.SCOPE), installer=record(installer),
        installedUiSha256=hashlib.sha256(expected_code).hexdigest(),
        allWarmupLogsRetained=True, productionLogicChanged=False), 'unknown/missing actual case006 derivation')
    installed_ui = [item for item in build.get('generatedEvaluator', []) if item['path']=='entry/src/test/Tasks16_17PagePortsUi.js']
    require(len(installed_ui)==1 and installed_ui[0]['sha256']==derivation['installedUiSha256'],
            'actual installed evaluator bytes differ from reviewed test-only derivation')
    ui_fixtures = [item for item in build['nativeUIObserver']['fixtures'] if Path(item['file']).name=='Tasks16_17PagePortsUi.js']
    require(len(ui_fixtures)==1 and ui_fixtures[0]['sha256']==derivation['installedUiSha256'] and
        ui_fixtures[0]['sourceSha256']==record(successor.UI)['sha256'], 'derived fixture source/installed hash differs')
    required_successors = {Path(successor.__file__).resolve(), successor.SCOPE.resolve(), installer.resolve(),
        ROOT/'scripts/runtime_semantics/tasks16_17_arkts_page_ports_build_v2.cjs'}
    successor_snapshots = receipt.get('successorSources', [])
    require({Path(item['current']['path']).resolve() for item in successor_snapshots}==required_successors,
        'complete retained successor evaluator sources missing')
    for item in successor_snapshots:
        snapshot = Path(item['snapshot']['path']).resolve()
        require(record(item['current']['path'])==item['current'] and snapshot.is_relative_to(root/'successor-sources') and
            record(snapshot)==item['snapshot'] and item['snapshot']['sha256']==item['current']['sha256'],
            'successor evaluator bytes changed')
    expected_evaluators = {
        'Tasks16_17SdkBoundary.js', 'Tasks16_17PhysicalPrefix.js', 'Task16Case003DomainInvariant.js', 'Tasks16_17PagePortsUi.js', 'Tasks16_17PagePortsUi.d.ts',
        'Tasks16_17PagePortsBridge.js', 'Tasks16_17PagePortsBridge.d.ts', 'Tasks16_17PagePortsSuite.ets',
        'Task17LoadingLaunch.js', 'Task17LoadingLaunchNative.js', 'Task17LoadingLaunchNative.d.ts',
        'Tasks16_17PagePorts.adapter.cjs'}
    require({Path(fixture['file']).name for fixture in build['nativeUIObserver']['fixtures']} == expected_evaluators,
            'unreviewed or incomplete evaluator set')
    snapshots = receipt.get('evaluatorSources')
    require(snapshots and len(snapshots) == len(expected_evaluators), 'nonempty retained evaluator snapshots required')
    require({Path(item['current']['path']).name for item in snapshots} == expected_evaluators, 'wrong retained evaluator set')
    for item in snapshots:
        current = Path(item['current']['path']).resolve()
        require(current == ROOT / 'state_tests/runtime/arkts/native' / current.name and
                record(current) == item['current'], 'snapshot does not bind current reviewed evaluator')
        snapshot = Path(item['snapshot']['path']).resolve()
        require(snapshot.is_relative_to(root/'evaluator-sources') and record(snapshot) == item['snapshot'] and
                item['snapshot']['sha256'] == item['current']['sha256'], 'evaluator bytes not independently retained')
    for fixture in build['nativeUIObserver']['fixtures']:
        path = Path(fixture['file']).resolve()
        require(path.is_relative_to(ROOT / 'state_tests/runtime/arkts/native') and
                record(path)['sha256'] == fixture.get('sourceSha256', fixture['sha256']),
                'evaluator differs from current reviewed fixture')
    archive = receipt['inputArchive']
    require(record(archive['path']) == archive, 'input archive changed')
    with tarfile.open(archive['path'], 'r:gz') as tar:
        members = [item for item in tar.getmembers() if item.isfile()]
        require(sorted(member.name for member in members) == sorted(item['path'] for item in reviewed_inputs),
                'input archive missing/extra files')
        for item in reviewed_inputs:
            data = tar.extractfile(item['path']).read()
            require(len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'], 'source archive differs')
    execution = checked(receipt['execution'])
    row = verify_execution_bytes(Path(receipt['execution']['path']).parent, execution, binding['build'],
                                 receipt['taskId'], case['caseId'])
    manifest = json.loads((root/'evidence-manifest.json').read_text())
    require(manifest.get('files'), 'final retained evidence manifest empty')
    listed = set()
    for item in manifest['files']:
        path = (root/item['relativePath']).resolve()
        require(path.is_relative_to(root) and record(path) == {key: item[key] for key in ('path', 'bytes', 'sha256')},
                'retained evidence manifest mismatch')
        listed.add(path)
    require(all(Path(item['snapshot']['path']).resolve() in listed for item in successor_snapshots), 'successor snapshots omitted from final manifest')
    require(all(Path(item['snapshot']['path']).resolve() in listed for item in snapshots) and
            all(Path(receipt[key]['path']).resolve() in listed for key in ('before', 'after', 'inputBinding', 'execution')),
            'captures/seal/evaluator snapshots omitted from manifest')
    matches = [item['nativePagePorts'] for item in row.get('evidence', []) if 'nativePagePorts' in item]
    require(len(matches) == 1, 'actual page/SDK raw missing')
    if matches[0].get('integrationTier') == 'actual_page_physical_prefix':
        from scripts.runtime_semantics import tasks16_17_arkts_entry_binding_v3 as prefix
        validators = receipt.get('validationSources', [])
        require({Path(item['current']['path']).resolve() for item in validators} ==
                {Path(prefix.__file__).resolve(), prefix.REFERENCE.resolve(), Path(__file__).resolve()},
                'nonempty current reviewed v3 validator/reference snapshots required')
        for item in validators:
            snapshot = Path(item['snapshot']['path']).resolve()
            require(record(item['current']['path']) == item['current'] and
                    snapshot.is_relative_to(root/'validation-sources') and snapshot in listed and
                    record(snapshot) == item['snapshot'] and item['current']['sha256'] == item['snapshot']['sha256'],
                    'v3 validator/reference does not bind current reviewed bytes')
        eligibility = prefix.assess(build, receipt['taskId'], receipt['inputBinding'])
        facts = prefix.physical_facts(case, matches[0])
        require(matches[0]['productionSources'] == build['nativeUIObserver']['production'], 'physical source binding differs')
        return dict(status='fail', semanticFailureKind='feature_missing_at_real_common_entry', **facts,
                    eligibility=eligibility, publicAdmissionChanged=False,
                    integrationTier='actual_page_physical_prefix', liveMatrixSdkOrServerVerified=False)
    require(matches[0].get('bootstrap'), 'Ability-first setup proof required for new positive episode')
    facts = derive(case, matches[0])
    passed = (all(facts['observed'].get(key) == value for key, value in case['expected'].items()) and
              all(item['passed'] for item in facts['invariantChecks']))
    return dict(status='pass' if passed else 'fail', **facts, publicAdmissionChanged=False,
                integrationTier='actual_page_controlled_external_sdk', liveMatrixSdkOrServerVerified=False)
