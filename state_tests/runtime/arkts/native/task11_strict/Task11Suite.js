import { installTask11Input } from './Task11Input';
import { acquireTask11Frame } from './Task11Frame';

const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const requireObserved = (condition, message) => { if (!condition) throw new Error(message); };
export const TASK11_CASES = [
  'ru_state_002_tombstone_is_read_only',
  'ru_state_003_open_successor',
  'ru_state_005_room_list_tombstone_preview',
  'ru_state_006_map_predecessor',
  'ru_state_007_predecessor_banner',
  'ru_state_008_open_predecessor'
];

export async function runTask11Case(spec, config, session, importModule, emit, trace = () => {}) {
  const result = { observed: {}, invariantChecks: [], unsupportedInvariants: [], evidence: [], notes: [],
    observationLevel: 'openharmony_api23_original_arkui_and_production_runtime',
    limitations: ['External room-info responses are evaluator controlled; all mapping, state, rendering and navigation remain original production code.'] };
  let observer, beforeRecorded = false, afterRecorded = false;
  const record = event => { const value = clone(event); result.evidence.push({ label: event.method, data: value }); emit(value); };
  const visible = control => {
    requireObserved(typeof control?.visible === 'boolean', 'Original UI visibility unavailable: ' + JSON.stringify(control?.selector));
    return control.visible;
  };
  const text = control => control?.text;
  const g = spec.given;
  const roomId = g.roomId || g.currentRoomId;
  const predecessorCase = spec.caseId.includes('_006_') || spec.caseId.includes('_007_') || spec.caseId.includes('_008_');
  const targetRoomId = predecessorCase ? '!new:example.org' : '!old:example.org';
  const response = config.apiVariant === 'base' ? {
    roomId: targetRoomId,
    composerEnabled: g.composerEnabled === undefined ? true : g.composerEnabled,
    name: predecessorCase ? 'Product planning v2' : 'Product planning',
    lastMessage: predecessorCase ? 'Welcome to the replacement room' : (g.lastMessage || g.history?.[0] || 'Earlier message'),
    successorRoom: predecessorCase ? null : { roomId: g.successorRoomId, reason: null },
    predecessorRoom: predecessorCase ? clone(g.predecessor || { roomId: g.predecessorRoomId, lastEventId: '$last:example.org' }) : null
  } : {
    roomId: targetRoomId,
    composerEnabled: g.composerEnabled === undefined ? true : g.composerEnabled,
    name: predecessorCase ? 'Product planning v2' : 'Product planning',
    history: predecessorCase ? ['Welcome to the replacement room'] : clone(g.history || [g.lastMessage || 'Earlier message']),
    successorRoom: predecessorCase ? undefined : { roomId: g.successorRoomId },
    predecessorRoom: predecessorCase ? clone(g.predecessor || { roomId: g.predecessorRoomId, lastEventId: '$last:example.org' }) : undefined
  };
  const historyText = predecessorCase ? 'Welcome to the replacement room' : (g.history?.[0] || g.lastMessage || 'Earlier message');
  const selectors = {
    currentRoom: [{ id: 'current_room_id' }],
    rooms: [{ type: 'Text', text: 'Rooms' }],
    timeline: [{ type: 'Text', text: 'Timeline' }],
    oldRoom: [{ id: 'room_list_tombstoned_room' }, { id: 'room_list_old_room' }],
    oldRoomSummary: [{ id: 'room_list_tombstoned_room_summary' }, { id: 'room_list_old_room_summary' }],
    replacementRoom: [{ id: 'room_list_replacement_room' }],
    history: [{ id: 'room_history' }],
    history0: [{ id: 'history_message_0' }, { type: 'Text', text: historyText }],
    beginning: [{ id: 'room_beginning_content' }],
    composer: [{ id: 'message_composer' }],
    successorBanner: [{ id: 'successor_room_banner' }, { id: 'room_tombstone_banner' }],
    successorId: [{ id: 'successor_room_id' }],
    successorAction: [{ id: 'open_successor_room' }],
    avatarMark: [{ id: 'room_avatar_tombstone_mark' }],
    predecessorBanner: [{ id: 'predecessor_room_banner' }, { id: 'predecessor_room_entry' }],
    predecessorId: [{ id: 'predecessor_room_id' }],
    predecessorAction: [{ id: 'open_predecessor_room' }]
  };
  const frame = async label => {
    const view = observer ? await acquireTask11Frame(session, label, selectors, () => observer.read(), record) :
      await session.observe(label, selectors);
    const value = { ...view, state: view.state || observer?.read() };
    record({ method: label, frame: value }); trace(label, value);
    if (label === 'before:event') beforeRecorded = true;
    if (label === 'after:event') afterRecorded = true;
    return value;
  };
  const wait = async predicate => {
    for (let attempt = 0; attempt < 120; attempt++) {
      const value = observer.read();
      if (predicate(value)) return value;
      await session.delay(25);
    }
    throw new Error('Original Task11 page did not reach the required runtime boundary');
  };
  const action = async (kind, control, value) => session.action(kind, control?.actionAncestor || control, value);
  const invariant = (passed, observed) => {
    requireObserved(spec.invariants.length === 1, 'Canonical invariant binding changed');
    result.invariantChecks.push({ description: spec.invariants[0], passed: Boolean(passed), observed: clone(observed) });
  };
  const requestFor = state => state.requests.find(request => request.roomId === targetRoomId && !request.settled);
  try {
    requireObserved(spec.taskId === '11_room_upgrade_navigation' && TASK11_CASES.includes(spec.caseId), 'Unsupported Task11 canonical case');
    requireObserved(['base', 'final', 'agent'].includes(config.role) && ['base', 'final'].includes(config.apiVariant) &&
      config.mode === 'after-page-ready-prefix', 'Explicit Task11 runtime role/API variant/mode required');
    const warm = await frame('prefix:original-page-ready');
    requireObserved(warm.available && warm.routeName === config.entryRoute && visible(warm.controls.rooms) &&
      visible(warm.controls.timeline) && visible(warm.controls.oldRoom), 'Original Task11 page root/list/timeline unavailable');
    requireObserved(config.productionSources.some(source =>
      config.productionModuleUrl.endsWith(source.path.replace('entry/src/main/', '').replace(/\.ets$/, ''))),
    'Original Task11 module URL mismatch');
    record({ method: 'Task11.beforeOriginalModuleImport', role: config.role, url: config.productionModuleUrl,
      routeName: warm.routeName, windowId: warm.windowId, source: config.productionSources });
    const namespace = await importModule(config.productionModuleUrl);
    observer = installTask11Input(namespace, config.apiVariant, response, record);
    if (!predecessorCase) observer.setAvailableResponse({ ...response,
      successorRoom: config.apiVariant === 'base' ? null : undefined,
      predecessorRoom: config.apiVariant === 'base' ? null : undefined,
      composerEnabled: true });
    await session.reloadOriginalPage();
    await wait(state => state.available && state.instanceCount === 1);

    let composerEnabled;
    if (!predecessorCase) {
      await wait(state => state.room?.roomId === targetRoomId && !state.room?.successorRoom);
      const ordinary = await frame('prefix:ordinary-sdk-response-rendered');
      requireObserved(visible(ordinary.controls.composer) && ordinary.controls.composer.enabled === true,
        'Canonical writable input boundary is not enabled after original SDK/page setup');
      observer.enableHold();
      const method = config.apiVariant === 'base' ? 'observeRoomInfo' : 'observeTimelineRoomInfo';
      const operation = observer.invoke(method, targetRoomId);
      const pendingState = await wait(state => Boolean(requestFor(state)));
      const pending = await frame('prefix:successor-response-pending');
      requireObserved(pending.state.instanceId === pendingState.instanceId && visible(pending.controls.composer),
        'Writable original room was not rendered before successor delivery');
      composerEnabled = pending.controls.composer.enabled;
      requireObserved(composerEnabled === true, 'Canonical writable input boundary is not enabled');
      observer.releaseResponse(requestFor(pendingState).id);
      await operation;
      await wait(state => state.room?.successorRoom?.roomId === g.successorRoomId);
      observer.setAvailableResponse(response);
      const refresh = await frame('prefix:successor-sdk-response-mapped');
      requireObserved(visible(refresh.controls.oldRoom), 'Original room entry unavailable for actual page refresh');
      await action('click', refresh.controls.oldRoom);
      await session.delay(80);
    } else {
      const current = await frame('prefix:ordinary-room-ready');
      if (current.state.currentRoomId !== targetRoomId) {
        requireObserved(visible(current.controls.replacementRoom), 'Ordinary replacement-room selector unavailable');
        await action('click', current.controls.replacementRoom);
        await wait(state => state.currentRoomId === targetRoomId);
      }
      observer.enableHold();
      if (spec.key !== 'map_predecessor_metadata') {
        const method = config.apiVariant === 'base' ? 'observeRoomInfo' : 'observeTimelineRoomInfo';
        const pending = observer.invoke(method, targetRoomId);
        const requestState = await wait(state => Boolean(requestFor(state)));
        observer.releaseResponse(requestFor(requestState).id);
        await pending;
        await wait(state => state.currentRoomId === targetRoomId);
        if (config.apiVariant === 'final') {
          const mapped = await frame('prefix:predecessor-response-mapped');
          requireObserved(visible(mapped.controls.oldRoom), 'Original old-room selector unavailable after predecessor mapping');
          await action('click', mapped.controls.oldRoom);
          await wait(state => state.currentRoomId === '!old:example.org');
          const oldRoom = await frame('prefix:old-room-refresh');
          requireObserved(visible(oldRoom.controls.replacementRoom), 'Original replacement-room selector unavailable for mapped refresh');
          await action('click', oldRoom.controls.replacementRoom);
          await wait(state => state.currentRoomId === targetRoomId);
        }
      }
    }

    const established = observer.read();
    const establishedRoom = established.rooms.find(room => room?.roomId === roomId) || established.room;
    const inputEvidence = {
      roomId: established.currentRoomId,
      externalRoomInfo: clone(response),
      successorRoomId: establishedRoom?.successorRoom?.roomId,
      predecessorRoom: establishedRoom?.predecessorRoom,
      composerEnabled
    };
    record({ method: 'Task11.givenEstablished', role: config.role, caseId: spec.caseId,
      externalBoundaryEstablished: true, productionState: inputEvidence,
      note: 'predecessor fields may remain absent in base because mapping is the feature under test' });

    const before = await frame('before:event');
    requireObserved(before.state.currentRoomId === roomId, 'Canonical current room was not established on the original page');
    let after = before;
    if (spec.key === 'map_predecessor_metadata') {
      const method = config.apiVariant === 'base' ? 'observeRoomInfo' : 'observeTimelineRoomInfo';
      const operation = observer.invoke(method, targetRoomId);
      const requestState = await wait(state => Boolean(requestFor(state)));
      observer.releaseResponse(requestFor(requestState).id);
      await operation;
      await wait(state => state.currentRoomId === targetRoomId);
      after = await frame('after:event');
      const mapped = after.state.rooms.find(room => room?.roomId === roomId)?.predecessorRoom;
      result.observed = { predecessorRoom: clone(mapped ?? null) };
      invariant(mapped?.lastEventId === g.predecessor.lastEventId,
        { external: response.predecessorRoom, mapped: clone(mapped ?? null) });
    } else if (spec.key === 'open_successor' || spec.key === 'open_predecessor') {
      const successor = spec.key === 'open_successor';
      const control = successor ? before.controls.successorAction : before.controls.predecessorAction;
      const target = successor ? g.successorRoomId : g.predecessor.roomId;
      const original = clone(before.state.rooms.find(room => room?.roomId === roomId));
      const navigationBefore = before.state.navigationCount || 0;
      if (control.present === false && control.inspectorMatches === 0) {
        after = await frame('after:event');
        result.observed = { effect: null, roomId: null, navigationState: 'entry_missing' };
      } else {
        requireObserved(visible(control), 'Original navigation action visibility unavailable');
        await action('click', control);
        await wait(state => state.currentRoomId === target || state.navigationState === 'failure');
        after = await frame('after:event');
        result.observed = {
          effect: after.state.lastOpenedRoomId === target && (after.state.navigationCount || 0) > navigationBefore ? 'navigate_to_room' : null,
          roomId: after.state.currentRoomId,
          navigationState: after.state.navigationState
        };
      }
      const retained = after.state.rooms.find(room => room?.roomId === roomId) || after.state.room;
      invariant(successor ? same(original?.history, retained?.history) :
        same(original?.predecessorRoom, retained?.predecessorRoom) &&
          retained?.predecessorRoom?.lastEventId === g.predecessor.lastEventId,
      { before: original, after: retained });
    } else {
      await session.delay(80);
      after = await frame('after:event');
      const retained = after.state.rooms.find(room => room?.roomId === roomId) || after.state.room;
      if (spec.key === 'tombstone_is_read_only') {
        result.observed = { history: clone(retained?.history || after.state.history),
          composerVisible: visible(after.controls.composer), successorBannerVisible: visible(after.controls.successorBanner) };
        invariant(same(before.state.history, after.state.history) && visible(after.controls.history) && visible(after.controls.history0),
          { before: before.state.history, after: after.state.history });
      } else if (spec.key === 'room_list_tombstone_preview') {
        const label = text(after.controls.oldRoomSummary.present === true ? after.controls.oldRoomSummary : after.controls.oldRoom);
        requireObserved(typeof label === 'string', 'Original room-list label unavailable');
        result.observed = { isTombstoned: Boolean(retained?.successorRoom),
          preview: label.includes('This room has been replaced') ? 'room_replaced' : label.split(' - ').slice(1).join(' - '),
          avatarMarkedTombstoned: visible(after.controls.avatarMark) };
        invariant((retained?.history || after.state.history)?.slice(-1)[0] === g.lastMessage,
          { room: retained, renderedLabel: label });
      } else if (spec.key === 'predecessor_banner') {
        result.observed = { predecessorBannerVisible: visible(after.controls.predecessorBanner),
          historyVisible: visible(after.controls.history) && visible(after.controls.history0) };
        invariant(visible(after.controls.beginning), { beginning: after.controls.beginning });
      }
    }
  } catch (error) {
    result.unsupported = String(error.message || error);
  } finally {
    if (!beforeRecorded) trace('before:event', { executed: false, reason: result.unsupported });
    if (!afterRecorded) trace('after:event', { executed: false, reason: result.unsupported });
    if (observer) observer.dispose();
    for (const description of spec.invariants || []) if (!result.invariantChecks.some(check => check.description === description))
      result.unsupportedInvariants.push({ description, reason: result.unsupported || 'Native invariant unavailable' });
  }
  return result;
}
