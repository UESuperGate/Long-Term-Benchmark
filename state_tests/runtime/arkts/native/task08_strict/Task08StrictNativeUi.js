import { runTask08TimelineUI } from './Task08TimelineUI';

let binding;

export function configureTask08StrictBinding(configJson, importModule = url => import(url)) {
  const config = JSON.parse(configJson);
  if (!config.bundleName || config.moduleName !== 'entry' || !['base', 'final', 'agent'].includes(config.role)) {
    throw new Error('Invalid Task08 strict binding');
  }
  binding = { config, importModule };
}

function installObserver(namespace, role) {
  const presenterName = role === 'base' ? 'RoomTimelinePresenter' : 'ThreadPresenter';
  const gatewayName = role === 'base' ? 'RoomTimelineGateway' : 'ThreadGateway';
  const Presenter = namespace[presenterName];
  const Gateway = namespace[gatewayName];
  if (typeof Presenter !== 'function' || typeof Gateway !== 'function') {
    throw new Error(`Original Task08 ${role} production classes unavailable`);
  }
  const calls = [], presenters = [], restores = [];
  let parent;
  const snapshot = presenter => role === 'base' ? {
    events: presenter.events?.slice(), composerText: presenter.composerText,
    sendState: presenter.sendState, gatewayLastBody: presenter.gateway?.lastBody
  } : {
    surface: presenter.surface, threadRootId: presenter.threadRootId,
    threadEvents: presenter.threadEvents?.slice(), mainRoomEvents: presenter.mainRoomEvents?.slice(),
    focusedEventId: presenter.focusedEventId, focusState: presenter.focusState,
    composerText: presenter.composerText, replyTargetId: presenter.replyTargetId,
    sendState: presenter.sendState, attempts: presenter.gateway?.attempts,
    lastEffect: presenter.gateway?.lastEffect, lastBody: presenter.gateway?.lastBody,
    lastThreadRootId: presenter.gateway?.lastThreadRootId,
    lastReplyTargetId: presenter.gateway?.lastReplyTargetId
  };
  const presenterMethods = role === 'base' ? ['setComposerText', 'sendMessage'] : [
    'openThread', 'focusEvent', 'setComposerText', 'setReplyTarget', 'sendMessage',
    'retrySend', 'sendAttachment', 'openAttachmentPreview', 'openNestedSurface',
    'returnToThread', 'navigateBack'
  ];
  const gatewayMethods = role === 'base' ? ['sendMessage'] : ['sendMessage', 'sendAttachment'];
  for (const [owner, methods, presenterOwner] of [[Presenter, presenterMethods, true], [Gateway, gatewayMethods, false]]) {
    for (const method of methods) {
      const descriptor = Object.getOwnPropertyDescriptor(owner.prototype, method);
      if (!descriptor || !descriptor.configurable || typeof descriptor.value !== 'function') {
        throw new Error(`Original Task08 method cannot be observed: ${presenterName}.${method}`);
      }
      const wrapped = function(...args) {
        if (presenterOwner && !presenters.includes(this)) presenters.push(this);
        const presenter = presenterOwner ? this : parent;
        const call = { sequence: calls.length + 1, owner: presenterOwner ? presenterName : gatewayName,
          method, args: args.slice(), completed: false,
          presenterId: presenter ? presenters.indexOf(presenter) + 1 : null,
          sameGatewayReceiver: presenter ? presenter.gateway === this : undefined };
        if (presenter) call.before = snapshot(presenter);
        calls.push(call);
        const previous = parent;
        if (presenterOwner) parent = this;
        try {
          const value = descriptor.value.apply(this, args);
          call.completed = true;
          call.result = value;
          return value;
        } finally {
          if (presenter) call.after = snapshot(presenter);
          parent = previous;
        }
      };
      Object.defineProperty(owner.prototype, method, { ...descriptor, value: wrapped });
      restores.push(() => Object.defineProperty(owner.prototype, method, descriptor));
    }
  }
  return {
    read() {
      return { available: presenters.length === 1, instanceCount: presenters.length,
        state: presenters.length === 1 ? snapshot(presenters[0]) : null,
        calls: JSON.parse(JSON.stringify(calls)) };
    },
    invoke(method, args = []) {
      if (presenters.length !== 1 || typeof presenters[0][method] !== 'function') {
        throw new Error(`Task08 production receiver unavailable for ${method}`);
      }
      return presenters[0][method](...args);
    },
    dispose() { for (const restore of restores.reverse()) restore(); }
  };
}

export async function runTask08StrictNativeUi(caseJson, bundleName, driver, ON, launch) {
  const spec = JSON.parse(caseJson);
  if (!binding || binding.config.bundleName !== bundleName || spec.taskId !== '08_threads') {
    throw new Error('Task08 strict native identity mismatch');
  }
  if (binding.config.productionVariant === 'timeline')
    return runTask08TimelineUI(spec, binding.config, binding.importModule, driver, ON, launch);
  const role = binding.config.role;
  const variant = binding.config.productionVariant;
  const result = { taskId: spec.taskId, caseId: spec.caseId, key: spec.key,
    traceDigest: spec.traceDigest, bundleName, role, productionVariant: variant,
    sessionId: `${spec.caseId}:${Date.now()}`,
    frames: [], actions: [], entryExecuted: false, eventExecuted: false,
    observationMode: 'runtime_state_transition' };
  let observer, verifiedWindow, inputPending = false, sequence = 0, stage = 'start';
  const selectors = {
    roomComposer: [ON.id('room_composer')], roomSend: [ON.id('room_send')],
    roomRoot: [ON.id('room_event_root')], threadRoot: [ON.id('thread_event_root')],
    threadReply: [ON.id('thread_event_reply')], replyReply: [ON.id('thread_reply_reply')],
    composer: [ON.id('thread_composer')], send: [ON.id('thread_send')],
    focus: [ON.id('thread_focus_state')], replyTarget: [ON.id('thread_reply_target')],
    attachment: [ON.id('thread_send_attachment')], preview: [ON.id('thread_attachment_preview')],
    location: [ON.id('thread_location_picker')], poll: [ON.id('thread_poll_composer')],
    nested: [ON.id('thread_nested_surface')], returnToThread: [ON.id('return_to_thread')],
    failNext: [ON.id('thread_fail_next')], retry: [ON.id('thread_retry')],
    back: [ON.id('thread_back')], status: [ON.id('thread_status')]
  };
  const stableText = { threadRoot: '$root', threadReply: '$reply' };
  async function find(name) {
    for (const selector of selectors[name] || []) {
      const nodes = await driver.findComponents(selector.inWindow(bundleName)) || [];
      let matches = nodes;
      if (nodes.length > 1 && stableText[name]) {
        matches = [];
        for (const node of nodes) if (await node.getText() === stableText[name]) matches.push(node);
      }
      if (nodes.length > 1 && name === 'replyReply') {
        const replyNodes = await driver.findComponents(selectors.threadReply[0].inWindow(bundleName)) || [];
        const originalReplies = [];
        for (const node of replyNodes) if (await node.getText() === stableText.threadReply) originalReplies.push(node);
        if (originalReplies.length !== 1) throw new Error('Original Task08 reply event is not unique');
        const replyBounds = await originalReplies[0].getBounds();
        matches = [];
        for (const node of nodes) {
          const bounds = await node.getBounds();
          if (bounds.top === replyBounds.top && bounds.bottom === replyBounds.bottom) matches.push(node);
        }
      }
      if (matches.length > 1) throw new Error(`Ambiguous Task08 control: ${name}`);
      if (matches.length === 1) return matches[0];
    }
    return undefined;
  }
  async function inspect(name) {
    if (!verifiedWindow) throw new Error('Task08 candidate window identity has not been verified');
    const node = await find(name);
    if (!node) return { name, present: false, visible: false };
    const bounds = await node.getBounds(), viewport = verifiedWindow.bounds;
    return { name, present: true, id: await node.getId(), text: await node.getText(),
      enabled: await node.isEnabled(), clickable: await node.isClickable(), bounds,
      visible: Math.min(viewport.right, bounds.right) > Math.max(viewport.left, bounds.left) &&
        Math.min(viewport.bottom, bounds.bottom) > Math.max(viewport.top, bounds.top) };
  }
  async function capture(label) {
    const controls = [];
    for (const name of Object.keys(selectors)) controls.push(await inspect(name));
    const frame = { label, sequence: ++sequence, sessionId: result.sessionId, windowIdentity: verifiedWindow,
      controls, pageObserver: observer?.read() || { available: false } };
    if (variant === 'base') {
      const nodes = await driver.findComponents(ON.inWindow(bundleName));
      if (!Array.isArray(nodes) || !nodes.length) throw new Error('Task08 room native UI inventory unavailable');
      frame.inventory = [];
      for (const node of nodes) frame.inventory.push({ id: await node.getId(), text: await node.getText(),
        type: await node.getType(), bounds: await node.getBounds() });
    }
    result.frames.push(frame);
    return frame;
  }
  const visible = (frame, name) => frame.controls.some(control => control.name === name && control.visible);
  const text = (frame, name) => frame.controls.find(control => control.name === name)?.text;
  async function dismissInputFor(name) {
    if (!inputPending) return;
    const receipt = { kind: 'key', target: 'inputMethod', value: 'Back',
      sequence: ++sequence, executed: false };
    result.actions.push(receipt);
    await driver.pressBack();
    receipt.executed = true;
    inputPending = false;
    for (let attempt = 0; attempt < 20; attempt++) {
      const control = await inspect(name);
      if (control.present && control.visible && control.enabled) return;
      await driver.delayMs(100);
    }
  }
  async function action(kind, name, value) {
    let node = await find(name), control = await inspect(name);
    if ((!node || !control.visible || !control.enabled) && inputPending) {
      await dismissInputFor(name);
      node = await find(name);
      control = await inspect(name);
    }
    if (!node || !control.visible || !control.enabled || (kind === 'click' && !control.clickable)) {
      throw new Error(`Task08 control unavailable for ${kind}: ${name}`);
    }
    const receipt = { kind, target: name, value, sequence: ++sequence, executed: false };
    result.actions.push(receipt);
    if (kind === 'click') await node.click();
    else if (kind === 'input') { await node.inputText(value); inputPending = true; }
    else throw new Error(`Unsupported Task08 action ${kind}`);
    receipt.executed = true;
    await driver.delayMs(100);
  }
  try {
    stage = 'launch';
    await launch.start();
    result.entryExecuted = true;
    let ready = false;
    let readinessError;
    for (let attempt = 0; attempt < 80; attempt++) {
      try {
        verifiedWindow = await launch.check(driver);
        const node = await find(variant === 'base' ? 'roomComposer' : 'roomRoot');
        if (node) { ready = true; break; }
      } catch (error) { readinessError = error; }
      await driver.delayMs(120);
    }
    if (!ready) throw new Error('Original Task08 page did not become ready: ' + String(readinessError || 'anchor absent'));
    result.verifiedWindow = verifiedWindow;
    stage = 'bind_original_page';
    observer = installObserver(await binding.importModule(binding.config.productionModuleUrl), variant);
    if (variant === 'base') {
      const payload = `task08-positive-control:${spec.caseId}`;
      await action('input', 'roomComposer', payload);
      const before = await capture('before_event');
      await action('click', 'roomSend');
      const after = await capture('after_event');
      const state = observer.read().state;
      if (!state || state.gatewayLastBody !== payload || state.composerText !== '' || state.sendState !== 'success') {
        throw new Error('Base room positive-control transition did not complete');
      }
      if (visible(after, 'roomRoot')) throw new Error('Base unexpectedly exposes the final thread route');
      for (const frame of [before, after]) {
        if (frame.inventory.some(node => /^(thread_|room_open_thread_)/.test(node.id) ||
            (/Button/.test(node.type) && /thread/i.test(node.text))))
          throw new Error('Task08 alternate thread entry needs a candidate-specific binding');
      }
      if (!after.inventory.some(node => node.text === payload))
        throw new Error('Task08 real room positive-control message did not render');
      result.basePositiveControl = { roomRendered: visible(before, 'roomComposer'), roomSendCompleted: true,
        requestedAction: 'open_thread', routeAvailable: false };
      result.prefixExecuted = true;
      result.entryFailure = { classification: 'required_feature_entry_missing', requestedAction: 'open_thread',
        positiveControlBody: payload, canonicalEventExecuted: false };
      result.eventExecuted = false;
    } else {
      await action('click', 'roomRoot');
      const opened = await capture('thread_opened');
      if (!visible(opened, 'threadRoot') || !visible(opened, 'threadReply')) {
        throw new Error('Final thread root/reply timeline did not render');
      }
      stage = `case:${spec.key}`;
      if (spec.key === 'open_thread') {
        result.uiAssertions = { threadSurface: true, rootVisible: true, replyVisible: true };
      } else if (spec.key === 'focus_reply') {
        await action('click', 'threadReply');
        const after = await capture('after_event');
        result.uiAssertions = { focusReply: text(after, 'focus') === 'Focus: $reply' };
      } else if (spec.key === 'focus_failure_preserves_thread') {
        await action('click', 'threadReply');
        observer.invoke('focusEvent', ['$missing']);
        const state = observer.read().state;
        await capture('after_event');
        result.uiAssertions = { failedFocusPreserved: state.focusState === 'failure' &&
          state.focusedEventId === spec.expected.focusedEventId && state.threadRootId === '$root' &&
          JSON.stringify(state.threadEvents) === JSON.stringify(['$root', '$reply']) };
      } else if (spec.key === 'send_thread_message') {
        await action('input', 'composer', 'hello');
        await action('click', 'send');
        await dismissInputFor('status');
        const after = await capture('after_event');
        const state = observer.read().state;
        result.uiAssertions = { sent: state.lastEffect === 'send_message' && state.lastBody === 'hello' &&
          state.lastThreadRootId === '$root' && state.composerText === '' && text(after, 'status') === 'Sent in thread' };
      } else if (spec.key === 'reply_remote_event') {
        observer.invoke('setReplyTarget', ['$remote']);
        await action('input', 'composer', 'reply');
        await action('click', 'send');
        await dismissInputFor('status');
        const state = observer.read().state;
        await capture('after_event');
        result.uiAssertions = { remoteReply: state.lastEffect === 'reply_message' && state.lastReplyTargetId === '$remote' &&
          state.lastThreadRootId === '$root' && state.replyTargetId === '' };
      } else if (spec.key === 'send_thread_attachment') {
        await action('click', 'attachment');
        const state = observer.read().state;
        await capture('after_event');
        result.uiAssertions = { attachmentSent: state.lastEffect === 'send_attachment' &&
          state.lastBody === 'image-1:diagram' && state.lastThreadRootId === '$root' };
      } else if (spec.key === 'restore_nested_context') {
        await action('input', 'composer', 'draft');
        await action('click', 'replyReply');
        for (const name of ['preview', 'location', 'poll']) {
          await action('click', name);
          const nested = await capture(`nested_${name}`);
          if (!visible(nested, 'nested')) throw new Error(`Nested Task08 surface missing: ${name}`);
          await action('click', 'returnToThread');
        }
        const state = observer.read().state;
        await capture('after_event');
        result.uiAssertions = { nestedContextRestored: state.surface === 'thread' && state.threadRootId === '$root' &&
          state.composerText === 'draft' && state.replyTargetId === '$reply' };
      } else if (spec.key === 'retry_failed_send') {
        await action('input', 'composer', 'retry me');
        await action('click', 'failNext');
        await action('click', 'send');
        const failed = observer.read().state;
        await capture('failed_send');
        await action('click', 'retry');
        const state = observer.read().state;
        await capture('after_event');
        result.uiAssertions = { retryPreserved: failed.sendState === 'failure' && failed.composerText === 'retry me' &&
          state.sendState === 'success' && state.attempts === 2 && state.lastBody === 'retry me' &&
          state.lastThreadRootId === '$root' };
      } else if (spec.key === 'back_isolates_room') {
        await action('click', 'threadReply');
        await action('input', 'composer', 'thread-only draft');
        await action('click', 'back');
        const after = await capture('after_event'), state = observer.read().state;
        result.uiAssertions = { roomRestored: visible(after, 'roomRoot') && state.surface === 'room' &&
          state.threadRootId === '' && state.focusedEventId === '' && state.replyTargetId === '' && state.composerText === '' };
      } else throw new Error(`Unsupported Task08 case ${spec.key}`);
      if (!Object.values(result.uiAssertions).every(Boolean)) throw new Error('Task08 final UI assertion failed');
      result.finalPositiveControl = { threadOpened: true, rootVisible: true, replyVisible: true };
      result.eventExecuted = true;
    }
  } catch (error) {
    result.failure = { stage, message: String(error), stack: error?.stack };
    try { await capture('failure_diagnostic_only'); } catch (captureError) { result.failure.captureError = String(captureError); }
  } finally {
    observer?.dispose();
    try { await launch.dispose(); } catch (error) { result.failure = { ...result.failure, cleanupError: String(error) }; }
    result.launchEvidence = launch.read();
  }
  return JSON.stringify(result);
}
