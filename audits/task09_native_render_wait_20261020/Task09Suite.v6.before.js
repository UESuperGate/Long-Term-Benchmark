import { installTask09Input } from './Task09Input';
import { runTask09RepositoryCase } from './Task09Repository';

const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const requireObserved = (condition, message) => { if (!condition) throw new Error(message); };
export const TASK09_CASES = [
  'sp_state_001_open_space', 'sp_state_002_paginate_children', 'sp_state_003_join_child_success',
  'sp_state_004_join_failure_retry', 'sp_state_005_accept_invite', 'sp_state_006_default_leave_selection',
  'sp_state_007_bulk_and_toggle_selection', 'sp_state_008_leave_failure_retry', 'sp_state_009_leave_selected_rooms'
];

export async function runTask09Case(spec, config, session, importModule, emit, trace = () => {}, preparedObserver) {
  if (config.productionVariant === 'repository')
    return runTask09RepositoryCase(spec, config, session, importModule, emit, trace, preparedObserver);
  const result = { observed: {}, invariantChecks: [], evidence: [],
    observationLevel: 'openharmony_api23_original_arkui_and_production_runtime',
    limitations: ['Only external hierarchy/join responses are evaluator controlled; original page, presenter, gateway and UI actions own transitions.'] };
  let observer;
  const record = event => { const value = clone(event); result.evidence.push({ label: event.method, data: value }); emit(value); };
  const wait = async predicate => {
    for (let attempt = 0; attempt < 200; attempt++) {
      const state = observer.read();
      if (predicate(state)) return state;
      await session.delay(25);
    }
    throw new Error('Original Task09 page did not reach the required runtime boundary');
  };
  const select = async (name, selector) => {
    const frame = await session.observe('Task09.' + name, { target: [selector] });
    const target = frame.controls.target;
    requireObserved(target?.present === true && target.visible === true, 'Original Task09 control unavailable: ' + JSON.stringify(selector));
    return target;
  };
  const click = async (name, selector) => session.action('click', await select(name, selector));
  const settledClick = async (name, selector, predicate) => {
    await click(name, selector);
    for (let attempt = 1; attempt <= 20; attempt++) {
      // UiTest click resolves before ArkUI has necessarily committed the
      // refresh triggered by the production handler. Always yield first so a
      // following bulk/toggle action cannot enter the same render pass.
      await session.delay(50);
      const state = observer.read();
      if (predicate(state)) {
        record({ method: 'Task09.harnessUiStepSettled', name, attempt,
          selectedLeaveRoomIds: state.selectedLeaveRoomIds });
        return state;
      }
    }
    throw new Error('Original Task09 UI step did not settle: ' + name);
  };
  const checkpoint = async label => {
    const frame = await session.observe(label, { status: [{ id: 'spaces_status' }], home: [{ id: 'spaces_home' }],
      placeholder: [{ id: 'spaces_unavailable' }], leave: [{ id: 'leave_space_surface' }] });
    const state = observer.read();
    const value = { state, routeName: frame.routeName, windowId: frame.windowId, controls: frame.controls, tree: frame.tree };
    record({ method: label, frame: value }); trace(label, value); return value;
  };
  const invariant = (passed, observed) => {
    requireObserved(spec.invariants.length === 1, 'Canonical Task09 invariant binding changed');
    result.invariantChecks.push({ description: spec.invariants[0], passed: Boolean(passed), observed: clone(observed) });
  };
  const actionState = (state, roomId) => state.joinActions.find(action => action.roomId === roomId);
  const membership = (state, roomId) => state.children.find(room => room.roomId === roomId)?.membership || null;
  const openSpace = async () => {
    await click('open-space', { id: 'space_!space' });
    return wait(state => state.available && state.selectedSpaceId === '!space' &&
      ['loading', 'success', 'failure'].includes(state.childrenState));
  };
  const openReady = async () => {
    await openSpace();
    return wait(state => state.childrenState === 'success');
  };
  const openLeave = async () => { await click('open-leave', { id: 'open_leave_space' }); return wait(state => state.surface === 'leave'); };
  try {
    requireObserved(spec.taskId === '09_spaces_lifecycle' && TASK09_CASES.includes(spec.caseId), 'Unsupported Task09 canonical case');
    const namespace = await importModule(config.productionModuleUrl);
    observer = installTask09Input(namespace, config.productionVariant === 'base' ? 'base' : 'final', spec, record);
    await session.reloadOriginalPage();
    await session.delay(80);
    if (config.productionVariant === 'base') {
      await click('common-chats-prefix', { id: 'home_chats_tab' });
      await wait(value => value.available && value.surface === 'chats');
      const before = await session.observe('before:event', { spaces: [{ id: 'home_spaces_tab' }],
        placeholder: [{ id: 'spaces_unavailable' }] });
      const stateBefore = observer.read();
      trace('before:event', { ...before, state: stateBefore });
      await session.action('click', before.controls.spaces);
      const state = await wait(value => value.available && value.surface === 'spaces');
      const after = await checkpoint('after:event');
      record({ method: 'Task09.missingFeatureEntry', eventExecuted: true,
        before, after, stateBefore, stateAfter: state });
      // A real missing entry does not establish any lifecycle post-state.
      // The source-bound host verifier classifies only this early entry failure.
      return result;
    }

    if (spec.key === 'accept_invite') {
      await checkpoint('before:event');
      await click('accept-invite', { id: 'accept_space_!invited' });
      const state = await wait(value => value.available && value.gateway.lastAcceptedInviteId === '!invited');
      await checkpoint('after:event');
      const joined = state.spaces.find(space => space.roomId === '!invited');
      result.observed = { effect: 'accept_invite', membership: joined?.membership || null, seenInvites: state.seenInviteIds };
      invariant(!state.invites.some(invite => invite.roomId === '!invited') && joined?.membership === 'joined',
        { invites: state.invites, spaces: state.spaces, gateway: state.gateway });
      return result;
    }

    if (spec.key === 'open_space') {
      await checkpoint('before:event');
      const pending = await openSpace();
      requireObserved(pending.childrenState === 'loading', 'Original open-space loading state was not observed');
      await checkpoint('after:event');
      result.observed = { surface: pending.surface, selectedSpaceId: pending.selectedSpaceId, childrenState: pending.childrenState };
      observer.releaseChildren();
      const settled = await wait(state => state.childrenState === 'success');
      invariant(settled.selectedSpaceId === '!space' && settled.surface === 'space', { pending, settled });
      return result;
    }

    await openReady();
    if (spec.key === 'paginate_children') {
      await checkpoint('before:event');
      await click('load-more', { id: 'space_load_more' });
      const state = await wait(value => value.paginationState === 'idle' && value.hasMoreToLoad === false);
      await checkpoint('after:event');
      const children = state.children.map(room => room.roomId);
      result.observed = { children, hasMoreToLoad: state.hasMoreToLoad, paginationState: state.paginationState };
      invariant(JSON.stringify(children) === JSON.stringify(['!a', '!b', '!c']) &&
        children.filter(id => id === '!b').length === 1, { children });
    } else if (spec.key === 'join_child_success') {
      await checkpoint('before:event');
      await click('join-a', { id: 'join_!a' });
      const state = await wait(value => membership(value, '!a') === 'joined');
      await checkpoint('after:event');
      result.observed = { memberships: { '!a': membership(state, '!a'), '!b': membership(state, '!b') },
        joinActions: { '!a': actionState(state, '!a') ? actionState(state, '!a').state : 'cleared' }, effect: 'join_room' };
      invariant(membership(state, '!b') === null, { children: state.children, gateway: state.gateway });
    } else if (spec.key === 'join_failure_retry') {
      await click('fail-next-join', { id: 'fail_next_join' });
      await click('join-a-failure', { id: 'join_!a' });
      await wait(value => actionState(value, '!a')?.state === 'failure');
      await click('join-b-held', { id: 'join_!b' });
      await wait(value => actionState(value, '!b')?.state === 'loading');
      await checkpoint('before:event');
      await click('clear-join-failures', { id: 'clear_join_failures' });
      await click('join-a-retry', { id: 'join_!a' });
      const state = await wait(value => membership(value, '!a') === 'joined');
      await checkpoint('after:event');
      result.observed = { joinActions: { '!a': actionState(state, '!a') ? actionState(state, '!a').state : 'cleared',
        '!b': actionState(state, '!b')?.state || null }, memberships: { '!a': membership(state, '!a'), '!b': membership(state, '!b') },
        attempts: { '!a': state.attempts['!a'] } };
      invariant(actionState(state, '!b')?.state === 'loading' && membership(state, '!b') === null,
        { joinActions: state.joinActions, attempts: state.attempts });
    } else if (spec.key === 'default_leave_selection') {
      await checkpoint('before:event'); await openLeave(); const state = observer.read(); const after = await checkpoint('after:event');
      const visibleChildren = state.children.filter(room => !room.isDirect).map(room => room.roomId);
      result.observed = { visibleChildren, selectedRoomIds: state.selectedLeaveRoomIds,
        disabledRoomIds: state.children.filter(room => room.isLastAdmin).map(room => room.roomId) };
      const admin = await select('disabled-admin', { id: 'leave_room_!admin' });
      invariant(!visibleChildren.includes('!dm') && !state.selectedLeaveRoomIds.includes('!admin') && admin.enabled === false,
        { state, controls: after.controls, admin });
    } else if (spec.key === 'bulk_and_toggle_selection') {
      await openLeave();
      await settledClick('toggle-b-prefix', { id: 'leave_room_!b' },
        state => JSON.stringify(state.selectedLeaveRoomIds) === JSON.stringify(['!a']));
      await checkpoint('before:event');
      const deselected = await settledClick('deselect-all', { id: 'deselect_all_leave_rooms' },
        state => state.selectedLeaveRoomIds.length === 0);
      const afterDeselectAll = deselected.selectedLeaveRoomIds;
      const selected = await settledClick('select-all', { id: 'select_all_leave_rooms' },
        state => JSON.stringify(state.selectedLeaveRoomIds) === JSON.stringify(['!a', '!b']));
      const afterSelectAll = selected.selectedLeaveRoomIds;
      const state = await settledClick('toggle-b', { id: 'leave_room_!b' },
        value => JSON.stringify(value.selectedLeaveRoomIds) === JSON.stringify(['!a']));
      const admin = await select('admin-disabled', { id: 'leave_room_!admin' });
      await checkpoint('after:event');
      result.observed = { afterDeselectAll, afterSelectAll, selectedRoomIds: state.selectedLeaveRoomIds,
        lastAdminSelected: state.selectedLeaveRoomIds.includes('!admin') };
      invariant(admin.enabled === false && !afterSelectAll.includes('!admin') && !state.selectedLeaveRoomIds.includes('!admin'),
        { admin, afterDeselectAll, afterSelectAll, selected: state.selectedLeaveRoomIds });
    } else if (spec.key === 'leave_failure_retry') {
      await openLeave(); await click('toggle-b-prefix', { id: 'leave_room_!b' }); await checkpoint('before:event');
      await click('fail-next-leave', { id: 'fail_next_leave' }); await click('confirm-failure', { id: 'confirm_leave_space' });
      let state = await wait(value => value.leaveState === 'failure'); const firstState = state.leaveState;
      const selectionAfterFailure = state.selectedLeaveRoomIds; await click('close-error', { id: 'close_leave_error' });
      await click('confirm-retry', { id: 'confirm_leave_space' }); state = await wait(value => value.leaveState === 'success');
      await checkpoint('after:event');
      result.observed = { firstState, selectionAfterFailure, finalState: state.leaveState, attempts: state.leaveAttempts };
      invariant(firstState === 'failure' && JSON.stringify(selectionAfterFailure) === JSON.stringify(['!a']),
        { firstState, selectionAfterFailure, gateway: state.gateway });
    } else if (spec.key === 'leave_selected_rooms') {
      await click('load-more-for-c', { id: 'space_load_more' }); await wait(value => value.hasMoreToLoad === false);
      await openLeave(); await click('deselect-all-prefix', { id: 'deselect_all_leave_rooms' });
      await click('select-a-prefix', { id: 'leave_room_!a' }); await click('select-c-prefix', { id: 'leave_room_!c' });
      await checkpoint('before:event'); await click('confirm-leave', { id: 'confirm_leave_space' });
      const state = await wait(value => value.leaveState === 'success' && value.surface === 'home'); await checkpoint('after:event');
      result.observed = { effect: 'leave_space', payload: state.gateway.lastLeftRoomIds,
        leaveState: state.leaveState, surface: state.surface };
      invariant(JSON.stringify(state.gateway.lastLeftRoomIds) === JSON.stringify(['!a', '!c']),
        { selected: state.selectedLeaveRoomIds, payload: state.gateway.lastLeftRoomIds });
    }
  } catch (error) {
    result.unsupported = String(error.message || error);
  } finally {
    if (observer) observer.dispose();
    for (const description of spec.invariants || []) if (!result.invariantChecks.some(check => check.description === description))
      result.unsupportedInvariants = [{ description, reason: result.unsupported || 'Task09 invariant unavailable' }];
  }
  return result;
}
