const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));

function room(namespace, roomId, membership = '', direct = false, lastAdmin = false) {
  return new namespace.SpaceRoom(roomId, roomId, membership, direct, lastAdmin);
}

export function installTask09Input(namespace, role, spec, emit) {
  const Presenter = role === 'base' ? namespace.HomeRoomsPresenter : namespace.SpacesPresenter;
  if (!Presenter?.prototype) throw new Error('Original Task09 presenter export unavailable');
  const methods = role === 'base' ? ['openChats', 'openSpaces', 'openRoom'] : [
    'openSpace', 'loadMore', 'joinChild', 'clearJoinFailures', 'acceptInvite', 'openLeaveSpace',
    'deselectAllRooms', 'selectAllRooms', 'toggleRoomSelection', 'leaveSpace', 'closeLeaveError'
  ];
  const restores = [], receivers = [], calls = [], childRequests = [], joinRequests = [];
  const attempts = {}, heldChildren = [], heldJoins = [];
  let active, disposed = false;
  const id = value => { if (!receivers.includes(value)) receivers.push(value); return receivers.indexOf(value) + 1; };
  const record = (method, data = {}) => emit({ method: 'Task09.' + method, ...clone(data) });
  const childFixture = cursor => {
    const key = spec.key;
    if (key === 'default_leave_selection') return { children: [
      room(namespace, '!normal'), room(namespace, '!admin', 'joined', false, true),
      room(namespace, '!dm', 'joined', true, false)
    ], nextCursor: undefined };
    if (cursor !== undefined) return { children: [room(namespace, '!b'), room(namespace, '!c')], nextCursor: undefined };
    const nextCursor = ['paginate_children', 'leave_selected_rooms'].includes(key) ? 'next' : undefined;
    const children = [room(namespace, '!a'), room(namespace, '!b')];
    if (key === 'bulk_and_toggle_selection') children.push(room(namespace, '!admin', 'joined', false, true));
    return { children, nextCursor };
  };
  const installExternalSources = presenter => {
    if (role === 'base' || presenter.gateway.__task09StrictSources) return;
    presenter.gateway.__task09StrictSources = true;
    presenter.gateway.childrenSource = { loadChildren(spaceId, cursor) {
      const request = { id: childRequests.length + 1, spaceId, cursor, settled: false };
      childRequests.push(request); record('externalChildrenRequested', request);
      if (spec.key === 'open_space' && cursor === undefined) return new Promise(resolve => {
        request.resolve = resolve; heldChildren.push(request);
      });
      request.settled = true;
      const page = childFixture(cursor);
      request.response = clone(page); record('externalChildrenResolved', request);
      return Promise.resolve(page);
    } };
    presenter.gateway.joinSource = { joinRoom(roomId) {
      const request = { id: joinRequests.length + 1, roomId, settled: false };
      joinRequests.push(request); record('externalJoinRequested', request);
      if (spec.key === 'join_failure_retry' && roomId === '!b') return new Promise(resolve => {
        request.resolve = resolve; heldJoins.push(request);
      });
      request.settled = true; request.response = true; record('externalJoinResolved', request);
      return Promise.resolve(true);
    } };
  };
  try {
    for (const method of methods) {
      const descriptor = Object.getOwnPropertyDescriptor(Presenter.prototype, method);
      if (!descriptor || typeof descriptor.value !== 'function' || descriptor.configurable !== true)
        throw new Error('Original Task09 method unavailable: ' + method);
      Object.defineProperty(Presenter.prototype, method, { ...descriptor, value: function(...args) {
        active = this; installExternalSources(this);
        if (method === 'joinChild') attempts[args[0]] = (attempts[args[0]] || 0) + 1;
        const call = { method, receiverId: id(this), args: clone(args), completed: false };
        calls.push(call); record('originalCall', call);
        try {
          const value = descriptor.value.apply(this, args);
          if (value && typeof value.then === 'function') value.then(result => {
            call.completed = true; call.result = clone(result); record('originalReturn', call);
          }, error => { call.completed = true; call.error = String(error); record('originalThrow', call); });
          else { call.completed = true; call.result = clone(value); record('originalReturn', call); }
          return value;
        } catch (error) { call.completed = true; call.error = String(error); record('originalThrow', call); throw error; }
      } });
      restores.push(() => Object.defineProperty(Presenter.prototype, method, descriptor));
    }
  } catch (error) { restores.reverse().forEach(restore => restore()); throw error; }
  const read = () => {
    if (!active) return { available: false, role, instanceCount: receivers.length };
    if (role === 'base') return { available: true, role, instanceId: id(active), instanceCount: receivers.length,
      surface: active.surface, selectedRoomId: active.selectedRoomId, calls: clone(calls) };
    return { available: true, role, instanceId: id(active), instanceCount: receivers.length,
      surface: active.surface, selectedSpaceId: active.selectedSpaceId, childrenState: active.childrenState,
      paginationState: active.paginationState, hasMoreToLoad: active.hasMoreToLoad,
      children: clone(active.children), joinActions: clone(active.joinActions), invites: clone(active.invites),
      spaces: clone(active.spaces), seenInviteIds: clone(active.seenInviteIds),
      selectedLeaveRoomIds: clone(active.selectedLeaveRoomIds), leaveState: active.leaveState,
      leaveAttempts: active.leaveAttempts, gateway: clone({ lastJoinedRoomId: active.gateway.lastJoinedRoomId,
        lastAcceptedInviteId: active.gateway.lastAcceptedInviteId, lastLeftRoomIds: active.gateway.lastLeftRoomIds }),
      attempts: clone(attempts), calls: clone(calls), childRequests: clone(childRequests), joinRequests: clone(joinRequests) };
  };
  return {
    read,
    releaseChildren() {
      const request = heldChildren.find(item => !item.settled);
      if (!request) throw new Error('No held Task09 children response');
      request.settled = true; request.response = clone(childFixture(request.cursor));
      record('externalChildrenResolved', request); request.resolve(childFixture(request.cursor));
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      for (const request of heldChildren) if (!request.settled) { request.settled = true; request.resolve(childFixture(request.cursor)); }
      for (const request of heldJoins) if (!request.settled) { request.settled = true; request.resolve(false); }
      restores.reverse().forEach(restore => restore());
      record('inputObserverDisposed', { restoredDescriptors: restores.length });
    }
  };
}
