import { observeTask15Page } from './Task15PageObserver';

let binding;
export function configureTask15Binding(configJson, importModule = url => import(url)) {
  const config = JSON.parse(configJson);
  const expectedModule = config.presenterSourcePath ? '@bundle:' + config.bundleName + '/entry/' +
    config.presenterSourcePath.replace(/^entry\/src\/main\//, '').replace(/\.(ets|ts)$/, '') :
    '@bundle:' + config.bundleName + '/entry/ets/features/AccountDeactivationFeature';
  if (!config.bundleName || config.moduleName !== 'entry' ||
    config.productionModuleUrl !== expectedModule || expectedModule.includes('..')) {
    throw new Error('Task15 original module identity is invalid');
  }
  binding = { config, importModule };
}

export async function runTask15NativeUi(caseJson, bundleName, driver, ON, launch, integration, inspector, dismissKeyboard) {
  const spec = JSON.parse(caseJson);
  const entryDiagnostic = spec.key === 'capability_gates_entry';
  const loadingDiagnostic = spec.key === 'confirm_sends_payload';
  const setupGiven = loadingDiagnostic ? { ...spec.given, action: 'uninitialized' } : spec.given;
  const result = { taskId: spec.taskId, caseId: spec.caseId, traceDigest: spec.traceDigest,
    sessionId: spec.caseId + ':' + Date.now(), bundleName, entryExecuted: false, eventExecuted: false,
    frames: [], actions: [], unsupported: '', observationMode: 'runtime_state_transition' };
  const profile = binding?.config || {};
  const submitId = profile.submitId || 'deactivate_submit';
  const confirmationText = profile.confirmationText || 'Are you sure you want to deactivate this account?';
  const confirmText = profile.confirmText || 'Confirm deactivation';
  const loadingId = profile.loadingId || 'deactivation_loading_dialog';
  let sequence = 0, observer, stage = 'validate';
  const find = async selectors => {
    for (const selector of selectors) {
      const nodes = await driver.findComponents(selector.inWindow(bundleName)) || [];
      if (nodes.length > 1) throw new Error('Ambiguous candidate UI selector');
      if (nodes.length === 1) return nodes[0];
    }
    return undefined;
  };
  const windowBounds = async () => {
    return (await launch.check(driver)).bounds;
  };
  const inspect = async (name, selectors) => {
    const viewport = await windowBounds(), node = await find(selectors);
    if (!node) return { name, present: false, visible: false };
    const bounds = await node.getBounds();
    const value = { name, present: true, id: await node.getId(), text: await node.getText(),
      enabled: await node.isEnabled(), focused: await node.isFocused(), bounds,
      visible: Math.min(viewport.right, bounds.right) > Math.max(viewport.left, bounds.left) &&
        Math.min(viewport.bottom, bounds.bottom) > Math.max(viewport.top, bounds.top) };
    if (await node.isCheckable()) value.checked = await node.isChecked();
    return value;
  };
  const inspectRaw = id => {
    if (!inspector || typeof inspector.byKey !== 'function') return undefined;
    return inspector.byKey(id);
  };
  const receipt = async (kind, target, fn, extra = {}) => {
    const action = { sessionId: result.sessionId, sequence: ++sequence, kind, target, executed: false, ...extra };
    result.actions.push(action);
    try { await fn(); action.executed = true; }
    catch (error) { action.error = String(error); throw error; }
    await driver.delayMs(100);
  };
  const click = async (name, selectors) => {
    const control = await inspect(name, selectors);
    if (!control.visible || !control.enabled) throw new Error('Native control unavailable/disabled: ' + name + ': ' + JSON.stringify(control));
    const node = await find(selectors);
    await receipt('click', name, () => node.click());
  };
  const password = [ON.id('deactivation_password')];
  const toggle = [ON.type('Toggle'), ON.type('Switch'), ON.type('Checkbox')];
  const capture = async label => {
    const controls = [];
    for (const [name, selectors] of [
      ['password', password], ['erase', toggle], ['submit', [ON.id(submitId)]],
      ['confirmation', [ON.text(confirmationText)]],
      ['confirm', [ON.type('Button').text(confirmText)]], ['cancel', [ON.type('Button').text('Cancel')]],
      ['loadingModal', [ON.id(loadingId)]],
      ['loadingMessage', [ON.id('deactivation_loading_message')]]
    ]) controls.push(await inspect(name, selectors));
    const frame = { label, sessionId: result.sessionId, bundleName, sequence: ++sequence, controls,
      windowIdentity: launch.read().lastReady,
      presenter: observer ? observer.read() : { available: false } };
    if (inspector && typeof inspector.tree === 'function' &&
        ['fixture_after_password', 'fixture_after_keyboard_dismissed', 'before_event', 'failure_diagnostic_only'].includes(label)) {
      frame.nativeTree = { origin: 'original UIContext.runScopedTask(getInspectorTree)',
        windowIdentity: frame.windowIdentity, tree: inspector.tree() };
    }
    result.frames.push(frame);
    console.info('TASK15_UI_CHECKPOINT ' + JSON.stringify(frame));
    return frame;
  };
  try {
    const validGivenAndEvent = entryDiagnostic ?
      spec.given.serverCanDeactivateAccount === true && spec.given.surface === 'settings' && spec.event.name === 'load_settings' :
      ['first_submit_confirms', 'confirm_sends_payload'].includes(spec.key) && spec.given.password === 'secret' &&
      spec.given.eraseData === true && spec.given.action === (loadingDiagnostic ? 'confirming' : 'uninitialized') &&
      spec.event.name === 'deactivate_account' && spec.event.isRetry === false;
    if (spec.taskId !== '15_account_deactivation' || !/^[a-f0-9]{64}$/.test(spec.traceDigest) || !validGivenAndEvent) {
      throw new Error('Unsupported Task15 native case');
    }
    if (!binding || binding.config.bundleName !== bundleName) throw new Error('Original app binding not configured');
    stage = 'launch';
    if (entryDiagnostic) result.frames.push({ label: 'before_event', sessionId: result.sessionId, bundleName,
      sequence: ++sequence, phase: 'before_startAbility', controls: [], uiObserved: false,
      scope: 'Launch boundary only; no pre-launch visibility or capability result asserted' });
    await launch.start();
    result.entryExecuted = true;
    if (integration && typeof integration.prepare === 'function') {
      stage = 'external_https_account_setup';
      await integration.prepare({ find, inspect, inspectRaw, click, receipt, bundleName, result, binding: profile });
      result.integration = integration.evidence();
    }
    stage = 'await_original_main_window_and_settings';
    const entry = [ON.id(profile.entryId || 'deactivate_account_entry')];
    const startedAt = Date.now(), budgetMs = 6000, maxAttempts = 40;
    result.readiness = { budgetMs, maxAttempts, attempts: [], ready: false };
    for (let attempt = 0; attempt < maxAttempts && Date.now() - startedAt < budgetMs; attempt++) {
      const observation = { attempt: attempt + 1, at: Date.now() };
      result.readiness.attempts.push(observation);
      try {
        const settings = await inspect('settings', [ON.text('Settings')]);
        const notifications = await inspect('notifications', [ON.type('Button').text('Notifications')]);
        const ready = await inspect('entry', entry);
        result.prerequisite = { rootConfirmed: settings.visible && notifications.visible, controls: [settings, notifications, ready] };
        observation.rootConfirmed = result.prerequisite.rootConfirmed;
        observation.entryReady = ready.visible && ready.enabled;
        observation.windowIdentity = launch.read().lastReady;
        if (observation.rootConfirmed && (entryDiagnostic || observation.entryReady)) { result.readiness.ready = true; break; }
      } catch (error) {
        observation.error = String(error);
      }
      const remaining = budgetMs - (Date.now() - startedAt);
      if (attempt + 1 < maxAttempts && remaining > 0) await driver.delayMs(Math.min(150, remaining));
    }
    if (!result.readiness.ready) throw new Error('Bounded original foreground/main-window/settings readiness exhausted: ' +
      JSON.stringify(result.readiness.attempts[result.readiness.attempts.length - 1]));
    if (entryDiagnostic) {
      const frame = { label: 'after_event', sessionId: result.sessionId, bundleName, sequence: ++sequence,
        controls: result.prerequisite.controls, windowIdentity: launch.read().lastReady,
        scope: 'Actual settings root and entry only; capability response, native color and unsupported branch unobserved' };
      result.frames.push(frame);
      console.info('TASK15_UI_CHECKPOINT ' + JSON.stringify(frame));
      result.eventExecuted = true;
      result.unsupported = 'Entry visibility sampled on original settings page; native destructive styling and unsupported-server hiding unobserved';
    } else {
      stage = 'open_form';
      await click('deactivation_entry', entry);
      const loaded = await capture('original_page_ready_before_binding');
      if (!loaded.controls.find(c => c.name === 'password' && c.visible)) throw new Error('Original password form not ready');
      stage = 'postload_original_binding';
      const presenterModule = await binding.importModule(binding.config.productionModuleUrl);
      const serviceModule = typeof presenterModule.AccountClient === 'function' ? presenterModule :
        await binding.importModule(binding.config.serviceModuleUrl);
      const namespace = { ...presenterModule, AccountClient: serviceModule.AccountClient };
      observer = observeTask15Page(namespace, { ...binding.config, importCompleted: true,
        importPhase: 'after_original_page_ready_before_fixture', namespaceExports: Object.keys(namespace) });
      await capture('observer_installed');
      stage = 'fixture_erase_data';
      const erase = await inspect('erase', toggle);
      if (typeof erase.checked !== 'boolean') throw new Error('Erase toggle is not checkable');
      if (erase.checked !== spec.given.eraseData) await click('erase', toggle);
      await capture('erase_selected');
      stage = 'fixture_password_input';
      const field = await inspect('password', password);
      if (!field.enabled || !field.visible) throw new Error('Native password input unavailable');
      const input = await find(password);
      await receipt('input', 'password', () => input.inputText(spec.given.password), { value: spec.given.password });
      await capture('fixture_after_password');
      const typedField = await inspect('password', password);
      const submitAfterInput = await inspect('submit', [ON.id(submitId)]);
      if (!submitAfterInput.visible && typedField.focused && typeof dismissKeyboard === 'function') {
        stage = 'dismiss_native_input_method';
        await receipt('hide_input_method', 'inputMethod.getController().hideTextInput', dismissKeyboard,
          { focusedInputId: typedField.id, submitBefore: submitAfterInput });
        await capture('fixture_after_keyboard_dismissed');
      }
      stage = 'await_native_submit_ready';
      const submitStartedAt = Date.now(), submitBudgetMs = 2000, submitMaxAttempts = 10;
      result.submitReadiness = { budgetMs: submitBudgetMs, maxAttempts: submitMaxAttempts, attempts: [], ready: false };
      for (let attempt = 0; attempt < submitMaxAttempts && Date.now() - submitStartedAt < submitBudgetMs; attempt++) {
        const submit = await inspect('submit', [ON.id(submitId)]);
        const presenter = observer.read();
        const frame = { label: 'fixture_submit_probe_' + (attempt + 1), sessionId: result.sessionId, bundleName,
          sequence: ++sequence, controls: [submit], presenter, windowIdentity: launch.read().lastReady };
        result.frames.push(frame);
        const givensMatch = presenter.available && Object.entries(setupGiven).every(([key, value]) => presenter[key] === value);
        result.submitReadiness.attempts.push({ sequence: frame.sequence, at: Date.now(), givensMatch,
          present: submit.present, visible: submit.visible, enabled: submit.enabled });
        if (givensMatch && submit.present && submit.visible && submit.enabled) { result.submitReadiness.ready = true; break; }
        const remaining = submitBudgetMs - (Date.now() - submitStartedAt);
        if (attempt + 1 < submitMaxAttempts && remaining > 0) await driver.delayMs(Math.min(150, remaining));
      }
      // Preserve the actual disabled value if it never changes. No tapping a
      // disabled control or forcing a re-render to manufacture the event.
      const before = await capture(loadingDiagnostic ? 'fixture_before_first_submit' : 'before_event');
      if (!before.presenter.available || Object.entries(setupGiven).some(([key, value]) => before.presenter[key] !== value)) {
        throw new Error('Actual UI fixture did not establish canonical givens');
      }
      stage = 'first_submit';
      await click('submit', [ON.id(submitId)]);
      if (!loadingDiagnostic) result.eventExecuted = true;
      stage = 'capture_confirmation';
      // Settling poll only. A missing dialog remains an observed false value,
      // never an instruction to call the presenter or inject confirmation.
      for (let attempt = 0; attempt < 5; attempt++) {
        if ((await inspect('confirm', [ON.type('Button').text(confirmText)])).visible) break;
        await driver.delayMs(100);
      }
      if (loadingDiagnostic) {
        const confirming = await capture('before_event');
        if (!confirming.presenter.available || Object.entries(spec.given).some(([key, value]) => confirming.presenter[key] !== value) ||
          confirming.presenter.requestCount !== 0) throw new Error('Actual confirmation UI did not establish canonical givens');
        stage = 'confirm_loading_diagnostic';
        const confirm = await inspect('confirm', [ON.type('Button').text(confirmText)]);
        if (!confirm.visible || !confirm.enabled) throw new Error('Original confirm control unavailable/disabled');
        const node = await find([ON.type('Button').text(confirmText)]);
        const action = { sessionId: result.sessionId, sequence: ++sequence, kind: 'click', target: 'confirm', executed: false };
        result.actions.push(action);
        await node.click();
        action.executed = true;
        result.eventExecuted = true;
        // No settling delay, held service Promise or direct presenter invocation.
        // UiTest reads are asynchronous: this is not an atomic rendered-frame claim.
        const after = await capture('after_event');
        result.loadingObservation = {
          presenterAction: after.presenter.action,
          loadingModalVisible: after.controls.some(c => c.name === 'loadingModal' && c.present && c.visible),
          formInputBlocked: 'unproven',
          atomicLoadingFrame: false,
          scope: 'Post-click native control observations, not simultaneous frame or input-routing proof'
        };
        result.unsupported = 'No simultaneous natural Loading/modal/input-blocking proof; original confirmation and service diagnostics only';
      } else {
        await capture('after_event');
        if (integration && typeof integration.continueSequence === 'function') {
          stage = 'external_https_deactivation_sequence';
          await integration.continueSequence({ find, inspect, click, receipt, capture, observer, bundleName, result, binding: profile });
          result.integration = integration.evidence();
        }
      }
    }
  } catch (error) {
    result.unsupported = String(error);
    result.failure = { stage, message: String(error), stack: error && error.stack, code: error && error.code,
      presenter: observer && observer.read() };
    try { await capture('failure_diagnostic_only'); } catch (captureError) { result.failure.captureError = String(captureError); }
  } finally {
    if (integration && typeof integration.cleanup === 'function') {
      try {
        result.integrationCleanup = await integration.cleanup();
        result.integration = integration.evidence();
      } catch (error) {
        result.integration = integration.evidence();
        result.failure = { ...result.failure, integrationCleanupError: String(error) };
        result.unsupported = result.unsupported || 'Task15 E2E cleanup unavailable: ' + String(error);
      }
    }
    if (observer) observer.dispose();
    result.launchEvidence = launch.read();
    try { await launch.dispose(); }
    catch (error) {
      result.failure = { ...result.failure, cleanupError: String(error) };
      result.unsupported = result.unsupported || 'Native lifecycle cleanup unavailable: ' + String(error);
    }
  }
  return JSON.stringify(result);
}
