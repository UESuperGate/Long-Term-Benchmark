// Read-only observation plus a controllable external room-info boundary.
// Production methods and page receivers remain the owners of every state change.
export function installTask11Input(namespace, apiVariant, response, emit) {
  const Presenter = apiVariant === 'base' ? namespace.RoomPresenter : namespace.RoomUpgradePresenter;
  const Gateway = apiVariant === 'base' ? namespace.RoomGateway : namespace.RoomNavigationGateway;
  if (!Presenter?.prototype || !Gateway?.prototype) throw new Error('Original Task11 exports unavailable for ' + apiVariant);
  const presenterMethods = apiVariant === 'base' ? ['observeRoomInfo', 'selectRoom', 'openRoom', 'sendMessage',
    'openSuccessorRoom', 'openPredecessorRoom'] :
    ['observeTimelineRoomInfo', 'selectRoom', 'selectOldRoom', 'selectReplacementRoom',
      'openSuccessorRoom', 'openPredecessorRoom', 'navigateToRoom'];
  const gatewayMethods = apiVariant === 'base' ? ['requestRoomInfo', 'openRoom'] : ['requestRoomInfo', 'navigateToRoom'];
  const restores = [], receivers = [], gateways = [], calls = [], requests = [];
  let active, responseMode = 'original', automaticResponse, disposed = false;
  const copy = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
  const id = (items, value) => { if (!items.includes(value)) items.push(value); return items.indexOf(value) + 1; };
  const record = (method, data) => emit({ method: 'Task11.' + method, ...copy(data) });
  const roomValue = presenter => apiVariant === 'base' ? presenter.room : presenter.currentRoom;
  const roomsValue = presenter => {
    if (apiVariant !== 'base') return [presenter.oldRoom, presenter.replacementRoom];
    if (typeof presenter.gateway.roomSummaries !== 'function') return [presenter.room];
    const cached = presenter.gateway.roomSummaries();
    if (!Array.isArray(cached)) throw new Error('Original roomSummaries observation is not an array');
    // Overlay the actual displayed receiver's value, not a synthesized room.
    return [...cached.filter(room => room.roomId !== presenter.room.roomId), presenter.room];
  };
  const state = () => {
    if (!active) return { available: false, reason: 'No original page receiver observed' };
    const room = roomValue(active);
    const navigationCalls = calls.filter(call => call.owner === 'gateway' &&
      ['openRoom', 'navigateToRoom'].includes(call.method) && call.completed);
    const successfulNavigation = navigationCalls.filter(call => call.result === true);
    const lastNavigation = navigationCalls[navigationCalls.length - 1];
    const navigationState = typeof active.navigationState === 'string' ? active.navigationState :
      active.navigationError || active.gateway.lastOpenFailed === true || lastNavigation?.result === false ? 'failure' :
        lastNavigation?.result === true && room?.roomId === active.gateway.lastOpenedRoomId ? 'success' : 'idle';
    return {
      available: true,
      apiVariant,
      instanceId: id(receivers, active),
      instanceCount: receivers.length,
      gatewayId: id(gateways, active.gateway),
      room: copy(room),
      history: copy(apiVariant === 'base' ? active.history : room?.history),
      currentRoomId: room?.roomId,
      rooms: copy(roomsValue(active)),
      navigationState,
      navigationCount: typeof active.gateway.navigationCount === 'number' ? active.gateway.navigationCount : successfulNavigation.length,
      lastOpenedRoomId: active.gateway.lastOpenedRoomId,
      navigationObservation: { explicitPresenterState: active.navigationState,
        gatewayLastOpenFailed: active.gateway.lastOpenFailed, presenterNavigationError: active.navigationError,
        originalGatewayReturn: copy(lastNavigation), successfulOriginalGatewayCallCount: successfulNavigation.length },
      calls: copy(calls),
      requests: requests.map(({ resolve, ...request }) => copy(request))
    };
  };
  const wrap = (owner, method, ownerName) => {
    const descriptor = Object.getOwnPropertyDescriptor(owner.prototype, method);
    if (!descriptor || typeof descriptor.value !== 'function' || descriptor.configurable !== true) return;
    Object.defineProperty(owner.prototype, method, { ...descriptor, value: function(...args) {
      if (ownerName === 'presenter') active = this;
      const receiver = ownerName === 'presenter' ? this : active;
      const gateway = ownerName === 'gateway' ? this : this.gateway;
      const call = { owner: ownerName, method, instanceId: receiver ? id(receivers, receiver) : undefined,
        gatewayId: gateway ? id(gateways, gateway) : undefined, args: copy(args), completed: false };
      calls.push(call); record('originalCall', call);
      try {
        const result = descriptor.value.apply(this, args);
        if (result && typeof result.then === 'function') result.then(value => {
          call.completed = true; call.result = copy(value); record('originalReturn', call);
        }, error => { call.completed = true; call.error = String(error); record('originalThrow', call); });
        else { call.completed = true; call.result = copy(result); record('originalReturn', call); }
        return result;
      } catch (error) { call.completed = true; call.error = String(error); record('originalThrow', call); throw error; }
    } });
    restores.push(() => Object.defineProperty(owner.prototype, method, descriptor));
  };
  try {
    presenterMethods.forEach(method => wrap(Presenter, method, 'presenter'));
    gatewayMethods.filter(method => method !== 'requestRoomInfo').forEach(method => wrap(Gateway, method, 'gateway'));
    const descriptor = Object.getOwnPropertyDescriptor(Gateway.prototype, 'requestRoomInfo');
    if (!descriptor || typeof descriptor.value !== 'function' || descriptor.configurable !== true)
      throw new Error('Original room-info boundary unavailable');
    Object.defineProperty(Gateway.prototype, 'requestRoomInfo', { ...descriptor, value: function(roomId) {
      if (disposed || responseMode === 'original' || roomId !== response.roomId) return descriptor.value.call(this, roomId);
      const request = { id: requests.length + 1, roomId, gatewayId: id(gateways, this), settled: false };
      requests.push(request); record('externalRoomInfoRequested', request);
      const pending = new Promise(resolve => { request.resolve = resolve; });
      if (responseMode === 'automatic') {
        request.settled = true; request.response = copy(automaticResponse);
        record('externalRoomInfoResolved', { id: request.id, roomId, gatewayId: request.gatewayId,
          response: request.response, deliveryMode: 'available_external_response' });
        request.resolve(copy(automaticResponse));
      }
      return pending;
    } });
    restores.push(() => Object.defineProperty(Gateway.prototype, 'requestRoomInfo', descriptor));
  } catch (error) { restores.reverse().forEach(restore => restore()); throw error; }
  return {
    read: state,
    enableHold() { responseMode = 'hold'; record('externalRoomInfoHoldEnabled', { roomId: response.roomId }); },
    setAvailableResponse(value) {
      if (value?.roomId !== response.roomId) throw new Error('External response room identity changed');
      automaticResponse = copy(value); responseMode = 'automatic';
      record('externalRoomInfoAvailable', { response: automaticResponse,
        scope: 'Only external SDK input; original presenter and original page still own state/rendering' });
    },
    releaseResponse(requestId) {
      const request = requests.find(item => item.id === requestId);
      if (disposed || !request || request.settled) throw new Error('One live original room-info request is required');
      request.settled = true;
      request.response = copy(response);
      record('externalRoomInfoResolved', { id: request.id, roomId: request.roomId,
        gatewayId: request.gatewayId, response: request.response });
      request.resolve(copy(response));
    },
    invoke(method, ...args) {
      if (!active || !presenterMethods.includes(method) || typeof active[method] !== 'function')
        throw new Error('Original page presenter method unavailable: ' + method);
      return active[method](...args);
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      for (const request of requests) if (!request.settled) {
        request.settled = true; request.cancelledByEvaluatorCleanup = true; request.resolve(undefined);
      }
      restores.reverse().forEach(restore => restore());
      record('inputObserverDisposed', { restoredDescriptors: restores.length });
    }
  };
}
