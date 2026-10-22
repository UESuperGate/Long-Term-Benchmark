// V2 is the raw transport/packager alias only. ALL five cases below are new
// v5 native episodes; no host VM or case005 result is ever consumed.
export const TASK15_PAGE_OWNER_PROTOCOL = 'task15.arkts.same-original-page-owner.v5';
const keys = new Set(['default_form_blocks_submit', 'password_enables_submit', 'erase_data_option',
  'success_completes', 'close_dialog_resets_action']);
const need = (condition, message) => { if (!condition) throw Error(message); };

export async function runTask15PageOwnerCaseV5(ports) {
  const { spec, driver, ON, launch, inspector, integration, binding, bundleName } = ports;
  const result = { protocol: 'task15.arkts.fresh-physical-actions.v2', pageOwnerProtocol: TASK15_PAGE_OWNER_PROTOCOL,
    taskId: spec.taskId, caseId: spec.caseId, traceDigest: spec.traceDigest, bundleName,
    actions: [], frames: [], entryExecuted: false, eventExecuted: false, outcome: 'not_scored', failure: null };
  result.sessionId = 'launch:' + Date.now();
  let sequence = 0, observer, stage = 'common_start';
  const budget = () => need(Date.now() < ports.deadlineEpochMs, 'Original overall deadline exhausted');
  const names = { settings: ON.text('Settings'), notifications: ON.type('Button').text('Notifications'),
    entry: ON.id(binding.entryId), password: ON.id(binding.passwordId), erase: ON.id(binding.eraseId),
    submit: ON.id(binding.submitId), confirm: ON.type('Button').text(binding.confirmText),
    close: ON.type('Button').text(binding.closeText) };
  const pathForObservation = (id, text, bounds) => {
    const found = [];
    const visit = (node, path) => {
      const attrs = node?.$attrs || {};
      if ((attrs.id || '') === id && (id || [attrs.text, attrs.content, attrs.label].includes(text)) &&
        JSON.stringify(JSON.parse('[' + node.$rect + ']')) ===
          JSON.stringify([[bounds.left, bounds.top], [bounds.right, bounds.bottom]])) found.push(path);
      (node?.$children || []).forEach((child, index) => visit(child, path + '/' + index));
    };
    visit(inspector.tree(), 'root');
    need(found.length === 1, 'No unique full-tree source-bound native node path');
    return found[0];
  };
  const find = async selectors => {
    budget();
    if (typeof selectors === 'string') selectors = names[selectors];
    for (const selector of Array.isArray(selectors) ? selectors : [selectors]) {
      need(selector, 'Unbound physical selector');
      const nodes = await driver.findComponents(selector.inWindow(bundleName)) || [];
      need(nodes.length <= 1, 'Unknown/ambiguous native action');
      if (nodes.length === 1) return nodes[0];
    }
    return undefined;
  };
  const inspect = async (name, selectors = names[name]) => {
    const window = await launch.check(driver), node = await find(selectors);
    if (!node) return { name, present: false, visible: false };
    const bounds = await node.getBounds(), id = await node.getId(), text = await node.getText();
    const value = { name, id, treePath: pathForObservation(id, text, bounds), present: true, bounds,
      text, enabled: await node.isEnabled(),
      visible: bounds.left >= window.bounds.left && bounds.top >= window.bounds.top &&
        bounds.right <= window.bounds.right && bounds.bottom <= window.bounds.bottom &&
        bounds.right > bounds.left && bounds.bottom > bounds.top };
    if (await node.isCheckable()) value.checked = await node.isChecked();
    return value;
  };
  const capture = async label => {
    budget(); const frame = { label, sequence: ++sequence, at: Date.now(), sessionId: result.sessionId,
      windowIdentity: await launch.check(driver), windowAndIme: await inspector.ime(), nativeTree: inspector.tree(),
      pageOwner: observer?.read(), provider: await integration.control.status(), controls: [] };
    for (const name of Object.keys(names)) frame.controls.push(await inspect(name));
    result.frames.push(frame); return frame;
  };
  const receipt = async (kind, target, execute, extra = {}, phase = 'setup') => {
    budget(); const callStart = observer?.read().calls.length || 0;
    const action = { kind, target, phase, sequence: ++sequence, sessionId: result.sessionId, executed: false,
      callStart, startedAt: Date.now(), ...extra };
    result.actions.push(action);
    try { await execute(); action.executed = true; await driver.delayMs(150); }
    finally { action.callEnd = observer?.read().calls.length || 0; action.finishedAt = Date.now(); }
    return action;
  };
  const click = async (name, selectors = names[name], phase = 'setup') => {
    if (selectors === 'event' || selectors === 'setup') { phase = selectors; selectors = names[name]; }
    const control = await inspect(name, selectors);
    need(control.present && control.visible && control.enabled === true, 'Native action not eligible: ' + name);
    const node = await find(selectors);
    return receipt('click', name, () => node.click(), { nativeControl: control }, phase);
  };
  const input = async (value, phase = 'setup') => {
    const control = await inspect('password');
    need(control.present && control.visible && control.enabled === true, 'Native input unavailable');
    const node = await find('password');
    await receipt('input', 'password', () => node.inputText(value),
      { value, driverArguments: [value], nativeControl: control }, phase);
  };
  const hideObservedIme = async () => {
    const before = await capture('ime_observation');
    if (before.windowAndIme.keyboardVisible === true) {
      need(before.windowAndIme.visibilitySource === 'native_window_keyboard_avoid_area', 'Unknown IME');
      await receipt('system_back', 'Driver.pressBack', () => driver.pressBack(), { observedImeBefore: before.windowAndIme });
    } else need(before.windowAndIme.keyboardVisible === false, 'Unknown IME; no Back');
  };
  const release = async (number, status, phase = 'setup') => {
    const response = await receipt('https_response', 'own_pending_deactivation', async () => {
      const value = await integration.control.release(number, status);
      need(value.released === number && value.status === status, 'Wrong actual response');
    }, { requestId: number, status }, phase);
    return response;
  };
  try {
    budget(); need(keys.has(spec.key) && spec.taskId === '15_account_deactivation', 'Own canonical case required');
    await launch.start(); result.entryExecuted = true;
    await integration.prepare({ find, inspect, click, receipt, inspectRaw: id => inspector.byKey(id), bundleName, result, binding });
    result.integration = integration.evidence(); result.nonce = result.integration.nonce;
    result.launchSetupSessionId = result.sessionId;
    result.sessionId = result.nonce + ':' + spec.caseId;
    stage = 'passive_original_owner_acquisition';
    // Postload only after the ORIGINAL page is ready. Physical lifecycle reload
    // must make the ORIGINAL page render call its own receiver. No getter call,
    // no presenter construction, no setter repair can acquire the owner here.
    need((await inspect('settings')).visible && (await inspect('entry')).visible, 'Actual settings positive control missing');
    const namespace = await ports.importModule(binding.productionModuleUrl);
    const services = typeof namespace.AccountClient === 'function' ? namespace : await ports.importModule(binding.serviceModuleUrl);
    observer = ports.observePage({ ...namespace, AccountClient: services.AccountClient }, binding.ownerBinding, result.sessionId);
    await receipt('ability_start', 'original_settings', () => launch.reload());
    await driver.delayMs(300);
    need(observer.read().available, 'No actual production render receiver; NS, never getter/setter discovery');
    await capture('common_start');
    if (spec.key === 'default_form_blocks_submit') {
      await capture('before_event'); await click('entry', 'event');
    } else {
      await click('entry');
      if (spec.key === 'password_enables_submit') {
        await capture('before_event'); await input(spec.event.value, 'event'); await hideObservedIme();
      } else if (spec.key === 'erase_data_option') {
        await capture('before_event'); await click('erase', 'event');
      } else {
        if ((await inspect('erase')).checked === false) await click('erase');
        await input('secret'); await hideObservedIme();
        await click('submit'); await click('confirm');
        await integration.control.waitHeld(1);
        await release(1, 401); await integration.control.waitHeld(2);
        if (spec.key === 'success_completes') {
          await capture('before_event'); await release(2, 200, 'event');
        } else {
          await release(2, 503); await driver.delayMs(300);
          await capture('before_event'); await click('close', 'event');
        }
      }
    }
    // Fixed observation delay, never wait for expected/success state to appear.
    await driver.delayMs(300); await capture('after_event');
    result.eventExecuted = true; result.outcome = 'transition_observed';
  } catch (error) { result.failure = { stage, message: String(error) }; result.outcome = 'not_scored'; }
  finally {
    try { result.cleanup = await integration.cleanup(); result.integration = integration.evidence(); }
    catch (error) { result.outcome = 'not_scored'; result.failure = { stage: 'cleanup', message: String(error) }; }
    observer?.dispose();
    try { await launch.dispose(); } catch (error) { result.outcome = 'not_scored'; result.failure = { stage: 'lifecycle_cleanup', message: String(error) }; }
    result.deadlineEpochMs = ports.deadlineEpochMs; result.finishedAt = Date.now();
  }
  return result;
}
