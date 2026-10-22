'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { isDeepStrictEqual } = require('node:util');
const { setTimeout: delay } = require('node:timers/promises');

const ROOT = 'entry/src/main/ets/features/';
const LIMITATIONS = 'Host JavaScript execution of transpiled original .ets production modules. ' +
  'Observations are production_domain, not native ArkUI rendering, device media encoding, persistence, or network integration.';

class Unbound extends Error {}
const requireCapability = (condition, reason) => { if (!condition) throw new Unbound(reason); };
const has = (object, name) => typeof object?.[name] === 'function';
const nullable = value => value === '' || value === undefined ? null : value;
const copy = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value, (_key, item) => {
  if (item instanceof Map || Object.prototype.toString.call(item) === '[object Map]') return Object.fromEntries(item);
  if (item instanceof Set || Object.prototype.toString.call(item) === '[object Set]') return Array.from(item);
  return item;
}));
// The loader executes exports in another VM realm. Compare serialized state,
// not Array/Object prototypes belonging to different JavaScript contexts.
const equal = (left, right) => isDeepStrictEqual(copy(left), copy(right));
const enumState = (table, value) => typeof value === 'number' ? table?.[value]?.toLowerCase() : value;
const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};

async function modules(ctx, names) {
  const exports = {};
  for (const name of names) {
    const relative = ROOT + name + '.ets';
    if (!fs.existsSync(path.join(ctx.project, relative))) continue;
    try {
      Object.assign(exports, await ctx.load(relative));
      ctx.evidence.push({ module: relative, observationLevel: 'production_domain' });
    } catch (error) {
      throw new Unbound(`Cannot load production module ${relative}: ${error.message}`);
    }
  }
  return exports;
}

function method(object, names) {
  const name = names.find(candidate => has(object, candidate));
  requireCapability(name, `No production API bound for ${names.join(' / ')}`);
  return (...args) => object[name](...args);
}

function checkpoint(ctx, label, data) {
  const snapshot = copy(data);
  ctx.evidence.push({ label, data: snapshot, observationLevel: 'production_domain' });
  ctx.trace(label, snapshot);
  return snapshot;
}

function check(ctx, passed, observed) {
  // These cases currently have one invariant each. Never silently certify newly added ones.
  requireCapability(ctx.caseSpec.invariants.length === 1, 'Invariant contract changed; explicit binding required');
  if (ctx.bindingUnsupported) {
    ctx.unsupportedInvariants.push({ description: ctx.caseSpec.invariants[0], reason: ctx.bindingUnsupported });
    checkpoint(ctx, 'diagnostic:invariant', { description: ctx.caseSpec.invariants[0],
      passed: Boolean(passed), observed, scorable: false, reason: ctx.bindingUnsupported });
    return;
  }
  ctx.invariantChecks.push({ description: ctx.caseSpec.invariants[0], passed: Boolean(passed), observed: copy(observed) });
}

function unsupportedFixture(ctx, reason, observed) {
  ctx.bindingUnsupported = reason;
  const diagnostic = { kind: 'fixture_not_established', reason, observed: copy(observed), scorable: false };
  ctx.notes.push(diagnostic);
  checkpoint(ctx, 'fixture:unsupported', diagnostic);
}

function watch(gateway, names, ctx) {
  const calls = [];
  for (const name of names) {
    if (!has(gateway, name)) continue;
    const original = gateway[name].bind(gateway);
    gateway[name] = (...args) => {
      const call = { method: name, args: copy(args) };
      calls.push(call);
      const result = original(...args);
      if (result && typeof result.then === 'function') {
        checkpoint(ctx, `gateway:${name}:pending`, call);
        return result.then(value => {
          call.result = copy(value);
          checkpoint(ctx, `gateway:${name}:completed`, call);
          return value;
        }, error => {
          call.error = String(error);
          checkpoint(ctx, `gateway:${name}:failed`, call);
          throw error;
        });
      }
      call.result = result;
      checkpoint(ctx, `gateway:${name}`, call);
      return call.result;
    };
  }
  return calls;
}

function failNext(gateway, names) {
  const name = names.find(key => key in gateway);
  requireCapability(name, `External dependency has no failure control (${names.join(', ')})`);
  gateway[name] = true;
}

async function legacyDomain(ctx, m, family) {
  await observeLegacyEntry(ctx, family);
  const key = ctx.caseSpec.key;
  const g = ctx.caseSpec.given;
  let observed = {};
  if (family === 'threads' && m.RoomTimelinePresenter && m.RoomTimelineGateway) {
    const gateway = new m.RoomTimelineGateway();
    const calls = watch(gateway, ['sendMessage'], ctx);
    const p = new m.RoomTimelinePresenter(gateway);
    const snapshot = () => ({ mainRoomEvents: copy(p.events), composerText: p.composerText, sendState: p.sendState });
    requireCapability(has(p, 'setComposerText') && has(p, 'sendMessage'),
      'Legacy room positive-control entrypoints are unavailable');
    const positiveText = `task08-positive-control:${ctx.caseSpec.caseId}`;
    const roomBefore = snapshot();
    p.setComposerText(positiveText);
    const roomSendResult = p.sendMessage();
    const roomAfter = snapshot();
    requireCapability(roomSendResult === true && gateway.lastBody === positiveText &&
      roomAfter.composerText === '' && roomAfter.mainRoomEvents.length === roomBefore.mainRoomEvents.length + 1,
      'Legacy room positive-control transition did not complete');

    const actionPrefix = {
      startSurface: 'room',
      roomTimelineReachable: true,
      roomSendCompleted: true,
      requestedAction: 'open_thread',
      rootEventId: g.threadRootId ?? ctx.caseSpec.event.rootEventId ?? '$root',
      routeAvailable: false,
      reason: 'The production base has no ThreadPresenter/openThread route.'
    };
    checkpoint(ctx, 'task08:common-room-positive-control', { before: roomBefore, after: roomAfter, calls: copy(calls) });
    checkpoint(ctx, 'before:event', { room: roomAfter, actionPrefix });

    // These values are observations of the reachable base room after the same
    // open-thread prefix, not projections of the canonical expected object.
    const baseState = {
      surface: 'room', timelineMode: 'room', threadRootId: null,
      visibleEvents: copy(roomAfter.mainRoomEvents), focusedEventId: null,
      focusState: 'unavailable', sendState: roomAfter.sendState,
      effect: 'send_message', body: positiveText, composerText: '',
      replyTargetId: null, composerMode: 'normal', attachmentId: null,
      caption: null, attempts: calls.length, mainRoomFocus: null
    };
    observed = {};
    for (const field of Object.keys(ctx.caseSpec.expected || {})) observed[field] = baseState[field];
    for (const description of ctx.caseSpec.invariants || []) {
      ctx.invariantChecks.push({ description, passed: false, observed: { actionPrefix, roomBefore, roomAfter } });
    }
    checkpoint(ctx, 'after:event', { observed, roomState: roomAfter, actionPrefix, calls });
    ctx.notes.push({ kind: 'semantic_absence_after_reachable_prefix', actionPrefix,
      reason: 'The shared room entry and room-send control passed; the canonical thread route remained absent.' });
  } else if (family === 'spaces' && m.HomeRoomsPresenter) {
    const p = new m.HomeRoomsPresenter();
    const snapshot = () => ({ rooms: copy(p.rooms), selectedRoomId: p.selectedRoomId });
    checkpoint(ctx, 'before:event', snapshot());
    checkpoint(ctx, 'after:event', { executed: false, home: snapshot() });
    ctx.bindingUnsupported = 'Home-room presenter instantiated; ordinary openRoom is not a Space lifecycle operation and cannot bind this event.';
  } else if (family === 'media' && m.AttachmentPresenter && m.AttachmentGateway) {
    const gateway = new m.AttachmentGateway();
    const calls = watch(gateway, ['send'], ctx);
    const p = new m.AttachmentPresenter(gateway);
    const snapshot = () => ({ caption: p.caption, sendState: p.sendState });
    if (key === 'failure_cancel_retry' && has(p, 'setCaption') && has(p, 'send')) {
      p.setCaption(g.caption);
      failNext(gateway, ['failNextSend']);
      p.send();
      checkpoint(ctx, 'before:event', snapshot());
      // Direct retry is supported here. There is no clear-failure/quality API,
      // so only shared upload results are observed and the case stays unscored.
      p.send();
      observed = { finalState: p.sendState, caption: gateway.lastCaption, attempts: calls.length };
    } else {
      checkpoint(ctx, 'before:event', snapshot());
      if (key === 'async_loading') {
        p.setCaption('caption while preview is open');
        observed = { sendState: p.sendState };
      }
    }
    checkpoint(ctx, 'after:event', { observed, attachmentState: snapshot(), calls });
    ctx.bindingUnsupported = 'Attachment behavior executed; no quality, metadata/limit loading, or prepared-media recovery API binds the canonical fixture.';
  } else if (family === 'roomUpgrade' && m.RoomPresenter && m.RoomGateway) {
    const p = new m.RoomPresenter(new m.RoomGateway());
    const before = checkpoint(ctx, 'before:event', { history: p.history, room: p.room });
    if (key === 'tombstone_is_read_only') observed = { history: copy(p.history) };
    if (key === 'room_list_tombstone_preview') observed = { preview: p.room?.lastMessage };
    checkpoint(ctx, 'after:event', { observed, history: p.history, room: p.room });
    if (key === 'room_list_tombstone_preview') check(ctx,
      p.room?.lastMessage === g.lastMessage && equal(before.history, p.history), { before, after: { history: p.history, room: p.room } });
    ctx.bindingUnsupported = 'Room history/summary production state was read; successor/predecessor ingestion and native upgrade rendering are unavailable.';
  } else throw new Unbound(`No compatible production ${family} exports are available`);
  if (ctx.bindingUnsupported) ctx.notes.push({ kind: 'partial_production_observation', reason: ctx.bindingUnsupported });
  return observed;
}

async function observeLegacyEntry(ctx, family) {
  const ui = ctx.native?.ui;
  if (!has(ui, 'snapshot')) return;
  const record = (label, data) => {
    ctx.evidence.push({ label, data: copy(data), observationLevel: 'native_candidate_ui' });
    ctx.trace(label, copy(data));
  };
  try {
    const before = await ui.snapshot();
    const anchorIds = { threads: ['room_composer', 'room_send'], spaces: [],
      media: ['attachment_caption', 'attachment_send'], roomUpgrade: ['message_composer', 'room_list_old_room'] }[family];
    const anchored = anchorIds.length && has(ui, 'observe') ? await ui.observe(anchorIds, anchorIds[0]) : undefined;
    requireCapability((before.candidatePageVerified === true && before.completeTree === true) || anchored?.available,
      'Baseline candidate route and a real rendered root/anchor were not verified');
    const nodes = [];
    const visit = node => {
      if (!node || typeof node !== 'object') return;
      const attrs = node.$attrs ?? {};
      nodes.push({ type: node.$type, id: attrs.id, text: attrs.content ?? attrs.text,
        enabled: attrs.enabled, visibility: attrs.visibility, bounds: node.$rect });
      for (const child of node.$children ?? node.children ?? []) visit(child);
    };
    visit(before.tree);
    const title = { threads: 'Element X Room', spaces: 'Element X Home', media: 'Attachment preview', roomUpgrade: 'Product planning' }[family];
    const rootObserved = nodes.some(node => node.text === title) || anchored?.available === true;
    record('native:legacy-entry-before', { caseId: ctx.caseSpec.caseId, route: before.route, rootObserved, nodes, anchored });
    // A legacy room opening is diagnostic, not the canonical upgrade action.
    // Do not send a room message or replace a Space/thread event with this action.
    let action;
    if (family === 'roomUpgrade' && rootObserved && has(ui, 'observe') && has(ui, 'sendEvent')) {
      const view = await ui.observe(['room_list_old_room'], 'message_composer');
      const control = view.controls?.find(item => item.id === 'room_list_old_room');
      if (view.available && control?.present && ['true', true].includes(control.node?.$attrs?.enabled))
        action = { id: 'room_list_old_room', transportResult: await ui.sendEvent('room_list_old_room', 10, {}), canonicalEvent: false };
    }
    record('native:legacy-entry-after', { caseId: ctx.caseSpec.caseId, action, snapshot: await ui.snapshot(),
      candidateState: has(ctx.native?.roomUpgrade, 'read') ? ctx.native.roomUpgrade.read() : undefined,
      givenEstablished: false, semanticVerdict: null });
    ctx.notes.push({ kind: 'native_legacy_entry', rootObserved,
      reason: 'Actual legacy entry was inspected. Missing feature selectors alone do not establish canonical given or semantic failure.' });
  } catch (error) {
    record('native:legacy-entry-unavailable', { reason: error.message });
  }
}

async function threads(ctx) {
  const m = await modules(ctx, ['ThreadFeature', 'ThreadTimelineFeature', 'RoomTimelineFeature']);
  const Presenter = [m.ThreadPresenter, m.ThreadTimelinePresenter].find(C => C && has(C.prototype, 'openThread'));
  const Gateway = [m.ThreadGateway, m.ThreadTimelineGateway].find(C => C &&
    (has(C.prototype, 'sendMessage') || has(C.prototype, 'sendThreadMessage')));
  if (!Presenter || !Gateway) return legacyDomain(ctx, m, 'threads');
  const gateway = new Gateway();
  const g = ctx.caseSpec.given;
  if (has(gateway, 'getRoomTimeline') && g.roomTimeline) gateway.getRoomTimeline = () => copy(g.roomTimeline);
  if (has(gateway, 'getThreadTimeline') && g.visibleEvents) gateway.getThreadTimeline = () => copy(g.visibleEvents);
  const calls = watch(gateway, ['sendMessage', 'sendThreadMessage', 'sendAttachment', 'sendThreadAttachment'], ctx);
  const p = new Presenter(gateway);
  const room = m.RoomTimelinePresenter && m.RoomTimelineGateway ?
    new m.RoomTimelinePresenter(new m.RoomTimelineGateway()) : null;
  const main = () => 'mainRoomEvents' in p ? p.mainRoomEvents : room?.events;
  const snapshot = () => ({
    surface: p.surface ?? p.composerSurface,
    threadRootId: nullable(p.threadRootId),
    visibleEvents: copy(p.threadEvents ?? p.visibleEvents),
    focusedEventId: nullable(p.focusedEventId),
    focusState: p.focusState,
    composerText: p.composerText,
    replyTargetId: nullable(p.replyTargetId),
    sendState: p.sendState,
    mainRoomEvents: copy(main()),
    mainRoomFocus: 'mainRoomFocus' in p ? nullable(p.mainRoomFocus) :
      (room && 'focusedEventId' in room ? nullable(room.focusedEventId) :
        (p.surface === 'room' ? nullable(p.focusedEventId) : undefined)),
    mainRoomComposer: room?.composerText,
    isOpen: p.isOpen
  });
  const event = ctx.caseSpec.event;
  const key = ctx.caseSpec.key;
  const initial = snapshot();
  const root = g.threadRootId ?? event.rootEventId;
  if (key !== 'open_thread') await p.openThread(root);
  if (g.composerText !== undefined) method(p, ['setComposerText'])(g.composerText);
  if (g.replyTargetId !== undefined) await method(p, ['setReplyTarget'])(g.replyTargetId);
  if (g.focusedEventId) method(p, ['focusEvent'])(g.focusedEventId);
  if (key === 'back_isolates_room') method(p, ['setComposerText'])('thread-only draft');
  if (key === 'restore_nested_context') {
    if (has(p, 'openNestedSurface')) p.openNestedSurface(g.surface);
    else method(p, ['openAttachmentPreview'])();
  }
  let failed;
  if (key === 'retry_failed_send') {
    failNext(gateway, ['failNextSend', 'failNextRequest']);
    await method(p, ['sendMessage'])();
    failed = checkpoint(ctx, 'thread:failed-send', snapshot());
  }
  const before = checkpoint(ctx, 'before:event', snapshot());
  if (g.roomTimeline && !equal(initial.mainRoomEvents, g.roomTimeline))
    unsupportedFixture(ctx, 'The production room timeline could not establish the given event window.', { given: g.roomTimeline, actual: initial.mainRoomEvents });
  if (g.visibleEvents && !equal(before.visibleEvents, g.visibleEvents))
    unsupportedFixture(ctx, 'The production thread timeline could not establish the given event window.', { given: g.visibleEvents, actual: before.visibleEvents });
  if (key === 'reply_remote_event' && before.replyTargetId !== g.replyTargetId) {
    unsupportedFixture(ctx, 'Remote-reply setup not established: production rejected the given replyTargetId; subsequent send observations are diagnostic only.',
      { givenReplyTargetId: g.replyTargetId, actualReplyTargetId: before.replyTargetId,
        threadRootId: before.threadRootId, visibleEvents: before.visibleEvents });
  }
  let result;
  switch (key) {
    case 'open_thread': result = p.openThread(event.rootEventId); break;
    case 'focus_reply':
    case 'focus_failure_preserves_thread': result = method(p, ['focusEvent'])(event.eventId); break;
    case 'send_thread_message':
    case 'reply_remote_event': result = method(p, ['sendMessage'])(); break;
    case 'send_thread_attachment':
      if (has(gateway, 'sendThreadAttachment')) {
        requireCapability(m.ThreadAttachment, 'Thread attachment constructor is unavailable');
        result = method(p, ['sendAttachment'])(new m.ThreadAttachment(g.attachmentId, g.caption, 'image'));
      } else result = method(p, ['sendAttachment'])(g.attachmentId, g.caption);
      break;
    case 'restore_nested_context': result = method(p, ['returnToThread'])(); break;
    case 'retry_failed_send': result = method(p, ['retrySend'])(); break;
    case 'back_isolates_room': result = method(p, ['navigateBack', 'closeThread'])(); break;
    default: throw new Unbound(`Thread case is not implemented: ${key}`);
  }
  result = await result;
  const after = checkpoint(ctx, 'after:event', { ...snapshot(), result });
  const observed = { ...after };
  // Thread presenters own separate timelines. Surface/isOpen are actual production navigation state.
  observed.timelineMode = after.isOpen !== undefined ? (after.isOpen ? 'thread' : 'room') : after.surface;
  if (result === true || result === false) observed.focusState = after.focusState ?? (result ? 'success' : 'failure');
  const successful = calls.filter(call => call.result === true);
  const sent = successful[successful.length - 1];
  if (sent) {
    if (sent.method === 'sendMessage' || sent.method === 'sendThreadMessage') {
      const [body, threadRootId, replyTargetId] = sent.method === 'sendMessage' ? sent.args :
        [sent.args[2], sent.args[0], sent.args[1]];
      Object.assign(observed, { effect: replyTargetId ? 'reply_message' : 'send_message', body, threadRootId,
        replyTargetId: nullable(replyTargetId), composerMode: after.replyTargetId === null ? 'normal' : 'reply' });
    } else {
      const [attachmentId, caption, threadRootId] = sent.method === 'sendAttachment' ? sent.args :
        [sent.args[2].attachmentId, sent.args[2].caption, sent.args[0]];
      Object.assign(observed, { effect: 'send_attachment', attachmentId, caption, threadRootId });
    }
  } else if (['send_thread_message', 'reply_remote_event', 'send_thread_attachment', 'retry_failed_send'].includes(key)) {
    observed.effect = null;
  }
  if (key === 'retry_failed_send') observed.attempts = calls.length;
  const mainUnchanged = main() !== undefined && equal(initial.mainRoomEvents, after.mainRoomEvents);
  switch (key) {
    case 'open_thread': check(ctx, mainUnchanged, { before: initial.mainRoomEvents, after: after.mainRoomEvents }); break;
    case 'focus_reply': check(ctx, observed.timelineMode === 'thread' && equal(before.visibleEvents, after.visibleEvents), { before, after }); break;
    case 'focus_failure_preserves_thread': check(ctx, observed.timelineMode === 'thread' &&
      equal(before.visibleEvents, after.visibleEvents) && before.focusedEventId === after.focusedEventId, { before, after }); break;
    case 'send_thread_message': check(ctx, mainUnchanged && sent && observed.threadRootId === root, { mainUnchanged, sent }); break;
    case 'reply_remote_event': check(ctx, sent && observed.replyTargetId === g.replyTargetId && observed.threadRootId === root, { sent }); break;
    case 'send_thread_attachment': check(ctx, sent && observed.threadRootId === root, { sent }); break;
    case 'retry_failed_send': check(ctx, failed.sendState === 'failure' && failed.composerText === g.composerText &&
      failed.threadRootId === root && calls.length === 2 && equal(calls[0].args, calls[1].args), { failed, calls }); break;
    case 'restore_nested_context': {
      const visits = [{ before, after }];
      if (!has(p, 'openNestedSurface')) {
        ctx.unsupportedInvariants.push({ description: ctx.caseSpec.invariants[0], reason:
          'Attachment preview was exercised; no production APIs bind nested location and poll navigation.' });
        break;
      }
      for (const surface of ['location_picker', 'poll_composer']) {
        p.openNestedSurface(surface);
        const nested = snapshot();
        p.returnToThread();
        visits.push({ before: nested, after: snapshot() });
      }
      check(ctx, visits.every(v => v.after.surface === 'thread' && v.after.threadRootId === root &&
        v.after.composerText === g.composerText && v.after.replyTargetId === g.replyTargetId), visits);
      break;
    }
    case 'back_isolates_room': check(ctx, mainUnchanged && after.focusedEventId === null &&
      after.replyTargetId === null && after.composerText === '' && equal(initial.mainRoomComposer, after.mainRoomComposer), { before, after }); break;
  }
  return observed;
}

async function spaces(ctx) {
  const m = await modules(ctx, ['SpacesFeature', 'SpaceModels', 'SpacesPresenter', 'HomeRoomsFeature']);
  if (!m.SpacesPresenter || !has(m.SpacesPresenter.prototype, 'openSpace')) return legacyDomain(ctx, m, 'spaces');
  const gateway = m.SpacesGateway ? new m.SpacesGateway() : null;
  const p = gateway ? new m.SpacesPresenter(gateway) : new m.SpacesPresenter();
  const mapApi = has(p, 'setSpaceChildren') && has(p, 'getSelectedSpaceChildren');
  const g = ctx.caseSpec.given;
  const key = ctx.caseSpec.key;
  const event = ctx.caseSpec.event;
  const spaceId = g.spaceId ?? event.spaceId ?? '!space';
  const childSourceApi = has(gateway, 'loadChildren');
  const pendingChildren = deferred();
  if (childSourceApi) {
    const fixture = g.children ?? (g.memberships ? Object.keys(g.memberships) :
      g.eligibleRoomIds ? [...g.eligibleRoomIds.map(roomId => ({ roomId })),
        ...g.lastAdminRoomIds.map(roomId => ({ roomId, isLastAdmin: true }))] :
      g.selectedRoomIds ? [...g.selectedRoomIds, '!unselected'] : []);
    const page = (items, nextCursor) => ({ children: items.map(item => {
      const child = typeof item === 'string' ? { roomId: item } : item;
      return new m.SpaceRoom(child.roomId, child.roomId, child.membership ?? '',
        child.isDirect ?? false, child.isLastAdmin ?? false);
    }), nextCursor });
    gateway.loadChildren = (id, cursor) => {
      checkpoint(ctx, 'gateway:loadChildren:request', { spaceId: id, cursor: nullable(cursor) });
      const response = key === 'open_space' ? pendingChildren.promise :
        Promise.resolve(cursor === undefined ? page(fixture, g.hasMoreToLoad ? 'next' : undefined) : page(event.page, undefined));
      return response.then(value => {
        checkpoint(ctx, 'gateway:loadChildren:response', value);
        return value;
      });
    };
  }
  const calls = [];
  let failJoin = false;
  let failLeave = false;
  let inFlightJoin;
  const join = roomId => {
    const call = { effect: 'join_room', roomId };
    calls.push(call);
    if (inFlightJoin && roomId === '!b') inFlightJoin();
    call.result = !failJoin;
    failJoin = false;
    checkpoint(ctx, 'gateway:join', call);
    return call.result;
  };
  const leave = (...args) => {
    const call = { effect: 'leave_space', spaceId: mapApi ? args[0] : spaceId, payload: copy(mapApi ? args[1] : args[0]), result: !failLeave };
    failLeave = false;
    calls.push(call);
    checkpoint(ctx, 'gateway:leave', call);
    return call.result;
  };
  // Only external gateway dependencies are replaced; presenter state is never assigned.
  if (mapApi) { p.joinRoomApi = { joinRoom: join }; p.leaveSpaceApi = { leaveSpace: leave }; }
  else {
    requireCapability(gateway && has(gateway, 'joinRoom') && has(gateway, 'leaveSpace'), 'Space gateway cannot be bound');
    gateway.joinRoom = join;
    gateway.leaveSpace = leave;
    watch(gateway, ['acceptInvite'], ctx);
  }
  const children = () => mapApi ? p.getSelectedSpaceChildren() : p.children;
  const selected = () => mapApi ? Array.from(p.getSelectedLeaveRooms(spaceId)) : p.selectedLeaveRoomIds.slice();
  const candidates = () => mapApi ? p.getEligibleLeaveRooms(spaceId) : method(p, ['leaveCandidates'])();
  const leaveState = () => mapApi ? enumState(m.LeaveActionState, p.getLeaveState(spaceId)) : p.leaveState;
  const membership = id => mapApi ? (p.getMembership(id) === m.MembershipState.Member ? 'joined' : null) :
    nullable(children().find(child => child.roomId === id)?.membership);
  const action = id => {
    if (mapApi) return p.joinActions.has(id) ? enumState(m.JoinActionState, p.getJoinState(id)) : 'cleared';
    return p.actionFor(id)?.state ?? 'cleared';
  };
  const surface = () => p.surface ?? (p.isLeaveDialogOpen?.(spaceId) ? 'leave' : (p.selectedSpaceId ? 'space' : 'home'));
  const snapshot = () => ({ surface: surface(), selectedSpaceId: nullable(p.selectedSpaceId), childrenState: p.childrenState,
    children: children().map(child => child.roomId), memberships: Object.fromEntries(children().map(child => [child.roomId, membership(child.roomId)])),
    joinActions: { '!a': action('!a'), '!b': action('!b') }, selectedRoomIds: selected(), leaveState: leaveState(),
    hasMoreToLoad: mapApi ? p.hasMoreChildren(spaceId) : p.hasMoreToLoad,
    paginationState: mapApi ? (p.isPaginationLoading(spaceId) ? 'loading' : 'idle') : p.paginationState });
  const setChildren = list => {
    requireCapability(mapApi, 'Canonical child fixture cannot be supplied through a production API (no setSpaceChildren)');
    p.setSpaceChildren(spaceId, list.map(item => {
      const c = typeof item === 'string' ? { roomId: item } : item;
      return new m.SpaceChildSummary(c.roomId, c.roomId, c.isDirect ?? false, c.isLastAdmin ?? false);
    }));
  };
  const toggle = id => mapApi ? p.toggleLeaveRoom(spaceId, id) : method(p, ['toggleRoomSelection'])(id);
  const deselect = () => mapApi ? p.deselectAllLeave(spaceId) : method(p, ['deselectAllRooms'])();
  const selectAll = () => mapApi ? p.selectAllLeave(spaceId) : method(p, ['selectAllRooms'])();
  const confirm = () => mapApi ? p.confirmLeave(spaceId) : method(p, ['leaveSpace'])();
  const clearJoin = () => mapApi ? p.clearJoinFailure(event.roomId) : method(p, ['clearJoinFailures'])();
  if (key !== 'open_space' && key !== 'accept_invite') await p.openSpace(spaceId);
  if (key === 'paginate_children') {
    if (mapApi) {
      setChildren(g.children);
      p.setChildrenHasMore(spaceId, g.hasMoreToLoad);
    } else requireCapability(equal(children().map(c => c.roomId), g.children),
      'Pagination fixture requires exactly the given children; built-in children differ and there is no production replacement API');
  }
  if (key === 'join_child_success' && mapApi) setChildren(g.children);
  if (key === 'join_failure_retry' && mapApi) setChildren(Object.keys(g.memberships));
  if (key === 'default_leave_selection') {
    if (mapApi) setChildren(g.children);
    else requireCapability(equal(children().map(c => ({ roomId: c.roomId, isDirect: c.isDirect, isLastAdmin: c.isLastAdmin })), g.children),
      'Default leave fixture cannot be supplied through a production child ingestion API');
  }
  if (key === 'bulk_and_toggle_selection' && mapApi) setChildren([
    ...g.eligibleRoomIds.map(roomId => ({ roomId })), ...g.lastAdminRoomIds.map(roomId => ({ roomId, isLastAdmin: true }))]);
  if (['leave_failure_retry', 'leave_selected_rooms'].includes(key)) {
    if (mapApi) setChildren([...g.selectedRoomIds, '!unselected'].map(roomId => ({ roomId })));
    else if (g.selectedRoomIds.some(id => !children().some(c => c.roomId === id))) await method(p, ['loadMore'])();
  }
  if (['bulk_and_toggle_selection', 'leave_failure_retry', 'leave_selected_rooms'].includes(key)) {
    p.openLeaveSpace(spaceId);
    deselect();
    for (const id of g.selectedRoomIds) toggle(id);
    requireCapability(equal(selected(), g.selectedRoomIds), 'Production selection APIs could not establish the canonical initial selection');
  }
  let before = checkpoint(ctx, 'before:event', snapshot());
  let observed;
  switch (key) {
    case 'open_space': {
      if (!childSourceApi) unsupportedFixture(ctx, 'Space loading contract boundary unsupported: no explicit pending child-load fixture is bound; opening alone does not establish childrenState=loading.',
        { given: g, event, before });
      else ctx.notes.push({ kind: 'contract_boundary_assumption', caseId: ctx.caseSpec.caseId,
        assumption: 'Cold hierarchy request held pending; canonical given does not explicitly name this source boundary.',
        upstream: 'SpacePresenter.present / RustSpaceRoomList.paginate at a2ad98c2c6606e4d27f7f53edffd7443b3e91ce3' });
      const opening = p.openSpace(event.spaceId);
      observed = snapshot();
      const retained = p.selectedSpaceId;
      checkpoint(ctx, 'after:event', observed);
      if (childSourceApi) {
        pendingChildren.resolve({ children: [new m.SpaceRoom('!checkpoint', 'checkpoint', '')], nextCursor: undefined });
        await opening;
        checkpoint(ctx, 'space:children-completed', snapshot());
      } else if (mapApi) p.setSpaceChildren(event.spaceId, [new m.SpaceChildSummary('!checkpoint', 'checkpoint')]);
      else await method(p, ['loadMore'])();
      check(ctx, retained === event.spaceId && p.selectedSpaceId === retained, { selectedBeforeUpdate: retained, selectedAfterUpdate: p.selectedSpaceId });
      break;
    }
    case 'paginate_children': {
      if (mapApi) {
        p.loadMoreChildren(spaceId, event.page.map(id => new m.SpaceChildSummary(id, id)));
        // Pagination completion is a separate production ingestion API, as used by the page.
        p.setChildrenHasMore(spaceId, false);
      } else await p.loadMore();
      observed = snapshot();
      check(ctx, equal(observed.children.slice(0, before.children.length), before.children) &&
        new Set(observed.children).size === observed.children.length, { before: before.children, after: observed.children });
      break;
    }
    case 'join_child_success': {
      await p.joinChild(event.roomId);
      observed = { memberships: Object.fromEntries(g.children.map(c => [c.roomId, membership(c.roomId)])),
        joinActions: { [event.roomId]: action(event.roomId) }, effect: calls.some(c => c.effect === 'join_room') ? 'join_room' : null };
      const others = children().filter(c => c.roomId !== event.roomId).map(c => c.roomId);
      check(ctx, others.every(id => before.memberships[id] === membership(id)), { before: before.memberships, after: snapshot().memberships });
      break;
    }
    case 'join_failure_retry': {
      failJoin = true;
      p.joinChild(event.roomId);
      const failure = checkpoint(ctx, 'space:join-failed', snapshot());
      // A synchronous gateway callback lets us observe B in-flight while A retries.
      // B's eventual result occurs after the evaluated checkpoint.
      inFlightJoin = () => {
        before = checkpoint(ctx, 'before:event', snapshot());
        clearJoin();
        const cleared = checkpoint(ctx, 'space:join-cleared', snapshot());
        p.joinChild(event.roomId);
        observed = { joinActions: { '!a': action('!a'), '!b': action('!b') },
          memberships: { '!a': membership('!a'), '!b': membership('!b') },
          attempts: { [event.roomId]: calls.filter(c => c.roomId === event.roomId).length } };
        check(ctx, failure.joinActions[event.roomId] === 'failure' && before.joinActions['!b'] === 'loading' &&
          cleared.joinActions['!b'] === 'loading' && observed.joinActions['!b'] === 'loading' &&
          observed.memberships['!b'] === before.memberships['!b'], { failure, before, cleared, after: observed });
        checkpoint(ctx, 'after:event', observed);
      };
      p.joinChild('!b');
      inFlightJoin = undefined;
      break;
    }
    case 'accept_invite': {
      const invites = mapApi ? p.spaceInvites.map(i => i.spaceId) : p.invites.map(i => i.roomId);
      requireCapability(g.spaceInvites.every(id => invites.includes(id)), 'Requested invite cannot be seeded through production APIs');
      const seenBefore = mapApi ? Array.from(p.inviteSeen) : p.seenInviteIds.slice();
      requireCapability(equal(seenBefore, g.seenInvites), 'Production seen-invite state does not match the canonical given');
      checkpoint(ctx, 'space:invite-before-accept', { invites, seenInvites: seenBefore });
      await p.acceptInvite(event.spaceId);
      const joined = mapApi ? p.joinedSpaces.some(s => s.spaceId === event.spaceId) : p.spaces.some(s => s.roomId === event.spaceId && s.membership === 'joined');
      const accepted = mapApi ? p.getInviteHandlingState(event.spaceId) === m.InviteHandlingState.Accepted : gateway.lastAcceptedInviteId === event.spaceId;
      observed = { effect: accepted ? 'accept_invite' : null, membership: joined ? 'joined' : null,
        seenInvites: mapApi ? Array.from(p.inviteSeen) : p.seenInviteIds.slice() };
      const remaining = mapApi ? p.spaceInvites.map(i => i.spaceId) : p.invites.map(i => i.roomId);
      check(ctx, accepted && joined && !remaining.includes(event.spaceId) &&
        equal(observed.seenInvites, seenBefore.filter(id => id !== event.spaceId)), { seenBefore, observed, remaining });
      ctx.notes.push({ kind: 'upstream_semantics',
        upstream: 'a2ad98c2c6606e4d27f7f53edffd7443b3e91ce3:features/invite/impl/src/main/kotlin/io/element/android/features/invite/impl/AcceptInvite.kt',
        symbols: ['DefaultAcceptInvite.invoke', 'DefaultSeenInvitesStore.markAsUnSeen'],
        detail: 'Successful acceptance marks the invite unseen: the accepted ID is removed and other seen IDs are preserved.' });
      break;
    }
    case 'default_leave_selection': {
      p.openLeaveSpace(spaceId);
      observed = { visibleChildren: candidates().map(c => c.roomId), selectedRoomIds: selected(),
        disabledRoomIds: candidates().filter(c => c.isLastAdmin).map(c => c.roomId) };
      check(ctx, g.children.filter(c => c.isDirect).every(c => !observed.visibleChildren.includes(c.roomId)) &&
        g.children.filter(c => c.isLastAdmin).every(c => !observed.selectedRoomIds.includes(c.roomId)), observed);
      break;
    }
    case 'bulk_and_toggle_selection': {
      deselect();
      const afterDeselectAll = selected();
      selectAll();
      const afterSelectAll = selected();
      toggle(event.roomId);
      const afterToggle = selected();
      for (const id of g.lastAdminRoomIds) toggle(id);
      observed = { afterDeselectAll, afterSelectAll, selectedRoomIds: selected(),
        lastAdminSelected: g.lastAdminRoomIds.some(id => selected().includes(id)) };
      check(ctx, [afterDeselectAll, afterSelectAll, afterToggle, selected()].every(ids =>
        g.lastAdminRoomIds.every(id => !ids.includes(id))), { ...observed, afterToggle });
      break;
    }
    case 'leave_failure_retry': {
      failLeave = true;
      confirm();
      const firstState = leaveState();
      const selectionAfterFailure = selected();
      checkpoint(ctx, 'space:leave-failed', { firstState, selectionAfterFailure });
      if (has(p, 'closeLeaveError')) p.closeLeaveError();
      confirm();
      observed = { firstState, selectionAfterFailure, finalState: leaveState(),
        attempts: calls.filter(c => c.effect === 'leave_space').length };
      check(ctx, firstState === 'failure' && equal(selectionAfterFailure, g.selectedRoomIds) &&
        equal(calls[0]?.payload, calls[1]?.payload), { ...observed, calls });
      break;
    }
    case 'leave_selected_rooms': {
      confirm();
      const call = calls.find(c => c.effect === 'leave_space');
      observed = { effect: call?.effect ?? null, payload: call?.payload ?? null, leaveState: leaveState(), surface: surface() };
      const eligible = candidates().filter(c => !c.isLastAdmin).map(c => c.roomId);
      check(ctx, call && equal(call.payload, before.selectedRoomIds) && call.payload.every(id => eligible.includes(id)), { call, eligible, selected: before.selectedRoomIds });
      break;
    }
    default: throw new Unbound(`Space case is not implemented: ${key}`);
  }
  checkpoint(ctx, 'after:event', observed);
  return observed;
}

async function media(ctx) {
  const m = await modules(ctx, ['MediaQualityFeature', 'AttachmentFeature', 'ServerLimitFeature']);
  const Presenter = [m.MediaQualityPresenter, m.AttachmentPresenter].find(C => C &&
    (has(C.prototype, 'openPreview') || has(C.prototype, 'openAttachmentPreview')));
  if (!Presenter) return legacyDomain(ctx, m, 'media');
  const callbackApi = has(Presenter.prototype, 'openAttachmentPreview');
  const Gateway = callbackApi ? m.AttachmentGateway : m.MediaQualityGateway;
  requireCapability(Gateway, 'Media upload gateway export is unavailable');
  const gateway = new Gateway();
  const preferences = callbackApi ? new m.MediaQualityPreferences() : new m.MediaPreferences();
  const p = new Presenter(gateway, preferences);
  if (callbackApi) p.preferences = preferences;
  const calls = watch(gateway, ['preprocess', 'upload', 'send'], ctx);
  const g = ctx.caseSpec.given;
  const event = ctx.caseSpec.event;
  const key = ctx.caseSpec.key;
  const promiseApi = has(gateway, 'requestUploadLimit') && has(gateway, 'requestMetadata');
  let metadataComplete;
  let limitComplete;
  let metadataRequest;
  let limitRequest;
  let opening;
  let limitProvider;
  if (callbackApi) {
    p.metadataLoader = { requestMetadata(_uri, callback) { metadataComplete = callback; } };
    // Keep the real provider's fallback policy. Hold only delivery of its response.
    const provider = new m.HomeserverLimitProvider();
    limitProvider = provider;
    provider.configuredLimit = g.maxUploadSize ?? 35_000_000;
    provider.failNextRequest = key === 'limit_fallback';
    p.limitProvider = { requestLimit(callback) {
      provider.requestLimit(result => { limitComplete = () => callback(result); });
    } };
  } else {
    gateway.maxUploadSize = g.maxUploadSize ?? 35_000_000;
    gateway.failLimitRequest = key === 'limit_fallback';
    if (promiseApi) {
      gateway.requestUploadLimit = () => {
        limitRequest = deferred();
        checkpoint(ctx, 'gateway:upload-limit:pending', {});
        return limitRequest.promise;
      };
      gateway.requestMetadata = mediaType => {
        metadataRequest = deferred();
        checkpoint(ctx, 'gateway:metadata:pending', { mediaType });
        return metadataRequest.promise;
      };
    }
  }
  const setPreference = preset => method(preferences, ['saveVideoPreset', 'setVideoPreset'])(preset);
  if (g.defaultPreset || g.selectedPreset) setPreference(g.defaultPreset ?? g.selectedPreset);
  const durationMs = g.durationMs ?? g.metadata?.durationMs;
  const durationSeconds = g.durationSeconds ?? g.metadata?.durationSeconds;
  if (durationMs !== undefined) {
    requireCapability(Number.isFinite(durationMs) && durationMs >= 0, 'Media durationMs must be a finite nonnegative metadata input');
    requireCapability(durationSeconds === undefined || durationMs / 1000 === durationSeconds,
      'Conflicting durationMs and durationSeconds cannot establish one metadata fixture');
  }
  const metadata = { mediaType: g.mediaType ?? 'video', durationSeconds: durationMs === undefined ? durationSeconds ?? 60 : durationMs / 1000,
    width: g.metadata?.width ?? g.width ?? 1920, height: g.metadata?.height ?? g.height ?? 1080,
    originalSize: g.mediaType === 'image' ? 5_000_000 : 50_000_000,
    filename: g.mediaType === 'image' ? 'fixture.jpg' : 'fixture.mp4', uri: 'mem://fixture' };
  checkpoint(ctx, 'media:metadata-fixture', { durationMs, metadata });
  const snapshot = () => ({
    limitState: callbackApi ? (p.serverLimitLoaded ? 'success' : 'loading') : p.limitState,
    estimationState: callbackApi ? (p.estimationsCompleted ? (p.metadata?.mediaType === 'image' ? 'uninitialized' : 'success') : 'loading') : p.estimationState,
    sendState: p.sendState, maxUploadSize: p.maxUploadSize,
    fallbackUsed: callbackApi ? p.serverLimitFromFallback : p.fallbackUsed,
    selectedPreset: nullable(p.selectedPreset), selectorOpen: p.selectorOpen,
    estimations: copy(p.estimations), caption: p.caption,
    optimizeImages: callbackApi ? p.preferences.optimizeImages : p.optimizeImages,
    preparedMedia: callbackApi ? p.preparedMediaUri : p.preparedMedia,
    preparedFilename: p.preparedFilename, preparedAttachmentOrder: p.preparedAttachmentOrder,
    fileTooLargeError: p.fileTooLargeError, errorMessage: p.errorMessage
  });
  const open = () => {
    opening = callbackApi ? p.openAttachmentPreview(metadata.filename, 0) : p.openPreview(metadata.mediaType);
    return opening;
  };
  const finish = async () => {
    if (callbackApi) {
      await Promise.resolve();
      requireCapability(metadataComplete && limitComplete, 'Preview did not request metadata and server limit dependencies');
      metadataComplete(copy(metadata));
      limitComplete();
    } else if (promiseApi) {
      requireCapability(metadataRequest && limitRequest, 'Preview did not request both asynchronous information sources');
      metadataRequest.resolve(copy(metadata));
      if (gateway.failLimitRequest) limitRequest.reject(new Error('Fixture upload-limit request failed'));
      else limitRequest.resolve(gateway.maxUploadSize);
      await opening;
      checkpoint(ctx, 'media:information-completed', snapshot());
    }
  };
  const recalculate = () => callbackApi ? p.calculateEstimations() : p.calculateVideoEstimations(metadata.durationSeconds);
  const choose = () => callbackApi ? p.loadPreferencesAndEstimations() : p.chooseBestPreset(preferences.videoPreset);
  const size = estimate => estimate.sizeInBytes ?? estimate.estimatedSize;
  const sendable = () => {
    if (has(p, 'canSend')) return p.canSend().ok;
    // Exercise actual send validation; gateway interception records whether upload was reached.
    const count = calls.length;
    const result = method(p, ['send'])();
    return result === true && calls.slice(count).some(c => c.method === 'upload' && c.result === true);
  };
  if (key !== 'async_loading' && key !== 'limit_fallback') { open(); await finish(); }
  if (key === 'limit_fallback') open();
  // Estimation fixtures are delivered as external limits and metadata, never assigned to presenter estimations.
  if (g.estimations) {
    const acceptable = g.estimations.filter(e => e.canUpload).map(e => e.preset);
    const estimates = p.estimations;
    const threshold = acceptable.length ? Math.max(...estimates.filter(e => acceptable.includes(e.preset)).map(size)) : 1;
    requireCapability(Number.isFinite(threshold), 'No production estimation can establish the requested eligibility fixture');
    if (callbackApi) p.finishLimitRequest(threshold, false);
    else { gateway.maxUploadSize = threshold; open(); await finish(); }
    const actual = p.estimations;
    requireCapability(g.estimations.every(e => actual.find(a => a.preset === e.preset)?.canUpload === e.canUpload),
      'Production metadata/limit inputs cannot establish the requested eligibility fixture');
  }
  if (key === 'dismiss_preserves_selection' || key === 'reject_oversized_preset' || key === 'failure_cancel_retry') {
    method(p, ['selectVideoPreset'])(g.selectedPreset);
    requireCapability(p.selectedPreset === g.selectedPreset, 'Production selection APIs could not establish the initial preset');
  }
  let failure;
  if (key === 'failure_cancel_retry') {
    p.setCaption(g.caption);
    failNext(gateway, ['failNextUpload', 'failNextSend']);
    p.send();
    failure = checkpoint(ctx, 'media:upload-failed', snapshot());
  }
  if (key === 'choose_best_preset') setPreference(g.defaultPreset);
  const before = checkpoint(ctx, 'before:event', snapshot());
  let observed;
  switch (key) {
    case 'async_loading': {
      if (!callbackApi && !promiseApi && (g.maxUploadSize === null || g.metadata === null)) {
        unsupportedFixture(ctx, 'Pending media fixture unrepresented: the synchronous numeric limit gateway and fixed metadata path cannot establish the given unknown limit/metadata; post-open success is diagnostic only.',
          { givenMaxUploadSize: g.maxUploadSize, givenMetadata: g.metadata,
            configuredGatewayLimit: gateway.maxUploadSize, before });
      }
      open();
      observed = snapshot();
      if (has(p, 'cancel')) {
        let pending;
        let edited;
        let cancelled;
        const interact = () => {
          pending = snapshot();
          p.setCaption('caption while loading');
          edited = snapshot();
          p.cancel();
          cancelled = snapshot();
        };
        if (callbackApi || promiseApi) interact();
        else {
          // Exercise editing/cancel at the real external-call boundary while
          // production loading states are active, in a separate probe opening.
          const request = gateway.getMaxUploadSize.bind(gateway);
          gateway.getMaxUploadSize = () => { interact(); return request(); };
          open();
          gateway.getMaxUploadSize = request;
        }
        observed.previewUsable = edited.caption === 'caption while loading' && cancelled.sendState === 'done';
        let lateCompletion;
        if (promiseApi) {
          await finish();
          lateCompletion = snapshot();
        }
        check(ctx, observed.previewUsable && pending.limitState === 'loading' && pending.estimationState === 'loading' &&
          (!lateCompletion || equal(cancelled, lateCompletion)), { pending, edited, cancelled, lateCompletion });
      } else {
        p.setCaption('caption while loading');
        checkpoint(ctx, 'media:caption-edited-while-pending', snapshot());
        ctx.unsupportedInvariants.push({ description: ctx.caseSpec.invariants[0], reason:
          'Caption editing was executed while dependencies were pending; cancellation has no production domain API.' });
      }
      break;
    }
    case 'limit_fallback':
      await finish(); observed = snapshot();
      check(ctx, observed.maxUploadSize === 100 * 1024 * 1024 && observed.fallbackUsed === true, observed);
      break;
    case 'image_optimization': {
      p.selectImageOptimization(event.enabled);
      const after = snapshot();
      observed = { optimizeImages: after.optimizeImages, videoEstimationState: after.estimationState };
      if (callbackApi) {
        p.send();
        const sent = calls.find(c => c.method === 'send');
        if (sent?.args[1] === 'image:original' || sent?.args[1] === 'image:optimized') {
          observed.preprocessConfig = { compressImages: sent.args[1] === 'image:optimized' };
        }
      } else {
        await p.send();
        const prepared = calls.find(c => c.method === 'preprocess');
        if (typeof prepared?.args[1]?.compressImages === 'boolean')
          observed.preprocessConfig = { compressImages: prepared.args[1].compressImages };
      }
      check(ctx, p.estimations.length === 0 && (p.metadata === undefined || p.metadata?.mediaType === 'image'),
        { before, after, metadata: p.metadata, calls });
      break;
    }
    case 'estimate_video_presets': {
      if (callbackApi && g.presetBitrates) for (const [preset, bitrate] of Object.entries(g.presetBitrates))
        method(p.estimator, ['setPresetBitrate'])(preset, bitrate);
      recalculate();
      const estimates = copy(p.estimations);
      // Read the actual estimator output/configuration, never infer a bitrate from expected sizes.
      const actualBitrates = Object.fromEntries(estimates.map(e => [e.preset,
        Number.isFinite(e.bitrateKbps) && e.bitrateKbps > 0 ? e.bitrateKbps * 1000 : p.estimator?.bitrates?.[e.preset]])
        .filter(([, bitrate]) => Number.isFinite(bitrate) && bitrate > 0));
      if (durationMs !== undefined || g.width !== undefined || g.height !== undefined || g.metadata) {
        const actualMetadata = p.metadata;
        if (!actualMetadata || actualMetadata.width !== metadata.width || actualMetadata.height !== metadata.height ||
          actualMetadata.durationSeconds !== metadata.durationSeconds) {
          unsupportedFixture(ctx, 'Production metadata ingestion did not establish the requested video dimensions/duration.',
            { requestedMetadata: metadata, actualMetadata, estimates });
        }
      }
      if (g.presetBitrates && Object.keys(actualBitrates).length && !equal(actualBitrates, g.presetBitrates)) {
        unsupportedFixture(ctx, 'Canonical arbitrary presetBitrates are not inputs to the upstream dimensions-based compressor helper; this given cannot be established. Actual estimates are retained as contract-mismatch evidence.',
          { requestedBitrates: g.presetBitrates, actualBitrates, dimensions: { width: metadata.width, height: metadata.height }, estimates });
        ctx.notes.push({ kind: 'upstream_contract_contradiction',
          upstream: '4c67edf0582ea30b34f5469a6bb84e5617cea76e:libraries/androidutils/src/main/kotlin/io/element/android/libraries/androidutils/media/VideoCompressorHelper.kt',
          symbols: ['getOutputSize', 'calculateOptimalBitrate', 'VideoCompressionPreset.compressorHelper'],
          detail: 'Canonical bitrate constants require approval/correction to a reachable dimensions fixture. No expected value or production bitrate was changed to obtain a pass.' });
      }
      const ratios = estimates.map(e => {
        const bitrate = actualBitrates[e.preset];
        const durationMilliseconds = Math.trunc(metadata.durationSeconds * 1000);
        const rawSize = Number.isFinite(e.bitrateKbps) && e.bitrateKbps > 0 ?
          Math.trunc(e.bitrateKbps * durationMilliseconds / 8) : Math.floor(bitrate * metadata.durationSeconds / 8);
        return rawSize > 0 ? size(e) / rawSize : undefined;
      });
      observed = { sizes: Object.fromEntries(estimates.map(e => [e.preset, size(e)])),
        canUpload: Object.fromEntries(estimates.map(e => [e.preset, e.canUpload])),
        actualBitrates, metadata: copy(p.metadata) };
      if (ratios.length && ratios.every(Number.isFinite))
        observed.safetyOverhead = ratios.every(r => Math.abs(r - ratios[0]) < 1e-12) ? ratios[0] : ratios;
      else ctx.notes.push({ kind: 'unobserved_field', field: 'safetyOverhead',
        reason: 'Production bitrate evidence and a nonzero duration are required to observe the overhead ratio.' });
      const boundary = [];
      for (const estimate of estimates) {
        for (const offset of [0, -1]) {
          const maxUploadSize = size(estimate) + offset;
          if (callbackApi) limitProvider.configuredLimit = maxUploadSize;
          else gateway.maxUploadSize = maxUploadSize;
          checkpoint(ctx, 'media:boundary-before-request', { preset: estimate.preset, maxUploadSize, offset });
          open();
          await finish();
          const result = copy(p.estimations.find(e => e.preset === estimate.preset));
          const probe = { ...result, preset: estimate.preset, maxUploadSize, offset,
            actualMaxUploadSize: p.maxUploadSize };
          boundary.push(probe);
          checkpoint(ctx, 'media:boundary-after-request', probe);
        }
      }
      check(ctx, boundary.length > 0 && boundary.every(e => e.actualMaxUploadSize === e.maxUploadSize &&
        size(e) === observed.sizes[e.preset] && e.canUpload === (e.offset === 0)), { boundary });
      break;
    }
    case 'choose_best_preset': {
      choose();
      const selected = p.estimations.find(e => e.preset === p.selectedPreset);
      observed = { selectedPreset: nullable(p.selectedPreset), selectionState: selected?.canUpload ? 'success' : 'failure' };
      const order = p.estimations.map(e => e.preset);
      check(ctx, selected?.canUpload === true && order.indexOf(selected.preset) >= order.indexOf(g.defaultPreset), { selected, estimates: p.estimations });
      break;
    }
    case 'dismiss_preserves_selection':
      p.openSelector(); method(p, ['dismissSelector', 'closeSelector'])();
      observed = { selectedPreset: nullable(p.selectedPreset), selectorOpen: p.selectorOpen };
      check(ctx, observed.selectedPreset === before.selectedPreset, { before, after: observed });
      break;
    case 'reject_oversized_preset': {
      p.openSelector(); p.selectVideoPreset(event.preset);
      observed = { selectedPreset: nullable(p.selectedPreset), selectorOpen: p.selectorOpen, sendable: sendable() };
      check(ctx, observed.selectedPreset === before.selectedPreset && p.estimations.find(e => e.preset === p.selectedPreset)?.canUpload === true,
        { before, after: observed, estimates: p.estimations });
      break;
    }
    case 'block_when_all_oversized': {
      recalculate(); choose();
      const selectedPreset = nullable(p.selectedPreset);
      const sendEnabled = sendable();
      observed = { sendEnabled, selectedPreset, fileTooLargeError: callbackApi ?
        /exceeds|too large/i.test(p.canSend().reason) : p.fileTooLargeError };
      check(ctx, !sendEnabled && !p.estimations.some(e => e.canUpload) &&
        !calls.some(c => (c.method === 'upload' || c.method === 'send') && c.result === true), { observed, estimates: p.estimations, calls });
      break;
    }
    case 'failure_cancel_retry': {
      p.clearFailure();
      const cleared = checkpoint(ctx, 'media:failure-cleared', snapshot());
      p.send();
      const after = snapshot();
      const uploads = calls.filter(c => c.method === 'upload' || c.method === 'send');
      const preparation = calls.filter(c => c.method === 'preprocess');
      const last = uploads[uploads.length - 1];
      observed = { stateAfterClear: cleared.sendState, finalState: after.sendState,
        caption: last?.args[0], presetUsed: callbackApi ? last?.args[1]?.replace(/^video:/, '') : preparation[0]?.args[0], attempts: uploads.length };
      check(ctx, failure.sendState === 'failure' && failure.preparedMedia &&
        equal(failure.preparedMedia, cleared.preparedMedia) && failure.caption === g.caption && cleared.caption === g.caption &&
        after.caption === g.caption && equal(uploads[0]?.args, uploads[1]?.args) &&
        (callbackApi ? after.preparedMedia === failure.preparedMedia : preparation.length === 1), { failure, cleared, after, calls });
      break;
    }
    default: throw new Unbound(`Media case is not implemented: ${key}`);
  }
  checkpoint(ctx, 'after:event', observed);
  return observed;
}

async function restoredBaseRoomInput(ctx, m) {
  const g = ctx.caseSpec.given;
  const key = ctx.caseSpec.key;
  const gateway = new m.RoomGateway();
  const p = new m.RoomPresenter(gateway);
  const snapshot = () => ({ room: copy(p.room), history: copy(p.history) });
  checkpoint(ctx, 'before:room-info-input', snapshot());
  const response = { roomId: g.roomId, name: p.room.name,
    lastMessage: g.lastMessage ?? p.room.lastMessage,
    successorRoom: { roomId: g.successorRoomId, reason: null } };
  // Only the external room-info response is scripted. The original consumer
  // performs all assignments and mapping; this instance is not a native page.
  gateway.requestRoomInfo = async requestedRoomId => {
    requireCapability(requestedRoomId === response.roomId, 'Production requested a different room-info input');
    checkpoint(ctx, 'gateway:room-info-response', { requestedRoomId, response });
    return copy(response);
  };
  const calls = watch(gateway, ['requestRoomInfo'], ctx);
  const loaded = await p.observeRoomInfo(g.roomId);
  const actual = snapshot();
  const established = {
    roomId: actual.room?.roomId === g.roomId,
    successorRoomId: actual.room?.successorRoom?.roomId === g.successorRoomId,
    ...(g.history === undefined ? {} : { history: equal(actual.history, g.history) }),
    ...(g.lastMessage === undefined ? {} : { lastMessage: actual.room?.lastMessage === g.lastMessage })
  };
  checkpoint(ctx, 'after:room-info-input', { loaded, actual, established, calls });
  requireCapability(calls.length === 1 && loaded === true && Object.values(established).every(value => value === true),
    'Production room-info ingestion did not establish all bound canonical data inputs');
  const unresolvedGiven = g.composerEnabled === undefined ? [] : ['composerEnabled'];
  ctx.notes.push({ kind: 'canonical_data_input_established', established, unresolvedGiven,
    fullGivenEstablished: unresolvedGiven.length === 0, scope: 'host production instance, not the mounted native page', actual });
  ctx.notes.push({ kind: 'native_base_input_binding_required', module: ROOT + 'RoomFeature.ets',
    gatewayExport: 'RoomGateway', externalResponsePort: 'requestRoomInfo',
    presenterExport: 'RoomPresenter', productionConsumer: 'observeRoomInfo', pageCallsite: 'Index.aboutToAppear',
    entryAnchors: ['message_composer', 'room_list_old_room'],
    reason: 'The original page receiver must consume this gateway response during its real lifecycle; a host instance or UI snapshot alone cannot establish it.' });
  const before = checkpoint(ctx, 'before:event', { event: ctx.caseSpec.event, actual, established, unresolvedGiven,
    nativePageGivenEstablished: false });
  const after = snapshot();
  // These render events require a verified original page. In particular, a
  // plain lastMessage is not a rendered preview, nor metadata an avatar mark.
  const observed = { roomId: after.room.roomId, successorRoom: after.room.successorRoom,
    ...(key === 'tombstone_is_read_only' ? { history: after.history } : { lastMessage: after.room.lastMessage }) };
  ctx.bindingUnsupported = key === 'tombstone_is_read_only' ?
    'Canonical roomId/history/successorRoomId established through original observeRoomInfo; composerEnabled input and render_messages UI/history visibility require the mounted native page.' :
    'Canonical roomId/lastMessage/successorRoomId established through original observeRoomInfo; render_room_list_summary, tombstone presentation and avatar mark require the mounted native page.';
  checkpoint(ctx, 'after:event', { eventExecuted: false, reason: ctx.bindingUnsupported, actual: after, observed });
  if (key === 'room_list_tombstone_preview') check(ctx,
    before.actual.room.lastMessage === after.room.lastMessage && after.room.lastMessage === g.lastMessage,
    { before: before.actual.room, after: after.room, renderEventExecuted: false });
  return observed;
}

async function roomUpgrade(ctx) {
  const m = await modules(ctx, ['RoomUpgradeFeature', 'RoomFeature']);
  const storeApi = m.RoomStore && m.RoomPresenter && has(m.RoomPresenter.prototype, 'applyPredecessorMetadata');
  const Presenter = storeApi ? m.RoomPresenter : m.RoomUpgradePresenter;
  const Gateway = storeApi ? m.RoomGateway : m.RoomNavigationGateway;
  if (!Presenter || !Gateway) {
    if (['tombstone_is_read_only', 'room_list_tombstone_preview'].includes(ctx.caseSpec.key) &&
        m.RoomPresenter && m.RoomGateway && has(m.RoomPresenter.prototype, 'observeRoomInfo') &&
        has(m.RoomGateway.prototype, 'requestRoomInfo')) return restoredBaseRoomInput(ctx, m);
    return legacyDomain(ctx, m, 'roomUpgrade');
  }
  if (ctx.caseSpec.key !== 'map_predecessor_metadata' && has(ctx.native?.roomUpgrade, 'read') &&
    has(ctx.native?.ui, 'observe') && (has(ctx.native?.ui, 'click') || has(ctx.native?.ui, 'sendEvent'))) return nativeRoomUpgrade(ctx);
  const gateway = new Gateway();
  const store = storeApi ? new m.RoomStore() : null;
  const p = new Presenter(gateway, store);
  const sourceApi = has(gateway, 'requestRoomInfo') && has(p, 'observeTimelineRoomInfo');
  const calls = watch(gateway, ['openRoom', 'navigateToRoom'], ctx);
  const g = ctx.caseSpec.given;
  const key = ctx.caseSpec.key;
  const roomId = g.roomId ?? g.currentRoomId;
  const current = () => storeApi ? p.currentRoom() : p.currentRoom;
  const predecessor = room => room?.predecessorRoom ?? room?.predecessor;
  let incomingRoom;
  if (storeApi) {
    p.observeRoomInfo(roomId, 'Fixture room');
    store.setRoomHistory(roomId, g.history ?? [g.lastMessage ?? 'Earlier message']);
    if (g.successorRoomId) p.applySuccessorMetadata(roomId, { roomId: g.successorRoomId, reason: null });
    if (key !== 'map_predecessor_metadata' && (g.predecessor || g.predecessorRoomId))
      p.applyPredecessorMetadata(roomId, g.predecessor ?? { roomId: g.predecessorRoomId, lastEventId: null });
    store.selectRoom(roomId);
  } else if (sourceApi) {
    const existing = [p.oldRoom, p.replacementRoom].find(room => room.roomId === roomId);
    incomingRoom = { roomId, name: existing?.name ?? 'Fixture room',
      history: copy(g.history ?? (g.lastMessage ? [g.lastMessage] : existing?.history ?? [])),
      successorRoom: g.successorRoomId ? { roomId: g.successorRoomId } : undefined,
      predecessorRoom: key === 'map_predecessor_metadata' ? undefined :
        copy(g.predecessor ?? (g.predecessorRoomId ? { roomId: g.predecessorRoomId,
          lastEventId: existing?.predecessorRoom?.lastEventId ?? '' } : undefined)) };
    gateway.requestRoomInfo = async id => {
      checkpoint(ctx, 'gateway:room-info', { requestedRoomId: id, room: incomingRoom });
      return copy(incomingRoom);
    };
    await p.observeTimelineRoomInfo(roomId);
    requireCapability(p.selectRoom(roomId), 'Loaded room info could not be selected through production navigation');
  } else {
    if (p.oldRoom.roomId === roomId) p.selectOldRoom();
    else if (p.replacementRoom.roomId === roomId) p.selectReplacementRoom();
    else throw new Unbound('Fixed production room snapshots cannot ingest the requested room ID');
    requireCapability(!g.history || equal(current().history, g.history), 'Production history fixture differs and has no ingestion API');
    requireCapability(!g.successorRoomId || current().successorRoom?.roomId === g.successorRoomId, 'Successor metadata fixture cannot be ingested');
    requireCapability(!g.predecessor || equal(copy(predecessor(current())), g.predecessor), 'Predecessor fixture cannot be ingested');
  }
  const originalRoom = current();
  const snapshot = () => ({ roomId: current()?.roomId, history: copy(current()?.history),
    predecessorRoom: copy(predecessor(current())),
    isTombstoned: storeApi ? current()?.isTombstoned() : p.isTombstoned,
    canCompose: storeApi ? current()?.composerEnabled() : p.canCompose,
    navigationState: p.navigationState });
  const before = checkpoint(ctx, 'before:event', snapshot());
  const nativeView = ['tombstone_is_read_only', 'room_list_tombstone_preview', 'predecessor_banner'].includes(key) ?
    await observeRoomView(ctx, roomId) : undefined;
  let observed;
  switch (key) {
    case 'tombstone_is_read_only': {
      const after = snapshot();
      observed = { history: after.history, composerVisible: after.canCompose, successorBannerVisible: after.isTombstoned };
      if (nativeView) {
        observed.composerVisible = nativeView.visible('message_composer');
        observed.successorBannerVisible = nativeView.visible('successor_room_banner');
      } else ctx.notes.push('composerVisible and successorBannerVisible are production getter projections; native widget visibility was not observed.');
      check(ctx, equal(before.history, after.history) && (!nativeView || nativeView.historyVisible),
        { before: before.history, after: after.history, nativeHistoryVisible: nativeView?.historyVisible });
      break;
    }
    case 'open_successor':
    case 'open_predecessor': {
      const count = calls.length;
      const result = key === 'open_successor' ? method(p, ['openSuccessorRoom', 'openSuccessor'])() :
        method(p, ['openPredecessorRoom', 'openPredecessor'])();
      const call = calls.slice(count).find(c => c.result === true);
      observed = { effect: call ? 'navigate_to_room' : null, roomId: call?.args[0] ?? null,
        navigationState: p.navigationState };
      if (observed.navigationState === undefined && call && current()?.roomId === call.args[0])
        observed.navigationState = 'success';
      if (observed.navigationState === undefined && result === false)
        ctx.notes.push('Navigation returned false, but no production navigation state is exposed. Callback delivery alone is not navigation success.');
      if (key === 'open_successor') check(ctx, equal(before.history, originalRoom.history), { before: before.history, after: originalRoom.history });
      else check(ctx, equal(before.predecessorRoom, copy(predecessor(originalRoom))) &&
        predecessor(originalRoom)?.lastEventId === g.predecessor.lastEventId, { before: before.predecessorRoom, after: predecessor(originalRoom) });
      break;
    }
    case 'map_predecessor_metadata': {
      requireCapability(storeApi || sourceApi, 'Presenter exposes only a pre-seeded predecessor snapshot; no production room-info mapping API can be executed');
      if (sourceApi) {
        incomingRoom.predecessorRoom = copy(g.predecessor);
        await p.observeTimelineRoomInfo(roomId);
      } else {
        await p.observeTimelineRoomInfo(roomId, 'Fixture room');
        p.applyPredecessorMetadata(roomId, copy(g.predecessor));
      }
      observed = { predecessorRoom: copy(predecessor(current())) };
      check(ctx, observed.predecessorRoom?.lastEventId === g.predecessor.lastEventId, observed);
      break;
    }
    case 'room_list_tombstone_preview': {
      if (storeApi) {
        const summary = p.summaries().find(s => s.roomId === roomId);
        observed = { isTombstoned: summary?.tombstoned };
      } else {
        const text = p.roomListPreview(current());
        observed = { isTombstoned: p.isTombstoned, preview: text === 'This room has been replaced' ? 'room_replaced' : text };
      }
      check(ctx, originalRoom.history[originalRoom.history.length - 1] === g.lastMessage, { history: originalRoom.history });
      if (nativeView) observed.avatarMarkedTombstoned = nativeView.visible('room_avatar_tombstone_mark');
      else ctx.notes.push('Native avatar rendering requires a verified candidate page and established room fixture.');
      break;
    }
    case 'predecessor_banner':
      observed = { predecessorRoom: copy(predecessor(current())), history: copy(current().history) };
      if (nativeView) {
        observed.predecessorBannerVisible = nativeView.visible('predecessor_room_banner');
        observed.historyVisible = nativeView.historyVisible;
        check(ctx, nativeView.visible('room_beginning_content'), nativeView.record);
      } else ctx.unsupportedInvariants.push({ description: ctx.caseSpec.invariants[0], reason:
        'Room-beginning content and predecessor banner require actual candidate view composition; no native room fixture was bound.' });
      break;
    default: throw new Unbound(`Room-upgrade case is not implemented: ${key}`);
  }
  checkpoint(ctx, 'after:event', observed);
  return observed;
}

async function nativeRoomUpgrade(ctx) {
  const ui = ctx.native.ui;
  const g = ctx.caseSpec.given;
  const key = ctx.caseSpec.key;
  const roomId = g.roomId ?? g.currentRoomId;
  const ids = ['current_room_id', 'room_list_tombstoned_room', 'room_list_replacement_room',
    'room_list_old_room', 'room_detail_back', `room_list_open_${roomId.replace(/[:!]/g, '_')}`,
    'open_successor_room', 'open_successor', 'open_predecessor_room', 'open_predecessor',
    'predecessor_room_banner', 'successor_room_banner', 'room_beginning_content', 'room_history',
    'history_message_0', 'message_composer', 'room_avatar_tombstone_mark'];
  const record = (label, data) => {
    const value = copy(data);
    ctx.evidence.push({ label, data: value, observationLevel: 'native_candidate_ui_and_production_state' });
    ctx.trace(label, value);
    return value;
  };
  const read = () => {
    const state = ctx.native.roomUpgrade.read();
    requireCapability(state?.available && state.instanceId, state?.reason ?? 'Same-page production observer has not captured a presenter');
    return copy(state);
  };
  let view;
  const capture = async label => {
    for (const anchor of ['current_room_id', 'room_detail_back', 'room_list_old_room',
      `room_list_open_${roomId.replace(/[:!]/g, '_')}`]) {
      view = await ui.observe(ids, anchor);
      if (view.available) break;
    }
    requireCapability(view?.available, 'Actual candidate route and rendered room anchor are unavailable');
    const state = read();
    ctx.nativeUIObserved = true;
    ctx.nativeRoomStateObserved = true;
    return record(label, { view, state });
  };
  const control = id => view.controls.find(c => c.id === id);
  const visible = id => {
    const c = control(id);
    requireCapability(typeof c?.present === 'boolean', `Native visibility unavailable for ${id}`);
    if (!c.present) return false;
    const attrs = c.node?.$attrs;
    requireCapability(typeof attrs?.visibility === 'string' && Number.isFinite(Number(attrs.opacity)),
      `Native visibility attributes unavailable for ${id}`);
    const bounds = JSON.parse(`[${c.node.$rect}]`);
    requireCapability(bounds.length === 2 && bounds.every(point => Array.isArray(point) && point.length === 2),
      `Native layout bounds unavailable for ${id}`);
    const width = Number(view.snapshot?.tree?.width);
    const height = Number(view.snapshot?.tree?.height);
    requireCapability(width > 0 && height > 0, 'Native viewport bounds are unavailable');
    return attrs.visibility === 'Visibility.Visible' && Number(attrs.opacity) > 0 &&
      Math.min(bounds[1][0], width) > Math.max(bounds[0][0], 0) &&
      Math.min(bounds[1][1], height) > Math.max(bounds[0][1], 0);
  };
  const actionId = alternatives => {
    const id = alternatives.find(candidate => control(candidate)?.present);
    requireCapability(id && visible(id), 'No visible candidate event control: ' + alternatives.join(' / '));
    const enabled = control(id).node?.$attrs?.enabled;
    requireCapability(enabled === true || enabled === 'true', 'Candidate event control is disabled or its enabled state is unavailable');
    return id;
  };
  const dispatch = async id => {
    const physical = has(ui, 'click');
    const delivered = physical ? await ui.click(id) : await ui.sendEvent(id, 10, {});
    record('native:room-action', { id, backend: physical ? 'native_ui_click' : 'native_keyed_event', transportResult: delivered });
    requireCapability(physical ? delivered !== false : delivered === true, 'Native room action was not delivered');
  };
  await capture('native:room-entry');
  if (read().currentRoomId !== roomId) {
    const id = actionId(g.predecessor || g.predecessorRoomId ?
      ['room_list_replacement_room', `room_list_open_${roomId.replace(/[:!]/g, '_')}`] :
      ['room_list_tombstoned_room', `room_list_open_${roomId.replace(/[:!]/g, '_')}`, 'room_list_old_room']);
    await dispatch(id);
    for (let attempt = 0; attempt < 20; attempt++) {
      await delay(25);
      if (read().currentRoomId === roomId) break;
    }
  }
  const before = await capture('before:event');
  const original = before.state.rooms.find(room => room.roomId === roomId);
  requireCapability(before.state.currentRoomId === roomId && original, 'Canonical current room is not established on the actual candidate page');
  requireCapability(!g.history || equal(original.history, g.history), 'Canonical history is not established on the actual candidate page');
  requireCapability(!g.lastMessage || original.history?.slice(-1)[0] === g.lastMessage, 'Canonical last message is not established');
  requireCapability(!g.successorRoomId || original.successorRoom?.roomId === g.successorRoomId, 'Canonical successor metadata is not established');
  requireCapability(!g.predecessorRoomId || original.predecessorRoom?.roomId === g.predecessorRoomId, 'Canonical predecessor room is not established');
  requireCapability(!g.predecessor || equal(original.predecessorRoom, g.predecessor), 'Canonical predecessor metadata is not established on the actual page');
  requireCapability(g.composerEnabled === undefined,
    'The canonical composerEnabled input is not independently bound on this page; a derived tombstone canCompose getter cannot establish the pre-render permission/input');
  let observed;
  if (key === 'open_successor' || key === 'open_predecessor') {
    const target = key === 'open_successor' ? original.successorRoom.roomId : original.predecessorRoom.roomId;
    const id = actionId(key === 'open_successor' ? ['open_successor_room', 'open_successor'] : ['open_predecessor_room', 'open_predecessor']);
    await dispatch(id);
    for (let attempt = 0; attempt < 20; attempt++) {
      await delay(25);
      if (read().currentRoomId === target) {
        const rendered = await ui.observe(ids, 'current_room_id');
        if (rendered.available && rendered.controls.find(c => c.id === 'current_room_id')?.node?.$attrs?.content === target) break;
      }
    }
    const after = await capture('after:event');
    const eventMethods = key === 'open_successor' ? ['openSuccessorRoom', 'openSuccessor'] : ['openPredecessorRoom', 'openPredecessor'];
    requireCapability(after.state.calls.slice(before.state.calls.length).some(call => eventMethods.includes(call.method)),
      'Native action transport accepted the event, but the original candidate navigation callback did not execute');
    requireCapability(after.state.stateOwnerId === before.state.stateOwnerId && before.state.stateOwnerId &&
      after.state.gatewayId === before.state.gatewayId && before.state.gatewayId,
      'Navigation changed production state ownership; a same-store/gateway binding is required before comparing retained metadata');
    const displayedId = view.controls.find(c => c.id === 'current_room_id')?.node?.$attrs?.content;
    requireCapability(typeof displayedId === 'string', 'Rendered destination room identifier is not observable');
    requireCapability(Number.isFinite(before.state.navigationCount) && Number.isFinite(after.state.navigationCount),
      'Actual navigation call counter is unavailable');
    observed = { roomId: displayedId, navigationState: after.state.navigationState,
      effect: after.state.lastOpenedRoomId === target && after.state.navigationCount > before.state.navigationCount ? 'navigate_to_room' : null };
    if (observed.navigationState === undefined && displayedId === target && after.state.currentRoomId === target &&
      observed.effect === 'navigate_to_room') observed.navigationState = 'success';
    if (displayedId !== target || after.state.currentRoomId !== target) {
      ctx.notes.push({ kind: 'native_navigation_mismatch', target, displayedId, actual: copy(observed) });
    }
    const retained = after.state.rooms.find(room => room.roomId === roomId);
    requireCapability(retained, 'Original room state is no longer observable after navigation');
    check(ctx, key === 'open_successor' ? equal(original.history, retained.history) :
      equal(original.predecessorRoom, retained.predecessorRoom), { before: original, after: retained, instanceId: after.state.instanceId });
    // Supplemental probe only. The canonical case remains the single click
    // above; reset through an actual selection control before sending two taps.
    const resetId = g.predecessor ? 'room_list_replacement_room' : 'room_list_tombstoned_room';
    try { if (control(resetId)?.present) {
      await dispatch(actionId([resetId]));
      await delay(50);
      await capture('native:doubletap-before');
      const reset = read();
      if (reset.currentRoomId === roomId && equal(reset.rooms.find(room => room.roomId === roomId), original)) {
        const tap = actionId([id]);
        const physical = has(ui, 'doubleClick');
        const delivered = physical ? [await ui.doubleClick(tap)] : [ui.sendEvent(tap, 10, {}), ui.sendEvent(tap, 10, {})];
        await delay(50);
        const repeated = await capture('native:doubletap-after');
        record('native:doubletap-diagnostic', { canonicalAssertion: false, delivered,
          before: reset, after: repeated.state, navigationDelta: repeated.state.navigationCount - reset.navigationCount,
          callbackCalls: repeated.state.calls.slice(reset.calls.length).filter(call => eventMethods.includes(call.method)).length,
          limitation: physical ? 'Native UI double-click; supplemental diagnostic, not a new canonical case.' :
            'Two immediate native keyed click dispatches, not a physical touchscreen double-tap gesture.' });
      }
    } } catch (error) {
      record('native:doubletap-unavailable', { canonicalAssertion: false, reason: error.message });
    }
  } else {
    const after = await capture('after:event');
    const retained = after.state.rooms.find(room => room.roomId === roomId);
    if (key === 'tombstone_is_read_only') {
      observed = { history: retained?.history, composerVisible: visible('message_composer'), successorBannerVisible: visible('successor_room_banner') };
      check(ctx, equal(original.history, retained?.history) && visible('room_history') && visible('history_message_0'), { before, after });
    } else if (key === 'predecessor_banner') {
      observed = { predecessorBannerVisible: visible('predecessor_room_banner'), historyVisible: visible('room_history') && visible('history_message_0') };
      check(ctx, visible('room_beginning_content'), { before, after });
    } else if (key === 'room_list_tombstone_preview') {
      const attrs = control('room_list_tombstoned_room')?.node?.$attrs;
      const text = attrs?.label ?? attrs?.content ?? attrs?.text;
      requireCapability(typeof text === 'string', 'Rendered room-list summary text is unavailable');
      observed = { isTombstoned: original.successorRoom !== null,
        preview: text.includes('This room has been replaced') ? 'room_replaced' : text,
        avatarMarkedTombstoned: visible('room_avatar_tombstone_mark') };
      check(ctx, retained?.history?.slice(-1)[0] === g.lastMessage, { before: original, after: retained });
    } else throw new Unbound('Native room event not bound: ' + key);
  }
  return observed;
}

async function observeRoomView(ctx, roomId) {
  const ui = ctx.native?.ui;
  if (!has(ui, 'observe') || !has(ui, 'sendEvent')) return undefined;
  const g = ctx.caseSpec.given;
  const ids = ['current_room_id', 'room_list_tombstoned_room', 'room_list_replacement_room',
    'room_history', 'room_beginning_content', 'predecessor_room_id', 'successor_room_id',
    'predecessor_room_banner', 'successor_room_banner', 'message_composer', 'room_avatar_tombstone_mark',
    ...Array.from({ length: Math.max(1, g.history?.length ?? 0) }, (_, i) => `history_message_${i}`)];
  const textOf = control => control?.node?.$attrs?.content ?? control?.node?.$attrs?.text;
  const record = (label, data) => {
    ctx.evidence.push({ label, data: copy(data), observationLevel: 'native_candidate_ui' });
    ctx.trace(label, copy(data));
  };
  try {
    let view = await ui.observe(ids, 'current_room_id');
    if (!view.available) {
      record('native:room-fixture-unavailable', view);
      return undefined;
    }
    const control = id => view.controls.find(c => c.id === id);
    if (textOf(control('current_room_id')) !== roomId) {
      // Select through the candidate's real entry control, never through its presenter instance.
      const selection = g.predecessor || g.predecessorRoomId || ctx.caseSpec.key === 'map_predecessor_metadata' ?
        'room_list_replacement_room' : 'room_list_tombstoned_room';
      requireCapability(control(selection)?.present, 'Candidate has no bound room-selection control');
      requireCapability(await ui.sendEvent(selection, 10, {}), 'Native room selection event was not delivered');
      for (let attempt = 0; attempt < 20; attempt++) {
        await delay(25);
        view = await ui.observe(ids, 'current_room_id');
        if (view.available && textOf(control('current_room_id')) === roomId) break;
      }
    }
    requireCapability(view.available && textOf(control('current_room_id')) === roomId,
      'Native UI did not establish the given current room');
    if (g.successorRoomId) requireCapability(textOf(control('successor_room_id')) === g.successorRoomId,
      'Native UI did not establish the given successor metadata');
    if (g.predecessorRoomId) requireCapability(textOf(control('predecessor_room_id')) === g.predecessorRoomId,
      'Native UI did not establish the given predecessor metadata');
    if (g.history) requireCapability(g.history.every((message, i) => textOf(control(`history_message_${i}`)) === message),
      'Native UI did not establish the given room history');
    record('native:before:event', view);
    view = await ui.observe(ids, 'current_room_id');
    requireCapability(view.available, 'Candidate page anchor disappeared during rendering');
    record('native:after:event', view);
    const visible = id => {
      const c = control(id);
      requireCapability(typeof c?.present === 'boolean', `Native visibility unavailable for ${id}`);
      if (!c.present) return false;
      const attrs = c.node?.$attrs;
      requireCapability(attrs && typeof attrs.visibility === 'string', `Native visibility attribute unavailable for ${id}`);
      const bounds = JSON.parse(`[${c.node.$rect}]`);
      requireCapability(bounds.length === 2 && bounds.every(p => Array.isArray(p) && p.length === 2),
        `Native layout bounds unavailable for ${id}`);
      return attrs.visibility === 'Visibility.Visible' && Number(attrs.opacity) > 0 &&
        bounds[1][0] > bounds[0][0] && bounds[1][1] > bounds[0][1];
    };
    // Evaluate here so unsupported inspector attributes cannot produce a partial UI success.
    const visibility = Object.fromEntries(ids.map(id => [id, visible(id)]));
    ctx.nativeUIObserved = true;
    return { record: copy(view), visible: id => visibility[id],
      historyVisible: visibility.room_history && visibility.history_message_0 };
  } catch (error) {
    record('native:room-fixture-unavailable', { reason: error.message });
    ctx.notes.push({ kind: 'native_fixture_unavailable', reason: error.message });
    return undefined;
  }
}

function compareForNotes(expected, observed, prefix = '') {
  const missing = [];
  const mismatches = [];
  for (const [key, value] of Object.entries(expected)) {
    const field = prefix ? `${prefix}.${key}` : key;
    if (!observed || !Object.prototype.hasOwnProperty.call(observed, key) || observed[key] === undefined) missing.push(field);
    else if (value !== null && typeof value === 'object' && !Array.isArray(value) &&
      observed[key] !== null && typeof observed[key] === 'object' && !Array.isArray(observed[key])) {
      const nested = compareForNotes(value, observed[key], field);
      missing.push(...nested.missing); mismatches.push(...nested.mismatches);
    } else if (!equal(value, observed[key])) mismatches.push({ field, expected: value, observed: observed[key] });
  }
  return { missing, mismatches };
}

async function runCase({ taskId, caseSpec, project, load, trace = () => {}, native }) {
  const ctx = { taskId, caseSpec, project, load, trace, native, evidence: [], invariantChecks: [], unsupportedInvariants: [], notes: [] };
  const result = { observed: {}, evidence: ctx.evidence, invariantChecks: ctx.invariantChecks,
    unsupportedInvariants: ctx.unsupportedInvariants, observationLevel: 'production_domain', limitations: [LIMITATIONS], notes: ctx.notes };
  checkpoint(ctx, 'before:binding', { taskId, caseId: caseSpec.caseId, event: caseSpec.event });
  try {
    const adapter = { '08_threads': threads, '09_spaces_lifecycle': spaces, '10_media_upload_quality': media,
      '11_room_upgrade_navigation': roomUpgrade }[taskId];
    requireCapability(adapter, `No adapter for task ${taskId}`);
    result.observed = await adapter(ctx);
    if (ctx.nativeUIObserved) {
      result.observationLevel = ctx.nativeRoomStateObserved ? 'native_candidate_ui_and_production_state' : 'production_domain_and_native_candidate_ui';
      result.limitations = ['Native UI checkpoints cover the verified candidate room view only. Domain fixtures use external gateway doubles; device media encoding, persistence and network integration remain unobserved.'];
    }
    // Expected values are used only for completeness/diagnostics, never to produce observations.
    const comparison = compareForNotes(caseSpec.expected, result.observed);
    if (ctx.bindingUnsupported) result.unsupported = ctx.bindingUnsupported;
    else if (comparison.missing.length) result.unsupported = `Required production observations unavailable: ${comparison.missing.join(', ')}`;
    for (const mismatch of comparison.mismatches) ctx.notes.push({ kind: 'runtime_contract_mismatch', ...mismatch,
      scorable: !ctx.bindingUnsupported, ...(ctx.bindingUnsupported ? { reason: ctx.bindingUnsupported } : {}) });
  } catch (error) {
    result.unsupported = error instanceof Unbound ? error.message : `Runtime adapter could not complete: ${error.stack ?? error}`;
    if (!ctx.evidence.some(e => e.label === 'before:event')) checkpoint(ctx, 'before:event', { executed: false, reason: result.unsupported });
    checkpoint(ctx, 'after:event', { unsupported: result.unsupported });
  }
  for (const description of caseSpec.invariants ?? []) {
    if (!ctx.invariantChecks.some(c => c.description === description) && !ctx.unsupportedInvariants.some(c => c.description === description))
      ctx.unsupportedInvariants.push({ description, reason: result.unsupported ?? 'No executable invariant observation was bound' });
  }
  if (!ctx.evidence.some(e => e.label === 'before:event')) checkpoint(ctx, 'before:event', { executed: false, reason: result.unsupported });
  checkpoint(ctx, 'after:case', { observed: result.observed, unsupported: result.unsupported,
    invariantChecks: result.invariantChecks, unsupportedInvariants: result.unsupportedInvariants, notes: result.notes,
    observationLevel: result.observationLevel, limitations: result.limitations });
  return result;
}

module.exports = { runCase };
