// Read-only method observation and input records for split repository applications.
// No presenter/repository result is synthesized; all calls delegate to the original.
const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const requireRuntime = (value, reason) => { if (!value) throw new Error(reason); };

export function observeTask09Repository(spacesModule, leaveModule, registryModule, spec, emit) {
  const repository = registryModule.SpaceServiceRegistry.getRepository();
  const account = repository.account;
  requireRuntime(account && Array.isArray(account.spaces) && account.rooms instanceof Map &&
    Array.isArray(account.invites) && Array.isArray(account.seenSpaceIds),
    'Task09 adapter_binding_incomplete: original account input storage unavailable');
  const restores = [], calls = [], held = [], paginationEvents = [];
  let spaces, leave, holdNext = false, disposed = false;
  const attempts = {};
  // Fixture records enter before a fresh original page loads them. Production
  // account membership, pagination, invitation and leave methods remain intact.
  const room = (roomId, isDirect = false, isLastAdmin = false) => ({ roomId, name: roomId,
    spaceId: '!space', isDirect, isLastAdmin, canJoin: true,
    membership: spec.key.includes('join_') ? 'none' : 'joined' });
  let rooms = spec.key === 'default_leave_selection' ?
    [room('!normal'), room('!admin', false, true), room('!dm', true)] : [room('!a'), room('!b')];
  if (spec.key === 'bulk_and_toggle_selection') rooms.push(room('!admin', false, true));
  if (['paginate_children', 'leave_selected_rooms'].includes(spec.key)) rooms.push(room('!c'));
  const paginated = ['paginate_children', 'leave_selected_rooms'].includes(spec.key);
  const childRoomIds = paginated ? ['!a', '!b', '!b', '!b', '!b', '!c'] : rooms.map(value => value.roomId);
  account.spaces = [{ spaceId: '!space', name: '!space', topic: '', memberCount: 3, joined: true, childRoomIds },
    { spaceId: '!invited', name: '!invited', topic: '', memberCount: 1, joined: false, childRoomIds: [] }];
  account.rooms = new Map(rooms.map(value => [value.roomId, value]));
  account.invites = spec.key === 'accept_invite' ?
    [{ spaceId: '!invited', name: '!invited', inviterName: 'Alice', seen: false }] : [];
  account.seenSpaceIds = [];
  const wrap = (prototype, method, before, after) => {
    const descriptor = Object.getOwnPropertyDescriptor(prototype, method);
    requireRuntime(descriptor?.configurable && typeof descriptor.value === 'function',
      'Task09 adapter_binding_incomplete: original method unavailable: ' + method);
    Object.defineProperty(prototype, method, { ...descriptor, value: function(...args) {
      before?.(this, args);
      const receipt = { method, args: clone(args), completed: false };
      calls.push(receipt); emit({ method: 'Task09.originalRepositoryCall', receipt: clone(receipt) });
      try {
        const result = descriptor.value.apply(this, args);
        if (result && typeof result.then === 'function') return result.then(value => {
          receipt.completed = true; receipt.result = clone(value); after?.(this, args, value);
          emit({ method: 'Task09.originalRepositoryReturn', receipt: clone(receipt) }); return value;
        }, error => { receipt.completed = true; receipt.error = String(error); throw error; });
        receipt.completed = true; receipt.result = clone(result); after?.(this, args, result);
        return result;
      } catch (error) { receipt.completed = true; receipt.error = String(error); throw error; }
    } });
    restores.push(() => Object.defineProperty(prototype, method, descriptor));
  };
  try {
    for (const method of ['load', 'selectSpace', 'openSelectedSpace', 'loadMoreChildren', 'joinChild',
      'clearJoinFailure', 'retryJoin', 'acceptInvite'])
      wrap(spacesModule.SpacesPresenter.prototype, method, receiver => {
        spaces = receiver;
        if (method === 'loadMoreChildren') {
          const before = clone(receiver.view());
          if (before.hasMoreChildren && !before.loadingMore && !before.childrenLoading)
            paginationEvents.push({ before });
        }
      });
    for (const method of ['bind', 'load', 'setSelected', 'selectAll', 'deselectAll', 'confirmLeave',
      'clearLeaveFailure', 'retryLeave'])
      wrap(leaveModule.LeaveSpacePresenter.prototype, method, receiver => { leave = receiver; });
    for (const method of ['loadHome', 'markInviteSeen', 'respondToInvite', 'loadChildrenPage',
      'joinChildRoom', 'loadLeaveCandidates', 'leaveSpace'])
      wrap(Object.getPrototypeOf(repository), method, (receiver, args) => {
        if (method === 'joinChildRoom') {
          attempts[args[1]] = (attempts[args[1]] || 0) + 1;
          if (spec.key === 'join_failure_retry' && args[1] === '!b') holdNext = true;
        }
        if (method === 'loadChildrenPage' && spec.key === 'open_space') holdNext = true;
        if (method === 'loadChildrenPage' && spec.key === 'paginate_children' && args[1]) holdNext = true;
        // Keep unrelated automatic seen-tracking responses pending so the
        // canonical empty-seen given is not changed before the Accept event.
        if (method === 'markInviteSeen' && spec.key === 'accept_invite') holdNext = true;
      });
    const descriptor = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(repository), 'settle');
    requireRuntime(descriptor?.configurable && typeof descriptor.value === 'function',
      'Task09 adapter_binding_incomplete: original request latency boundary unavailable');
    Object.defineProperty(Object.getPrototypeOf(repository), 'settle', { ...descriptor, value: function(...args) {
      if (!holdNext) return descriptor.value.apply(this, args);
      holdNext = false;
      return new Promise(resolve => held.push(() => resolve(descriptor.value.apply(this, args))));
    } });
    restores.push(() => Object.defineProperty(Object.getPrototypeOf(repository), 'settle', descriptor));
  } catch (error) { restores.reverse().forEach(restore => restore()); throw error; }
  return {
    read: () => ({ spaces: spaces?.view(), leave: leave?.view(),
      account: { spaces: clone(account.spaces), rooms: clone(Array.from(account.rooms.values())),
        invites: clone(account.invites), seenSpaceIds: clone(account.seenSpaceIds) },
      calls: clone(calls), attempts: clone(attempts), paginationEvents: clone(paginationEvents) }),
    setJoinPermission: allowed => { account.rooms.get('!a').canJoin = allowed; },
    setSyncReady: ready => { account.ready = ready; },
    release: () => { const next = held.shift(); requireRuntime(next, 'No pending original Task09 request'); next(); },
    dispose: () => { if (!disposed) { disposed = true; held.splice(0).forEach(release => release());
      restores.reverse().forEach(restore => restore()); } }
  };
}

export async function prepareTask09Repository(spec, config, importModule, emit) {
  const namespaces = {};
  for (const [key, url] of Object.entries(config.repositoryModules)) namespaces[key] = await importModule(url);
  // Entry HAP modules can only be imported after the original ability loads.
  // The local repository has one request-latency boundary; two original reads
  // drain the initial home read and its subsequent automatic seen requests.
  const repository = namespaces.registry.SpaceServiceRegistry.getRepository();
  await repository.loadHome();
  await repository.loadHome();
  emit({ method: 'Task09.initialRequestsDrained', originalHomeReads: 2 });
  return observeTask09Repository(namespaces.spaces, namespaces.leave, namespaces.registry, spec, emit);
}

export async function runTask09RepositoryCase(spec, config, session, importModule, emit, trace, preparedObserver) {
  const result = { observed: {}, evidence: [], invariantChecks: [],
    observationLevel: 'openharmony_api23_original_arkui_and_production_repository_runtime',
    limitations: ['Fixture account records and request latency are controlled; original production methods and actual UI transitions execute unchanged.'] };
  let observer;
  const record = (label, value) => {
    const data = clone(value); result.evidence.push({ label, data }); emit({ method: label, data });
  };
  const wait = async predicate => {
    for (let attempt = 0; attempt < 200; attempt++) {
      const state = observer.read(); if (predicate(state)) return state; await session.delay(25);
    }
    throw new Error('Task09 original repository application did not reach the required runtime boundary');
  };
  const observe = async (label, selectors) => {
    for (let attempt = 1; attempt <= 8; attempt++) {
      try { return await session.observe(label, selectors); }
      catch (error) {
        if (!/NoCandidates|dose not exist on current UI/.test(String(error)) || attempt === 8) throw error;
        record('Task09.readOnlyAcquisitionRetry', { label, attempt, error: String(error) });
        await session.delay(50);
      }
    }
  };
  const control = async selector => (await observe('Task09.control', {
    target: Array.isArray(selector) ? selector : [selector] })).controls.target;
  const click = async selector => {
    if (selector?.id?.startsWith('leave_space_checkbox_')) {
      const row = observer.read().leave.rooms.find(value =>
        'leave_space_checkbox_' + value.roomId.replace(/[^A-Za-z0-9]/g, '_') === selector.id);
      requireRuntime(row && typeof session.checked === 'function', 'Task09 native checkbox binding unavailable');
      for (let attempt = 0; attempt < 20; attempt++) {
        const actual = await session.checked(selector);
        const current = observer.read().leave.rooms.find(value => value.roomId === row.roomId);
        record('Task09.checkboxRenderCommit', { roomId: row.roomId, nativeChecked: actual,
          productionSelected: current.selected, attempt });
        if (actual === current.selected) break;
        await session.delay(50);
      }
    }
    for (let attempt = 1; attempt <= 8; attempt++) {
      const target = await control(selector);
      try { await session.action('click', target); break; }
      catch (error) {
        // This exact exception is raised by the shared transport before click().
        // Never retry after a physical dispatch or a semantic FAIL.
        if (String(error.message || error) !== 'Original UI action target changed' || attempt === 8) throw error;
        record('Task09.preDispatchAcquisitionRetry', { selector, attempt, error: String(error) });
        await session.delay(50);
      }
    }
    await session.delay(100);
  };
  const checkpoint = async label => {
    const frame = await observe(label, { spaces: [{ id: 'spaces_list' }],
      loading: [{ id: 'space_children_loading' }], leave: [{ id: 'leave_space_rooms' }],
      success: [{ id: 'leave_space_success' }] });
    const value = { state: observer.read(), frame }; record(label, value); trace(label, value); return value;
  };
  const invariant = (passed, observed) => {
    requireRuntime(spec.invariants.length === 1, 'Task09 canonical invariant shape changed');
    result.invariantChecks.push({ description: spec.invariants[0], passed: Boolean(passed), observed: clone(observed) });
  };
  const child = (state, id) => state.spaces.children.find(value => value.roomId === id);
  const membership = (state, id) => child(state, id)?.membership === 'none' ? null : child(state, id)?.membership;
  const joinAction = async (state, id) => {
    const row = child(state, id);
    if (row.joinState === 'success') {
      const suffix = id.replace(/[^A-Za-z0-9]/g, '_');
      for (let attempt = 0; attempt < 10; attempt++) {
        const frame = await observe('Task09.joinActionCommit', {
          joined: [{ id: 'space_child_joined_' + suffix }], join: [{ id: 'space_child_join_' + suffix }] });
        record('Task09.joinActionCommit', frame);
        if (frame.controls.joined.present === true && frame.controls.joined.visible === true &&
            frame.controls.join.present === false) return 'cleared';
        if (attempt === 9 && frame.controls.join.present === true && frame.controls.join.visible === true)
          return row.joinState; // Real stale rendered action is a semantic mismatch, not transport NS.
        await session.delay(50);
      }
      throw new Error('Task09 joined/action visibility unavailable after bounded render wait');
    }
    return row.joinState;
  };
  const selected = state => state.leave.rooms.filter(room => room.selected).map(room => room.roomId);
  const openLeave = async () => {
    await click({ id: 'space_leave_action' });
    return wait(state => state.leave && !state.leave.loading && state.leave.rooms.length > 0);
  };
  try {
    requireRuntime(preparedObserver, 'Task09 repository fixtures must be installed before original page launch');
    observer = preparedObserver;
    await wait(state => state.spaces && !state.spaces.loading && state.spaces.spaces.length > 0);
    await click({ id: 'home_spaces_tab' });
    if (spec.key === 'accept_invite') {
      await checkpoint('before:event');
      await click({ id: 'invite_accept__invited' });
      const state = await wait(value => value.calls.some(call => call.method === 'acceptInvite' && call.completed));
      await checkpoint('after:event');
      const joined = state.account.spaces.find(space => space.spaceId === '!invited');
      result.observed = { effect: state.calls.some(call => call.method === 'respondToInvite' && call.completed && !call.error) ? 'accept_invite' : null,
        membership: joined.joined ? 'joined' : null, seenInvites: state.account.seenSpaceIds };
      invariant(!state.account.invites.some(invite => invite.spaceId === '!invited') && joined.joined, state);
      return result;
    }
    await checkpoint(spec.key === 'open_space' ? 'before:event' : 'before:open-space');
    await click({ id: 'space_row__space' });
    if (spec.key === 'open_space') {
      const pending = await wait(state => state.spaces.childrenLoading);
      const frame = await checkpoint('after:event');
      result.observed = { surface: frame.frame.controls.spaces.visible && pending.spaces.selectedSpaceId ? 'space' : null,
        selectedSpaceId: pending.spaces.selectedSpaceId, childrenState: pending.spaces.childrenLoading ? 'loading' : 'idle' };
      observer.release();
      const settled = await wait(state => !state.spaces.childrenLoading);
      invariant(settled.spaces.selectedSpaceId === '!space', { pending, settled });
      return result;
    }
    await wait(state => !state.spaces.childrenLoading && state.spaces.children.length > 0);
    if (spec.key === 'paginate_children') {
      if (!observer.read().paginationEvents.length) {
        await checkpoint('before:event');
        await click({ id: 'space_load_more' });
      }
      const pending = await wait(value => value.paginationEvents.length > 0 && value.spaces.loadingMore);
      const before = pending.paginationEvents[0].before;
      requireRuntime(before.hasMoreChildren && !before.loadingMore &&
        JSON.stringify(before.children.map(value => value.roomId)) === JSON.stringify(spec.given.children),
        'Task09 actual pagination given was not established');
      record('Task09.actualPaginationDispatch', pending.paginationEvents[0]);
      trace('before:event', { productionStateBeforeDispatch: before });
      observer.release();
      const state = await wait(value => !value.spaces.loadingMore && !value.spaces.hasMoreChildren);
      await checkpoint('after:event'); const children = state.spaces.children.map(value => value.roomId);
      result.observed = { children, hasMoreToLoad: state.spaces.hasMoreChildren, paginationState: state.spaces.loadingMore ? 'loading' : 'idle' };
      invariant(JSON.stringify(children) === JSON.stringify(['!a', '!b', '!c']), state);
    } else if (['join_child_success', 'join_failure_retry'].includes(spec.key)) {
      if (spec.key === 'join_failure_retry') {
        observer.setJoinPermission(false); await click({ id: 'space_child_join__a' });
        await wait(state => child(state, '!a').joinState === 'failure');
        observer.setJoinPermission(true); await click({ id: 'space_child_join__b' });
        await wait(state => child(state, '!b').joinState === 'loading');
      }
      await checkpoint('before:event');
      // Both controls dispatch the same room join operation; the raw runtime
      // state and action-removal assertions, not the button label, decide it.
      await click(spec.key === 'join_failure_retry' ?
        [{ id: 'space_child_retry__a' }, { id: 'space_child_join__a' }] : { id: 'space_child_join__a' });
      const state = await wait(value => child(value, '!a').joinState !== 'loading');
      await checkpoint('after:event');
      result.observed = { memberships: { '!a': membership(state, '!a'), '!b': membership(state, '!b') },
        joinActions: { '!a': await joinAction(state, '!a') } };
      if (spec.key === 'join_failure_retry') {
        result.observed.joinActions['!b'] = await joinAction(state, '!b');
        result.observed.attempts = { '!a': state.attempts['!a'] };
        invariant(child(state, '!b').joinState === 'loading' && membership(state, '!b') === null, state);
      } else {
        result.observed.effect = state.calls.some(call => call.method === 'joinChildRoom' && call.completed && !call.error) ? 'join_room' : null;
        invariant(membership(state, '!b') === null, state);
      }
    } else {
      if (spec.key === 'leave_selected_rooms') {
        const state = observer.read().spaces;
        if (state.hasMoreChildren && !state.loadingMore) {
          try { await click({ id: 'space_load_more' }); }
          catch (error) {
            const current = observer.read().spaces;
            if (String(error.message || error) !== 'Original UI action target changed' ||
                current.hasMoreChildren && !current.loadingMore) throw error;
            record('Task09.setupPaginationAlreadyDispatched', observer.read().paginationEvents);
          }
        }
        await wait(state => !state.spaces.hasMoreChildren && !state.spaces.loadingMore);
      }
      await checkpoint('before:event'); let state = await openLeave();
      if (spec.key === 'default_leave_selection') {
        const frame = await checkpoint('after:event');
        const admin = await control({ id: 'leave_space_checkbox__admin' });
        result.observed = { visibleChildren: state.leave.rooms.map(room => room.roomId),
          selectedRoomIds: selected(state), disabledRoomIds: state.leave.rooms.filter(room => !room.eligible && room.isLastAdmin).map(room => room.roomId) };
        invariant(!state.leave.rooms.some(room => room.isDirect) && !selected(state).includes('!admin') && admin.enabled === false, frame);
      } else if (spec.key === 'bulk_and_toggle_selection') {
        await click({ id: 'leave_space_checkbox__b' });
        await checkpoint('before:event'); await click({ id: 'leave_space_deselect_all' });
        const afterDeselectAll = selected(observer.read());
        await click({ id: 'leave_space_select_all' }); const afterSelectAll = selected(observer.read());
        await click({ id: 'leave_space_checkbox__b' }); state = observer.read();
        const admin = await control({ id: 'leave_space_checkbox__admin' }); await checkpoint('after:event');
        result.observed = { afterDeselectAll, afterSelectAll, selectedRoomIds: selected(state), lastAdminSelected: selected(state).includes('!admin') };
        invariant(admin.enabled === false && !afterSelectAll.includes('!admin') && !selected(state).includes('!admin'), state);
      } else if (spec.key === 'leave_failure_retry') {
        await click({ id: 'leave_space_checkbox__b' }); await checkpoint('before:event');
        observer.setSyncReady(false); await click({ id: 'leave_space_confirm' });
        state = await wait(value => value.leave.leaveState === 'failure');
        const firstState = state.leave.leaveState, selectionAfterFailure = selected(state);
        observer.setSyncReady(true); await click([{ id: 'leave_space_retry' }, { id: 'leave_space_confirm' }]);
        state = await wait(value => value.leave.leaveState !== 'loading'); await checkpoint('after:event');
        result.observed = { firstState, selectionAfterFailure, finalState: state.leave.leaveState,
          attempts: state.calls.filter(call => call.method === 'leaveSpace').length };
        invariant(firstState === 'failure' && JSON.stringify(selectionAfterFailure) === '["!a"]', state);
      } else if (spec.key === 'leave_selected_rooms') {
        await click({ id: 'leave_space_deselect_all' }); await click({ id: 'leave_space_checkbox__a' });
        await click({ id: 'leave_space_checkbox__c' }); await checkpoint('before:event');
        await click({ id: 'leave_space_confirm' });
        state = await wait(value => value.leave.leaveState !== 'loading');
        const after = await checkpoint('after:event');
        const effect = state.calls.filter(call => call.method === 'leaveSpace' && call.completed && !call.error).slice(-1)[0];
        result.observed = { effect: effect ? 'leave_space' : null, payload: effect?.args[1],
          leaveState: state.leave.leaveState, surface: after.frame.routeName === config.entryRoute ? 'home' : 'leave' };
        invariant(JSON.stringify(effect?.args[1]) === '["!a","!c"]', state);
      } else throw new Error('Unsupported Task09 repository case: ' + spec.key);
    }
  } catch (error) {
    result.unsupported = String(error.message || error) + '\n' + String(error.stack || '');
  } finally {
    if (observer) { record('Task09.finalOriginalRepositoryState', observer.read()); observer.dispose(); }
    if (result.unsupported) result.unsupportedInvariants = spec.invariants.map(description => ({ description, reason: result.unsupported }));
  }
  return result;
}
