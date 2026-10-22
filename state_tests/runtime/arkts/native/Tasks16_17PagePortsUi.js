import { createIdentitySdkControl, createPinnedSdkControl, observePageOwner } from './Tasks16_17SdkBoundary';
import { runPhysicalPrefix } from './Tasks16_17PhysicalPrefix';
import { createCase003Bindings } from './Task16Case003DomainInvariant';

let binding;
export function configurePagePortsBinding(json, importModule = url => import(url)) {
  binding = { config: JSON.parse(json), importModule };
}

export async function runPagePortsUi(caseJson, bundleName, driver, ON, launch, preferences) {
  const spec = JSON.parse(caseJson), config = binding.config;
  if (bundleName !== config.bundleName || spec.taskId !== config.taskId) throw new Error('Page/SDK identity mismatch');
  const identityTask = spec.taskId === '16_identity_reset';
  const control = identityTask ? createIdentitySdkControl() : createPinnedSdkControl();
  const reentry = identityTask && spec.key === 'confirm_starts_handle' ? createCase003Bindings() : undefined;
  const raw = { schemaVersion: 1, taskId: spec.taskId, caseId: spec.caseId, key: spec.key,
    traceDigest: spec.traceDigest, bundleName, integrationTier: 'actual_page_controlled_external_sdk',
    liveMatrixSdkOrServerVerified: false, frames: [], actions: [], invariantChecks: [],
    productionSources: config.productionSources, eventExecuted: false };
  let observer, sequence = 0, expectedOwnerCount = 1, probeScope = 'bootstrap_ui';
  raw.bootstrap = { version: 'original-ability-first-remount.v2', frames: [], actions: [], setupEvents: [] };
  const setup = name => raw.bootstrap.setupEvents.push({ name, sequence: ++sequence });
  const require = (condition, message) => { if (!condition) throw new Error(message); };
  const sdkCalls = kind => control.calls.filter(call => call.kind === kind);
  const owner = () => {
    const state = observer.read();
    require(state.ownerCount === expectedOwnerCount && state.current?.sdkPortMatches, 'Actual page episode owner/SDK chain not bound');
    return state.current;
  };
  const find = async id => {
    const nodes = await driver.findComponents(ON.id(id).inWindow(bundleName)) || [];
    require(nodes.length <= 1, 'Ambiguous UI control: ' + id);
    return nodes[0];
  };
  const inspect = async id => {
    const node = await find(id);
    return node ? { id, present: true, text: await node.getText(), enabled: await node.isEnabled(),
      bounds: await node.getBounds() } : { id, present: false };
  };
  const wait = async (description, predicate) => {
    const start = Date.now();
    while (Date.now() - start < 8000) {
      if (await predicate()) return;
      await driver.delayMs(80);
    }
    throw new Error('Runtime precondition unavailable: ' + description);
  };
  const capture = async (label, bootstrap = false) => {
    const windowIdentity = await launch.check(driver), inventory = [];
    for (const node of await driver.findComponents(ON.inWindow(bundleName)) || []) {
      inventory.push({ id: await node.getId(), text: await node.getText(), type: await node.getType(),
        enabled: await node.isEnabled(), clickable: await node.isClickable(), bounds: await node.getBounds() });
    }
    const frame = { label, sequence: ++sequence, windowIdentity, inventory, owner: observer ? observer.read() : null,
      externalSdk: JSON.parse(JSON.stringify(control.calls)) };
    if (!identityTask) {
      const context = launch.current().abilityContext;
      const store = await preferences.getPreferences(context, 'element_x_pinned_messages');
      const value = await store.get('room_design_pinned_events', '');
      frame.nativePreferences = { store: 'element_x_pinned_messages', key: 'room_design_pinned_events',
        sameAbilityContext: context === launch.current().abilityContext, raw: value,
        rows: value ? JSON.parse(value) : [] };
    }
    (bootstrap ? raw.bootstrap.frames : raw.frames).push(frame);
    return frame;
  };
  const click = async (id, double = false, bootstrap = false) => {
    const node = await find(id);
    require(node && await node.isEnabled(), 'Missing/disabled physical control: ' + id);
    const action = { sequence: ++sequence, kind: double ? 'double_click' : 'click', id, completed: false };
    (bootstrap ? raw.bootstrap.actions : raw.actions).push(action);
    if (double) await node.doubleClick();
    else await node.click();
    action.completed = true;
    await driver.delayMs(80);
  };
  const input = async value => {
    const node = await find('identity_reset_password');
    require(node && await node.isEnabled(), 'Password input unavailable');
    await node.inputText(value);
    raw.actions.push({ sequence: ++sequence, kind: 'input', id: 'identity_reset_password', completed: true });
    await wait('physical password input delivered', () => owner().password === value);
  };
  const invariant = (index, passed, evidence) => {
    require(typeof spec.invariants[index] === 'string', 'Unbound invariant');
    raw.invariantChecks.push({ description: spec.invariants[index], passed: Boolean(passed), evidence });
  };
  const confirm = async (double = false) => {
    await click('identity_reset_continue');
    await wait('destructive confirmation', async () => (await inspect('identity_reset_confirm')).present);
    await click('identity_reset_confirm', double);
    await wait('actual SDK request', () => sdkCalls('start_identity_reset').length > 0);
  };
  const passwordRoute = async () => {
    await confirm();
    control.deliverHandle(0, 'password');
    await wait('password page', async () => (await inspect('identity_reset_password')).present);
  };
  const openPinned = async (ids = ['$a', '$b']) => {
    await click('open_pinned_messages');
    await wait('actual open request', () => sdkCalls('open_pinned_timeline').length > 0);
    await capture('loading_before_external_response');
    control.openResult();
    await wait('production SDK items subscriber', () => control.read().itemSubscriberCount === 1);
    control.emitItems(ids);
    await wait('real filled/empty page state', () => ['filled', 'empty'].includes(owner().listState));
  };
  const openActions = async id => {
    await click('message_actions_' + id);
    await wait('actual message action surface', async () => (await inspect('view_in_timeline_' + id)).present);
  };
  try {
    // API23 cannot resolve an original entry module until its Ability loaded
    // the real HAP. This first page remains genuinely unconfigured/unavailable.
    await launch.start(); setup('ability_started');
    await wait('original Ability page ready before any module import', async () => {
      try {
        await launch.check(driver);
        const titles = identityTask ? ['Chat backup', 'Reset cryptographic identity'] : ['Design team'];
        for (const title of titles) {
          if ((await driver.findComponents(ON.text(title).inWindow(bundleName)) || []).length === 1) return true;
        }
        return false;
      } catch (_) { return false; }
    });
    await capture('initial_unconfigured_original_page', true); setup('original_page_ready');
    let types;
    try { types = await binding.importModule(config.productionModuleUrl); }
    catch (error) {
      // Missing module remains diagnostic; reuse this same real launch once.
      const prefix = await runPhysicalPrefix(spec, bundleName, driver, ON, launch, { alreadyStarted: true });
      prefix.moduleDiagnostic = String(error);
      prefix.productionSources = config.productionSources;
      prefix.launchEvidence = launch.read();
      prefix.bootstrap = raw.bootstrap;
      return JSON.stringify(prefix);
    }
    setup('original_module_imported');
    observer = observePageOwner(types, spec.taskId, control.port, control.handles,
      { ...(reentry ? { capture: reentry.capture } : {}), scope: () => reentry ? reentry.scope() : probeScope });
    if (reentry) reentry.scope('bootstrap_ui');
    if (identityTask) {
      // This is a separate setup episode, not the primary testcase transition.
      await click('identity_reset_continue', false, true);
      require(observer.read().ownerCount === 1 && observer.read().current.serviceAvailable === false,
        'Initial original owner unexpectedly has an unbound SDK service');
      await click('identity_reset_confirm', false, true);
      await wait('real unconfigured SDK failure', () => observer.read().current.errorMessage.includes('SDK service unavailable'));
    } else {
      await click('open_pinned_messages', false, true);
      await wait('real unconfigured pinned timeline failure', () => observer.read().ownerCount === 1 &&
        observer.read().current.serviceAvailable === false && observer.read().current.listState === 'failed');
    }
    require(control.calls.length === 0 && observer.read().current.sdkPortId === null,
      'Unconfigured original page used external SDK or default success');
    const unavailable = await capture('unconfigured_original_owner_unavailable', true);
    raw.bootstrap.warmupOwnerId = unavailable.owner.current.ownerId;
    setup('unconfigured_owner_observed');
    if (identityTask) {
      const services = await binding.importModule(config.serviceModuleUrl);
      services.IdentityResetSession.configure(control.port);
    } else {
      control.prepareRoom(['$b', '$a']);
      control.permission(spec.given.canPinUnpin !== false);
      types.PinnedMessagesSession.configureRoom(control.port);
    }
    setup('external_ports_connected');
    raw.sdkSetupOrder = 'original_ability_profile_ready_then_original_module_then_external_ports';
    await driver.delayMs(100);
    // Only real framework navigation constructs the next ORIGINAL page. Keep
    // warm-up owner/disposal records; never assign its service or hide it.
    const remount = { sequence: ++sequence, kind: 'framework_navigation', route: 'pages/Index', completed: false };
    raw.bootstrap.actions.push(remount);
    expectedOwnerCount = 2;
    await launch.current().uiContext.getRouter().replaceUrl({ url: 'pages/Index' });
    await wait('actual remounted page owner/subscription and warm-up disposal', () => {
      const value = observer.read(), warmup = value.owners.find(item => item.ownerId === raw.bootstrap.warmupOwnerId);
      return value.ownerCount === 2 && value.current.sdkPortMatches && warmup?.disposed;
    });
    remount.completed = true; setup('original_page_remounted');
    raw.bootstrap.primaryOwnerId = observer.read().current.ownerId;
    await capture('ports_bound_original_page_remounted', true);
    probeScope = 'runtime'; if (reentry) reentry.scope('runtime');
    await launch.check(driver);
    await capture('original_page_ready');
    if (identityTask) {
      switch (spec.key) {
        case 'continue_requests_confirmation': {
          await capture('before_event'); await click('identity_reset_continue');
          await wait('confirmation visible', () => owner().confirmationVisible);
          raw.observed = { confirmationVisible: owner().confirmationVisible, startResetCount: sdkCalls('start_identity_reset').length };
          invariant(0, raw.observed.confirmationVisible && raw.observed.startResetCount === 0, raw.observed);
          break;
        }
        case 'dismiss_confirmation': {
          await click('identity_reset_continue'); await capture('before_event'); await click('identity_reset_cancel_confirmation');
          raw.observed = { confirmationVisible: owner().confirmationVisible, startResetCount: sdkCalls('start_identity_reset').length };
          invariant(0, sdkCalls('start_identity_reset').length === 0, control.calls);
          break;
        }
        case 'confirm_starts_handle': {
          await click('identity_reset_continue');
          await wait('actual confirmation given', async () => owner().confirmationVisible &&
            (await inspect('identity_reset_confirm')).enabled);
          await capture('before_event');
          reentry.scope('primary_ui');
          try { await click('identity_reset_confirm'); } finally { reentry.scope('runtime'); }
          await wait('held external request', () => sdkCalls('start_identity_reset').length === 1);
          const state = owner();
          raw.observed = { confirmationVisible: state.confirmationVisible, handleState: state.handleState,
            effect: sdkCalls('start_identity_reset').length ? 'start_identity_reset' : null };
          await capture('after_event');
          const bound = reentry.productionBindings();
          raw.domainInvariant = { version: 'same-page-owner-callback-reentry.v1', scope: 'domain_invariant',
            primaryEvent: 'native_ui_single_confirm', successContinuation: 'same_manager_public_getResetHandle' };
          reentry.scope('domain_invariant_loading');
          let repeated;
          try { repeated = bound.presenterMethod.call(bound.presenterReceiver); }
          finally { reentry.scope('runtime'); }
          await capture('domain_invariant_pending_reentry');
          // Deliver only at the external SDK boundary. If a faulty manager made
          // extra requests, settle each and retain the duplication as a failure.
          for (let index = 0; index < control.requests.length; index++) control.deliverHandle(index, 'password');
          await repeated;
          await wait('both original manager operations settled', () => observer.read().managerInvocations.length >= 2 &&
            observer.read().managerInvocations.filter(call => call.managerId === state.managerId).length === 2 &&
            observer.read().managerInvocations.filter(call => call.managerId === state.managerId).every(call => call.settled));
          await capture('domain_invariant_handle_success');
          reentry.scope('domain_invariant_cached_success');
          try { await bound.managerMethod.call(bound.managerReceiver); }
          finally { reentry.scope('runtime'); }
          const cached = await capture('domain_invariant_cached_success');
          const invocations = cached.owner.managerInvocations.filter(call => call.managerId === state.managerId);
          const [first, second, third] = invocations;
          invariant(0, invocations.length === 3 && sdkCalls('start_identity_reset').length === 1 &&
            first.managerId === state.managerId && second.managerId === state.managerId && third.managerId === state.managerId &&
            Boolean(first.pendingAfterReturnId) && first.pendingAfterReturnId === second.pendingAtEntryId &&
            first.pendingAfterReturnId === second.pendingAfterReturnId &&
            Boolean(first.returnedHandleId) && first.returnedHandleId === second.returnedHandleId &&
            first.returnedHandleId === third.returnedHandleId && third.returnedHandleId === cached.owner.current.handleId &&
            first.returnedSdkHandleId === second.returnedSdkHandleId &&
            first.returnedSdkHandleId === third.returnedSdkHandleId &&
            third.returnedSdkHandleId === cached.owner.current.sdkHandleId && cached.owner.current.sdkHandleMatches &&
            cached.owner.current.sdkHandleOrdinal === 1 && third.handleAtEntryId === cached.owner.current.handleId,
            { scope: 'domain_invariant', managerInvocations: invocations });
          break;
        }
        case 'password_handle_routes': {
          await confirm(); await capture('before_event'); control.deliverHandle(0, 'password');
          await wait('same handle routed', async () => (await inspect('identity_reset_password')).present);
          const state = owner(); raw.observed = { handleState: state.handleState, screen: state.screen, password: state.password };
          invariant(0, Boolean(state.handleId && state.sdkHandleId && state.sdkHandleMatches), state);
          break;
        }
        case 'oidc_handle_routes_and_resets': {
          await confirm(); await capture('before_event'); control.deliverHandle(0, 'oidc');
          await wait('actual WebView and SDK poll', async () => (await inspect('identity_reset_oidc_webview')).present && sdkCalls('reset_oidc').length === 1);
          const state = owner(); raw.observed = { handleState: state.handleState, effect: 'open_oidc_approval',
            url: state.approvalUrl, pollEffect: sdkCalls('reset_oidc').length ? 'reset_oidc' : null };
          invariant(0, state.approvalSurface === 'embedded_webview' && (await inspect('identity_reset_oidc_webview')).present,
            { state, external: control.calls });
          break;
        }
        case 'handle_failure_recovers': {
          await confirm(); await capture('before_event'); control.deliverHandle(0, undefined);
          await wait('stable cleanup', async () => owner().handleState === 'uninitialized' && (await inspect('identity_reset_retry')).present);
          const stable = owner(); await capture('after_failure_cleanup');
          await click('identity_reset_retry'); await click('identity_reset_confirm');
          await wait('second pending acquisition', () => sdkCalls('start_identity_reset').length === 2);
          const transitions = observer.read().managerTransitions;
          const stateSequence = [transitions[0]?.from, ...transitions.map(value => value.to)];
          raw.observed = { failureObserved: stateSequence.includes('failure'), stateSequence,
            stableHandleState: stable.handleState, screen: stable.screen, progressVisible: stable.progressVisible,
            retryEnabled: (await inspect('identity_reset_exit')).enabled, retryHandleState: owner().handleState };
          invariant(0, stateSequence.includes('failure') && !stateSequence.includes('success'), transitions);
          invariant(1, stable.handleState === 'uninitialized' && stable.cleanupHistory.includes('failure') && !stable.progressVisible, stable);
          invariant(2, owner().handleState === 'loading' && sdkCalls('start_identity_reset').length === 2, control.calls);
          break;
        }
        case 'password_submit_calls_handle': {
          await passwordRoute(); const handle = owner().handleId, empty = await inspect('identity_reset_password_submit');
          await capture('empty_password_submit_control');
          await input(spec.given.password); await capture('before_event'); await click('identity_reset_password_submit');
          await wait('external password operation', () => sdkCalls('reset_password').length === 1);
          const state = owner(); raw.observed = { resetAction: state.resetAction, effect: 'reset_password',
            password: sdkCalls('reset_password')[0]?.password, progressVisible: state.progressVisible };
          invariant(0, empty.enabled === false && owner().handleId === handle, { empty, handle, after: state });
          break;
        }
        case 'password_failure_clears_on_edit': {
          await passwordRoute(); const handle = owner().handleId;
          await input(spec.given.password); await click('identity_reset_password_submit'); await capture('before_event');
          control.passwordResult(0, true);
          await wait('rendered password failure', () => owner().resetAction === 'failure' && owner().errorMessage.length > 0);
          await capture('password_failure'); await input(spec.event.value);
          const state = owner(); raw.observed = { resetAction: state.resetAction, password: state.password,
            errorVisible: state.errorMessage.length > 0, retryEnabled: (await inspect('identity_reset_password_submit')).enabled };
          invariant(0, state.handleId === handle && Boolean(state.sdkHandleId), state);
          break;
        }
        case 'success_waits_for_verification': {
          await passwordRoute(); await input('secret'); await click('identity_reset_password_submit'); await capture('before_event');
          control.passwordResult(0);
          await wait('waiting real verification', () => owner().resetAction === 'success');
          const waiting = owner(); await capture('awaiting_verification_callback');
          control.verification(true); control.verification(true);
          await wait('single parent completion', () => owner().completionCount === 1 && owner().parentCompletionCount === 1);
          raw.observed = { resetAction: waiting.resetAction, progressVisibleUntilVerified: waiting.progressVisible,
            completionCount: owner().completionCount };
          invariant(0, waiting.parentCompletionCount === 0 && owner().parentCompletionCount === 1 && owner().parentCompleted,
            { waiting, after: owner(), external: control.calls });
          break;
        }
        case 'cancel_cleans_up': {
          await confirm(); control.deliverHandle(0, 'oidc');
          await wait('pending OIDC', () => sdkCalls('reset_oidc').length === 1); await capture('before_event');
          const episodes = [];
          await click('identity_reset_exit'); await wait('real handle cleaned', () => sdkCalls('destroy_reset_handle').length === 1);
          episodes.push({ reason: 'cancel', state: owner(), frame: await capture('after_physical_exit') });
          const replacePage = async () => {
            const action = { sequence: ++sequence, kind: 'framework_navigation', route: 'pages/Index', completed: false };
            raw.actions.push(action);
            expectedOwnerCount += 1;
            await launch.current().uiContext.getRouter().replaceUrl({ url: 'pages/Index' });
            await wait('fresh original page episode', () => observer.read().ownerCount === expectedOwnerCount);
            action.completed = true;
            await wait('fresh page controls', async () => (await inspect('identity_reset_continue')).present);
          };
          await replacePage(); await confirm(); control.deliverHandle(1, 'oidc');
          await wait('second pending OIDC', () => sdkCalls('reset_oidc').length === 2);
          await capture('before_actual_oidc_return');
          raw.actions.push({ sequence: ++sequence, kind: 'native_back', completed: false });
          await driver.pressBack(); raw.actions[raw.actions.length-1].completed = true;
          await wait('actual OIDC-return lifecycle cleanup', () => sdkCalls('destroy_reset_handle').length === 2);
          episodes.push({ reason: 'oidc_return', state: owner(), frame: await capture('after_actual_oidc_return') });
          await replacePage(); await confirm(); control.deliverHandle(2, 'oidc');
          await wait('third pending OIDC', () => sdkCalls('reset_oidc').length === 3);
          const destroyedOwnerId = owner().ownerId;
          await capture('before_actual_node_destruction'); await replacePage();
          await wait('original node destruction cancelled actual handle', () => sdkCalls('destroy_reset_handle').length === 3);
          const destroyed = observer.read().owners.find(value => value.ownerId === destroyedOwnerId);
          episodes.push({ reason: 'node_destroy', state: destroyed, frame: await capture('after_actual_node_destruction') });
          raw.lifecycleEpisodes = episodes;
          raw.observed = { effect: sdkCalls('cancel_reset_handle').length === 3 ? 'cancel_reset_handle' : null,
            handleState: destroyed.handleState, resetJobActive: destroyed.resetJobActive,
            completionWatcherActive: destroyed.completionWatcherActive };
          invariant(0, episodes.every(episode => episode.state.cleanupHistory.includes(episode.reason) &&
            episode.state.handleState === 'uninitialized' && !episode.state.resetJobActive &&
            !episode.state.completionWatcherActive) && sdkCalls('destroy_reset_handle').length === 3, episodes);
          break;
        }
        default: throw new Error('Unknown identity transition');
      }
    } else {
      switch (spec.key) {
        case 'open_loading': {
          await capture('before_event'); await click('open_pinned_messages');
          await wait('pending SDK open and rendered loading', async () => sdkCalls('open_pinned_timeline').length === 1 &&
            (await inspect('pinned_messages_loading')).present);
          const loading = await capture('held_sdk_rendered_loading');
          raw.observed = { screen: 'pinned_messages', listState: owner().listState, effects: ['open_pinned_timeline'] };
          await click('pinned_messages_back');
          invariant(0, (await inspect('open_pinned_messages')).present && owner().parentTimelineId === loading.owner.current.parentTimelineId,
            { loading, parent: owner() });
          break;
        }
        case 'load_failure': case 'empty_success': case 'filled_list': {
          await click('open_pinned_messages'); await wait('held open/loading', () => sdkCalls('open_pinned_timeline').length === 1);
          await capture('before_event');
          control.openResult(spec.key === 'load_failure');
          if (spec.key !== 'load_failure') {
            await wait('SDK subscription', () => control.read().itemSubscriberCount === 1);
            control.emitItems(spec.key === 'empty_success' ? [] : spec.given.pinnedTimelineItems.map(item => item.eventId));
          }
          await wait('real final load state', () => owner().listState !== 'loading');
          const state = owner();
          if (spec.key === 'load_failure') {
            raw.observed = { listState: state.listState, emptyStateVisible: (await inspect('pinned_messages_empty')).present,
              errorVisible: (await inspect('pinned_messages_failed')).present };
            invariant(0, state.listState === 'failed' && !raw.observed.emptyStateVisible, state);
          } else if (spec.key === 'empty_success') {
            raw.observed = { listState: state.listState, loadedPinnedMessagesCount: state.eventIds.length,
              failureVisible: (await inspect('pinned_messages_failed')).present };
            invariant(0, state.listState === 'empty' && state.errorMessage.length === 0, state);
          } else {
            raw.observed = { listState: state.listState, visibleEventIds: state.eventIds, loadedPinnedMessagesCount: state.eventIds.length };
            invariant(0, JSON.stringify(state.eventIds) === JSON.stringify(spec.given.pinnedTimelineItems.map(item => item.eventId)),
              { state, external: control.read() });
          }
          break;
        }
        case 'unpin_permission_denied': case 'unpin_permission_allowed': {
          await openPinned(); await wait('permission input applied', () => owner().canPinUnpin === (spec.given.canPinUnpin === true));
          await capture('before_event'); await openActions('$a');
          const view = await inspect('view_in_timeline_$a'), unpin = await inspect('unpin_$a');
          await capture('message_actions_opened');
          raw.observed = { actionsVisible: [view.present ? 'view_in_timeline' : null, unpin.present ? 'unpin' : null].filter(Boolean) };
          if (spec.key === 'unpin_permission_denied') {
            raw.observed.actionsHidden = unpin.present ? [] : ['unpin'];
            invariant(0, sdkCalls('unpin_event').length === 0 && JSON.stringify(owner().eventIds) === JSON.stringify(['$a', '$b']), owner());
          } else {
            control.permission(false); await wait('permission revoked on mounted UI', async () => !(await inspect('unpin_$a')).present);
            invariant(0, unpin.present && !owner().canPinUnpin && sdkCalls('can_pin_unpin').some(call => !call.allowed), control.calls);
          }
          break;
        }
        case 'view_in_timeline': {
          await openPinned(); const before = owner().eventIds; await capture('before_event');
          await openActions(spec.given.eventId);
          await click('view_in_timeline_' + spec.given.eventId);
          await wait('real parent event/scroll target', async () => (await inspect('room_event_' + spec.given.eventId)).present &&
            (await inspect('open_pinned_messages')).present && owner().focusedIndex >= 0);
          const state = owner(); raw.observed = { screen: 'room_timeline', focusedEventId: state.focusedEventId,
            effects: sdkCalls('room_timeline').some(call => call.focusedEventId === spec.given.eventId) ? ['navigate_to_event'] : [] };
          invariant(0, JSON.stringify(before) === JSON.stringify(state.eventIds), { state, external: control.read() });
          break;
        }
        case 'unpin_success': case 'unpin_failure_recovery': {
          await openPinned(); await wait('real unpin permission', () => owner().canPinUnpin);
          await capture('before_event'); control.setUnpinFailure(spec.key === 'unpin_failure_recovery');
          await openActions(spec.event.eventId);
          await click('unpin_' + spec.event.eventId);
          await wait('actual active SDK unpin call', () => sdkCalls('unpin_event').length === 1);
          await capture('after_sdk_unpin_before_item_flow');
          if (spec.key === 'unpin_success') {
            // External authoritative stream, not a feature-side filter.
            control.emitItems(['$b']); await wait('SDK update rendered', async () => owner().eventIds.length === 1 && !(await inspect('unpin_$a')).present);
          } else await wait('rendered unpin error', async () => (await inspect('unpin_error')).present);
          const state = owner(); raw.observed = { visibleEventIds: state.eventIds, errorVisible: state.errorMessage.length > 0,
            retryEnabled: state.retryEnabled, effects: spec.key === 'unpin_success' ? ['unpin_event', 'persist_pinned_state'] : ['show_error'] };
          const persisted = await capture('actual_native_preferences_after_unpin');
          require(JSON.stringify(persisted.nativePreferences.rows.map(item => item.eventId)) === JSON.stringify(state.eventIds),
            'Actual native cache does not match authoritative SDK item flow');
          invariant(0, JSON.stringify(state.eventIds) === JSON.stringify(spec.key === 'unpin_success' ? ['$b'] : spec.given.visibleEventIds),
            { state, external: control.read() });
          break;
        }
        default: throw new Error('Unknown pinned transition');
      }
    }
    if (!raw.frames.some(frame => frame.label === 'after_event')) await capture('after_event');
    require(raw.invariantChecks.length === spec.invariants.length, 'Not all original invariants evaluated');
    raw.eventExecuted = true;
  } catch (error) {
    raw.failure = { message: String(error), stack: error?.stack };
    raw.observed = null;
    raw.invariantChecks = [];
    raw.unevaluatedInvariants = spec.invariants;
    if (observer) raw.ownerDiagnostic = observer.read();
  } finally {
    raw.externalSdk = JSON.parse(JSON.stringify(control.calls));
    raw.launchEvidence = launch.read();
    observer?.dispose();
    await launch.dispose();
  }
  return JSON.stringify(raw);
}
