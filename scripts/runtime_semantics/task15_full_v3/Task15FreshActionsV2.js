// Fresh physical cases only. Classification and calibration belong to the independent verifier.
export const TASK15_FRESH_PROTOCOL = 'task15.arkts.fresh-physical-actions.v2';
const supported = {
  ad_state_001_capability_gates_entry: 'capability_gates_entry',
  ad_state_005_first_submit_confirms: 'first_submit_confirms',
  ad_state_006_confirm_sends_payload: 'confirm_sends_payload',
  ad_state_008_failure_preserves_form: 'failure_preserves_form',
  ad_state_009_retry_bypasses_confirmation: 'retry_bypasses_confirmation'
};
const clone = value => JSON.parse(JSON.stringify(value));
const need = (condition, message) => { if (!condition) throw new Error(message); };

export async function runTask15FreshPhysicalCase(ports) {
  const { spec, bundleName, driver, ON, launch, integration, inspector, binding, observePage } = ports;
  const result = { protocol: TASK15_FRESH_PROTOCOL, taskId: spec.taskId, caseId: spec.caseId,
    bundleName,
    traceDigest: spec.traceDigest, key: spec.key, sessionId: spec.caseId + ':' + Date.now(),
    actions: [], frames: [], entryExecuted: false, eventExecuted: false, outcome: 'not_scored',
    deadlineEpochMs: ports.deadlineEpochMs, failure: null, cleanup: null };
  let observer, sequence = 0, stage = 'validate';
  const budget = () => need(Number.isFinite(ports.deadlineEpochMs) && Date.now() < ports.deadlineEpochMs,
    'Whole scorer deadline exhausted; no semantic failure');
  const names = {
    settings: [ON.text('Settings')], notifications: [ON.type('Button').text('Notifications')],
    entry: [ON.id(binding.entryId)], password: [ON.id('deactivation_password')],
    erase: [ON.id('deactivation_erase_data'), ON.type('Toggle'), ON.type('Switch')],
    submit: [ON.id(binding.submitId)], confirmation: [ON.text(binding.confirmationText)],
    confirm: [ON.type('Button').text(binding.confirmText)],
    loading: [ON.id(binding.loadingId)], retry: [ON.type('Button').text('Retry')]
  };
  const find = async selectors => {
    budget();
    for (const selector of selectors) {
      const nodes = await driver.findComponents(selector.inWindow(bundleName)) || [];
      need(nodes.length <= 1, 'Ambiguous physical control');
      if (nodes.length === 1) return nodes[0];
    }
    return undefined;
  };
  const inspect = async (name, selectors = names[name]) => {
    budget();
    const windowIdentity = await launch.check(driver), node = await find(selectors);
    if (!node) return { name, present: false, visible: false };
    const bounds = await node.getBounds(), viewport = windowIdentity.bounds;
    const value = { name, id: await node.getId(), text: await node.getText(), present: true,
      enabled: await node.isEnabled(), focused: await node.isFocused(), bounds,
      visible: bounds.left >= viewport.left && bounds.top >= viewport.top &&
        bounds.right <= viewport.right && bounds.bottom <= viewport.bottom &&
        bounds.right > bounds.left && bounds.bottom > bounds.top };
    if (await node.isCheckable()) value.checked = await node.isChecked();
    return value;
  };
  const receipt = async (kind, target, call, extra = {}, phase = 'setup') => {
    budget();
    const action = { kind, target, phase, sequence: ++sequence, sessionId: result.sessionId,
      startedAt: Date.now(), executed: false, ...extra };
    result.actions.push(action);
    try { await call(); action.executed = true; }
    catch (error) { action.error = String(error); throw error; }
    finally { action.finishedAt = Date.now(); }
    await driver.delayMs(100);
    return action;
  };
  const click = async (name, selectors = names[name], phase = 'setup') => {
    const control = await inspect(name, selectors);
    need(control.present && control.visible && control.enabled === true,
      'Physical control unavailable/disabled: ' + name);
    const node = await find(selectors);
    return receipt('click', name, () => node.click(), { nativeControl: control }, phase);
  };
  const capture = async label => {
    budget();
    const windowIdentity = await launch.check(driver);
    const frame = { label, sequence: ++sequence, at: Date.now(), sessionId: result.sessionId,
      windowIdentity, nativeTree: inspector.tree(), windowAndIme: await inspector.ime(), controls: [],
      presenter: observer ? observer.read() : null,
      provider: await integration.control.status() };
    need(frame.nativeTree && frame.windowAndIme, 'Full production UI tree/window/IME observation unavailable');
    for (const name of ['settings', 'notifications', 'entry', 'password', 'erase', 'submit', 'confirmation', 'confirm', 'loading', 'retry'])
      frame.controls.push(await inspect(name));
    result.frames.push(frame);
    return frame;
  };
  const control = (frame, name) => frame.controls.find(item => item.name === name);
  const given = frame => frame.presenter?.available === true &&
    Object.entries(spec.given).every(([key, value]) => frame.presenter[key] === value);
  const wait = async (label, read, accept) => {
    const end = Math.min(ports.deadlineEpochMs, Date.now() + 8000);
    for (let attempt = 0; attempt < 80 && Date.now() < end; attempt++) {
      budget();
      const value = await read();
      if (accept(value)) return value;
      await driver.delayMs(100);
    }
    throw new Error('Bounded native readiness unavailable: ' + label);
  };
  const release = async (count, status, phase = 'setup') => {
    let response;
    await receipt('https_response', 'deactivation:' + count, async () => {
      response = await integration.control.release(count, status);
      need(response.released === count && response.status === status, 'Wrong actual HTTP release');
    }, { deactivationNumber: count, status }, phase);
    return response;
  };
  const firstSubmit = async phase => {
    await click('submit', names.submit, phase);
    if (phase === 'event') { await driver.delayMs(300); return capture('after_event'); }
    return wait('original confirmation', () => capture(phase === 'event' ? 'after_event' : 'setup_confirmation'),
      frame => frame.presenter?.action === 'confirming' && control(frame, 'confirmation').visible &&
        control(frame, 'confirm').visible);
  };
  const confirmAndHold = async phase => {
    await click('confirm', names.confirm, phase);
    if (phase === 'event') { await driver.delayMs(100); return capture('after_event'); }
    await integration.control.waitHeld(1);
    return wait('original held loading', () => capture(phase === 'event' ? 'after_event' : 'setup_loading'),
      frame => frame.presenter?.action === 'loading' && control(frame, 'loading').visible);
  };
  const authenticateHeld = async () => {
    await release(1, 401);
    await integration.control.waitHeld(2);
  };
  try {
    budget();
    need(spec.taskId === '15_account_deactivation' && supported[spec.caseId] === spec.key &&
      /^[a-f0-9]{64}$/.test(spec.traceDigest), 'Unbound case; never reuse a case005 session');
    need(integration && integration.control && typeof ports.importModule === 'function', 'Actual native integration unavailable');
    stage = 'common_start';
    await launch.start();
    result.entryExecuted = true;
    await integration.prepare({ find, inspect, inspectRaw: id => inspector.byKey(id), click, receipt,
      bundleName, result, binding });
    result.integration = integration.evidence();
    result.nonce = result.integration.nonce;
    result.sessionId = result.nonce + ':' + spec.caseId;
    // Existing setup receipts retain their original session identity; later actions must not masquerade as those setup calls.
    result.launchSetupSessionId = result.actions[0]?.sessionId;
    result.settings = { settings: await inspect('settings'), notifications: await inspect('notifications'),
      entry: await inspect('entry') };
    need(result.settings.settings.visible && result.settings.notifications.visible && result.settings.entry.visible,
      'Actual common settings/entry positive control unavailable');
    if (spec.caseId === 'ad_state_001_capability_gates_entry') {
      stage = 'load_settings';
      await capture('before_event');
      await receipt('ability_start', 'original_settings', () => launch.reload(), {}, 'event');
      result.eventExecuted = true;
      await capture('after_event');
      result.outcome = 'transition_observed';
    } else {
      stage = 'open_original_form';
      await click('entry');
      const initial = await capture('original_form_before_import');
      need(control(initial, 'password').visible, 'Original form not reached');
      const presenter = await ports.importModule(binding.productionModuleUrl);
      const service = typeof presenter.AccountClient === 'function' ? presenter : await ports.importModule(binding.serviceModuleUrl);
      observer = observePage({ ...presenter, AccountClient: service.AccountClient }, {
        ...binding, importCompleted: true, importPhase: 'after_original_page_ready_before_fixture',
        namespaceExports: Object.keys(presenter) });
      stage = 'physical_givens';
      const erase = await inspect('erase');
      need(typeof erase.checked === 'boolean', 'Unknown erase state');
      if (erase.checked !== true) await click('erase');
      const password = await inspect('password'), input = await find(names.password);
      need(password.present && password.visible && password.enabled, 'Physical password input unavailable');
      await receipt('input', 'password', () => input.inputText('secret'), { value: 'secret' });
      const afterInput = await capture('after_password_before_ime_action');
      if (afterInput.windowAndIme.keyboardVisible === true) {
        need(afterInput.windowAndIme.visibilitySource === 'native_window_keyboard_avoid_area', 'IME inferred, not observed');
        await receipt('system_back', 'Driver.pressBack', () => driver.pressBack(),
          { observedImeBefore: afterInput.windowAndIme });
      } else need(afterInput.windowAndIme.keyboardVisible === false, 'Unknown IME; no action');
      const readinessStartedAt = Date.now();
      const samples = [];
      let ready;
      while (true) {
        budget();
        ready = await capture('physical_submit_readiness');
        samples.push(ready.sequence);
        need(ready.windowAndIme.keyboardVisible === false && control(ready, 'password').visible &&
          control(ready, 'erase').visible, 'Form/IME/owner not proven after Back');
        if (control(ready, 'submit').present && control(ready, 'submit').visible && control(ready, 'submit').enabled === true) break;
        if (Date.now() - readinessStartedAt >= 2000 && samples.length >= 2) break;
        await driver.delayMs(100);
      }
      result.submitSamples = samples;
      result.submitReadinessStartedAt = readinessStartedAt;
      if (spec.caseId === 'ad_state_005_first_submit_confirms' && given(ready) &&
          control(ready, 'submit').present && control(ready, 'submit').visible && control(ready, 'submit').enabled === false) {
        stage = 'blocked_required_physical_action';
        result.blockedAction = { target: 'submit', requiredEvent: clone(spec.event),
          sampleSequences: samples, frameSequence: ready.sequence, canonicalGivenEstablished: true };
        result.outcome = 'blocked_required_physical_action';
      } else {
        need(control(ready, 'submit').enabled === true, 'Own case setup cannot reach its canonical given; NOT_SCORED');
        if (spec.caseId === 'ad_state_005_first_submit_confirms') {
          need(given(ready), 'Original case005 given not established');
          ready.label = 'before_event';
          stage = 'physical_event';
          await firstSubmit('event');
        } else {
          await firstSubmit('setup');
          if (spec.caseId === 'ad_state_006_confirm_sends_payload') {
            const before = await capture('before_event');
            need(given(before), 'Own case006 confirming given not established');
            stage = 'physical_event';
            const loading = await confirmAndHold('event');
            if (control(loading, 'loading').present && control(loading, 'loading').visible) {
              need(typeof ports.modalInput === 'function', 'Actual modal hit-routing probe unavailable');
              const passwordNode = uniqueNative(loading.nativeTree, 'deactivation_password');
              const geometry = JSON.parse('[' + passwordNode.$rect + ']');
              let error;
              await receipt('modal_physical_input', 'password_coordinates', async () => {
                try { await ports.modalInput(geometry, 'tampered'); }
                catch (value) { error = String(value); }
              }, { geometry, attemptedText: 'tampered' }, 'invariant');
              const after = await capture('after_modal_input');
              result.modalProbe = { beforeSequence: loading.sequence, afterSequence: after.sequence, inputError: error || null };
            }
          } else {
            await confirmAndHold('setup');
            await authenticateHeld();
            if (spec.caseId === 'ad_state_008_failure_preserves_form') {
              const before = await capture('before_event');
              need(given(before), 'Own case008 loading given not established');
              stage = 'physical_event';
              await release(2, 503, 'event');
              await driver.delayMs(300);
              await capture('after_event');
            } else {
              await release(2, 503);
              await wait('own retry given', () => capture('setup_failure'), frame => frame.presenter?.action === 'failure');
              const before = await capture('before_event');
              need(given(before), 'Own case009 failure/requestCount given not established');
              stage = 'physical_event';
              await click('retry', names.retry, 'event');
              await driver.delayMs(100);
              await capture('after_event');
            }
          }
        }
        result.eventExecuted = true;
        result.outcome = 'transition_observed';
      }
    }
  } catch (error) {
    result.outcome = 'not_scored';
    result.failure = { stage, message: String(error) };
  } finally {
    try { result.cleanup = await integration.cleanup(); result.integration = integration.evidence(); }
    catch (error) { result.outcome = 'not_scored'; result.failure = { stage: 'cleanup', message: String(error) }; }
    if (observer) observer.dispose();
    result.launchEvidence = launch.read();
    try { await launch.dispose(); }
    catch (error) { result.outcome = 'not_scored'; result.failure = { stage: 'lifecycle_cleanup', message: String(error) }; }
    result.finishedAt = Date.now();
  }
  return result;
}

function uniqueNative(tree, id) {
  const nodes = [];
  const visit = value => {
    if (value?.$attrs?.id === id) nodes.push(value);
    for (const child of value?.$children || []) visit(child);
  };
  visit(tree);
  need(nodes.length === 1, 'Unknown original native node geometry');
  return nodes[0];
}
