'use strict';

const FEATURE = 'entry/src/main/ets/features/IdentityResetFeature.ets';
const BASE_FEATURE = 'entry/src/main/ets/features/SecureBackupBase.ets';
const copy = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
const drain = async () => { for (let index = 0; index < 24; index++) await Promise.resolve(); };

function treeHasText(node, expected) {
  if (!node || typeof node !== 'object') return false;
  const attrs = node.$attrs || node.attributes || {};
  if (attrs.text === expected || attrs.label === expected) return true;
  return Object.values(node).some(value => Array.isArray(value)
    ? value.some(child => treeHasText(child, expected))
    : value && typeof value === 'object' && treeHasText(value, expected));
}

function state(presenter) {
  const manager = presenter.manager;
  return {
    confirmationVisible: presenter.confirmationVisible,
    handleState: manager.handleState,
    screen: presenter.screen,
    password: presenter.password,
    resetAction: presenter.resetAction,
    progressVisible: presenter.progressVisible,
    errorVisible: presenter.errorMessage.length > 0,
    retryEnabled: presenter.screen === 'reset_root' && presenter.errorMessage.length > 0 && !presenter.progressVisible,
    resetJobActive: manager.resetJobActive,
    completionWatcherActive: manager.completionWatcherActive,
    completionCount: presenter.completionCount,
    approvalUrl: presenter.approvalUrl,
    approvalSurface: presenter.approvalSurface,
    oidcOpenCount: presenter.oidcOpenCount,
    cleanupHistory: manager.cleanupHistory.slice()
  };
}

function fixture(types, options = {}) {
  const starts = options.starts || [deferred()];
  const reset = options.reset || deferred();
  const calls = [];
  let startIndex = 0;
  const kind = options.kind || types.ResetAuthenticationType.Password;
  const handle = {
    kind,
    url: options.url || 'https://id.example/reset',
    cancelled: false,
    async resetPassword(password) {
      calls.push({ name: 'reset_password', password, sameHandle: this === handle });
      return reset.promise;
    },
    async resetOidc() {
      calls.push({ name: 'reset_oidc', sameHandle: this === handle });
      if (options.oidcImmediate) return;
      return reset.promise;
    },
    async cancel() {
      calls.push({ name: 'cancel_reset_handle', sameHandle: this === handle });
      this.cancelled = true;
    }
  };
  const service = {
    async startIdentityReset() {
      calls.push({ name: 'start_identity_reset', index: startIndex });
      const operation = starts[Math.min(startIndex, starts.length - 1)];
      startIndex += 1;
      return operation.promise;
    }
  };
  const manager = new types.IdentityResetFlowManager(service);
  const presenter = new types.IdentityResetPresenter(manager);
  return { starts, reset, calls, handle, service, manager, presenter };
}

async function verifyMountedPage(native, expectedTitle) {
  const snapshot = native.ui.snapshot();
  if (!snapshot.completeTree || !snapshot.candidateRouteVerified || !treeHasText(snapshot.tree, expectedTitle)) {
    throw new Error('Actual candidate page was not mounted with the expected positive title: ' + expectedTitle);
  }
  return snapshot;
}

async function runBase(args, result, checkpoint) {
  if (typeof args.native.runTask16BaseUI !== 'function') throw new Error('Base requires the original-app UiTest entry probe');
  const raw = await args.native.runTask16BaseUI();
  if (raw.failure || !raw.entryExecuted || !raw.eventExecuted || raw.frames?.length !== 2 ||
      raw.positiveControl !== 'Backup state: enabled') throw new Error('Actual base entry probe incomplete: ' + JSON.stringify(raw.failure || {}));
  const before = raw.frames[0];
  const after = raw.frames[1];
  const absent = frame => frame.controls.filter(item => ['finalTitle', 'finalEntry'].includes(item.name))
    .every(item => !item.present);
  if (!absent(before) || !absent(after)) throw new Error('Base unexpectedly renders the final-only identity-reset entry');
  const presenter = args.evaluatorRole === 'agent' ? null : new (await args.load(BASE_FEATURE)).SecureBackupBasePresenter();
  checkpoint('base_actual_page_before_entry', { windowIdentity: before.windowIdentity,
    backupState: presenter ? presenter.backupState : 'rendered_runtime_positive_control',
    resetEntryVisible: false, expectedEvent: args.caseSpec.event });
  if (presenter) presenter.enableBackup();
  const backupState = presenter ? presenter.backupState : 'enabled';
  result.observed = {};
  result.invariantChecks = [];
  result.evidence.push({ kind: 'native_base_entry_absence', runtime: 'device_ohosTest_ArkVM_ArkUI', raw,
    actualProductionAction: presenter ? 'SecureBackupBasePresenter.enableBackup' : 'physical Enable backup control', resetEntryVisibleBefore: false,
    resetEntryVisibleAfter: false, finalOnlyEventDispatched: false });
  checkpoint('base_actual_page_after_rejected_entry', { windowIdentity: after.windowIdentity, backupState,
    resetEntryVisible: false, observed: result.observed });
}

async function candidateHasFinalEntry(args, result, checkpoint) {
  if (typeof args.native.runTask16BaseUI !== 'function') throw new Error('Agent requires the runtime entry classifier');
  const raw = await args.native.runTask16BaseUI();
  if (raw.failure || !raw.entryExecuted || !raw.eventExecuted || raw.frames?.length < 2) {
    throw new Error('Agent runtime entry classifier incomplete: ' + JSON.stringify(raw.failure || {}));
  }
  result.evidence.push({ kind: 'native_candidate_entry_classification', raw });
  checkpoint('candidate_runtime_entry', { classification: raw.classification, positiveControl: raw.positiveControl });
  if (raw.classification === 'feature_entry_present') return true;
  if (raw.classification === 'feature_entry_absent' && raw.positiveControl === 'Backup state: enabled') return false;
  throw new Error('Agent runtime entry classifier returned no strict classification');
}

async function runFinal(args, result, checkpoint) {
  const types = await args.load(FEATURE);
  const key = args.caseSpec.key;
  const invariants = new Map();
  const mark = (index, passed, observed) => invariants.set(args.caseSpec.invariants[index], {
    description: args.caseSpec.invariants[index], passed: Boolean(passed), observed: copy(observed)
  });
  if (!['oidc_handle_routes_and_resets', 'cancel_cleans_up'].includes(key)) {
    result.evidence.push({ kind: 'native_final_domain_entry', runtime: 'device_ohosTest_ArkVM',
      scope: 'Production presenter/manager/handle execution; no rendered-state claim for this case' });
  }

  if (key === 'continue_requests_confirmation') {
    const f = fixture(types);
    checkpoint('before_event', state(f.presenter));
    f.presenter.continue();
    result.observed = { confirmationVisible: f.presenter.confirmationVisible, startResetCount: 0 };
    mark(0, f.calls.length === 0 && f.manager.handleState === types.ResetOperationState.Uninitialized,
      { calls: f.calls, state: state(f.presenter) });
    checkpoint('after_event', state(f.presenter));
  } else if (key === 'dismiss_confirmation') {
    const f = fixture(types);
    f.presenter.continue();
    checkpoint('before_event', state(f.presenter));
    f.presenter.dismissConfirmation();
    result.observed = { confirmationVisible: f.presenter.confirmationVisible, startResetCount: 0 };
    mark(0, f.calls.length === 0, { calls: f.calls, state: state(f.presenter) });
    checkpoint('after_event', state(f.presenter));
  } else if (key === 'confirm_starts_handle') {
    const start = deferred();
    const f = fixture(types, { starts: [start] });
    f.presenter.continue();
    checkpoint('before_event', state(f.presenter));
    const first = f.presenter.confirmReset();
    await drain();
    const second = f.presenter.confirmReset();
    await drain();
    result.observed = { confirmationVisible: f.presenter.confirmationVisible,
      handleState: f.manager.handleState, effect: 'start_identity_reset' };
    checkpoint('loading_reused', { state: state(f.presenter), calls: f.calls });
    start.resolve(f.handle);
    await Promise.all([first, second]);
    mark(0, f.calls.filter(call => call.name === 'start_identity_reset').length === 1 &&
      f.manager.currentHandle === f.handle && f.manager.handleState === types.ResetOperationState.Success,
    { calls: f.calls, sameHandle: f.manager.currentHandle === f.handle });
    checkpoint('after_event', state(f.presenter));
  } else if (key === 'password_handle_routes') {
    const f = fixture(types);
    const states = [];
    f.manager.subscribeHandleState(value => states.push(value));
    f.presenter.continue();
    const pending = f.presenter.confirmReset();
    checkpoint('before_event', { state: state(f.presenter), stateSequence: states });
    f.starts[0].resolve(f.handle);
    await pending;
    result.observed = { handleState: f.manager.handleState, screen: f.presenter.screen, password: f.presenter.password };
    mark(0, f.manager.currentHandle === f.handle, { sameHandle: true, calls: f.calls });
    checkpoint('after_event', { state: state(f.presenter), stateSequence: states });
  } else if (key === 'oidc_handle_routes_and_resets') {
    if (typeof args.native.runTask16UI !== 'function') throw new Error('Final OIDC case requires the original-page native UI probe');
    const raw = await args.native.runTask16UI(args.caseSpec);
    const before = raw.frames && raw.frames.find(frame => frame.label === 'before_event');
    const after = raw.frames && raw.frames.find(frame => frame.label === 'after_event');
    const presenter = after && after.presenter;
    const web = after && after.controls.find(control => control.name === 'oidcWebview');
    const resetCall = presenter && presenter.calls.find(call => call.owner === 'oidc_handle' && call.method === 'resetOidc' && call.returned);
    if (raw.failure || !raw.entryExecuted || !raw.confirmExecuted || !raw.eventExecuted || !before || !after || !presenter) {
      throw new Error('Original-page OIDC transition incomplete: ' + JSON.stringify(raw.failure || {}));
    }
    result.observed = { handleState: presenter.handleState, effect: 'open_oidc_approval',
      url: presenter.approvalUrl, pollEffect: resetCall ? 'reset_oidc' : null };
    mark(0, web && web.present && web.visible && web.enabled && resetCall,
      { webview: web, resetOidcCall: resetCall, approvalSurface: presenter.approvalSurface });
    result.evidence.push({ nativeOriginalPage: raw });
    checkpoint('before_event', before);
    checkpoint('after_event', after);
  } else if (key === 'handle_failure_recovers') {
    const first = deferred();
    const retry = deferred();
    const f = fixture(types, { starts: [first, retry] });
    const sequence = [];
    f.manager.subscribeHandleState(value => sequence.push(value));
    f.presenter.continue();
    const failed = f.presenter.confirmReset();
    checkpoint('before_external_failure', { state: state(f.presenter), stateSequence: sequence });
    first.resolve(undefined);
    await failed;
    const stable = state(f.presenter);
    checkpoint('stable_after_cleanup', { state: stable, stateSequence: sequence });
    f.presenter.continue();
    const retryOperation = f.presenter.confirmReset();
    await drain();
    const retryState = state(f.presenter);
    result.observed = { failureObserved: sequence.includes(types.ResetOperationState.Failure),
      stateSequence: sequence.slice(), stableHandleState: stable.handleState, screen: stable.screen,
      progressVisible: stable.progressVisible, retryEnabled: stable.retryEnabled,
      retryHandleState: retryState.handleState };
    const exact = JSON.stringify(sequence) === JSON.stringify(['uninitialized', 'loading', 'failure', 'uninitialized', 'loading']);
    mark(0, sequence.includes('failure') && !sequence.includes('success'), { stateSequence: sequence });
    mark(1, stable.handleState === 'uninitialized' && stable.screen === 'reset_root' && stable.retryEnabled,
      { stable, cleanupHistory: f.manager.cleanupHistory });
    mark(2, exact && retryState.handleState === 'loading' && f.calls.filter(call => call.name === 'start_identity_reset').length === 2,
      { stateSequence: sequence, retryState, calls: f.calls });
    checkpoint('retry_loading', { state: retryState, stateSequence: sequence, observed: result.observed });
    retry.resolve(f.handle);
    await retryOperation;
  } else if (key === 'password_submit_calls_handle') {
    const reset = deferred();
    const f = fixture(types, { reset });
    f.manager.currentHandle = f.handle;
    f.manager.handleState = types.ResetOperationState.Success;
    f.manager.completionWatcherActive = true;
    f.presenter.screen = types.IdentityResetScreen.Password;
    f.presenter.setPassword(args.caseSpec.given.password);
    checkpoint('before_event', state(f.presenter));
    const pending = f.presenter.submitPassword();
    await drain();
    const loading = state(f.presenter);
    const call = f.calls.find(item => item.name === 'reset_password');
    result.observed = { resetAction: loading.resetAction, effect: call && call.name,
      password: call && call.password, progressVisible: loading.progressVisible };
    const empty = fixture(types);
    empty.manager.currentHandle = empty.handle;
    empty.manager.handleState = types.ResetOperationState.Success;
    empty.presenter.screen = types.IdentityResetScreen.Password;
    await empty.presenter.submitPassword();
    mark(0, call && call.sameHandle && empty.calls.every(item => item.name !== 'reset_password'),
      { submitted: call, emptyCalls: empty.calls });
    checkpoint('after_event', { state: loading, calls: f.calls });
    reset.resolve();
    await pending;
  } else if (key === 'password_failure_clears_on_edit') {
    const reset = deferred();
    const f = fixture(types, { reset });
    f.manager.currentHandle = f.handle;
    f.manager.handleState = types.ResetOperationState.Success;
    f.manager.completionWatcherActive = true;
    f.presenter.screen = types.IdentityResetScreen.Password;
    f.presenter.setPassword(args.caseSpec.given.password);
    const pending = f.presenter.submitPassword();
    checkpoint('before_external_failure', { state: state(f.presenter), calls: f.calls });
    reset.reject(new Error('Injected password rejection'));
    await pending;
    const failed = state(f.presenter);
    f.presenter.setPassword(args.caseSpec.event.value);
    const edited = state(f.presenter);
    result.observed = { resetAction: edited.resetAction, password: edited.password,
      errorVisible: edited.errorVisible, retryEnabled: edited.resetAction === 'uninitialized' && f.manager.currentHandle === f.handle };
    mark(0, failed.resetAction === 'failure' && f.manager.currentHandle === f.handle,
      { failed, edited, sameHandle: f.manager.currentHandle === f.handle });
    checkpoint('after_event', { failed, edited, calls: f.calls });
  } else if (key === 'success_waits_for_verification') {
    const reset = deferred();
    const f = fixture(types, { reset });
    f.manager.currentHandle = f.handle;
    f.manager.handleState = types.ResetOperationState.Success;
    f.manager.completionWatcherActive = true;
    f.presenter.screen = types.IdentityResetScreen.Password;
    f.presenter.setPassword('secret');
    const pending = f.presenter.submitPassword();
    checkpoint('before_reset_success', state(f.presenter));
    reset.resolve();
    await pending;
    const waiting = state(f.presenter);
    f.presenter.sessionVerified();
    f.presenter.sessionVerified();
    const completed = state(f.presenter);
    result.observed = { resetAction: waiting.resetAction,
      progressVisibleUntilVerified: waiting.progressVisible, completionCount: completed.completionCount };
    mark(0, waiting.completionCount === 0 && waiting.progressVisible && completed.completionCount === 1,
      { waiting, completed });
    checkpoint('after_event', { waiting, completed });
  } else if (key === 'cancel_cleans_up') {
    if (typeof args.native.runTask16UI !== 'function') throw new Error('Final cleanup case requires the original-page native UI probe');
    const raw = await args.native.runTask16UI(args.caseSpec);
    const before = raw.frames && raw.frames.find(frame => frame.label === 'before_event');
    const after = raw.frames && raw.frames.find(frame => frame.label === 'after_event');
    if (raw.failure || !before || !after || !raw.eventExecuted) throw new Error('Original-page cancellation incomplete');
    const lifecycle = [];
    for (const [method, reason] of [['oidcReturned', 'oidc_return'], ['dispose', 'node_destroy']]) {
      const f = fixture(types, { kind: types.ResetAuthenticationType.Oidc, oidcImmediate: true });
      f.manager.currentHandle = f.handle;
      f.manager.handleState = types.ResetOperationState.Success;
      f.manager.resetJobActive = true;
      f.manager.completionWatcherActive = true;
      await f.presenter[method]();
      lifecycle.push({ method, reason, state: state(f.presenter), calls: f.calls });
    }
    result.observed = { effect: 'cancel_reset_handle', handleState: after.presenter.handleState,
      resetJobActive: after.presenter.resetJobActive, completionWatcherActive: after.presenter.completionWatcherActive };
    const cleanupOk = lifecycle.every(item => item.state.handleState === 'uninitialized' &&
      item.state.cleanupHistory.includes(item.reason) && item.calls.some(call => call.name === 'cancel_reset_handle'));
    mark(0, cleanupOk && after.presenter.handleState === 'uninitialized', { originalPage: { before, after }, lifecycle });
    result.evidence.push({ nativeOriginalPage: raw, lifecycle });
    checkpoint('before_event', before);
    checkpoint('after_event', after);
  } else {
    throw new Error('Unsupported Task16 revision5 case: ' + key);
  }

  result.invariantChecks = (args.caseSpec.invariants || []).map(description => invariants.get(description) || {
    description, passed: false, observed: { missingEvaluatorBinding: true }
  });
}

async function runCase(args) {
  const result = { observed: {}, invariantChecks: [], evidence: [], unsupportedObservations: [],
    observationLevel: 'native_device_ArkVM_production_state_transition' };
  const checkpoint = (label, value) => {
    const data = copy(value);
    result.evidence.push({ label, data });
    args.trace(label, data);
  };
  checkpoint('revision5_contract_bound', { taskId: args.taskId, caseId: args.caseSpec.caseId,
    traceDigest: args.caseSpec.traceDigest, revision: 5 });
  if (args.taskId !== '16_identity_reset') throw new Error('Task16 revision5 adapter received another task');
  if (!['base', 'final', 'agent'].includes(args.evaluatorRole)) throw new Error('Task16 evaluator role missing');
  if (args.evaluatorRole === 'base') await runBase(args, result, checkpoint);
  else if (args.evaluatorRole === 'final') await runFinal(args, result, checkpoint);
  else if (await candidateHasFinalEntry(args, result, checkpoint)) await runFinal(args, result, checkpoint);
  else await runBase(args, result, checkpoint);
  return result;
}

module.exports = { runCase, treeHasText };
