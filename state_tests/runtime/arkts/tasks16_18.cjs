'use strict';

const fs = require('node:fs');
const path = require('node:path');

const ROOT = 'entry/src/main/ets/features/';
const copy = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
const drain = async () => { for (let i = 0; i < 64; i++) await Promise.resolve(); };

class Unsupported extends Error {}

function withholdUnsupportedChannelEffects(taskId, caseSpec, log) {
  if (taskId !== '18_custom_notification_sounds' || ![
    'message_preset', 'message_custom_copy', 'call_preset', 'call_custom_copy', 'latest_pick_wins'
  ].includes(caseSpec.key)) return;
  // There is no implemented OS channel completion/readback binding. Neither
  // gateway arguments, a local ledger nor a claimed receipt can substitute.
  const fields = caseSpec.key === 'latest_pick_wins' ? ['recreateOrder'] : ['effects'];
  const reason = 'OS channel effect unsupported: no implemented binding verifies the original production action at the notification-service API, its completion and effective slot/sound readback with a real consumer. Gateway calls, arguments and app-local channel ledgers are diagnostic only.';
  delete log.result.observed.recreateOrder;
  if (Array.isArray(log.result.observed.effects)) log.result.observed.effects = log.result.observed.effects.filter(effect =>
    effect !== 'recreate_message_channel' && effect !== 'recreate_call_channel');
  log.unavailable(fields, reason);
  log.result.unsupported = log.result.unsupported ? log.result.unsupported + '; ' + reason : reason;
  log.checkpoint('unsupported_os_channel_effect', { fields, reason, observed: log.result.observed,
    observationScope: 'Production state, file/prefs I/O and gateway request diagnostics only; no OS channel effect claimed.' });
}

function methods(object, names) {
  for (const name of names) {
    if (typeof object?.[name] !== 'function') throw new Unsupported(`Production API unavailable: ${name}`);
  }
}

function recorder(caseSpec, trace) {
  const result = {
    observed: {}, evidence: [], invariantChecks: [], unsupportedInvariants: [],
    observationLevel: 'production_domain', unsupportedObservations: []
  };
  const cleanup = [];
  result.evidence.push({ observationLevel: 'production_domain', nativeUIExecuted: false,
    scope: 'Production domain methods and presenter projections; no native ArkUI rendering, navigation stack, browser, or OS service behavior is asserted.' });
  const pending = () => {
    const operation = deferred();
    cleanup.push(() => operation.resolve());
    return operation;
  };
  const checkpoint = (label, data) => {
    const snapshot = copy(data);
    result.evidence.push({ label, data: snapshot });
    trace(label, snapshot);
  };
  const check = (passed, observed, index = 0) => {
    const description = caseSpec.invariants?.[index];
    if (description) result.invariantChecks.push({ description, passed: Boolean(passed), observed: copy(observed) });
  };
  const assert = (description, passed, observed) => {
    result.invariantChecks.push({ description, passed: Boolean(passed), observed: copy(observed) });
    checkpoint('payload_assertion', { description, passed: Boolean(passed), observed });
  };
  const unavailable = (fields, reason) => {
    result.unsupportedObservations.push({ fields, reason });
    result.evidence.push({ unavailableObservations: fields, reason });
  };
  const finish = () => {
    for (const description of caseSpec.invariants || []) {
      if (!result.invariantChecks.some(item => item.description === description)) {
        result.unsupportedInvariants.push({ description,
          reason: result.unsupported || 'This invariant requires a native UI/lifecycle entry point not exposed by the loaded domain API.' });
      }
    }
    if (result.unsupportedInvariants.length) result.evidence.push({ unsupportedInvariants: copy(result.unsupportedInvariants) });
    return result;
  };
  return { result, checkpoint, check, assert, unavailable, finish, pending, cleanup };
}

async function production(project, load, candidates, log) {
  for (const relative of candidates) {
    const modulePath = ROOT + relative;
    if (typeof project === 'string' && !fs.existsSync(path.join(project, modulePath))) continue;
    try {
      const exports = await load(modulePath);
      log.result.evidence.push({ productionModule: modulePath });
      return exports;
    } catch (error) {
      if (error.code === 'MODULE_NOT_FOUND' || error.code === 'ENOENT') continue;
      throw new Unsupported(`Cannot load unmodified production module ${modulePath}: ${error.message}`);
    }
  }
  throw new Unsupported(`No supported production module: ${candidates.join(', ')}`);
}

function identityFixture(exports, given, log) {
  const start = log.pending(), reset = log.pending(), verification = log.pending();
  const calls = [];
  const kind = given.authenticationType || 'password';
  const handle = {
    kind, authenticationType: kind, handleId: 'runtime-identity-handle',
    url: given.approvalUrl || 'https://id.example/reset',
    approvalUrl: given.approvalUrl || 'https://id.example/reset',
    isCancelled: false, isCompleted: false,
    resetPassword(password) { calls.push({ name: 'reset_password', password, sameHandle: this === handle }); return reset.promise; },
    resetOidc() { calls.push({ name: 'reset_oidc', sameHandle: this === handle }); return reset.promise; },
    async cancel() { calls.push({ name: 'cancel_reset_handle', sameHandle: this === handle }); this.isCancelled = true; }
  };
  const sdk = {
    startIdentityReset() { calls.push({ name: 'start_identity_reset' }); return start.promise; },
    resetWithPassword(actual, password) {
      calls.push({ name: 'reset_password', password, sameHandle: actual === handle }); return reset.promise;
    },
    completeOidcReset(actual) { calls.push({ name: 'reset_oidc', sameHandle: actual === handle }); return reset.promise; },
    awaitSessionVerification(actual) {
      calls.push({ name: 'watch_verification', sameHandle: actual === handle }); return verification.promise;
    },
    cancelReset(actual) { calls.push({ name: 'cancel_reset_handle', sameHandle: actual === handle }); if (actual) actual.isCancelled = true; }
  };
  const manager = exports.IdentityResetFlowManager ? new exports.IdentityResetFlowManager(sdk) : null;
  const presenter = new exports.IdentityResetPresenter(manager);
  if (!manager) presenter.sdk = sdk;
  let completionCount = 0, previousPhase = presenter.phase;
  if (typeof presenter.subscribe === 'function') {
    presenter.subscribe(() => {
      if (presenter.phase === 'completed' && previousPhase !== 'completed') completionCount++;
      previousPhase = presenter.phase;
    });
  }
  const currentHandle = () => manager ? manager.currentHandle : presenter.snapshotHandle();
  const read = () => {
    const state = manager || presenter;
    const value = {
      confirmationVisible: presenter.confirmationVisible,
      handleState: state.handleState === 'failed' ? 'failure' : state.handleState,
      resetAction: presenter.resetAction === 'failed' ? 'failure' : presenter.resetAction,
      password: presenter.password, resetJobActive: state.resetJobActive,
      completionWatcherActive: state.completionWatcherActive,
      completionCount: typeof presenter.completionCount === 'number' ? presenter.completionCount : completionCount,
      errorVisible: Boolean(presenter.errorMessage || presenter.passwordError || presenter.lastError),
      startResetCount: calls.filter(call => call.name === 'start_identity_reset').length
    };
    if (typeof presenter.progressVisible === 'boolean') value.progressVisible = presenter.progressVisible;
    if (presenter.screen !== undefined) value.screen = presenter.screen;
    else {
      const screens = { idle: 'reset_root', confirmation: 'reset_root', failed: 'reset_root',
        cancelled: 'reset_root', password_auth: 'reset_password', oidc_auth: 'reset_oidc', completed: 'complete' };
      if (screens[presenter.phase]) value.screen = screens[presenter.phase];
    }
    return value;
  };
  const proceed = () => {
    const name = typeof presenter.continue === 'function' ? 'continue' : 'continueToConfirmation';
    methods(presenter, [name]); presenter[name]();
  };
  const edit = password => {
    const name = typeof presenter.setPassword === 'function' ? 'setPassword' : 'onPasswordChanged';
    methods(presenter, [name]); presenter[name](password);
  };
  const submit = password => { edit(password); return presenter.submitPassword(password); };
  log.result.evidence.push({ boundaryFakes: ['identity SDK handle acquisition, reset, cancellation, verification stream'],
    nativeUI: 'Not rendered; screen is the production routing state, visibility fields are presenter state only.' });
  return { presenter, manager, calls, handle, start, reset, verification, read, proceed, edit, submit, currentHandle };
}

async function identity(args, log) {
  const { caseSpec, project, load } = args;
  const given = caseSpec.given || {}, key = caseSpec.key;
  const mod = await production(project, load, ['IdentityResetFeature.ets', 'identityreset/IdentityResetPresenter.ets', 'SecureBackupBase.ets'], log);
  methods(mod, ['IdentityResetPresenter']);
  const fixtureGiven = key === 'cancel_cleans_up' ? { ...given, authenticationType: 'oidc' } : given;
  const f = identityFixture(mod, fixtureGiven, log), p = f.presenter;
  methods(p, ['confirmReset', 'dismissConfirmation', 'submitPassword', 'cancel']);
  const capture = label => log.checkpoint(label, { ...f.read(), calls: f.calls });
  const observe = () => { log.result.observed = f.read(); };

  if (key === 'continue_requests_confirmation' || key === 'dismiss_confirmation') {
    if (given.confirmationVisible) f.proceed();
    capture('before_event');
    if (key === 'continue_requests_confirmation') f.proceed(); else p.dismissConfirmation();
    observe(); capture('after_event');
    log.check(f.calls.length === 0, { calls: f.calls, confirmationVisible: p.confirmationVisible });
    return;
  }

  f.proceed();
  if (key === 'confirm_starts_handle') {
    capture('before_event');
    const first = p.confirmReset();
    observe();
    log.result.observed.effect = f.calls.some(call => call.name === 'start_identity_reset') ? 'start_identity_reset' : null;
    capture('after_event');
    const second = p.confirmReset();
    await drain();
    const loadingCalls = f.calls.length;
    f.start.resolve(f.handle);
    await Promise.all([first, second]);
    const loadedHandle = f.currentHandle();
    await p.confirmReset();
    log.check(loadingCalls === 1 && f.calls.filter(c => c.name === 'start_identity_reset').length === 1 &&
      loadedHandle === f.handle && f.currentHandle() === loadedHandle,
    { loadingCalls, calls: f.calls, reusedHandle: f.currentHandle() === loadedHandle });
    capture('concurrent_and_successful_handle_reuse');
    return;
  }

  const acquisition = p.confirmReset();
  capture('before_event');
  if (key === 'handle_failure_recovers') {
    f.start.resolve(undefined);
    await acquisition;
    observe(); capture('after_event');
    const missingState = f.read();
    f.proceed();
    const retry = p.confirmReset();
    const retryState = f.read();
    log.result.observed.retryEnabled = retryState.handleState === 'loading' && retryState.startResetCount > missingState.startResetCount;
    if (missingState.progressVisible === undefined) log.unavailable(['progressVisible'], 'The native page owns progress projection; this presenter does not expose progress visibility.');
    await retry;
    const errors = identityFixture(mod, given, log);
    errors.proceed();
    const errorAcquisition = errors.presenter.confirmReset();
    errors.start.reject(new Error('Injected SDK acquisition failure'));
    await errorAcquisition;
    log.check(missingState.handleState === 'failure' && errors.read().handleState === 'failure',
      { missingHandle: missingState, thrownError: errors.read(), retryState });
    return;
  }
  f.start.resolve(f.handle);
  if (key === 'cancel_cleans_up') {
    await drain();
    let oidcReturn;
    if (!f.manager) {
      await acquisition;
      methods(p, ['completeOidcFromRedirect']);
      oidcReturn = p.completeOidcFromRedirect();
    }
    f.reset.resolve();
    await acquisition;
    if (oidcReturn) await oidcReturn;
    capture('before_event');
    await p.cancel();
    observe();
    log.result.observed.effect = f.calls.some(call => call.name === 'cancel_reset_handle' && call.sameHandle)
      ? 'cancel_reset_handle' : null;
    capture('after_event');
    f.verification.resolve(); await drain();
    capture('late_verification_after_cancel');
    log.unavailable(['nativeLifecycle'], 'Native OIDC return/destruction dispatch is not loaded; only the production OIDC and cancel methods were executed.');
    return;
  }
  if (key === 'oidc_handle_routes_and_resets') {
    await drain();
    observe();
    log.result.observed.url = p.approvalUrl;
    if (f.calls.some(call => call.name === 'reset_oidc')) log.result.observed.pollEffect = 'reset_oidc';
    // Opening a web page and choosing its fallback happen outside these presenters.
    log.unavailable(['effect'], 'Native browser/WebView launch and custom-tab fallback are not observable through this presenter.');
    capture('after_event');
    f.reset.resolve();
    await acquisition;
    return;
  }
  await acquisition;
  if (key === 'password_handle_routes') {
    observe(); capture('after_event');
    log.check(f.currentHandle() === f.handle, { handleId: f.currentHandle()?.handleId, identicalSdkHandle: f.currentHandle() === f.handle });
    return;
  }
  if (key === 'password_submit_calls_handle') {
    const emptyProbe = identityFixture(mod, given, log);
    emptyProbe.proceed();
    const emptyAcquisition = emptyProbe.presenter.confirmReset();
    emptyProbe.start.resolve(emptyProbe.handle);
    await emptyAcquisition;
    const emptySubmission = emptyProbe.submit('');
    await drain();
    const emptyCalls = emptyProbe.calls.filter(call => call.name === 'reset_password').length;
    emptyProbe.reset.resolve();
    await emptySubmission;
    await emptyProbe.presenter.cancel();
    emptyProbe.verification.resolve();
    f.edit(given.password);
    capture('before_event');
    const operation = p.submitPassword(given.password);
    observe();
    const call = f.calls.find(call => call.name === 'reset_password');
    log.result.observed.effect = call ? call.name : null;
    if (call) log.result.observed.password = call.password;
    if (log.result.observed.progressVisible === undefined) log.unavailable(['progressVisible'], 'Progress is computed in the native page, not exposed by this presenter.');
    capture('after_event');
    log.check(emptyCalls === 0, { emptyPasswordResetCalls: emptyCalls });
    f.reset.resolve(); await operation;
    await p.cancel(); f.verification.resolve(); await drain();
    return;
  }
  if (key === 'password_failure_clears_on_edit') {
    const operation = f.submit(given.password);
    const loading = f.read();
    capture('before_event');
    f.reset.reject(new Error('Injected password rejection'));
    await operation;
    const failed = f.read();
    capture('password_rejected');
    if (loading.resetAction !== 'loading' || !f.calls.some(call =>
      call.name === 'reset_password' && call.password === given.password && call.sameHandle)) {
      throw new Unsupported('Password-failure setup was not established: the SDK reset was not loading on the supplied handle.');
    }
    if (failed.resetAction !== 'failure' || !failed.errorVisible) {
      throw new Unsupported('Password-failure setup was not established: SDK rejection did not produce an observable failure with an error before editing.');
    }
    f.edit(caseSpec.event.value);
    observe(); capture('after_event');
    const retained = f.currentHandle() === f.handle;
    const retry = p.submitPassword(caseSpec.event.value);
    log.result.observed.retryEnabled = f.read().resetAction === 'loading';
    await retry;
    log.check(retained && f.currentHandle() === f.handle, { failed, sameHandleBeforeAndAfterRetry: retained && f.currentHandle() === f.handle });
    return;
  }
  if (key === 'success_waits_for_verification') {
    const operation = f.submit(given.password || 'secret');
    capture('before_event');
    f.reset.resolve(); await operation;
    const beforeVerified = f.read();
    capture('reset_succeeded_before_verification');
    if (typeof p.sessionVerified === 'function') { p.sessionVerified(); p.sessionVerified(); }
    else { f.verification.resolve(); await drain(); }
    observe();
    if (typeof beforeVerified.progressVisible === 'boolean') log.result.observed.progressVisibleUntilVerified = beforeVerified.progressVisible;
    else log.unavailable(['progressVisibleUntilVerified'], 'The native page owns progress projection; the domain presenter exposes only its verification phase.');
    capture('after_event');
    log.check(beforeVerified.completionCount === 0 && f.read().completionCount === 1,
      { completionBeforeVerification: beforeVerified.completionCount, completionAfterVerification: f.read().completionCount });
    return;
  }
  throw new Unsupported(`Identity transition API mapping unavailable: ${key}`);
}

async function nativePageTransition(args, log) {
  const { taskId, caseSpec, load, project } = args;
  const native = args.context.native;
  if (!native.bundleName || typeof native.runTasks16To18UI !== 'function') {
    throw new Unsupported('Real candidate UI requires native.bundleName and native.runTasks16To18UI(request).');
  }
  let storedBefore, storedAfter, fixtureCallbacks, fixtureContext, fixtureScope;
  let fixturePrepared = false, fixtureReadBack = false;
  const isFocus = taskId === '17_pinned_messages' && caseSpec.key === 'view_in_timeline';
  if (isFocus) {
    const mod = await production(project, load, ['PinnedMessagesFeature.ets', 'PinnedMessagesBase.ets'], log);
    methods(mod, ['PinnedMessagesRepository', 'PinnedMessage']);
    const repository = new mod.PinnedMessagesRepository();
    methods(repository, ['persistPinnedState']);
    const preferencesModule = await load('@ohos.data.preferences');
    const preferences = preferencesModule.default || preferencesModule;
    methods(preferences, ['getPreferences']);
    const rows = [new mod.PinnedMessage(caseSpec.given.eventId, 'runtime sender', 'Runtime pinned message')];
    const scope = context => ({ origin: 'AbilityDelegator.waitAbilityMonitor().context',
      bundleName: context?.abilityInfo?.bundleName,
      moduleName: context?.abilityInfo?.moduleName || context?.currentHapModuleInfo?.name,
      preferencesDir: context?.preferencesDir, area: context?.area,
      storeName: 'element_x_pinned_messages', key: 'room_design_pinned_events' });
    const read = async context => {
      // openPinnedTimeline initializes defaults on an empty value. Read the
      // original SDK key directly so an invariant observation cannot repair it.
      const store = await preferences.getPreferences(context, 'element_x_pinned_messages');
      const raw = await store.get('room_design_pinned_events', '');
      let rows = null, parseError;
      try { const parsed = JSON.parse(raw); if (Array.isArray(parsed)) rows = parsed; }
      catch (error) { parseError = String(error); }
      return { raw, rows, parseError };
    };
    fixtureCallbacks = {
      async prepare(context) {
        if (args.uiAborted || fixtureContext) throw new Unsupported('Page fixture preparation is cancelled or repeated.');
        fixtureScope = scope(context);
        if (fixtureScope.bundleName !== native.bundleName || !fixtureScope.moduleName ||
          !fixtureScope.preferencesDir?.startsWith('/')) {
          throw new Unsupported('Actual candidate AbilityContext storage identity is unavailable.');
        }
        fixtureContext = context;
        try {
          await repository.persistPinnedState(context, rows);
          if (args.uiAborted) throw new Unsupported('Page fixture was cancelled during persistence.');
          const persisted = await read(context);
          if (args.uiAborted) throw new Unsupported('Page fixture was cancelled during seed readback.');
          storedBefore = copy(persisted.rows);
          log.checkpoint('native_page_storage_seeded', { context: fixtureScope, stored: storedBefore, ...persisted });
          if (!equal(storedBefore, copy(rows))) throw new Unsupported('Real repository did not establish the canonical pinned-event fixture.');
          fixturePrepared = true;
        } catch (error) { throw new Unsupported('Actual-AbilityContext seed failed: ' + String(error)); }
      },
      async afterEvent(context) {
        if (args.uiAborted || !fixturePrepared || fixtureReadBack || context !== fixtureContext ||
          !equal(scope(context), fixtureScope)) throw new Unsupported('Pinned readback requires the same prepared AbilityContext and storage scope.');
        try {
          const persisted = await read(context);
          if (args.uiAborted) throw new Unsupported('Page fixture was cancelled during after-event readback.');
          storedAfter = copy(persisted.rows);
          fixtureReadBack = true;
          log.checkpoint('native_page_storage_after_event', { context: fixtureScope, sameContext: true, ...persisted });
        } catch (error) { throw new Unsupported('Actual-AbilityContext readback failed: ' + String(error)); }
      }
    };
  }
  const request = { taskId, caseId: caseSpec.caseId, key: caseSpec.key, bundleName: native.bundleName,
    eventId: caseSpec.given?.eventId };
  const result = isFocus ? await native.runTasks16To18UI(request, fixtureCallbacks) : await native.runTasks16To18UI(request);
  if (args.uiAborted) return;
  if (result?.schemaVersion !== 1 || result.observationLevel !== 'native_candidate_ui' ||
    ['taskId', 'caseId', 'key', 'bundleName'].some(key => result[key] !== request[key]) ||
    !Array.isArray(result.checkpoints) || !Array.isArray(result.actions)) {
    throw new Unsupported('Native UI probe did not return matching candidate/case identity and raw checkpoints.');
  }
  log.result.evidence.push({ nativePageTransition: copy(result),
    scope: 'Real candidate page actions only. No separately constructed presenter state is merged with these UI observations.' });
  for (const checkpoint of result.checkpoints) log.checkpoint(`native_ui_${checkpoint.label}`, checkpoint);
  if (taskId === '18_custom_notification_sounds' && caseSpec.key === 'message_picker_launch') {
    const parseState = (checkpoint, field) => {
      const json = checkpoint?.[field];
      if (typeof json !== 'string') return undefined;
      try { return JSON.parse(json); } catch (_) { return undefined; }
    };
    const beforeFrame = result.checkpoints.find(item => item.label === 'launch_audio_picker_before');
    const afterFrame = result.checkpoints.find(item => item.label === 'after_event');
    const before = parseState(beforeFrame, 'pageStateJson'), after = parseState(afterFrame, 'pageStateJson');
    const launchBeforeSelect = call => {
      const calls = call?.presenterCallsBeforeSelect;
      if (!Array.isArray(before?.calls) || !Array.isArray(calls) || !Number.isFinite(call.startedAtMs) ||
        !equal(calls.slice(0, before.calls.length), before.calls)) return false;
      const added = calls.slice(before.calls.length);
      if (!added.length || !added.every((item, index) => item.sequence === before.calls.length + index + 1 &&
        item.instanceId === before.instanceId && item.outcome === 'returned' &&
        Number.isFinite(item.enteredAtMs) && Number.isFinite(item.returnedAtMs) &&
        item.enteredAtMs <= item.returnedAtMs && item.returnedAtMs <= call.startedAtMs)) return false;
      const launches = added.filter(item => item.method === 'launchSystemPicker');
      return launches.length === 1 && launches[0].slot === 'message' && added[0] === launches[0];
    };
    const pending = checkpoint => {
      const start = parseState(checkpoint, 'pickerStateBeforeJson'), end = parseState(checkpoint, 'pickerStateJson');
      if (!start?.observer?.available || !end?.observer?.available || start.calls?.length !== 1 || end.calls?.length !== 1) return undefined;
      const a = start.calls[0], b = end.calls[0];
      return a.id === b.id && a.startedAtMs === b.startedAtMs && a.status === 'pending' && b.status === 'pending' &&
        b.api === '@ohos.file.picker.AudioViewPicker.select' && b.instanceCount === 1 && b.samePageContext === true &&
        equal(a.presenterCallsBeforeSelect, b.presenterCallsBeforeSelect) && launchBeforeSelect(b) ? b : undefined;
    };
    const beforePicker = parseState(beforeFrame, 'pickerStateJson');
    const launchPending = pending(afterFrame);
    const samePage = before?.available && after?.available && before.instanceCount === 1 && after.instanceCount === 1 &&
      before.instanceId === after.instanceId && typeof before.storeId === 'number' && before.storeId === after.storeId &&
      before.source?.sha256 && before.source.sha256 === after.source?.sha256;
    if (samePage && before.messageDialog === true && before.messagePickerToken === caseSpec.given.messagePickerToken &&
      typeof after.messageDialog === 'boolean' && typeof after.messagePickerToken === 'number' &&
      before.persisted && after.persisted) {
      log.result.observed = { messageDialog: after.messageDialog ? 'open' : 'closed', messagePickerToken: after.messagePickerToken };
      if (launchPending && beforePicker?.observer?.available && beforePicker.calls?.length === 0) {
        log.check(equal(before.persisted, after.persisted), { before: before.persisted, after: after.persisted,
          instanceId: before.instanceId, storeId: before.storeId, productionSource: before.source,
          pickerPendingAcrossReadback: launchPending });
      }
    } else {
      log.unavailable(['messageDialog', 'messagePickerToken', 'unchangedPreferences'],
        'Canonical pre-click dialog/token and same original-page persistence were not all established.');
    }
    const visible = node => node.bounds?.right > node.bounds?.left && node.bounds?.bottom > node.bounds?.top;
    const action = result.actions.find(item => item.kind === 'id' && item.value === 'message_sound_picker' && item.before === beforeFrame?.label);
    const actualGiven = samePage && before.messageDialog === true && before.messagePickerToken === caseSpec.given.messagePickerToken &&
      beforeFrame?.focusedBundle === native.bundleName && !beforeFrame.error && action &&
      beforeFrame.nodes?.some(node => node.id === 'message_sound_picker' && node.enabled && node.clickable && visible(node)) &&
      beforeFrame.nodes?.some(node => node.id === 'message_sound_dialog' && visible(node));
    // Embedded UI requires both real ancestry and same-run provider records,
    // including the installed system audio-extension declaration.
    const identitySource = 'https://github.com/openharmony/applications_filepicker/blob/5438caec93de79e5c7395887771d2e7a304bd861/AppScope/app.json5';
    const extensionIds = ['audiopicker_selected', 'audiopicker_button'];
    const extensionWasAbsent = extensionIds.every(id => beforeFrame?.queryResults?.includes(`audio-extension:${id}:matches=0`));
    const embeddedFrame = result.checkpoints.find(item => !item.error && item.completed !== false &&
      item.focusedBundle === native.bundleName && extensionWasAbsent && extensionIds.every(id =>
        item.focusedNodes?.some(node => node.id === id && node.selectorScope === `audio-extension:${id}` && visible(node))) &&
      pending(item)?.id === launchPending?.id && launchPending);
    const provider = parseState(result, 'providerEvidenceJson'), record = provider?.matchedRecord;
    const installed = provider?.installedProvider, declaration = installed?.declaration;
    const host = before?.contextBinding?.scope;
    const providerVerified = !!(embeddedFrame === afterFrame && embeddedFrame && launchPending &&
      provider?.schemaVersion === 1 && provider.providerIdentityVerified === true && provider.intervalCorrelated === true &&
      provider.metadataIntervalCorrelated === true && provider.sdkCallId === launchPending.id &&
      provider.sdkStartedAtMs === launchPending.startedAtMs &&
      (provider.metadataTransport === 'delegator_shell' || provider.metadataTransport === 'nonce_bound_hdc' &&
        provider.hostTransportVerified === true && /^[a-f0-9]{32}$/.test(result.executionNonce || '') &&
        provider.executionNonce === result.executionNonce && native.capabilities?.execution?.nonce === result.executionNonce) &&
      typeof result.deviceUserId === 'string' && /^(0|[1-9][0-9]{0,9})$/.test(result.deviceUserId) &&
      Number(result.deviceUserId) <= 2147483647 && provider.deviceUserId === result.deviceUserId &&
      provider.deviceUserParameter === result.deviceUserParameter && result.deviceUserParameter === result.deviceUserId &&
      provider.deviceUserSource === 'AbilityDelegatorRegistry.getArguments().parameters["-s ltbDeviceUser"]' &&
      provider.deviceUserSource === result.deviceUserSource && !result.deviceUserError &&
      record?.correlatedNewHostExtension === true && record.newRecord === true && record.abilityType === 'UIEXTENSION' &&
      ['ACTIVE', 'FOREGROUND'].includes(record.state) && Number.isSafeInteger(record.pid) && record.pid > 0 &&
      typeof record.recordId === 'string' && /^\d+$/.test(record.recordId) &&
      typeof record.providerBundle === 'string' && /^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$/.test(record.providerBundle) &&
      provider.matches?.filter(item => item.correlatedNewHostExtension).length === 1 &&
      host?.bundleName === native.bundleName && typeof host.moduleName === 'string' && host.moduleName.length > 0 &&
      typeof host.abilityName === 'string' && host.abilityName.length > 0 &&
      record.rootHostBundle === host.bundleName && record.rootHostModule === host.moduleName && record.rootHostAbility === host.abilityName &&
      provider.host?.bundleName === host.bundleName && provider.host.moduleName === host.moduleName && provider.host.abilityName === host.abilityName &&
      installed?.verifiedSystemAudioProvider === true && installed.bundleName === record.providerBundle &&
      installed.applicationInfo?.bundleName === record.providerBundle && installed.applicationInfo.name === record.providerBundle &&
      installed.applicationInfo.isSystemApp === true && declaration?.bundleName === record.providerBundle &&
      declaration.name === record.providerAbility && declaration.moduleName === record.providerModule &&
      declaration.enabled === true && declaration.visible === true && declaration.extensionTypeName === 'sysPicker/audioPicker');
    if (embeddedFrame) log.result.evidence.push({ embeddedPickerAnchors: embeddedFrame.label,
      providerHostIdentityVerified: providerVerified, providerEvidence: provider,
      scope: 'Host ancestry requires the new active provider record, exact root host, pending-call time correlation, and installed system audio-extension declaration.' });
    const systemFrame = result.checkpoints.find(item => !item.error && item.completed !== false &&
      item.focusedBundle === 'com.ohos.filepicker' && item.focusedNodes?.some(visible) &&
      pending(item)?.id === launchPending?.id && launchPending);
    if (actualGiven && beforePicker?.observer?.available && beforePicker.calls?.length === 0 && launchPending && (systemFrame || providerVerified) &&
      log.result.invariantChecks.length > 0 && !afterFrame.error && !result.unsupported) {
      const source = before.source, binding = before.originalModuleBinding;
      const feature = source?.path?.slice(ROOT.length, -'.ets'.length);
      if (!source?.path?.startsWith(ROOT) || !source.path.endsWith('.ets') ||
        !['NotificationSoundFeature', 'NotificationSettingsBase'].includes(feature) ||
        !/^[a-f0-9]{64}$/.test(source.sha256 || '') || !equal(source, after.source) ||
        !binding?.importCompleted || !binding.receiverObserved ||
        binding.presenterExport !== 'NotificationSettingsPresenter' ||
        binding.timing !== 'after-mounted-page-positive-controls-before-message-dialog' ||
        !binding.readiness?.completed || binding.readiness.error || binding.readiness.focusedBundle !== native.bundleName ||
        binding.requestedModuleUrl !== `@bundle:${native.bundleName}/${before.contextBinding?.scope?.moduleName}/ets/features/${feature}` ||
        !equal(binding, after.originalModuleBinding) ||
        !equal(after.calls, launchPending.presenterCallsBeforeSelect) ||
        !after.calls.every(call => binding.wrappedNames?.includes(call.method))) {
        throw new Unsupported('Original-page production source/module/call provenance is incomplete or inconsistent.');
      }
      // The original-page observer already forwarded these calls and their
      // feature source to the shared recorder. Do not load a second module.
      log.result.evidence.push({ productionModule: source.path, productionSource: copy(source),
        originalModuleUrl: binding.requestedModuleUrl, actualPageCalls: copy(after.calls),
        scope: 'Already observed original-page calls and their bound feature source; no additional module load or presenter invocation.' });
      log.result.observed.effects = ['open_audio_picker'];
      log.result.observationLevel = 'native_candidate_ui';
      log.result.evidence.push({ pickerIdentitySource: providerVerified ? 'same-run aa dump -e and installed provider bm dump' : identitySource,
        systemWindow: providerVerified ? embeddedFrame.label : systemFrame.label,
        extensionAnchorSource: 'https://github.com/openharmony/applications_filepicker/blob/5438caec93de79e5c7395887771d2e7a304bd861/audiopicker/src/main/ets/pages/card/AudioPickerView.ets',
        nativeSelect: launchPending, pageObservationLevel: 'production_domain',
        scope: 'Original page token/dialog projection and same-store persistence; actual SDK select plus observed system-picker window/tree.' });
      return;
    }
    log.unavailable(['effects'], 'Requires canonical visible pre-click dialog, same-page pending native AudioViewPicker.select, and an identified system-picker window/tree. Host UIExtension anchors require a verified active provider-host record; click or token alone is insufficient.');
    throw new Unsupported(result.unsupported || 'Native picker evidence incomplete: ' + JSON.stringify({
      samePage: !!samePage, actualGiven: !!actualGiven, nativeSelectPending: !!launchPending,
      systemWindowObserved: !!systemFrame, embeddedAnchorsObserved: !!embeddedFrame,
      embeddedProviderIdentity: providerVerified ? 'verified' : 'not_verified', pickerObserver: beforePicker?.observer,
      focusedBundle: afterFrame?.focusedBundle, picker: parseState(afterFrame, 'pickerStateJson') }));
  }
  if (result.unsupported) throw new Unsupported(result.unsupported);
  if (!isFocus) throw new Unsupported('Raw candidate UI evidence is available, but same-page SDK effects or loading observations remain incomplete.');
  if (!fixturePrepared || !fixtureReadBack) throw new Unsupported('Actual-AbilityContext seed and after-event readback were not both observed.');
  const action = result.actions.find(item => item.kind === 'id' && item.value === `view_in_timeline_${caseSpec.given.eventId}`);
  const before = result.checkpoints.find(item => item.label === action?.before);
  const after = result.checkpoints.find(item => item.label === 'after_event');
  const usableNodes = checkpoint => (checkpoint?.nodes || []).filter(node =>
    node.bounds?.right > node.bounds?.left && node.bounds?.bottom > node.bounds?.top);
  const beforeNodes = usableNodes(before), afterNodes = usableNodes(after);
  const listIds = ['pinned_messages_filled', 'pinned_list', 'pinned_messages_loading', 'pinned_loading',
    'pinned_messages_empty', 'pinned_empty', 'pinned_messages_failed', 'pinned_failed'];
  if (!action || before?.focusedBundle !== native.bundleName ||
    !beforeNodes.some(node => listIds.includes(node.id)) || !beforeNodes.some(node =>
      node.id === action.value && node.enabled && node.clickable)) {
    throw new Unsupported('The actual candidate pinned-list control and canonical event were not established before the click.');
  }
  if (after?.focusedBundle !== native.bundleName) throw new Unsupported('Candidate UI after navigation is not observable in the focused window.');
  const isTimeline = afterNodes.some(node => node.text === 'Design team');
  const isList = afterNodes.some(node => listIds.includes(node.id));
  if (isTimeline === isList) throw new Unsupported('Post-event candidate screen is ambiguous or unavailable.');
  const focusedLabel = afterNodes.find(node => node.id === 'focused_event_label');
  if (isTimeline && !focusedLabel) throw new Unsupported('Candidate timeline does not expose an observed focused-event label.');
  const focusedEventId = focusedLabel?.text.startsWith('Focused ') ? focusedLabel.text.slice('Focused '.length) : '';
  log.result.observationLevel = 'native_candidate_ui';
  log.result.observed = { screen: isTimeline ? 'room_timeline' : 'pinned_messages', focusedEventId,
    effects: isTimeline && focusedEventId === caseSpec.given.eventId ? ['navigate_to_event'] : [] };
  log.check(equal(storedBefore, storedAfter), { storedBefore, storedAfter });
  log.checkpoint('after_event', { observed: log.result.observed, storedBefore, storedAfter,
    scope: 'Navigation effect is the actual page transition and rendered focus, not a separately invoked presenter method.' });
}

async function pinned(args, log) {
  const { caseSpec, project, load } = args;
  const g = caseSpec.given || {}, event = caseSpec.event || {}, key = caseSpec.key;
  const mod = await production(project, load, ['PinnedMessagesFeature.ets', 'PinnedMessagesBase.ets'], log);
  const context = { filesDir: '/runtime/app/files' };
  const rows = g.pinnedTimelineItems || (g.visibleEventIds || [g.eventId || '$a', '$b']).map(eventId => ({ eventId, body: eventId }));
  const calls = [], gate = log.pending();
  let presenter, repository, serverRows, read, open, permission, unpin, focus;
  if (typeof mod.PinnedMessagesListPresenter === 'function') {
    repository = new mod.PinnedMessagesRepository();
    methods(repository, ['unpinEvent']);
    const productionUnpin = repository.unpinEvent;
    repository.unpinEvent = function(...args) {
      calls.push({ name: 'unpin_event', eventId: args[1] });
      return productionUnpin.apply(this, args);
    };
    serverRows = rows.map(row => new mod.PinnedMessage(row.eventId, 'runtime sender', row.body));
    // Replace only I/O; unpinEvent's filtering and presenter rollback remain production code.
    repository.openPinnedTimeline = async () => {
      calls.push({ name: 'open_pinned_timeline' });
      await gate.promise;
      if (g.pinnedTimelineResult === 'failure') throw new Error('Injected timeline read failure');
      return serverRows.slice();
    };
    repository.persistPinnedState = async (_context, messages) => {
      calls.push({ name: 'persist_pinned_state', eventIds: messages.map(item => item.eventId), messages: copy(messages) });
      if (event.result === 'failure') throw new Error('Injected persistence failure');
      serverRows = copy(messages);
    };
    presenter = new mod.PinnedMessagesListPresenter(repository);
    read = () => ({ listState: presenter.listState, visibleEventIds: presenter.pinnedMessages.map(item => item.eventId),
      loadedPinnedMessagesCount: presenter.pinnedMessages.length, errorVisible: presenter.errorMessage.length > 0,
      failureVisible: presenter.errorMessage.length > 0, emptyStateVisible: presenter.listState === 'empty',
      retryEnabled: presenter.retryEnabled, focusedEventId: presenter.focusedEventId });
    open = () => presenter.openPinnedMessages(context);
    permission = value => presenter.setPermission(value);
    unpin = id => presenter.unpin(context, id);
    focus = id => presenter.viewInTimeline(id);
    log.result.evidence.push({ boundaryFakes: ['pinned timeline read', 'pinned state persistence'],
      productionExecuted: ['PinnedMessagesListPresenter', 'PinnedMessagesRepository.unpinEvent'] });
  } else if (typeof mod.RoomStore === 'function') {
    presenter = new mod.RoomStore();
    // The app's server simulator is seeded with GIVEN data, never post-event results.
    presenter.serverPinned = rows.map(row => new mod.PinnedEvent(row.eventId, row.body, 'runtime sender'));
    presenter.serverTimeline = presenter.serverPinned.slice();
    methods(presenter, ['applyServerToState', 'loadInitialPinnedPage', 'unpinEvent']);
    presenter.applyServerToState();
    read = () => ({ listState: presenter.pinnedList.listState,
      visibleEventIds: presenter.pinnedList.items.map(item => item.eventId),
      loadedPinnedMessagesCount: presenter.pinnedList.items.length,
      errorVisible: Boolean(presenter.pinnedList.loadFailureMessage || presenter.pinnedList.unpinFailureMessage),
      failureVisible: Boolean(presenter.pinnedList.loadFailureMessage),
      emptyStateVisible: presenter.pinnedList.listState === 'empty', focusedEventId: presenter.state.focusedEventId });
    open = () => presenter.loadInitialPinnedPage();
    permission = value => presenter.setCanPinUnpin(value);
    unpin = id => presenter.unpinEvent(id);
    focus = id => presenter.focusEventInTimeline(id);
    if (g.pinnedTimelineResult === 'failure') presenter.markNextLoadForFailure();
    log.result.evidence.push({ fixture: 'Seeded the production server simulator with canonical GIVEN rows; used actual asynchronous load and unpin methods.' });
  } else throw new Unsupported('No collection presenter or RoomStore API; the banner-only API cannot execute collection transitions.');
  const stored = () => copy(repository ? serverRows : presenter.serverPinned);
  const visible = () => copy(repository ? presenter.pinnedMessages : presenter.pinnedList.items);
  const checkpoint = label => log.checkpoint(label, { ...read(), stored: stored(), calls });
  permission(Boolean(g.canPinUnpin));
  checkpoint('before_event');
  const loading = open();
  if (key === 'open_loading') {
    log.result.observed = read();
    if (calls.some(call => call.name === 'open_pinned_timeline')) log.result.observed.effects = ['open_pinned_timeline'];
    checkpoint('after_event');
    gate.resolve(); await loading;
    log.unavailable(['screen', 'navigationParent'], 'Native page navigation and its parent stack are not exposed by the collection presenter.');
    return;
  }
  gate.resolve(); await loading;
  if (['load_failure', 'empty_success', 'filled_list'].includes(key)) {
    log.result.observed = read(); checkpoint('after_event');
    if (key === 'load_failure') log.check(read().listState !== 'empty' && read().errorVisible,
      { listState: read().listState, errorVisible: read().errorVisible });
    if (key === 'empty_success') log.check(read().listState === 'empty' && !read().errorVisible, read());
    if (key === 'filled_list') log.check(equal(read().visibleEventIds, rows.map(row => row.eventId)),
      { serverEventIds: rows.map(row => row.eventId), loadedEventIds: read().visibleEventIds });
    return;
  }
  const before = read();
  const storedBefore = stored(), callStart = calls.length;
  checkpoint('before_event');
  if (key === 'unpin_permission_denied' || key === 'unpin_permission_allowed') {
    if (typeof presenter.availableActions !== 'function') {
      throw new Unsupported('The action menu is implemented only in the native ArkUI page; RoomStore exposes permission but no action-menu API.');
    }
    const actions = presenter.availableActions();
    log.result.observed.actionsVisible = actions.slice();
    if (key === 'unpin_permission_denied') log.result.observed.actionsHidden = ['unpin'].filter(action => !actions.includes(action));
    checkpoint('after_event');
    if (key === 'unpin_permission_denied') log.check(equal(before.visibleEventIds, read().visibleEventIds) &&
      equal(storedBefore, stored()) && !calls.slice(callStart).some(call =>
        call.name === 'persist_pinned_state' || call.name === 'unpin_event'),
    { before: before.visibleEventIds, after: read().visibleEventIds, storedBefore, storedAfter: stored(), calls: calls.slice(callStart) });
    else {
      permission(false);
      const revoked = presenter.availableActions();
      await unpin(g.eventId);
      checkpoint('permission_revoked_probe');
      const unauthorizedCalls = calls.slice(callStart).filter(call =>
        call.name === 'unpin_event' || call.name === 'persist_pinned_state');
      log.check(actions.includes('unpin') && !revoked.includes('unpin') && equal(before.visibleEventIds, read().visibleEventIds) &&
        equal(storedBefore, stored()) && unauthorizedCalls.length === 0,
      { allowedActions: actions, revokedActions: revoked, eventIdsAfterDeniedUnpin: read().visibleEventIds,
        storedBefore, storedAfter: stored(), unauthorizedCalls });
    }
    return;
  }
  if (key === 'view_in_timeline') {
    focus(g.eventId);
    log.result.observed.focusedEventId = read().focusedEventId;
    checkpoint('after_event');
    log.check(equal(before.visibleEventIds, read().visibleEventIds) && equal(storedBefore, stored()),
      { before: before.visibleEventIds, after: read().visibleEventIds, storedBefore, storedAfter: stored() });
    log.unavailable(['screen', 'effects'], 'Focus state is observable; native router navigation is not part of this production API.');
    return;
  }
  if (key === 'unpin_success' || key === 'unpin_failure_recovery') {
    if (!repository && event.result === 'failure') presenter.markUnpinForFailure(event.eventId);
    const operation = unpin(event.eventId);
    const inFlight = read();
    const storedInFlight = stored();
    checkpoint('unpin_in_flight');
    await operation;
    log.result.observed = read(); checkpoint('after_event');
    if (repository && event.result === 'success') {
      const effects = [];
      for (const call of calls.slice(callStart)) {
        if (call.name === 'unpin_event' || call.name === 'persist_pinned_state') effects.push(call.name);
      }
      log.result.observed.effects = effects;
    } else if (event.result === 'failure') {
      log.result.observed.effects = read().errorVisible ? ['show_error'] : [];
    } else log.unavailable(['effects'], 'RoomStore mutates its simulated server in memory; no persistence I/O is exposed or claimed.');
    if (key === 'unpin_success') {
      const unrelated = before.visibleEventIds.filter(id => id !== event.eventId);
      const retainedRows = storedBefore.filter(row => row.eventId !== event.eventId);
      const eventCalls = calls.slice(callStart);
      const writes = eventCalls.filter(call => call.name === 'persist_pinned_state');
      const removals = eventCalls.filter(call => call.name === 'unpin_event');
      log.assert('Unpin persists exactly the remaining messages and dispatches the requested event ID',
        equal(stored(), retainedRows) && equal(visible(), retainedRows) && (!repository ||
          writes.length > 0 && writes.every(call => equal(call.messages, retainedRows)) &&
          removals.length > 0 && removals.every(call => call.eventId === event.eventId)),
      { eventId: event.eventId, retainedRows, storedAfter: stored(), visibleAfter: visible(), calls: eventCalls });
      log.check(equal(read().visibleEventIds.filter(id => id !== event.eventId), unrelated),
        { unrelatedBefore: unrelated, visibleAfter: read().visibleEventIds });
    } else {
      log.check(equal(before.visibleEventIds, inFlight.visibleEventIds) && equal(before.visibleEventIds, read().visibleEventIds) &&
        equal(storedBefore, storedInFlight) && equal(storedBefore, stored()),
      { before: before.visibleEventIds, inFlight: inFlight.visibleEventIds, after: read().visibleEventIds,
        storedBefore, storedInFlight, storedAfter: stored() });
      if (!repository) log.unavailable(['retryEnabled'], 'Retry visibility is owned by the native page; RoomStore has no retry-enabled getter.');
    }
    return;
  }
  throw new Unsupported(`Pinned-message transition API mapping unavailable: ${key}`);
}

function soundFixture(g, event, log) {
  const calls = [];
  const performCopy = async uri => {
    calls.push({ name: 'copy_to_app_storage', uri });
    if (event.copyResult === 'failure') throw new Error('Injected provider read failure');
    log.result.unsupported = 'Production sound copier cannot execute with filesystem-only mocks through the current loader.';
    throw new Unsupported(log.result.unsupported);
  };
  const semanticSound = selection => {
    const source = selection.kind || selection.source;
    if (source === 'preset') return selection.presetId;
    if (source !== 'custom') return source;
    const uri = selection.uri || selection.customFilePath;
    if (uri === '/runtime/app/files/explicit.audio' || uri === 'file:///runtime/app/files/explicit.audio') return 'custom_explicit';
    return uri;
  };
  return { calls, performCopy, semanticSound };
}

async function soundSetup(args, log, boundary) {
  const { project, load, caseSpec } = args, g = caseSpec.given || {};
  const mod = await production(project, load, ['NotificationSoundFeature.ets', 'NotificationSettingsBase.ets'], log);
  methods(mod, ['NotificationSettingsPresenter']);
  const calls = boundary.calls, context = { filesDir: '/runtime/app/files' };
  const message = g.persistedMessageSound || g.messageSound || 'system_default';
  const call = g.persistedCallRingtone || g.callRingtone || 'system_default';
  const versions = { message: g.messageChannelVersion || 0, call: g.callChannelVersion || 0 };
  if (mod.NotificationSoundSnapshot) {
    const selection = value => value === 'custom_explicit'
      ? mod.NotificationSoundSelection.custom('file:///runtime/app/files/explicit.audio', 'Explicit ringtone')
      : mod.NotificationSoundSelection.preset(value);
    let persisted = new mod.NotificationSoundSnapshot(selection(message), selection(call), versions.message, versions.call);
    const store = {
      async load() { calls.push({ name: 'load_preferences' }); return persisted.copy(); },
      async save(_context, snapshot) {
        calls.push({ name: 'persist_snapshot', snapshot: copy(snapshot) }); persisted = snapshot.copy();
      }
    };
    const copier = {
      async copyToAppFiles(_context, uri, slot) {
        try {
          await boundary.performCopy(uri);
        } catch (error) {
          if (error instanceof Unsupported) throw error;
          return new mod.SoundCopyResult(false, '', '', error.message);
        }
      },
      deleteStoredSoundFor(_context, slot) { calls.push({ name: 'delete_stored_sound', slot }); }
    };
    const channels = {
      async recreateChannel(_context, slot, sound, version) {
        calls.push({ name: 'recreate_channel', slot, sound: copy(sound), version });
        versions[slot] = version;
      }
    };
    const p = new mod.NotificationSettingsPresenter(store, copier, channels);
    methods(p, ['load', 'selectPreset', 'setCustomSound', 'showDialog', 'launchSystemPicker', 'dismissCopyError']);
    const read = () => ({
      messageSound: boundary.semanticSound(p.snapshot.messageSound), callRingtone: boundary.semanticSound(p.snapshot.callRingtone),
      messageDisplayName: p.snapshot.messageSound.displayName, callDisplayName: p.snapshot.callRingtone.displayName,
      messageChannelVersion: p.snapshot.messageChannelVersion, callChannelVersion: p.snapshot.callChannelVersion,
      messageDialog: p.showMessageSoundDialog ? 'open' : 'closed', callDialog: p.showCallRingtoneDialog ? 'open' : 'closed',
      messagePickerToken: p.pendingMessageSoundPickerLaunch, messageCopyError: p.messageCopyError.length > 0,
      callCopyError: p.callCopyError.length > 0,
      labelsResolved: p.snapshot.messageSound.displayName.length > 0 && p.snapshot.callRingtone.displayName.length > 0
    });
    return { p, read, restore: () => p.load(context), open: slot => p.showDialog(slot),
      preset: (slot, value) => p.selectPreset(context, slot, value),
      custom: (slot, uri) => p.setCustomSound(context, slot, uri),
      picker: slot => p.launchSystemPicker(slot), dismiss: slot => p.dismissCopyError(slot),
      migrate: () => p.migrateLegacyCallRingtone(context, selection(g.legacyChannelRingtone)),
      persisted: () => copy(persisted), shape: 'snapshot',
      state: () => ({ message: copy(p.snapshot.messageSound), call: copy(p.snapshot.callRingtone),
        messageVersion: p.snapshot.messageChannelVersion, callVersion: p.snapshot.callChannelVersion }),
      storedState: () => ({ message: copy(persisted.messageSound), call: copy(persisted.callRingtone),
        messageVersion: persisted.messageChannelVersion, callVersion: persisted.callChannelVersion }) };
  }
  const serviceMod = await production(project, load, ['sound/SoundSettingsService.ets'], log);
  const typeMod = await production(project, load, ['sound/SoundTypes.ets'], log);
  methods(serviceMod, ['SoundSettingsService']);
  const selection = (value, version) => value === 'custom_explicit'
    ? typeMod.makeCustomPreference('/runtime/app/files/explicit.audio', 'Explicit ringtone', version, 0)
    : value === 'system_default' ? typeMod.makeSystemDefaultPreference(version, 0)
      : typeMod.makePresetPreference(value, value === 'silent' ? 'Silent' : 'Element default', version, 0);
  const persisted = { message: selection(message, versions.message), call: selection(call, versions.call) };
  const repository = {
    defaultPreferenceFor() { return typeMod.makeSystemDefaultPreference(0, 0); },
    async read(slot) { calls.push({ name: 'load_preferences', slot }); return copy(persisted[slot]); },
    async write(slot, preference) { calls.push({ name: 'persist_slot', slot, preference: copy(preference) }); persisted[slot] = copy(preference); }
  };
  const channels = {
    async ensureSlotRegistered(slot) { calls.push({ name: 'register_slot', slot }); },
    currentChannelVersion(slot) { return versions[slot]; },
    async currentSlotSound(slot) { calls.push({ name: 'read_legacy_sound', slot }); return g.legacyChannelRingtone || ''; },
    async apply(slot, preference) {
      calls.push({ name: 'recreate_channel', slot, sound: copy(preference), version: preference.version });
      versions[slot] = preference.version;
    }
  };
  const service = new serviceMod.SoundSettingsService({ repository, channels,
    storage: {
      copyFromUri: uri => boundary.performCopy(uri),
      async delete(filePath) { calls.push({ name: 'delete_stored_sound', filePath }); }
    },
    picker: { isSupported: () => true, async launch() { calls.push({ name: 'open_audio_picker' }); return null; } }
  });
  const p = new mod.NotificationSettingsPresenter(service);
  methods(p, ['refreshSoundState', 'selectMessagePreset', 'setMessageSoundFromPicker']);
  const read = () => {
    p.refreshSoundState();
    return {
      messageSound: boundary.semanticSound(service.currentPreference('message')),
      callRingtone: boundary.semanticSound(service.currentPreference('call')),
      messageDisplayName: service.currentPreference('message').displayName,
      callDisplayName: service.currentPreference('call').displayName,
      messageChannelVersion: p.messageSoundChannelVersion, callChannelVersion: p.callRingtoneChannelVersion,
      messageDialog: p.messageDialogOpen ? 'open' : 'closed', callDialog: p.callDialogOpen ? 'open' : 'closed',
      messagePickerToken: p.messagePickerToken, messageCopyError: p.hasMessageError(), callCopyError: p.hasCallError(),
      labelsResolved: p.messageSoundLabel.length > 0 && p.callRingtoneLabel.length > 0
    };
  };
  return { p, service, read, restore: () => service.initialize(),
    open: slot => slot === 'message' ? p.openMessageSoundDialog() : p.openCallRingtoneDialog(),
    preset: (slot, value) => slot === 'message' ? p.selectMessagePreset(value) : p.selectCallPreset(value),
    custom: (slot, uri) => slot === 'message' ? p.setMessageSoundFromPicker(uri, g.displayName || '') : p.setCallRingtoneFromPicker(uri, g.displayName || ''),
    picker: slot => slot === 'message' ? p.launchMessageSoundPicker() : p.launchCallRingtonePicker(),
    dismiss: slot => slot === 'message' ? p.dismissMessageError() : p.dismissCallError(),
    async migrate() {
      const { LegacyRingtoneMigrator } = await production(project, load, ['sound/LegacyRingtoneMigrator.ets'], log);
      const outcome = await new LegacyRingtoneMigrator(channels, repository).migrateCallSlotIfNeeded();
      return outcome.migrated;
    },
    persisted: () => copy(persisted), shape: 'slots',
    state: () => ({ message: copy(service.currentPreference('message')), call: copy(service.currentPreference('call')),
      messageVersion: service.currentPreference('message').version, callVersion: service.currentPreference('call').version }),
    storedState: () => ({ message: copy(persisted.message), call: copy(persisted.call),
      messageVersion: persisted.message.version, callVersion: persisted.call.version }) };
}

// Native bridge inputs are transport only: a real isolated Context, the loader's
// call log, and provider fixtures. No production instance methods are replaced.
async function nativeSoundSetup(args, log) {
  const { caseSpec, project, load } = args, g = caseSpec.given || {};
  const native = args.context.native, context = native.context;
  const mod = await production(project, load, ['NotificationSoundFeature.ets', 'NotificationSettingsBase.ets'], log);
  methods(mod, ['NotificationSettingsPresenter']);
  const message = g.persistedMessageSound || g.messageSound || 'system_default';
  const call = g.persistedCallRingtone || g.callRingtone || 'system_default';
  const explicitPath = `${context.filesDir}/explicit.audio`;
  const messageVersion = g.messageChannelVersion || 0, callVersion = g.callChannelVersion || 0;
  const evictPreferences = async name => {
    const module = await load('@ohos.data.preferences'), preferences = module.default || module;
    await preferences.removePreferencesFromCache(context, name);
  };
  if (typeof mod.NotificationSoundStore === 'function') {
    methods(mod, ['NotificationSoundCopier', 'NotificationChannelGateway', 'NotificationSoundSnapshot']);
    const selection = value => value === 'custom_explicit'
      ? mod.NotificationSoundSelection.custom(`file://${explicitPath}`, 'Explicit ringtone')
      : mod.NotificationSoundSelection.preset(value);
    const seed = new mod.NotificationSoundSnapshot(selection(message), selection(call), messageVersion, callVersion);
    await new mod.NotificationSoundStore().save(context, seed);
    const store = new mod.NotificationSoundStore(), copier = new mod.NotificationSoundCopier();
    const channels = new mod.NotificationChannelGateway();
    const presenter = new mod.NotificationSettingsPresenter(store, copier, channels);
    let persisted;
    return {
      shape: 'snapshot', explicitPath, presenter, channels, channelObservationScope: 'app_local_preferences_ledger',
      seedState: () => ({ message: copy(seed.messageSound), call: copy(seed.callRingtone),
        messageVersion: seed.messageChannelVersion, callVersion: seed.callChannelVersion }),
      async restore() { await evictPreferences('element_x_notification_sounds'); await presenter.load(context); },
      async refresh() {
        await evictPreferences('element_x_notification_sounds');
        persisted = await new mod.NotificationSoundStore().load(context);
      },
      state: () => ({ message: copy(presenter.snapshot.messageSound), call: copy(presenter.snapshot.callRingtone),
        messageVersion: presenter.snapshot.messageChannelVersion, callVersion: presenter.snapshot.callChannelVersion }),
      stored: () => ({ message: copy(persisted.messageSound), call: copy(persisted.callRingtone),
        messageVersion: persisted.messageChannelVersion, callVersion: persisted.callChannelVersion }),
      ui: () => ({ messageDialog: presenter.showMessageSoundDialog ? 'open' : 'closed',
        callDialog: presenter.showCallRingtoneDialog ? 'open' : 'closed',
        messagePickerToken: presenter.pendingMessageSoundPickerLaunch,
        messageCopyError: presenter.messageCopyError.length > 0, callCopyError: presenter.callCopyError.length > 0,
        messageCopyErrorMessage: presenter.messageCopyError, callCopyErrorMessage: presenter.callCopyError }),
      open: slot => presenter.showDialog(slot), dismiss: slot => presenter.dismissCopyError(slot),
      preset: (slot, value) => presenter.selectPreset(context, slot, value),
      custom: (slot, source) => presenter.setCustomSound(context, slot, source.uri),
      migrate: () => presenter.migrateLegacyCallRingtone(context, selection(g.legacyChannelRingtone)),
      async channelState(slot) {
        const module = await load('@ohos.data.preferences'), preferences = module.default || module;
        await preferences.removePreferencesFromCache(context, 'element_x_notification_channels');
        const channelStore = await preferences.getPreferences(context, 'element_x_notification_channels');
        return { id: await channelStore.get(`${slot}_active_channel_id`, ''),
          kind: await channelStore.get(`${slot}_effective_sound_kind`, ''),
          uri: await channelStore.get(`${slot}_effective_sound_uri`, '') };
      }
    };
  }
  const serviceMod = await production(project, load, ['sound/SoundSettingsService.ets'], log);
  const typeMod = await production(project, load, ['sound/SoundTypes.ets'], log);
  const repoMod = await production(project, load, ['sound/SoundPreferenceRepository.ets'], log);
  const storageMod = await production(project, load, ['sound/LocalSoundStorage.ets'], log);
  const channelMod = await production(project, load, ['sound/NotificationChannelService.ets'], log);
  const pickerMod = await production(project, load, ['sound/DocumentSoundPicker.ets'], log);
  const catalogMod = await production(project, load, ['sound/SoundPresetCatalog.ets'], log);
  const options = { name: `runtime_sound_${caseSpec.caseId}` };
  const repository = new repoMod.SoundPreferenceRepository(options);
  const selection = (slot, value, version) => value === 'custom_explicit'
    ? typeMod.makeCustomPreference(explicitPath, 'Explicit ringtone', version, 0)
    : value === 'system_default' ? typeMod.makeSystemDefaultPreference(version, 0)
      : typeMod.makePresetPreference(value, catalogMod.SoundPresetCatalog.find(slot, value)?.label || value, version, 0);
  const seededMessage = selection('message', message, messageVersion), seededCall = selection('call', call, callVersion);
  await repository.write('message', seededMessage);
  await repository.write('call', seededCall);
  const channels = new channelMod.NotificationChannelService();
  const service = new serviceMod.SoundSettingsService({ repository: new repoMod.SoundPreferenceRepository(options),
    storage: new storageMod.LocalSoundStorage(context.filesDir), channels,
    picker: new pickerMod.SystemDocumentSoundPicker(['.ogg', '.wav', '.mp3']) });
  const presenter = new mod.NotificationSettingsPresenter(service);
  let persisted;
  const stateFrom = (message, call) => ({ message: copy(message), call: copy(call),
    messageVersion: message.version, callVersion: call.version });
  return {
    shape: 'slots', explicitPath, presenter, channels, channelObservationScope: 'production_service_projection_not_OS_readback',
    seedState: () => stateFrom(seededMessage, seededCall),
    restore: () => service.initialize(),
    async refresh() {
      await evictPreferences(options.name);
      const fresh = new repoMod.SoundPreferenceRepository(options);
      persisted = stateFrom(await fresh.read('message'), await fresh.read('call'));
      presenter.refreshSoundState();
    },
    state: () => stateFrom(service.currentPreference('message'), service.currentPreference('call')),
    stored: () => copy(persisted),
    ui: () => ({ messageDialog: presenter.messageDialogOpen ? 'open' : 'closed',
      callDialog: presenter.callDialogOpen ? 'open' : 'closed', messagePickerToken: presenter.messagePickerToken,
      messageCopyError: presenter.hasMessageError(), callCopyError: presenter.hasCallError() }),
    open: slot => slot === 'message' ? presenter.openMessageSoundDialog() : presenter.openCallRingtoneDialog(),
    dismiss: slot => slot === 'message' ? presenter.dismissMessageError() : presenter.dismissCallError(),
    preset: (slot, value) => slot === 'message' ? presenter.selectMessagePreset(value) : presenter.selectCallPreset(value),
    custom: (slot, source) => slot === 'message' ? presenter.setMessageSoundFromPicker(source.uri, source.displayName || '')
      : presenter.setCallRingtoneFromPicker(source.uri, source.displayName || ''),
    async migrate() {
      const { LegacyRingtoneMigrator } = await production(project, load, ['sound/LegacyRingtoneMigrator.ets'], log);
      return (await new LegacyRingtoneMigrator(channels, repository).migrateCallSlotIfNeeded()).migrated;
    },
    async channelState(slot) {
      return { version: channels.currentChannelVersion(slot), sound: channels.currentSlotSound(slot) };
    }
  };
}

function nativeFixtureWave(title, variant) {
  if (Array.from(title).some(character => character.charCodeAt(0) > 127)) {
    throw new Unsupported('The current native WAV fixture writer supports ASCII metadata only.');
  }
  const nameSize = title.length + 1, paddedNameSize = nameSize + nameSize % 2;
  const infoSize = 4 + 8 + paddedNameSize, dataSize = 1600;
  const bytes = new Uint8Array(12 + 24 + 8 + infoSize + 8 + dataSize);
  const view = new DataView(bytes.buffer);
  const tag = (offset, value) => { for (let i = 0; i < value.length; i++) bytes[offset + i] = value.charCodeAt(i); };
  tag(0, 'RIFF'); view.setUint32(4, bytes.length - 8, true); tag(8, 'WAVE');
  tag(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, 8000, true); view.setUint32(28, 16000, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  tag(36, 'LIST'); view.setUint32(40, infoSize, true); tag(44, 'INFO'); tag(48, 'INAM');
  view.setUint32(52, nameSize, true); tag(56, title);
  const data = 44 + infoSize;
  tag(data, 'data'); view.setUint32(data + 4, dataSize, true);
  for (let i = 0; i < dataSize / 2; i++) {
    view.setInt16(data + 8 + i * 2, Math.round(2000 * Math.sin(i * 2 * Math.PI * (400 + variant * 200) / 8000)), true);
  }
  return bytes;
}

async function prepareNativeAudioSources(args, log, canonicalUris) {
  const native = args.context.native;
  if (!canonicalUris.some(uri => !native.audioSources?.[uri])) return;
  if (!native.sandbox || !native.sandbox.startsWith('/')) {
    throw new Unsupported('A real native filesystem sandbox is required to create missing source fixtures.');
  }
  const fsModule = await args.load('@ohos.file.fs'), fileApi = fsModule.default || fsModule;
  const uriModule = await args.load('@ohos.file.fileuri'), fileUri = uriModule.default || uriModule;
  native.audioSources = native.audioSources || {};
  for (let index = 0; index < canonicalUris.length; index++) {
    const canonicalUri = canonicalUris[index];
    if (native.audioSources[canonicalUri]) continue;
    const title = args.caseSpec.given.displayName || `Runtime tone ${index + 1}`;
    const numericName = canonicalUri.split('/').pop().replace(/[^A-Za-z0-9_-]/g, '_');
    const sourcePath = `${native.sandbox}/${numericName || `source_${index}`}`;
    const uri = fileUri.getUriFromPath(sourcePath);
    if (args.caseSpec.event.copyResult === 'failure') {
      native.audioSources[canonicalUri] = { uri, sourcePath, unavailableSource: true };
      log.checkpoint('native_audio_fixture', { canonicalUri, uri, sourcePath, intentionallyAbsent: true });
      continue;
    }
    const bytes = nativeFixtureWave(title, index);
    const writer = await fileApi.open(sourcePath, fileApi.OpenMode.CREATE | fileApi.OpenMode.WRITE_ONLY | fileApi.OpenMode.TRUNC);
    log.cleanup.push(async () => { await fileApi.unlink(sourcePath); });
    try {
      const written = await fileApi.write(writer.fd, bytes.buffer);
      if (written !== bytes.byteLength) throw new Unsupported('Native audio fixture write was incomplete.');
    } finally { await fileApi.close(writer); }
    const mediaModule = await args.load('@ohos.multimedia.media'), media = mediaModule.default || mediaModule;
    const reader = await fileApi.open(uri, fileApi.OpenMode.READ_ONLY);
    let extractor;
    let metadata;
    try {
      const stat = await fileApi.stat(reader.fd);
      extractor = await media.createAVMetadataExtractor();
      extractor.fdSrc = { fd: reader.fd, offset: 0, length: stat.size };
      metadata = await extractor.fetchMetadata();
    } finally {
      try { if (extractor) await extractor.release(); }
      finally { await fileApi.close(reader); }
    }
    if (metadata.title !== title) {
      throw new Unsupported(`Native metadata extractor did not establish fixture title: ${JSON.stringify(metadata.title)}.`);
    }
    native.audioSources[canonicalUri] = { uri, sourcePath, displayName: metadata.title,
      metadataOrigin: 'native_AVMetadataExtractor', fixtureBytes: bytes.byteLength };
    log.checkpoint('native_audio_fixture', { canonicalUri, ...native.audioSources[canonicalUri],
      scope: 'Real file URI transport mapping for a selected audio source; no system-picker interaction or provider permission grant is claimed.' });
  }
}

async function nativeSounds(args, log) {
  const native = args.context.native, spec = args.caseSpec, g = spec.given || {}, event = spec.event || {};
  const key = spec.key, slot = key.startsWith('call_') ? 'call' : 'message', otherSlot = slot === 'call' ? 'message' : 'call';
  const calls = args.context.productionCalls || native.productionCalls;
  if (!native.context?.filesDir || !native.context.filesDir.startsWith('/') ||
    native.capabilities?.context?.available === false || native.capabilities?.filesystem?.available === false) {
    throw new Unsupported('Native bridge did not establish a real usable Context and filesystem. Domain fakes are not substituted for native I/O.');
  }
  if (!Array.isArray(calls)) throw new Unsupported('Native bridge must expose the actual loader productionCalls array to verify effect order and payloads.');
  if (key === 'message_picker_launch') throw new Unsupported('Picker launch requires the actual page callback and native picker UI; the real-I/O presenter path does not observe that UI.');
  log.result.evidence.push({ nativeIO: true, productionMethodsReplaced: false,
    scope: 'Actual production repository, copier, and channel classes with native imports and Context. Preferences/file I/O and app-local channel ledger or service projections are observed; OS slot/sound application, notification consumer wiring and audible delivery are unverified. Presenter projections are not native UI.' });
  const sourceInputs = key === 'latest_pick_wins' ? event.values : g.pickedUri ? [g.pickedUri] : [];
  await prepareNativeAudioSources(args, log, sourceInputs);
  const sources = [];
  let fileApi;
  async function readBytes(uri) {
    if (!fileApi) { const mod = await args.load('@ohos.file.fs'); fileApi = mod.default || mod; }
    const file = await fileApi.open(uri, fileApi.OpenMode.READ_ONLY);
    try {
      const stat = await fileApi.stat(file.fd);
      if (stat.size > 65536) throw new Unsupported('Use a small native audio fixture (at most 64 KiB) for byte-exact verification.');
      const buffer = new ArrayBuffer(stat.size);
      const length = await fileApi.read(file.fd, buffer);
      if (length !== stat.size) throw new Unsupported('Native fixture read did not return every byte.');
      return Array.from(new Uint8Array(buffer));
    } finally { await fileApi.close(file); }
  }
  for (const canonicalUri of sourceInputs) {
    const fixture = native.audioSources?.[canonicalUri];
    if (!fixture || typeof fixture.uri !== 'string') {
      throw new Unsupported(`Native provider fixture unavailable for ${canonicalUri}; no successful copier outcome is fabricated.`);
    }
    const source = { ...fixture };
    if (event.copyResult !== 'failure') {
      if (g.displayName && source.displayName !== g.displayName) throw new Unsupported('Provider fixture metadata does not establish the canonical display name.');
      source.bytes = await readBytes(source.uri);
      if (!source.bytes.length) throw new Unsupported('The native audio fixture is empty.');
    } else {
      let failed = false;
      try { await readBytes(source.uri); } catch (error) { if (error instanceof Unsupported) throw error; failed = true; }
      if (!failed) throw new Unsupported('The native broken-source fixture is readable; copy-failure setup was not established.');
    }
    sources.push({ ...source, canonicalUri });
  }
  const f = await nativeSoundSetup(args, log);
  await f.refresh();
  const storedSeed = f.stored();
  if (!equal(storedSeed, f.seedState())) {
    log.checkpoint('native_sound_setup_failed', { requestedSeed: f.seedState(), storedSeed });
    throw new Unsupported('Fresh native persistence did not establish the requested GIVEN selections and versions.');
  }
  log.checkpoint('before_event', { stage: 'new_presenter_before_restore', state: f.state(), persisted: storedSeed });
  await f.restore();
  await f.refresh();
  if (g.messageDialog === 'open') f.open('message');
  if (g.callDialog === 'open') f.open('call');
  const before = f.state(), storedBefore = f.stored();
  if (key !== 'restore_independent_slots' && (!equal(before, storedSeed) || !equal(storedBefore, storedSeed))) {
    log.checkpoint('native_sound_setup_failed', { storedSeed, before, storedBefore });
    throw new Unsupported('Native presenter restore did not establish the GIVEN state for this subsequent event.');
  }
  const channelBefore = await f.channelState(slot), otherChannelBefore = await f.channelState(otherSlot), callStart = calls.length;
  const customPath = value => value.uri || value.customFilePath || '';
  const baseSound = value => {
    const kind = value.kind || value.source;
    if (kind === 'preset') return value.presetId;
    if (kind !== 'custom') return kind;
    if ([f.explicitPath, `file://${f.explicitPath}`].includes(customPath(value))) return 'custom_explicit';
    return customPath(value);
  };
  const observe = () => {
    const state = f.state();
    return { messageSound: baseSound(state.message), callRingtone: baseSound(state.call),
      messageDisplayName: state.message.displayName, callDisplayName: state.call.displayName,
      messageChannelVersion: state.messageVersion, callChannelVersion: state.callVersion,
      labelsResolved: Boolean(state.message.displayName && state.call.displayName), ...f.ui() };
  };
  log.checkpoint('before_event', { state: before, persisted: storedBefore, ui: f.ui(), channel: channelBefore,
    otherChannel: otherChannelBefore, channelObservationScope: f.channelObservationScope });
  let migrated;
  const completions = [];
  if (key === 'restore_independent_slots') {
    log.result.observed = observe();
    log.check(equal(f.state(), storedSeed) && equal(f.stored(), storedSeed), { saved: storedSeed, restored: f.state(), reread: f.stored() });
    log.checkpoint('after_event', { observed: log.result.observed, persisted: f.stored() });
    return;
  }
  if (key === 'legacy_migration_guard') migrated = await f.migrate();
  else if (key.endsWith('_preset')) await f.preset(slot, event.value);
  else if (key === 'latest_pick_wins') {
    if (equal(sources[0].bytes, sources[1].bytes)) throw new Unsupported('Race fixtures must contain distinct bytes to identify which selection won.');
    const completed = index => {
      const completion = { index, state: f.state(), calls: copy(calls.slice(callStart)) };
      completions.push(completion);
      log.checkpoint('native_pick_completed', completion);
    };
    const first = f.custom(slot, sources[0]).then(() => completed(0));
    const second = f.custom(slot, sources[1]).then(() => completed(1));
    log.checkpoint('rapid_requests_dispatched', { state: f.state(), calls: calls.slice(callStart) });
    await Promise.all([first, second]);
  } else if (key.endsWith('_custom_copy') || key.endsWith('_copy_failure')) await f.custom(slot, sources[0]);
  else throw new Unsupported(`Native sound event mapping unavailable: ${key}`);
  await f.refresh();
  const after = f.state(), storedAfter = f.stored(), eventCalls = copy(calls.slice(callStart));
  log.checkpoint('native_sound_event_diagnostics', {
    ui: f.ui(),
    copyCalls: eventCalls.filter(call => call.nativeService && call.module === '@ohos.file.fs' && call.method === 'copyFile'),
    productionErrors: eventCalls.filter(call => call.method === 'setCopyError' || call.error),
    sourceTransports: sources.map(source => ({ canonicalUri: source.canonicalUri, uri: source.uri,
      sourcePath: source.sourcePath, metadataOrigin: source.metadataOrigin })),
    filesDir: native.context.filesDir,
    scope: 'Actual production error state and SDK invocations. Picker-style URIs remain unchanged; no raw-path retry or successful-copy substitute.'
  });
  const copies = eventCalls.filter(c => c.class === 'NotificationSoundCopier' && c.method === 'copyToAppFiles' ||
    c.class === 'LocalSoundStorage' && c.method === 'copyFromUri');
  const writes = eventCalls.filter(c => c.class === 'NotificationSoundStore' && c.method === 'save' ||
    c.class === 'SoundPreferenceRepository' && c.method === 'write');
  const channelCalls = eventCalls.filter(c => c.class === 'NotificationChannelGateway' && c.method === 'recreateChannel' ||
    c.class === 'NotificationChannelService' && c.method === 'apply');
  const payloads = channelCalls.map(c => c.class === 'NotificationChannelGateway'
    ? { slot: c.args[1], sound: c.args[2], version: c.args[3] }
    : { slot: c.args[0], sound: c.args[1], version: c.args[1].version });
  log.result.observed = observe();
  if (migrated !== undefined) log.result.observed.migrationApplied = migrated;
  if (key === 'legacy_migration_guard') {
    log.check(equal(before, after) && equal(storedBefore, storedAfter) && writes.length === 0 && channelCalls.length === 0,
      { before, after, storedBefore, storedAfter, writes, channelCalls });
  } else if (key.endsWith('_copy_failure')) {
    const afterFailure = f.ui();
    f.dismiss(slot);
    log.result.observed.channelRecreated = channelCalls.length > 0;
    log.result.observed.dismissible = afterFailure[`${slot}CopyError`] && !f.ui()[`${slot}CopyError`];
    log.check(equal(before, after) && equal(storedBefore, storedAfter) && !afterFailure[`${otherSlot}CopyError`],
      { before, after, storedBefore, storedAfter, afterFailure });
    log.assert('Native copy rejection makes no preference or channel writes', writes.length === 0 && channelCalls.length === 0,
      { writes, channelCalls, copies });
    const channelAfter = await f.channelState(slot), otherChannelAfter = await f.channelState(otherSlot);
    log.assert('Native copy rejection preserves both app-local channel ledgers or service projections',
      equal(channelBefore, channelAfter) && equal(otherChannelBefore, otherChannelAfter),
      { channelBefore, channelAfter, otherChannelBefore, otherChannelAfter, channelObservationScope: f.channelObservationScope });
    log.result.evidence.push({ channelAbsenceScope: 'No original gateway/service request was observed after copy rejection; local ledgers/projections were unchanged. This is not an independently initialized OS channel readback.',
      channelCalls, channelRecreatedObservation: log.result.observed.channelRecreated });
  } else {
    const latestPayload = payloads[payloads.length - 1];
    const writePayloads = writes.map(c => c.class === 'NotificationSoundStore'
      ? { slot, sound: c.args[1][slot === 'message' ? 'messageSound' : 'callRingtone'],
        version: c.args[1][slot === 'message' ? 'messageChannelVersion' : 'callChannelVersion'] }
      : { slot: c.args[0], sound: c.args[1], version: c.args[1].version });
    const preservesOtherSlot = writes.every(c => c.class === 'NotificationSoundStore'
      ? equal(c.args[1][otherSlot === 'message' ? 'messageSound' : 'callRingtone'], before[otherSlot]) &&
        c.args[1][otherSlot === 'message' ? 'messageChannelVersion' : 'callChannelVersion'] === before[`${otherSlot}Version`]
      : c.args[0] === slot);
    const channel = await f.channelState(slot);
    const otherChannelAfter = await f.channelState(otherSlot);
    const channelMatches = f.shape === 'snapshot'
      ? channel.id === `${slot}_notifications_v${after[`${slot}Version`]}` && channel.kind === after[slot].kind && channel.uri === after[slot].uri
      : channel.version === after[`${slot}Version`] && channel.sound === f.channels.resolveSoundForSlot(slot, after[slot]);
    log.assert('Real persistence and gateway payload/local projection preserve the selected value and untouched other slot',
      equal(after, storedAfter) && writes.length > 0 && latestPayload?.slot === slot &&
      equal(latestPayload?.sound, after[slot]) && latestPayload?.version === after[`${slot}Version`] &&
      equal(writePayloads, payloads) && preservesOtherSlot && payloads.every(p => p.slot === slot) &&
      writes.every((write, index) => eventCalls.indexOf(write) < eventCalls.indexOf(channelCalls[index])) &&
      channelMatches && equal(otherChannelBefore, otherChannelAfter) && equal(before[otherSlot], after[otherSlot]) &&
      before[`${otherSlot}Version`] === after[`${otherSlot}Version`],
      { before, after, storedAfter, writes, writePayloads, preservesOtherSlot, payloads, channel, otherChannelBefore, otherChannelAfter,
        channelObservationScope: f.channelObservationScope, osChannelEffectObserved: false });
    if (key.endsWith('_custom_copy') || key === 'latest_pick_wins') {
      const uri = customPath(after[slot]), localPath = uri.startsWith('file://') ? uri.slice(7) : uri;
      const owned = localPath.startsWith(native.context.filesDir + '/') && !localPath.split('/').includes('..') &&
        !sources.some(source => source.uri === uri || source.uri === localPath);
      let bytes;
      if (owned) bytes = await readBytes(localPath);
      const byteMatch = equal(bytes, sources[sources.length - 1].bytes);
      if (owned && byteMatch) log.result.observed[slot === 'message' ? 'messageSound' : 'callRingtone'] =
        key === 'latest_pick_wins' ? 'app_owned_custom_uri_for_B' : 'app_owned_custom_uri';
      log.assert('Production copy produces a distinct app-owned file with the selected source bytes', owned && byteMatch,
        { uri, owned, bytes, sourceBytes: sources[sources.length - 1].bytes });
      if (key === 'message_custom_copy') {
        const persistedUri = customPath(storedAfter[slot]);
        const transientUris = sources.flatMap(source => [source.canonicalUri, source.uri, source.sourcePath].filter(Boolean));
        log.check(!transientUris.includes(persistedUri), { persistedUri, transientUris, storedAfter });
      }
      else if (key === 'latest_pick_wins') {
        const copyUris = copies.map(c => c.class === 'NotificationSoundCopier' ? c.args[1] : c.args[0]);
        log.result.observed.copyOrder = copyUris.map(uri => sources.find(s => s.uri === uri)?.canonicalUri || uri);
        log.checkpoint('gateway_request_order_diagnostic', { requestedVersions: payloads.map(p => p.version),
          payloads, scope: 'Original gateway request order, not OS channel recreation completion order.' });
        const eventOrder = eventCalls.filter(c => copies.includes(c) || writes.includes(c) || channelCalls.includes(c));
        const secondCopyIndex = eventOrder.indexOf(copies[1]);
        const firstChannelIndex = eventOrder.indexOf(channelCalls[0]);
        log.check(owned && byteMatch && copies.length === 2 && channelCalls.length === 2 &&
          firstChannelIndex >= 0 && secondCopyIndex > firstChannelIndex &&
          equal(completions.map(c => c.index), [0, 1]) && completions[0]?.state.messageVersion === before.messageVersion + 1 &&
          completions[1]?.state.messageVersion === before.messageVersion + 2,
        { eventOrder, bytes, payloads, completions, after, storedAfter });
      }
    }
    if (key !== 'message_custom_copy' && key !== 'latest_pick_wins') log.check(
      equal(before[otherSlot], after[otherSlot]) && before[`${otherSlot}Version`] === after[`${otherSlot}Version`], { before, after });
    if (key !== 'latest_pick_wins') log.result.observed.effects = eventCalls.flatMap(c =>
      copies.includes(c) ? ['copy_to_app_storage'] : writes.includes(c) ? [slot === 'message' ? 'persist_message_sound' : 'persist_call_ringtone']
        : []);
  }
  log.checkpoint('after_event', { observed: log.result.observed, state: after, persisted: storedAfter, calls: eventCalls });
}

async function sounds(args, log) {
  const { caseSpec } = args, g = caseSpec.given || {}, event = caseSpec.event || {}, key = caseSpec.key;
  if (args.context?.native) return nativeSounds(args, log);
  if (key === 'restore_independent_slots') {
    throw new Unsupported('Persistence restore requires the production preference repository with external storage bindings; the loader supplies no storage-mock hook. A fixture snapshot cannot establish this transition.');
  }
  if (['message_custom_copy', 'call_custom_copy', 'latest_pick_wins'].includes(key)) {
    throw new Unsupported('Custom sound copying requires the production copier with filesystem-only bindings; the loader supplies no filesystem-mock hook. Owned URI, display name, and copy-dependent race outcomes are not inferred from fixtures.');
  }
  const boundary = soundFixture(g, event, log), f = await soundSetup(args, log, boundary);
  const calls = boundary.calls;
  log.result.evidence.push({ boundaryFakes: ['preference write/read port for fixture setup', 'rejected copy dependency', 'notification channel gateway', 'system picker'],
    scope: 'Runs production presenter/controller transitions and validates write/channel arguments. No successful copy result is fabricated. Persistence restore, successful copying, native rendering, and OS delivery remain unscored.' });
  const checkpoint = label => log.checkpoint(label, { ...f.read(), persisted: f.persisted(), calls });
  await f.restore();
  if (g.messageDialog === 'open') f.open('message');
  if (g.callDialog === 'open') f.open('call');
  const before = f.read(), persistedBefore = f.persisted(), stateBefore = f.state(), callStart = calls.length;
  const slot = key.startsWith('call_') ? 'call' : 'message';
  checkpoint('before_event');
  if (key === 'message_picker_launch') {
    f.picker('message');
    log.result.observed = f.read();
    const launched = calls.slice(callStart).filter(call => call.name === 'open_audio_picker');
    if (launched.length) log.result.observed.effects = launched.map(call => call.name);
    else log.unavailable(['effects'], 'Presenter picker token is observable, but no native picker launch was executed.');
    checkpoint('after_event');
    log.check(equal(persistedBefore, f.persisted()), { before: persistedBefore, after: f.persisted() });
    return;
  }
  if (key === 'legacy_migration_guard') {
    const migrated = await f.migrate();
    log.result.observed = { ...f.read(), migrationApplied: migrated };
    checkpoint('after_event');
    log.check(equal(persistedBefore, f.persisted()) && !calls.slice(callStart).some(call =>
      ['persist_slot', 'persist_snapshot', 'recreate_channel'].includes(call.name)),
    { before: persistedBefore, after: f.persisted(), calls: calls.slice(callStart) });
    return;
  }
  if (key === 'message_preset' || key === 'call_preset') await f.preset(slot, event.value);
  else if (['message_copy_failure', 'call_copy_failure'].includes(key)) await f.custom(slot, g.pickedUri);
  else throw new Unsupported(`Sound transition API mapping unavailable: ${key}`);
  log.result.observed = f.read();
  const effects = [], eventCalls = calls.slice(callStart);
  for (const call of eventCalls) {
    if (call.name === 'copy_completed') effects.push('copy_to_app_storage');
    if (call.name === 'persist_snapshot' || call.name === 'persist_slot' && call.slot === slot) {
      effects.push(slot === 'message' ? 'persist_message_sound' : 'persist_call_ringtone');
    }
  }
  log.result.observed.effects = effects;
  checkpoint('after_event');
  const stateAfter = f.state(), storedAfter = f.storedState();
  const writes = eventCalls.filter(call => call.name === 'persist_snapshot' || call.name === 'persist_slot');
  const channels = eventCalls.filter(call => call.name === 'recreate_channel');
  const otherSlot = slot === 'message' ? 'call' : 'message';
  if (key.endsWith('_preset')) {
    const payloadMatches = call => call.name === 'persist_snapshot'
      ? equal(call.snapshot.messageSound, stateAfter.message) && equal(call.snapshot.callRingtone, stateAfter.call) &&
        call.snapshot.messageChannelVersion === stateAfter.messageVersion && call.snapshot.callChannelVersion === stateAfter.callVersion
      : call.slot === slot && equal(call.preference, stateAfter[slot]);
    log.assert('Sound persistence and gateway request arguments match the selected sound and version without changing the other slot',
      equal(storedAfter, stateAfter) && writes.length > 0 && writes.every(payloadMatches) &&
      channels.length > 0 && channels.every(call => call.slot === slot &&
        equal(call.sound, stateAfter[slot]) && call.version === stateAfter[`${slot}Version`]) &&
      equal(stateBefore[otherSlot], stateAfter[otherSlot]) && stateBefore[`${otherSlot}Version`] === stateAfter[`${otherSlot}Version`],
    { slot, before: stateBefore, after: stateAfter, storedAfter, writes, channels,
      scope: 'Injected gateway argument checks only; no notification-service completion/readback.' });
  }
  if (key.endsWith('copy_failure')) {
    log.assert('Rejected copy preserves both persisted selections and versions without persistence or channel writes',
      equal(stateBefore, stateAfter) && equal(persistedBefore, f.persisted()) && writes.length === 0 && channels.length === 0,
    { before: stateBefore, after: stateAfter, persistedBefore, persistedAfter: f.persisted(), writes, channels });
    log.result.observed.channelRecreated = eventCalls.some(call => call.name === 'recreate_channel');
    log.result.evidence.push({ channelAbsenceScope: 'Copy-rejection check observes non-invocation of the injected gateway boundary, not OS channel state.',
      channels, channelRecreatedObservation: log.result.observed.channelRecreated });
    const afterFailure = f.read();
    f.dismiss(slot);
    log.result.observed.dismissible = afterFailure[`${slot}CopyError`] && !f.read()[`${slot}CopyError`];
    checkpoint('error_dismissed');
    if (slot === 'message') log.check(before.messageSound === afterFailure.messageSound &&
      before.messageChannelVersion === afterFailure.messageChannelVersion && equal(persistedBefore, f.persisted()),
    { before, afterFailure, persisted: f.persisted() });
    else log.check(afterFailure.callCopyError && !afterFailure.messageCopyError &&
      before.messageSound === afterFailure.messageSound && before.messageChannelVersion === afterFailure.messageChannelVersion,
    { before, afterFailure });
  } else if (slot === 'message') log.check(before.callRingtone === f.read().callRingtone && before.callChannelVersion === f.read().callChannelVersion,
    { before, after: f.read() });
  else log.check(before.messageSound === f.read().messageSound && before.messageChannelVersion === f.read().messageChannelVersion,
    { before, after: f.read() });
}

async function runCase({ taskId, caseSpec, project, load, context, native, trace = () => {} }) {
  const log = recorder(caseSpec, trace);
  if (native) context = { ...context, native };
  const args = { taskId, caseSpec, project, load, context, uiAborted: false };
  const entry = context?.native?.entryProbe;
  if (entry?.observationLevel === 'native_candidate_ui' && entry.before?.taskId === taskId &&
    entry.after?.taskId === taskId && entry.before.roots?.length > 0) {
    log.result.evidence.push({ nativeEntryProbe: copy(entry),
      scope: 'Actual candidate entry-page controls and action; absence is not inferred from missing production exports and does not fabricate downstream canonical state.' });
    log.checkpoint('native_entry_before_event', entry.before);
    log.checkpoint('native_entry_after_event', entry.after);
  }
  log.checkpoint('before_event', { taskId, caseId: caseSpec.caseId, given: caseSpec.given, event: caseSpec.event,
    stage: 'fixture_requested' });
  let timer;
  try {
    const execute = async () => {
      if (typeof context?.native?.runTasks16To18UI === 'function' &&
        ((taskId === '16_identity_reset' && ['oidc_handle_routes_and_resets', 'cancel_cleans_up'].includes(caseSpec.key)) ||
         (taskId === '17_pinned_messages' && ['open_loading', 'view_in_timeline'].includes(caseSpec.key)) ||
         (taskId === '18_custom_notification_sounds' && caseSpec.key === 'message_picker_launch'))) {
        return nativePageTransition(args, log);
      }
      if (taskId === '16_identity_reset') await identity(args, log);
      else if (taskId === '17_pinned_messages') await pinned(args, log);
      else if (taskId === '18_custom_notification_sounds') await sounds(args, log);
      else throw new Unsupported(`Task not handled: ${taskId}`);
    };
    await Promise.race([execute(), new Promise((_resolve, reject) => {
      // Device accessibility readback can outlast the domain-only budget.
      // This is an execution watchdog, not a business transition deadline.
      const timeout = typeof context?.native?.runTasks16To18UI === 'function' ? 45000 : 5000;
      timer = setTimeout(() => {
        args.uiAborted = true;
        context?.native?.cancelTasks16To18UI?.();
        reject(new Unsupported(`Production transition did not settle within ${timeout / 1000} seconds; no outcome inferred.`));
      }, timeout);
    })]);
  } catch (error) {
    if (!(error instanceof Unsupported)) throw error;
    log.result.unsupported = error.message;
    if (args.uiAborted && typeof context?.native?.getTasks16To18UIProgress === 'function') {
      const partial = context.native.getTasks16To18UIProgress();
      const result = partial?.result;
      if (result?.taskId === taskId && result?.caseId === caseSpec.caseId && result?.key === caseSpec.key &&
        result?.bundleName === context.native.bundleName && Array.isArray(result.checkpoints)) {
        log.result.evidence.push({ nativePageTransitionPartial: copy(partial),
          scope: 'Watchdog diagnostic only; no incomplete checkpoint or click is promoted into a scored outcome.' });
        for (const checkpoint of result.checkpoints) log.checkpoint(`native_ui_partial_${checkpoint.label}`, checkpoint);
        log.checkpoint('native_ui_partial_live_picker', partial.livePicker);
      }
    }
    log.checkpoint('after_event', { unsupported: error.message, observed: log.result.observed });
  } finally {
    clearTimeout(timer);
    for (const release of log.cleanup) {
      let cleanupTimer;
      try {
        const operation = release();
        if (operation && typeof operation.then === 'function') {
          await Promise.race([operation, new Promise((_resolve, reject) => {
            cleanupTimer = setTimeout(() => reject(new Unsupported('Native fixture cleanup did not settle within 1 second.')), 1000);
          })]);
        }
      }
      catch (error) {
        log.result.unsupported = `Runtime fixture cleanup failed: ${error.message}`;
        log.checkpoint('cleanup_error', { error: error.message });
      } finally { clearTimeout(cleanupTimer); }
    }
    await drain();
  }
  withholdUnsupportedChannelEffects(taskId, caseSpec, log);
  return log.finish();
}

module.exports = { runCase };
