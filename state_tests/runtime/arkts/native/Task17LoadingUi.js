import { observeTask17Loading } from './Task17LoadingObserver';
import { createTask17LoadingFrames } from './Task17LoadingFrames';
import { createTask17LoadingReadback } from './Task17LoadingReadback';

let binding;
export function configureTask17Loading(configJson, importModule = url => import(url)) {
  const config = JSON.parse(configJson);
  if (!config.bundleName || config.moduleName !== 'entry' || config.productionModuleUrl !==
    '@bundle:' + config.bundleName + '/entry/ets/features/PinnedMessagesFeature') throw new Error('Invalid Task17 original module identity');
  binding = { config, importModule };
}
export async function runTask17LoadingUi(caseJson, bundleName, driver, ON, launch, preferences, alreadyStarted = false) {
  const spec = JSON.parse(caseJson), result = { taskId: spec.taskId, caseId: spec.caseId, traceDigest: spec.traceDigest,
    bundleName, sessionId: spec.caseId + ':' + Date.now(), frames: [], actions: [], entryExecuted: false, eventExecuted: false };
  let observer, sampler, readback, sequence = 0, stage = 'validate';
  const selectors = { room: [ON.text('Design team')], focus: [ON.id('focused_event_label')],
    banner: [ON.id('pinned_messages_banner')], open: [ON.id('open_pinned_messages')],
    back: [ON.id('pinned_messages_back')], loading: [ON.id('pinned_messages_loading')],
    filled: [ON.id('pinned_messages_filled')], empty: [ON.id('pinned_messages_empty')], failed: [ON.id('pinned_messages_failed')] };
  async function find(name) {
    for (const selector of selectors[name]) {
      const nodes = await driver.findComponents(selector.inWindow(bundleName)) || [];
      if (nodes.length > 1) throw new Error('Ambiguous Task17 native control: ' + name);
      if (nodes.length) return nodes[0];
    }
  }
  async function inspect(name) {
    const window = await launch.check(driver), node = await find(name);
    if (!node) return { name, present: false, visible: false };
    const bounds = await node.getBounds(), viewport = window.bounds;
    return { name, present: true, text: await node.getText(), id: await node.getId(), enabled: await node.isEnabled(), bounds,
      visible: Math.min(viewport.right, bounds.right) > Math.max(viewport.left, bounds.left) &&
        Math.min(viewport.bottom, bounds.bottom) > Math.max(viewport.top, bounds.top) };
  }
  async function capture(label) {
    const controls = [];
    for (const name of Object.keys(selectors)) controls.push(await inspect(name));
    const frame = { label, sequence: ++sequence, sessionId: result.sessionId, bundleName, controls,
      windowIdentity: launch.read().lastReady, observer: observer ? JSON.parse(observer.snapshot()) : null };
    result.frames.push(frame); return frame;
  }
  async function click(name) {
    const control = await inspect(name);
    if (!control.visible || !control.enabled) throw new Error('Original UI control unavailable/disabled: ' + name);
    const node = await find(name), action = { kind: 'click', target: name, sequence: ++sequence, sessionId: result.sessionId, executed: false };
    result.actions.push(action); await node.click(); action.executed = true;
  }
  try {
    if (spec.taskId !== '17_pinned_messages' || spec.key !== 'open_loading' || spec.given.screen !== 'room_timeline' ||
      spec.given.pinnedList !== 'closed' || spec.event.name !== 'open_pinned_messages' ||
      !/^[a-f0-9]{64}$/.test(spec.traceDigest) || !binding || binding.config.bundleName !== bundleName) throw new Error('Unsupported Task17 case/binding');
    stage = alreadyStarted ? 'verify_existing_launch' : 'launch';
    if (alreadyStarted) await launch.check(driver);
    else await launch.start();
    result.entryExecuted = true;
    stage = 'await_original_room';
    result.readiness = { ready: false, attempts: [] };
    const started = Date.now();
    for (let attempt = 0; attempt < 40 && Date.now() - started < 6000; attempt++) {
      try {
        const room = await inspect('room'), open = await inspect('open');
        result.readiness.attempts.push({ attempt, room: room.visible, open: open.visible && open.enabled });
        if (room.visible && open.visible && open.enabled) { result.readiness.ready = true; break; }
      } catch (error) { result.readiness.attempts.push({ attempt, error: String(error) }); }
      await driver.delayMs(150);
    }
    if (!result.readiness.ready) throw new Error('Original room bounded readiness exhausted');
    stage = 'postload_binding';
    const namespace = await binding.importModule(binding.config.productionModuleUrl);
    result.binding = { ...binding.config, importCompleted: true, phase: 'after_original_room_ready_before_open' };
    const native = launch.current();
    observer = observeTask17Loading(namespace.PinnedMessagesListPresenter, namespace.PinnedMessagesRepository,
      preferences, native.abilityContext, { nativeReadback: true, onOpenReturned() { sampler.start(); } });
    sampler = createTask17LoadingFrames({ current: () => launch.current(), getInspectorTree: () => launch.getInspectorTree() },
      () => JSON.parse(observer.snapshot()));
    stage = 'read_original_store_before_open';
    readback = createTask17LoadingReadback(preferences, native.abilityContext);
    result.persistence = { before: await readback.before(launch.current().abilityContext) };
    result.persistence.before.sequence = ++sequence;
    if (result.persistence.before.present !== false) throw new Error('Fresh canonical entry requires absent stored key; no clearing or seeding is allowed');
    const before = await capture('before_event');
    const visible = name => before.controls.some(c => c.name === name && c.visible);
    if (!visible('room') || !visible('banner') || !visible('open') || visible('back') || visible('loading') || visible('filled') || visible('empty') || visible('failed')) {
      throw new Error('Canonical actual room/list-closed given not established');
    }
    stage = 'physical_open'; await click('open'); result.eventExecuted = true;
    stage = 'natural_frames';
    // Only waits outside production calls. No Promise gate or replacement I/O.
    const frameStarted = Date.now();
    for (let attempt = 0; attempt < 12 && Date.now() - frameStarted < 2000; attempt++) {
      if (!sampler.snapshot().active) break;
      await driver.delayMs(100);
    }
    result.loadingFrames = sampler.snapshot(); sampler.dispose();
    const after = await capture('after_event_settled_or_bounded');
    result.observer = JSON.parse(observer.snapshot());
    if (!result.observer.singlePresenterCallChainObserved || result.observer.presenterCount !== 1 || result.observer.repositoryCount !== 1) {
      throw new Error('Original page/presenter/repository receiver not observed');
    }
    stage = 'await_original_completion_for_readback';
    const completionStart = Date.now();
    let completed = false;
    for (let attempt = 0; attempt < 20 && Date.now() - completionStart < 2000; attempt++) {
      await launch.check(driver);
      const calls = JSON.parse(observer.snapshot()).calls;
      completed = ['openPinnedMessages', 'openPinnedTimeline', 'persistPinnedState'].every(method =>
        calls.some(call => call.method === method && call.phase === 'fulfilled'));
      if (completed) break;
      await driver.delayMs(100);
    }
    if (!completed) throw new Error('Original load/initialization did not complete; cache is not touched while production I/O may be pending');
    stage = 'read_original_store_after_completion';
    result.persistence.originalCompletion = JSON.parse(observer.snapshot());
    result.persistence.originalCompletionSequence = ++sequence;
    result.persistence.after = await readback.after(launch.current().abilityContext);
    result.persistence.after.sequence = ++sequence;
    if (!after.controls.some(c => c.name === 'back' && c.visible && c.enabled)) throw new Error('Actual parent-return control unavailable');
    stage = 'physical_back'; await click('back');
    for (let attempt = 0; attempt < 10; attempt++) { if ((await inspect('room')).visible) break; await driver.delayMs(100); }
    await capture('after_parent_return'); result.parentReturnExecuted = true;
  } catch (error) {
    result.failure = { stage, message: String(error), stack: error?.stack };
  } finally {
    if (sampler) { result.loadingFrames = sampler.snapshot(); sampler.dispose(); }
    if (observer) { result.observer = JSON.parse(observer.snapshot()); observer.dispose(); }
    if (readback) result.persistence = { ...result.persistence, ...readback.snapshot() };
    result.launchEvidence = launch.read();
    try { await launch.dispose(); } catch (error) { result.failure = { ...result.failure, cleanupError: String(error) }; }
  }
  return JSON.stringify(result);
}
