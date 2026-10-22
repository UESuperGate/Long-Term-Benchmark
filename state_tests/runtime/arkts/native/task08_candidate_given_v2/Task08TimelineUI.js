const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const need = (value, reason) => { if (!value) throw new Error(reason); };

export function task08SdkRoot(state) {
  const receipt = state.calls.filter(call => call.kind === 'threadGateway' && call.method === 'sendDraft' &&
    call.completed && call.result === true).slice(-1)[0];
  const payload = receipt?.args[0];
  return payload?.threadRootId ?? payload?.relation?.threadRootId ?? receipt?.args[1] ?? null;
}

export function observeTask08Timeline(roomModule, timelineModule, spec) {
  const calls = [], restores = [];
  let room, thread;
  const wrap = (owner, methods, kind) => {
    need(typeof owner === 'function', 'Task08 native production export unavailable: ' + kind);
    for (const method of methods) {
      const descriptor = Object.getOwnPropertyDescriptor(owner.prototype, method);
      need(descriptor?.configurable && typeof descriptor.value === 'function', 'Task08 original method unavailable: ' + method);
      Object.defineProperty(owner.prototype, method, { ...descriptor, value: function(...args) {
        if (kind === 'room') room = this;
        if (kind === 'thread') thread = this;
        if (kind === 'thread' && method === 'openThread') {
          const gateway = this.gateway;
          need(gateway?.corpus?.['$root'] && gateway.corpus['$reply'] && gateway.corpusReplies,
            'Task08 original gateway timeline input records unavailable');
          gateway.corpusReplies['$root'] = [gateway.corpus['$reply']];
          if (spec.key === 'reply_remote_event') {
            need(gateway.corpus['$remote'], 'Task08 remote-event input unavailable');
            gateway.corpusReplies['$root'].push(gateway.corpus['$remote']);
          }
        }
        const receipt = { kind, method, args: clone(args), completed: false };
        calls.push(receipt);
        try { const result = descriptor.value.apply(this, args); receipt.completed = true;
          receipt.result = clone(result); return result;
        } catch (error) { receipt.error = String(error); throw error; }
      } });
      restores.push(() => Object.defineProperty(owner.prototype, method, descriptor));
    }
  };
  try {
    wrap(roomModule.RoomTimelinePresenter, ['setComposerText', 'sendMessage'], 'room');
    wrap(roomModule.RoomTimelineGateway, ['sendMessage'], 'roomGateway');
    wrap(timelineModule.ThreadTimelinePresenter, ['openThread', 'closeThread', 'focusEvent', 'setReplyTarget',
      'setComposerText', 'sendDraft', 'retrySend', 'prepareAttachmentDraft', 'enterSurface', 'returnToThread'], 'thread');
    wrap(timelineModule.ThreadTimelineGateway, ['sendDraft'], 'threadGateway');
  } catch (error) { restores.reverse().forEach(restore => restore()); throw error; }
  return {
    seedRoom() { need(room && Array.isArray(room.events) && room.composerText === '', 'Original room fixture boundary unavailable');
      room.events = ['$root', '$reply']; },
    invoke(method, args) { need(thread && typeof thread[method] === 'function', 'Original thread receiver unavailable');
      return thread[method](...args); },
    failNextSend() { need(thread?.gateway, 'Original thread gateway unavailable'); thread.gateway.failNextSend = true; },
    read() { return clone({ room: room && { events: room.events, composerText: room.composerText,
        lastBody: room.gateway.lastBody, mainRoomFocus: room.focusedEventId ?? null }, thread: thread && { ...thread.snapshot(),
        sentDrafts: thread.gateway.sentDrafts, pendingFailedDraft: thread.pendingFailedDraft }, calls }); },
    dispose() { restores.reverse().forEach(restore => restore()); }
  };
}

export async function runTask08TimelineUI(spec, config, importModule, driver, ON, launch) {
  const result = { taskId: spec.taskId, caseId: spec.caseId, key: spec.key, traceDigest: spec.traceDigest,
    role: config.role, bundleName: config.bundleName, productionVariant: 'timeline',
    observationMode: 'runtime_state_transition', sessionId: spec.caseId + ':' + Date.now(),
    frames: [], actions: [], entryExecuted: false, eventExecuted: false };
  let observer, window, inputPending = false, stage = 'bind';
  const find = async id => {
    const nodes = await driver.findComponents(ON.id(id).inWindow(config.bundleName));
    if (nodes == null) return null;
    need(Array.isArray(nodes), 'Task08 native Driver query unavailable: ' + id);
    need(nodes.length < 2, 'Task08 ambiguous original control: ' + id);
    return nodes[0];
  };
  const inspect = async id => {
    const node = await find(id);
    if (!node) return { id, present: node === null ? null : false, visible: node === null ? undefined : false };
    const bounds = await node.getBounds();
    return { id, present: true, text: await node.getText(), enabled: await node.isEnabled(),
      clickable: await node.isClickable(), bounds,
      visible: Math.min(window.bounds.right, bounds.right) > Math.max(window.bounds.left, bounds.left) &&
        Math.min(window.bounds.bottom, bounds.bottom) > Math.max(window.bounds.top, bounds.top) };
  };
  const action = async (kind, id, value) => {
    let target = await inspect(id);
    if (inputPending && (kind === 'click' || !target.visible)) {
      await driver.pressBack(); inputPending = false; await driver.delayMs(100); target = await inspect(id);
      result.actions.push({ kind: 'key', target: 'inputMethod', value: 'Back', executed: true });
    }
    if (id === 'thread_open_poll' && spec.key === 'restore_nested_context' &&
        !(target.present && target.visible && target.enabled && target.clickable)) {
      const samples = [];
      for (let attempt = 0; attempt < 2; attempt++) {
        await driver.delayMs(250);
        const identity = await launch.check(driver);
        const nodes = await driver.findComponents(ON.inWindow(config.bundleName));
        need(Array.isArray(nodes) && nodes.length > 2, 'Task08 complete native entry inventory unavailable');
        const inventory = [];
        for (const node of nodes) inventory.push({ id: await node.getId(), text: await node.getText(),
          type: await node.getType(), bounds: await node.getBounds() });
        target = await inspect(id);
        const textMatches = await driver.findComponents(ON.text('Poll').inWindow(config.bundleName));
        samples.push({ windowIdentity: identity, target, inventory, pollTextCount: textMatches?.length || 0 });
      }
      if (!(target.present && target.visible && target.enabled && target.clickable)) {
        const error = new Error('Required original Poll entry is unreachable after native nested navigation');
        error.entryFailure = { classification: 'required_nested_entry_unreachable', target: id, samples };
        throw error;
      }
    }
    if (!(target.present && target.visible && target.enabled && (kind !== 'click' || target.clickable)))
      result.actions.push({ kind: 'unavailable_control', target: id, inspected: target, executed: false });
    need(target.present && target.visible && target.enabled && (kind !== 'click' || target.clickable),
      'Task08 original timeline control unavailable: ' + id);
    const node = await find(id);
    if (kind === 'input') {
      if (value === '') await node.clearText(); else await node.inputText(value);
      inputPending = true;
    }
    else await node.click();
    result.actions.push({ kind, target: id, value, executed: true }); await driver.delayMs(100);
  };
  const capture = async label => {
    window = await launch.check(driver);
    const state = observer.read(), controls = [];
    for (const id of ['room_composer', 'room_open_thread_$root', 'thread_composer', 'thread_back',
      'thread_reply_target', 'thread_focus_$root', 'thread_focus_$reply', 'thread_focus_error', 'thread_failure_banner'])
      controls.push(await inspect(id));
    result.frames.push({ label, state, controls }); return state;
  };
  const invariant = (passed, observed) => {
    need(spec.invariants.length === 1, 'Task08 canonical invariant shape changed');
    result.invariantChecks = [{ description: spec.invariants[0], passed: Boolean(passed), observed: clone(observed) }];
  };
  const ids = state => state.thread.visibleEvents.map(event => event.id);
  const mode = state => state.thread.lifecycle === 'open' ? 'thread' : 'room';
  const root = state => state.thread.rootEvent?.id || null;
  const sent = state => state.thread.visibleEvents.filter(event => event.senderId === '@me:qingyu.dev').slice(-1)[0];
  const draft = state => state.thread.sentDrafts.slice(-1)[0];
  const effect = state => !draft(state) ? null : draft(state).draftKind === 'attachment' ? 'send_attachment' :
    draft(state).replyTargetId ? 'reply_message' : 'send_message';
  const sdkRoot = task08SdkRoot;
  const roomUnchanged = state => JSON.stringify(state.room.events) === '["$root","$reply"]' &&
    state.room.lastBody === '' && !state.calls.some(call => call.kind === 'roomGateway');
  try {
    stage = 'launch'; await launch.start(); result.entryExecuted = true;
    for (let attempt = 0; attempt < 80; attempt++) {
      try { window = await launch.check(driver); if (await find('room_composer')) break; }
      catch (error) { if (attempt === 79) throw error; }
      await driver.delayMs(120);
    }
    need(window, 'Task08 original window unavailable'); result.verifiedWindow = window;
    // Entry's ABC must be loaded by its original Ability before a test-process
    // dynamic import; importing first is treated as an absent entry.hsp on API23.
    stage = 'bind-original-page';
    observer = observeTask08Timeline(await importModule(config.roomModuleUrl), await importModule(config.timelineModuleUrl), spec);
    // Seed incoming timeline records on the real receiver. The original empty
    // send handler refreshes its page mirror without dispatching any message.
    stage = 'fixture-prefix';
    await action('input', 'room_composer', 'fixture-input');
    await action('input', 'room_composer', ''); observer.seedRoom();
    await action('click', 'room_send');
    const given = await capture('fixture_room_ready');
    need(roomUnchanged(given), 'Task08 room fixture emitted an unintended message');
    if (spec.key === 'open_thread') await capture('before_event');
    await action('click', 'room_open_thread_$root');
    let state = await capture('thread_opened');
    need(state.thread && mode(state) === 'thread' && root(state) === '$root', 'Task08 original thread entry incomplete');
    stage = spec.key;
    if (spec.key === 'open_thread') {
      state = await capture('after_event');
      result.observed = { surface: state.thread.surface, timelineMode: mode(state), threadRootId: root(state), visibleEvents: ids(state) };
      invariant(roomUnchanged(state), state.room);
    } else if (['focus_reply', 'focus_failure_preserves_thread'].includes(spec.key)) {
      if (spec.key === 'focus_failure_preserves_thread') await action('click', 'thread_focus_$reply');
      const before = await capture('before_event');
      if (before.thread.focusedEventId !== spec.given.focusedEventId) {
        const error = new Error('Canonical focus given not reached by the original page prefix');
        error.fixtureFailure = { classification: 'fixture_given_unreachable',
          field: 'focusedEventId', required: spec.given.focusedEventId,
          actual: before.thread.focusedEventId, beforeFrame: 'before_event',
          canonicalEventEvaluated: false, poststateEvaluated: false, invariantsEvaluated: false };
        throw error;
      }
      if (spec.key === 'focus_reply') await action('click', 'thread_focus_$reply');
      else {
        observer.invoke('focusEvent', ['$missing']);
        // The canonical failed-focus API has no on-screen missing-event row.
        // Refresh the real page via its own composer handler, retaining focus.
        await action('input', 'thread_composer', 'fixture-refresh');
        await action('input', 'thread_composer', '');
      }
      state = await capture('after_event');
      const call = state.calls.filter(value => value.kind === 'thread' && value.method === 'focusEvent').slice(-1)[0];
      result.observed = { focusedEventId: state.thread.focusedEventId, focusState: call.result ? 'success' : 'failure', timelineMode: mode(state) };
      if (spec.key === 'focus_failure_preserves_thread') result.observed.visibleEvents = ids(state);
      invariant(root(state) === '$root' && JSON.stringify(ids(state)) === '["$root","$reply"]' && roomUnchanged(state), state);
    } else if (['send_thread_message', 'reply_remote_event', 'retry_failed_send'].includes(spec.key)) {
      const body = spec.key === 'send_thread_message' ? 'hello' : spec.key === 'reply_remote_event' ? 'reply' : 'retry me';
      if (spec.key === 'reply_remote_event') observer.invoke('setReplyTarget', ['$remote']);
      await action('input', 'thread_composer', body);
      let failed;
      if (spec.key === 'retry_failed_send') {
        observer.failNextSend(); await action('click', 'thread_send'); failed = await capture('failed_send');
        need(failed.thread.sendState === 'failure', 'Original failed-send given not established');
      }
      await capture('before_event');
      await action('click', spec.key === 'retry_failed_send' ? 'thread_retry' : 'thread_send');
      state = await capture('after_event');
      // A local optimistic event's root is not evidence of SDK send relation.
      result.observed = { sendState: state.thread.sendState, effect: effect(state), threadRootId: sdkRoot(state) };
      if (spec.key === 'reply_remote_event') {
        result.observed.replyTargetId = sent(state)?.parentId;
        result.observed.composerMode = state.thread.replyTargetId === null ? 'normal' : 'reply';
        invariant(sent(state)?.parentId === '$remote' && sdkRoot(state) === '$root' && roomUnchanged(state), state);
      } else {
        result.observed.body = draft(state)?.text;
        if (spec.key === 'send_thread_message') result.observed.composerText = state.thread.composerText;
        else result.observed.attempts = state.thread.attempts;
        invariant(roomUnchanged(state) && sdkRoot(state) === '$root' &&
          (!failed || failed.thread.pendingFailedDraft?.text === 'retry me'), { failed, state });
      }
    } else if (spec.key === 'send_thread_attachment') {
      await action('click', 'thread_open_attachment');
      await action('input', 'attachment_id_input', 'image-1');
      await action('input', 'attachment_caption_input', 'diagram');
      await capture('before_event'); await action('click', 'attachment_confirm'); state = await capture('after_event');
      result.observed = { effect: effect(state), attachmentId: draft(state)?.attachmentId,
        caption: draft(state)?.caption, threadRootId: sdkRoot(state), sendState: state.thread.sendState };
      invariant(sdkRoot(state) === '$root' && roomUnchanged(state), state);
    } else if (spec.key === 'restore_nested_context') {
      await action('input', 'thread_composer', 'draft'); await action('click', 'thread_reply_$reply');
      const nested = [];
      for (const [open, back] of [['thread_open_attachment', 'attachment_discard'],
        ['thread_open_location', 'location_discard'], ['thread_open_poll', 'poll_discard']]) {
        await action('click', open); await capture('before_event'); await action('click', back); nested.push(await capture('after_event'));
      }
      state = observer.read();
      result.observed = { surface: state.thread.surface, threadRootId: root(state), composerText: state.thread.composerText,
        replyTargetId: state.thread.replyTargetId };
      invariant(nested.every(value => value.thread.surface === 'thread' && root(value) === '$root' &&
        value.thread.composerText === 'draft' && value.thread.replyTargetId === '$reply'), nested);
    } else if (spec.key === 'back_isolates_room') {
      await action('click', 'thread_focus_$reply'); await action('input', 'thread_composer', 'thread-only draft');
      await capture('before_event'); await action('click', 'thread_back'); state = await capture('after_event');
      result.observed = { surface: mode(state), threadRootId: root(state), mainRoomFocus: state.room.mainRoomFocus };
      invariant(state.thread.focusedEventId === null && state.thread.replyTargetId === null &&
        state.thread.composerText === '' && state.room.composerText === '' && roomUnchanged(state), state);
    } else throw new Error('Unsupported Task08 canonical key: ' + spec.key);
    const rendered = result.frames.filter(frame => frame.label === 'after_event').slice(-1)[0];
    const control = id => rendered.controls.find(value => value.id === id);
    const uiChecks = {};
    if (state.thread.lifecycle === 'open') {
      need(control('thread_composer')?.present === true, 'Task08 original thread composer query incomplete');
      uiChecks.composerMirror = control('thread_composer').text === state.thread.composerText;
      uiChecks.rootAndReplyRendered = control('thread_focus_$root')?.present === true &&
        control('thread_focus_$reply')?.present === true;
      if (state.thread.replyTargetId !== null) uiChecks.replyTargetMirror =
        control('thread_reply_target')?.text?.includes(state.thread.replyTargetId) === true;
      if (state.thread.lastFocusedError) uiChecks.focusErrorMirror =
        control('thread_focus_error')?.text === state.thread.lastFocusedError;
    } else {
      need(control('room_composer')?.present === true, 'Task08 original room composer query incomplete');
      uiChecks.roomComposerMirror = control('room_composer').text === state.room.composerText;
      uiChecks.roomEntryRendered = control('room_open_thread_$root')?.present === true;
    }
    result.uiAssertions = uiChecks;
    result.invariantChecks[0].passed = result.invariantChecks[0].passed && Object.values(uiChecks).every(Boolean);
    result.eventExecuted = true;
  } catch (error) {
    if (error.fixtureFailure) {
      result.fixtureFailure = error.fixtureFailure;
      result.invariantChecks = [];
    } else if (error.entryFailure) {
      result.entryFailure = error.entryFailure; result.prefixExecuted = true;
    } else result.failure = { stage, message: String(error.message || error), stack: String(error.stack || '') };
    try { await capture('failure_diagnostic_only'); } catch (ignored) { /* Keep the original failure. */ }
  } finally {
    observer?.dispose();
    try { await launch.dispose(); } catch (error) { result.failure = { ...result.failure, cleanupError: String(error) }; }
    result.launchEvidence = launch.read();
  }
  return JSON.stringify(result);
}
