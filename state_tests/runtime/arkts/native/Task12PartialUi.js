import { observeTask12Partial } from './Task12PartialObserver';

let configured;
export function configureTask12Partial(configJson, importModule = url => import(url)) {
  const config = JSON.parse(configJson);
  if (!config.bundleName || config.moduleName !== 'entry' || config.productionModuleUrl !==
    '@bundle:' + config.bundleName + '/entry/ets/features/ReportRoomFeature') throw new Error('Invalid original Task12 module identity');
  configured = { config, importModule };
}

export async function runTask12Partial(caseJson, bundleName, driver, ON, launch, dismissKeyboard) {
  const spec = JSON.parse(caseJson);
  const raw = { taskId: spec.taskId, caseId: spec.caseId, traceDigest: spec.traceDigest, bundleName,
    sessionId: spec.caseId + ':' + Date.now(), observationMode: 'runtime_state_transition',
    entryExecuted: false, eventExecuted: false, invariantEventExecuted: false, frames: [], actions: [], unsupported: '' };
  let sequence = 0, observer, stage = 'validate';
  const find = async selector => {
    const nodes = await driver.findComponents(selector.inWindow(bundleName)) || [];
    if (nodes.length > 1) throw new Error('Ambiguous original page selector');
    return nodes[0];
  };
  const inspect = async (name, selector) => {
    const window = await launch.check(driver), node = await find(selector);
    if (!node) return { name, present: false, visible: false };
    const bounds = await node.getBounds(), viewport = window.bounds;
    const c = { name, present: true, id: await node.getId(), text: await node.getText(),
      enabled: await node.isEnabled(), focused: await node.isFocused(), bounds,
      visible: Math.min(bounds.right, viewport.right) > Math.max(bounds.left, viewport.left) &&
        Math.min(bounds.bottom, viewport.bottom) > Math.max(bounds.top, viewport.top) };
    if (await node.isCheckable()) c.checked = await node.isChecked();
    return c;
  };
  const selectors = {
    reason: ON.id('report_room_reason'), leave: ON.id('report_room_leave_toggle'), submit: ON.id('submit_report_room'),
    partial: ON.id('report_room_partial_failure'), retry: ON.id('retry_leave_room'), success: ON.id('report_room_success'),
    root: ON.text('Community support')
  };
  const action = async (kind, target, operation, extra = {}) => {
    const entry = { sessionId: raw.sessionId, sequence: ++sequence, kind, target, executed: false, ...extra };
    raw.actions.push(entry);
    try { await operation(); entry.executed = true; }
    catch (error) { entry.error = String(error); throw error; }
    await driver.delayMs(100);
  };
  const reveal = async name => {
    if ((await inspect(name, selectors[name])).visible) return;
    const scroll = await find(ON.type('Scroll'));
    if (!scroll || typeof scroll.scrollSearch !== 'function') throw new Error('Native report scroll container unavailable');
    await action('scroll_search', name, () => scroll.scrollSearch(selectors[name]));
  };
  const click = async name => {
    await reveal(name);
    const c = await inspect(name, selectors[name]);
    if (!c.visible || !c.enabled) throw new Error('Original UI action unavailable/disabled: ' + JSON.stringify(c));
    const node = await find(selectors[name]);
    await action('click', name, () => node.click());
  };
  const capture = async label => {
    const controls = [];
    for (const [name, selector] of Object.entries(selectors)) controls.push(await inspect(name, selector));
    const frame = { label, sequence: ++sequence, sessionId: raw.sessionId, bundleName, controls,
      windowIdentity: launch.read().lastReady, presenter: observer ? observer.read() : { available: false } };
    raw.frames.push(frame);
    console.info('TASK12_PARTIAL_CHECKPOINT ' + JSON.stringify(frame));
    return frame;
  };
  try {
    if (spec.taskId !== '12_report_room' || spec.key !== 'leave_failure_is_partial' || !/^[a-f0-9]{64}$/.test(spec.traceDigest) ||
      spec.given.reason !== 'Spam' || spec.given.leaveRoom !== true || spec.given.reportResult !== 'success' ||
      spec.given.leaveResult !== 'failure' || spec.event.name !== 'report') throw new Error('Unsupported native partial-failure case');
    if (!configured || configured.config.bundleName !== bundleName) throw new Error('Original Task12 binding unavailable');
    stage = 'launch';
    await launch.start(); raw.entryExecuted = true;
    stage = 'await_original_report_page';
    const started = Date.now();
    raw.readiness = { budgetMs: 6000, maxAttempts: 40, attempts: [], ready: false };
    for (let attempt = 0; attempt < 40 && Date.now() - started < 6000; attempt++) {
      const sample = { attempt: attempt + 1 };
      raw.readiness.attempts.push(sample);
      try {
        const root = await inspect('root', selectors.root), reason = await inspect('reason', selectors.reason);
        const submit = await inspect('submit', selectors.submit);
        raw.prerequisite = { rootConfirmed: root.visible, controls: [root, reason, submit] };
        if (root.visible && reason.visible && submit.present) { raw.readiness.ready = true; break; }
      } catch (error) { sample.error = String(error); }
      const remaining = 6000 - (Date.now() - started);
      if (attempt < 39 && remaining > 0) await driver.delayMs(Math.min(150, remaining));
    }
    if (!raw.readiness.ready) throw new Error('Original report page readiness exhausted');
    await capture('original_page_ready_before_binding');
    stage = 'postload_original_binding';
    const namespace = await configured.importModule(configured.config.productionModuleUrl);
    observer = observeTask12Partial(namespace, { ...configured.config, importCompleted: true, importPhase: 'after_original_page_ready_before_fixture' });
    stage = 'fixture_leave';
    const leave = await inspect('leave', selectors.leave);
    if (typeof leave.checked !== 'boolean') throw new Error('Original leave toggle is not checkable');
    if (!leave.checked) await click('leave');
    await capture('fixture_leave_selected');
    stage = 'fixture_reason';
    const reason = await inspect('reason', selectors.reason);
    if (!reason.visible || !reason.enabled) throw new Error('Original reason input unavailable');
    const input = await find(selectors.reason);
    await action('input', 'reason', () => input.inputText(spec.given.reason), { value: spec.given.reason });
    // OS housekeeping only; failure never fabricates visibility or enabled.
    try { await action('hide_input_method', 'keyboard', dismissKeyboard); } catch (error) { raw.keyboardDiagnostic = String(error); }
    await capture('fixture_form_entered');
    stage = 'fixture_original_gateway_outcomes';
    const original = observer.read();
    if (!original.available || original.reportCalls !== 0 || original.leaveCalls !== 0 || original.effects.length !== 0 ||
      original.reason !== spec.given.reason || original.leaveRoom !== spec.given.leaveRoom || original.reportAction !== 'uninitialized') {
      throw new Error('Fresh same-page canonical fixture not established');
    }
    observer.configureResults(spec.given.reportResult, spec.given.leaveResult, 'canonical_given');
    await reveal('submit');
    await capture('before_event');
    stage = 'canonical_report_click';
    await click('submit'); raw.eventExecuted = true;
    stage = 'observe_partial_failure';
    // Preserve first post-event facts even if the retry control cannot be revealed.
    await capture('after_report_before_retry_scroll');
    await reveal('retry');
    await capture('after_event');
    const beforeRetry = await capture('before_invariant_retry');
    const retry = beforeRetry.controls.find(c => c.name === 'retry');
    if (!retry.visible || !retry.enabled) throw new Error('Real retry entry is unavailable; remembered-report invariant cannot be exercised');
    stage = 'fixture_retry_boundary_recovery';
    observer.configureResults('success', 'success', 'invariant_retry_recovery');
    await capture('retry_boundary_recovered');
    stage = 'physical_retry_click';
    await click('retry'); raw.invariantEventExecuted = true;
    await capture('after_invariant_retry');
  } catch (error) {
    raw.unsupported = String(error);
    raw.failure = { stage, message: String(error), stack: error && error.stack, code: error && error.code,
      presenter: observer && observer.read() };
    try { await capture('failure_diagnostic_only'); } catch (failure) { raw.failure.captureError = String(failure); }
  } finally {
    if (observer) observer.dispose();
    raw.launchEvidence = launch.read();
    try { await launch.dispose(); } catch (error) { raw.failure = { ...raw.failure, cleanupError: String(error) }; }
  }
  return JSON.stringify(raw);
}
