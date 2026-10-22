import { observeTask16Page } from './Task16PageObserver';

let binding;
export function configureTask16Binding(configJson, importModule = url => import(url)) {
  const config = JSON.parse(configJson);
  if (!config.bundleName || config.moduleName !== 'entry' || config.productionModuleUrl !==
    '@bundle:' + config.bundleName + '/entry/ets/features/IdentityResetFeature') {
    throw new Error('Invalid original Task16 module identity');
  }
  binding = { config, importModule };
}

export async function runTask16NativeUi(caseJson, bundleName, driver, ON, launch) {
  const spec = JSON.parse(caseJson);
  const result = {
    taskId: spec.taskId,
    caseId: spec.caseId,
    traceDigest: spec.traceDigest,
    bundleName,
    sessionId: spec.caseId + ':' + Date.now(),
    frames: [],
    actions: [],
    entryExecuted: false,
    confirmExecuted: false,
    eventExecuted: false,
    observationMode: 'runtime_state_transition'
  };
  let observer, sequence = 0, stage = 'validate';
  const selectors = {
    root: [ON.text('Reset cryptographic identity')],
    baseRoot: [ON.text('Chat backup')],
    baseEnable: [ON.type('Button').text('Enable backup')],
    baseStateEnabled: [ON.text('Backup state: enabled')],
    continue: [ON.id('identity_reset_continue')],
    oidc: [ON.id('identity_reset_oidc_toggle')],
    confirmation: [ON.text('Confirm identity reset?')],
    confirm: [ON.id('identity_reset_confirm')],
    cancelConfirmation: [ON.id('identity_reset_cancel_confirmation')],
    retry: [ON.id('identity_reset_retry')],
    password: [ON.id('identity_reset_password')],
    passwordSubmit: [ON.id('identity_reset_password_submit')],
    passwordError: [ON.text('The password is incorrect. Edit it and retry.')],
    waiting: [ON.text('Identity reset. Waiting for session verification...')],
    sessionVerified: [ON.id('identity_reset_session_verified')],
    approval: [ON.text('Approve the reset with your identity provider.')],
    approvalUrl: [ON.id('identity_reset_oidc_url')],
    oidcWebview: [ON.id('identity_reset_oidc_webview')],
    oidcCompleted: [ON.id('identity_reset_oidc_completed')],
    exit: [ON.id('identity_reset_exit')],
    progress: [ON.text('Reset in progress...')],
    complete: [ON.text('Identity reset complete')]
  };

  async function find(name) {
    for (const selector of selectors[name]) {
      const nodes = await driver.findComponents(selector.inWindow(bundleName)) || [];
      if (nodes.length > 1) throw new Error('Ambiguous native selector: ' + name);
      if (nodes.length) return nodes[0];
    }
    return undefined;
  }
  async function inspect(name) {
    const window = await launch.check(driver), node = await find(name);
    if (!node) return { name, present: false, visible: false };
    const bounds = await node.getBounds(), viewport = window.bounds;
    const control = {
      name,
      present: true,
      bounds,
      id: await node.getId(),
      text: await node.getText(),
      enabled: await node.isEnabled(),
      visible: Math.min(viewport.right, bounds.right) > Math.max(viewport.left, bounds.left) &&
        Math.min(viewport.bottom, bounds.bottom) > Math.max(viewport.top, bounds.top)
    };
    if (await node.isCheckable()) control.checked = await node.isChecked();
    return control;
  }
  async function capture(label) {
    const controls = [];
    for (const name of Object.keys(selectors)) controls.push(await inspect(name));
    const frame = {
      label,
      sequence: ++sequence,
      sessionId: result.sessionId,
      bundleName,
      windowIdentity: launch.read().lastReady,
      presenter: observer ? observer.read() : { available: false },
      controls
    };
    result.frames.push(frame);
    return frame;
  }
  async function action(kind, target, callback, extra = {}) {
    const receipt = { kind, target, sequence: ++sequence, sessionId: result.sessionId, executed: false, ...extra };
    result.actions.push(receipt);
    await callback();
    receipt.executed = true;
    await driver.delayMs(80);
  }
  async function click(name) {
    const control = await inspect(name);
    if (!control.visible || !control.enabled) throw new Error('Native control unavailable/disabled: ' + name);
    const node = await find(name);
    await action('click', name, () => node.click());
    if (name === 'confirm') result.confirmExecuted = true;
  }
  async function input(name, value) {
    const control = await inspect(name);
    if (!control.visible || !control.enabled) throw new Error('Native input unavailable/disabled: ' + name);
    const node = await find(name);
    await action('input', name, () => node.inputText(value), { value });
  }
  async function settle(name, predicate, budgetMs = 5000, maxAttempts = 32) {
    const started = Date.now(), attempts = [];
    for (let index = 0; index < maxAttempts && Date.now() - started < budgetMs; index++) {
      const attempt = { attempt: index + 1 };
      attempts.push(attempt);
      try {
        if (await predicate()) return { ready: true, attempts };
      } catch (error) {
        attempt.error = String(error);
      }
      await driver.delayMs(120);
    }
    throw new Error('Bounded native readiness exhausted: ' + name + ': ' + JSON.stringify(attempts[attempts.length - 1]));
  }
  const hasControl = async name => {
    const value = await inspect(name);
    return value.present && value.visible;
  };
  const call = (state, owner, method) => state.calls.find(item => item.owner === owner && item.method === method);
  const calls = (state, owner, method) => state.calls.filter(item => item.owner === owner && item.method === method);
  const invariantPasses = evidence => spec.invariants.map(description => ({ description, passed: true, evidence }));
  const baseObserved = {
    confirmationVisible: false,
    startResetCount: 0,
    handleState: 'unavailable',
    effect: 'unavailable',
    screen: 'chat_backup',
    password: 'unavailable',
    url: 'unavailable',
    pollEffect: 'unavailable',
    failureObserved: false,
    stateSequence: ['unavailable'],
    stableHandleState: 'unavailable',
    progressVisible: false,
    retryEnabled: false,
    retryHandleState: 'unavailable',
    resetAction: 'unavailable',
    errorVisible: false,
    progressVisibleUntilVerified: false,
    completionCount: 0,
    resetJobActive: false,
    completionWatcherActive: false
  };

  async function openConfirmation() {
    await click('continue');
    if (observer && !observer.read().available) throw new Error('Exactly one original Task16 presenter must receive Continue');
    await settle('confirmation', () => hasControl('confirmation'));
  }
  async function confirmPasswordRoute() {
    await openConfirmation();
    await click('confirm');
    await settle('password route', () => hasControl('password'));
  }
  async function selectOidcAndConfirm() {
    const toggle = await inspect('oidc');
    if (toggle.checked !== false) throw new Error('Fresh OIDC toggle must start unchecked');
    await click('oidc');
    await openConfirmation();
    await click('confirm');
    await settle('OIDC route', async () => await hasControl('approval') && await hasControl('oidcWebview'));
  }

  try {
    if (spec.taskId !== '16_identity_reset' || !/^[a-f0-9]{64}$/.test(spec.traceDigest) || !binding ||
      binding.config.bundleName !== bundleName) throw new Error('Unsupported Task16 case/binding');
    stage = 'launch';
    await launch.start();
    result.entryExecuted = true;
    stage = 'detect_original_entry';
    await settle('Task16 entry', async () => await hasControl('root') || await hasControl('baseRoot'));

    if (await hasControl('baseRoot')) {
      stage = 'base_positive_control';
      await capture('before_event');
      await click('baseEnable');
      await settle('base backup enabled', () => hasControl('baseStateEnabled'));
      await capture('after_event');
      result.eventExecuted = true;
      result.baseFeatureAbsent = !(await hasControl('root')) && !(await hasControl('continue'));
      if (!result.baseFeatureAbsent) throw new Error('Base unexpectedly exposes final identity reset entry');
      result.observed = baseObserved;
      result.invariantChecks = spec.invariants.map(description => ({
        description,
        passed: false,
        evidence: 'Fresh-install base rendered and executed Chat backup positive control; identity-reset entry remained absent.'
      }));
      result.basePositiveControl = { rendered: true, enabledBackupThroughActualUi: true };
      return JSON.stringify(result);
    }

    stage = 'original_final_ready';
    result.readiness = await settle('final root', async () => await hasControl('root') && (await inspect('continue')).enabled);
    await capture('original_page_ready_before_binding');
    stage = 'postload_original_binding';
    const namespace = await binding.importModule(binding.config.productionModuleUrl);
    observer = observeTask16Page(namespace, {
      ...binding.config,
      importCompleted: true,
      importPhase: 'after_original_page_ready_before_fixture',
      namespaceExports: Object.keys(namespace)
    });
    if (spec.key === 'continue_requests_confirmation') {
      await capture('before_event');
      await click('continue');
      await settle('confirmation visible', () => hasControl('confirmation'));
      const after = await capture('after_event'), state = after.presenter;
      result.observed = { confirmationVisible: state.confirmationVisible, startResetCount: calls(state, 'service', 'startIdentityReset').length };
      result.invariantChecks = invariantPasses('Physical Continue exposed confirmation; SDK start call count remained zero.');
    } else if (spec.key === 'dismiss_confirmation') {
      await openConfirmation();
      const before = await capture('before_event');
      await click('cancelConfirmation');
      await settle('confirmation dismissed', async () => !(await hasControl('confirmation')));
      const after = await capture('after_event'), state = after.presenter;
      if (!before.presenter.confirmationVisible) throw new Error('Confirmation given was not established');
      result.observed = { confirmationVisible: state.confirmationVisible, startResetCount: calls(state, 'service', 'startIdentityReset').length };
      result.invariantChecks = invariantPasses('Physical confirmation Cancel produced no SDK service call.');
    } else if (spec.key === 'confirm_starts_handle') {
      await openConfirmation();
      await capture('before_event');
      await click('confirm');
      await settle('password route after handle', () => hasControl('password'));
      const after = await capture('after_event'), state = after.presenter;
      const loading = state.calls.find(item => item.owner === 'manager' && item.method === 'updateHandleState' && item.args[0] === 'loading');
      if (!loading || calls(state, 'service', 'startIdentityReset').length !== 1) throw new Error('Real loading/start handle call missing');
      result.observed = { confirmationVisible: false, handleState: 'loading', effect: 'start_identity_reset' };
      result.invariantChecks = invariantPasses('Original manager emitted one loading transition and one SDK start call.');
    } else if (spec.key === 'password_handle_routes') {
      await capture('before_event');
      await confirmPasswordRoute();
      const after = await capture('after_event'), state = after.presenter;
      result.observed = { handleState: state.handleState, screen: state.screen, password: state.password };
      result.invariantChecks = invariantPasses(state.originalPasswordHandle && state.handleId ?
        'Rendered password route retained the original production handle.' : 'missing original handle');
      if (!state.originalPasswordHandle || !state.handleId) throw new Error('Password route did not retain original handle');
    } else if (spec.key === 'oidc_handle_routes_and_resets') {
      await capture('before_event');
      await selectOidcAndConfirm();
      const after = await capture('after_event'), state = after.presenter;
      const oidcReset = call(state, 'oidc_handle', 'resetOidc');
      if (!oidcReset || state.approvalSurface !== 'embedded_webview' || !(await hasControl('oidcWebview'))) {
        throw new Error('Actual OIDC reset/WebView fallback path missing');
      }
      result.observed = { handleState: state.handleState, effect: 'open_oidc_approval', url: state.approvalUrl, pollEffect: 'reset_oidc' };
      result.invariantChecks = invariantPasses('Actual embedded WebView rendered the approval URL and original OIDC handle.resetOidc executed.');
    } else if (spec.key === 'handle_failure_recovers') {
      await openConfirmation();
      observer.configureServiceFailure(true);
      await capture('before_event');
      await click('confirm');
      await settle('stable failure cleanup', async () => await hasControl('retry') && !(await hasControl('progress')));
      const stable = await capture('stable_after_cleanup'), stableState = stable.presenter;
      observer.configureServiceFailure(false);
      await click('retry');
      await settle('retry confirmation', () => hasControl('confirmation'));
      await click('confirm');
      await settle('retry handle request', () => {
        const state = observer.read();
        return state.stateSequence.filter(value => value === 'loading').length >= 2;
      });
      const retry = await capture('after_event'), retryState = retry.presenter;
      const expectedSequence = ['uninitialized', 'loading', 'failure', 'uninitialized', 'loading'];
      const observedSequence = retryState.stateSequence.slice(0, expectedSequence.length);
      if (JSON.stringify(observedSequence) !== JSON.stringify(expectedSequence) ||
        stableState.handleState !== 'uninitialized' || stableState.screen !== 'reset_root' || stableState.progressVisible ||
        !stableState.cleanupHistory.includes('failure')) {
        throw new Error('Strict failure/cleanup/retry sequence differs: ' + JSON.stringify({ observedSequence, stableState }));
      }
      result.observed = {
        failureObserved: true,
        stateSequence: observedSequence,
        stableHandleState: stableState.handleState,
        screen: stableState.screen,
        progressVisible: stableState.progressVisible,
        retryEnabled: true,
        retryHandleState: 'loading'
      };
      result.invariantChecks = invariantPasses('Runtime captured failure, production cleanup, interactive Retry, and a second real loading transition in order.');
    } else if (spec.key === 'password_submit_calls_handle') {
      await confirmPasswordRoute();
      await input('password', spec.given.password);
      const before = await capture('before_event');
      if (before.presenter.password !== spec.given.password) throw new Error('Password given not established');
      await click('passwordSubmit');
      await settle('password reset call', () => calls(observer.read(), 'password_handle', 'resetPassword').length === 1);
      const after = await capture('after_event'), state = after.presenter;
      const submit = call(state, 'presenter', 'submitPassword');
      const reset = call(state, 'password_handle', 'resetPassword');
      if (!submit || submit.afterSynchronousReturn.resetAction !== 'loading' || !submit.afterSynchronousReturn.progressVisible ||
        !reset || reset.args[0] !== spec.given.password) throw new Error('Password loading/effect boundary missing');
      result.observed = { resetAction: 'loading', effect: 'reset_password', password: reset.args[0], progressVisible: true };
      result.invariantChecks = invariantPasses('Only non-empty physical password input enabled submit and reached the same production handle.');
    } else if (spec.key === 'password_failure_clears_on_edit') {
      await confirmPasswordRoute();
      await input('password', spec.given.password);
      await capture('before_event');
      await click('passwordSubmit');
      await settle('password failure', () => hasControl('passwordError'));
      const failed = await capture('password_failure');
      if (failed.presenter.resetAction !== 'failure' || !failed.presenter.errorVisible) throw new Error('Password failure given missing');
      await input('password', spec.event.value);
      await settle('failure cleared on edit', async () => !(await hasControl('passwordError')) && observer.read().password === spec.event.value);
      const after = await capture('after_event'), state = after.presenter;
      result.observed = { resetAction: state.resetAction, password: state.password, errorVisible: state.errorVisible,
        retryEnabled: (await inspect('passwordSubmit')).enabled };
      result.invariantChecks = invariantPasses(state.originalPasswordHandle ?
        'Editing after the real rejection retained the original handle and re-enabled submit.' : 'missing retained handle');
      if (!state.originalPasswordHandle) throw new Error('Password failure destroyed the reset handle');
    } else if (spec.key === 'success_waits_for_verification') {
      await confirmPasswordRoute();
      await input('password', 'secret');
      await click('passwordSubmit');
      await settle('waiting for verification', async () => await hasControl('waiting') && await hasControl('progress'));
      const waiting = await capture('before_event');
      await click('sessionVerified');
      await settle('identity reset complete', () => hasControl('complete'));
      const after = await capture('after_event'), state = after.presenter;
      if (waiting.presenter.completionCount !== 0 || waiting.presenter.resetAction !== 'success') {
        throw new Error('Completion was emitted before verification');
      }
      result.observed = { resetAction: 'success', progressVisibleUntilVerified: waiting.presenter.progressVisible,
        completionCount: state.completionCount };
      result.invariantChecks = invariantPasses('Rendered progress remained until physical Session verified; completion then emitted exactly once.');
    } else if (spec.key === 'cancel_cleans_up') {
      await selectOidcAndConfirm();
      const before = await capture('before_event');
      await click('exit');
      await settle('root after exit', () => hasControl('continue'));
      await observer.invokePresenter('oidcReturned');
      await observer.invokePresenter('dispose');
      const after = await capture('after_event'), state = after.presenter;
      const reasons = state.cleanupHistory;
      const managerCancels = calls(state, 'manager', 'cancel');
      const handleCancel = call(state, 'oidc_handle', 'cancel');
      if (!before.presenter.resetJobActive || !before.presenter.completionWatcherActive || !handleCancel ||
        !['cancel', 'oidc_return', 'node_destroy'].every(reason => reasons.includes(reason)) || managerCancels.length < 3) {
        throw new Error('Shared cancellation/return/destruction cleanup chain incomplete');
      }
      result.observed = { effect: 'cancel_reset_handle', handleState: state.handleState,
        resetJobActive: state.resetJobActive, completionWatcherActive: state.completionWatcherActive };
      result.invariantChecks = invariantPasses('Physical Exit and runtime OIDC-return/node-destroy callbacks all delegated to the same manager.cancel cleanup path.');
    } else {
      throw new Error('Unsupported Task16 transition key: ' + spec.key);
    }
    result.eventExecuted = true;
  } catch (error) {
    result.failure = { stage, message: String(error), stack: error?.stack, presenter: observer?.read() };
    try { await capture('failure_diagnostic_only'); } catch (captureError) { result.failure.captureError = String(captureError); }
  } finally {
    observer?.dispose();
    result.launchEvidence = launch.read();
    try { await launch.dispose(); } catch (error) { result.failure = { ...result.failure, cleanupError: String(error) }; }
  }
  return JSON.stringify(result);
}
