// Transparent observation of the configured Task14 chain. The Addon method
// always calls its original N-API/Rust/Matrix SDK implementation. Controlled
// outcomes are released only by the external evaluator HTTPS provider.
let configuredRoomsNamespace;
let nativeBridgeNamespace;
const receiverIds = new WeakMap();
let nextReceiverId = 0;
const idFor = value => {
  if (!receiverIds.has(value)) receiverIds.set(value, ++nextReceiverId);
  return receiverIds.get(value);
};
const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));

export function configureTask14ConfiguredNamespacesV7(roomsNamespace, bridgeNamespace) {
  if (configuredRoomsNamespace || nativeBridgeNamespace) throw Error('Configured namespaces are single-use');
  if (typeof roomsNamespace?.ConfiguredSessionRooms !== 'function' ||
      typeof bridgeNamespace?.AddonNativeMatrixBridge !== 'function')
    throw Error('Configured room/native bridge namespaces unavailable');
  configuredRoomsNamespace = roomsNamespace;
  nativeBridgeNamespace = bridgeNamespace;
}

export function installTask14JoinOwnerV7(presenterNamespace, providerControl, record = () => {}) {
  const Presenter = presenterNamespace.JoinRoomByAddressPresenter;
  if (typeof Presenter !== 'function' || typeof providerControl !== 'function')
    throw Error('Original presenter or provider control unavailable');
  const presenterProto = Presenter.prototype;
  const presenters = [], presenterCalls = [], resolverCalls = [], roomCalls = [], nativeCalls = [],
    navigation = [], restores = [], wrappedResolvers = new WeakSet(), navigators = new Set();
  const resolverStack = [], roomStack = [];
  let active, projection, bound = false, disposed = false;
  const ownResolver = receiver => !!active && active.resolver === receiver;
  const ownRooms = receiver => !!active && active.resolver?.rooms === receiver;
  const ownNative = receiver => ownRooms(active.resolver.rooms) && active.resolver.rooms.bridge === receiver;

  const bindResolver = resolver => {
    if (!bound || !resolver || wrappedResolvers.has(resolver)) return;
    const proto = Object.getPrototypeOf(resolver);
    const descriptor = Object.getOwnPropertyDescriptor(proto, 'resolveRoomAlias');
    if (!descriptor?.configurable || typeof descriptor.value !== 'function' || !resolver.rooms)
      throw Error('Unknown configured page resolver shape; NS');
    Object.defineProperty(proto, 'resolveRoomAlias', { ...descriptor, value: function(alias) {
      const call = { id: resolverCalls.length + 1, receiver: this, roomsReceiver: this.rooms,
        alias, calledOriginal: false, returned: false };
      resolverCalls.push(call);
      if (!ownResolver(this)) throw Error('Configured resolver is not the actual page owner resolver');
      call.calledOriginal = true; resolverStack.push(call);
      let result;
      try { result = descriptor.value.call(this, alias); call.returned = true; }
      catch (error) { call.settlement = 'threw'; call.error = String(error); throw error; }
      finally { resolverStack.pop(); }
      record({ method: 'Task14.configuredPageResolverEnteredV7', id: call.id, alias, calledOriginal: true });
      if (result?.then) result.then(value => { call.settlement = 'fulfilled'; call.value = clone(value); },
        error => { call.settlement = 'rejected'; call.error = String(error); });
      return result;
    }});
    restores.push(() => Object.defineProperty(proto, 'resolveRoomAlias', descriptor));
    wrappedResolvers.add(resolver);
  };

  for (const name of Object.getOwnPropertyNames(presenterProto)) {
    const descriptor = Object.getOwnPropertyDescriptor(presenterProto, name);
    if (name === 'constructor' || !descriptor.configurable) continue;
    const original = typeof descriptor.value === 'function' ? descriptor.value : descriptor.get;
    if (typeof original !== 'function') continue;
    const invoke = function(...args) {
      active = this;
      if (!presenters.includes(this)) presenters.push(this);
      bindResolver(this.resolver);
      const call = { sequence: presenterCalls.length + 1, instanceId: presenters.indexOf(this) + 1,
        nativeReceiverId: idFor(this), method: name, stack: String(new Error().stack),
        args: clone(args.map(value => typeof value === 'function' ? '[callback]' : value)) };
      presenterCalls.push(call); record({ method: 'Task14.originalPresenterCall', call });
      try { const result = original.apply(this, args); call.returned = true; if (name === 'visibleAddressState') projection = result; return result; }
      catch (error) { call.error = String(error); throw error; }
    };
    Object.defineProperty(presenterProto, name, typeof descriptor.value === 'function' ?
      { ...descriptor, value: invoke } : { ...descriptor, get: invoke });
    restores.push(() => Object.defineProperty(presenterProto, name, descriptor));
  }

  const bindNavigator = navigator => {
    if (!navigator || navigators.has(navigator)) return;
    navigators.add(navigator);
    for (const name of ['openRoom', 'back', 'dismissJoinRoomByAddress', 'dismiss']) {
      if (typeof navigator[name] !== 'function') continue;
      const own = Object.getOwnPropertyDescriptor(navigator, name);
      const original = navigator[name];
      Object.defineProperty(navigator, name, { configurable: true, writable: true, value: function(...args) {
        navigation.push({ receiver: this, method: name, args: clone(args), stack: String(new Error().stack) });
        return original.apply(this, args);
      }});
      restores.push(() => own ? Object.defineProperty(navigator, name, own) : delete navigator[name]);
    }
  };

  const publicState = value => value === 'not_found' ? 'room_not_found' : value;
  const requestRows = () => nativeCalls.map(call => ({ id: call.id, alias: call.alias,
    settled: call.settlement === 'fulfilled' || call.settlement === 'rejected',
    samePageResolver: ownNative(call.receiver), nativeCallId: call.id,
    externalLeaf: 'matrix_sdk::Client.resolve_room_alias' }));

  return {
    read() {
      if (!active) return { available: false, reason: 'No actual original page receiver observed' };
      bindResolver(active.resolver); bindNavigator(active.navigator);
      return clone({ available: true, instanceId: presenters.indexOf(active) + 1,
        nativeReceiverId: idFor(active), instanceCount: presenters.length,
        boundaryProtocol: 'task14.configured-native-sdk-provider.v7', address: active.address,
        addressState: publicState(active.addressState ?? active.state),
        internalAddressState: publicState(active.internalAddressState ?? active.addressState ?? active.state),
        visibleAddressState: publicState(projection), validationRequested: active.validationRequested,
        resolvedRoom: active.resolvedRoom, addressFlowVisible: active.navigator?.addressVisible ?? active.navigator?.addressFlowVisible,
        closed: active.closed ?? active.dismissed,
        navigationCount: navigation.filter(call => call.receiver === active.navigator && call.method === 'openRoom').length,
        pendingNavigation: active.pendingNavigation, calls: presenterCalls,
        navigationCalls: navigation.filter(call => call.receiver === active.navigator).map(({ method, args, stack }) => ({ method, args, stack })),
        resolverRequests: requestRows(),
        originalBridgeCalls: resolverCalls.map(call => ({ id: call.id, alias: call.alias,
          calledOriginal: call.calledOriginal, returned: call.returned, settlement: call.settlement,
          value: call.value, error: call.error, receiverIsPageResolver: ownResolver(call.receiver),
          roomsIsPageFoundation: ownRooms(call.roomsReceiver) })),
        configuredRoomCalls: roomCalls.map(call => ({ id: call.id, resolverCallId: call.resolverCallId,
          alias: call.alias, calledOriginal: call.calledOriginal, returned: call.returned,
          settlement: call.settlement, value: call.value, error: call.error,
          receiverIsPageRooms: ownRooms(call.receiver), nativeBridgeIsPageBridge: ownNative(call.bridgeReceiver) })),
        nativeBridgeCalls: nativeCalls.map(call => ({ id: call.id, roomCallId: call.roomCallId,
          alias: call.alias, handle: call.handle, calledOriginal: call.calledOriginal,
          returned: call.returned, settlement: call.settlement, value: call.value, error: call.error,
          receiverIsPageBridge: ownNative(call.receiver) })) });
    },
    bindExternalResolver() {
      if (bound || !configuredRoomsNamespace || !nativeBridgeNamespace)
        throw Error('Reviewed configured namespaces missing');
      const Rooms = configuredRoomsNamespace.ConfiguredSessionRooms;
      const Bridge = nativeBridgeNamespace.AddonNativeMatrixBridge;
      const roomsDescriptor = Object.getOwnPropertyDescriptor(Rooms.prototype, 'resolveRoomAlias');
      const nativeDescriptor = Object.getOwnPropertyDescriptor(Bridge.prototype, 'resolveRoomAlias');
      if (!roomsDescriptor?.configurable || typeof roomsDescriptor.value !== 'function' ||
          !nativeDescriptor?.configurable || typeof nativeDescriptor.value !== 'function')
        throw Error('Unknown configured/native bridge shape; NS');
      Object.defineProperty(Rooms.prototype, 'resolveRoomAlias', { ...roomsDescriptor, value: function(alias) {
        const parent = resolverStack.at(-1);
        const call = { id: roomCalls.length + 1, resolverCallId: parent?.id, receiver: this,
          bridgeReceiver: this.bridge, alias, calledOriginal: false, returned: false };
        roomCalls.push(call);
        if (!parent || parent.receiver !== active?.resolver || parent.roomsReceiver !== this || !ownRooms(this))
          throw Error('Configured rooms call did not originate from the actual page resolver');
        call.calledOriginal = true; roomStack.push(call);
        let result;
        try { result = roomsDescriptor.value.call(this, alias); call.returned = true; }
        catch (error) { call.settlement = 'threw'; call.error = String(error); throw error; }
        finally { roomStack.pop(); }
        record({ method: 'Task14.configuredRoomsEnteredV7', id: call.id,
          resolverCallId: call.resolverCallId, alias, calledOriginal: true });
        if (result?.then) result.then(value => { call.settlement = 'fulfilled'; call.value = clone(value); },
          error => { call.settlement = 'rejected'; call.error = String(error); });
        return result;
      }});
      restores.push(() => Object.defineProperty(Rooms.prototype, 'resolveRoomAlias', roomsDescriptor));
      Object.defineProperty(Bridge.prototype, 'resolveRoomAlias', { ...nativeDescriptor, value: function(handle, alias) {
        const parent = roomStack.at(-1);
        const call = { id: nativeCalls.length + 1, roomCallId: parent?.id, receiver: this,
          handle, alias, calledOriginal: false, returned: false };
        nativeCalls.push(call);
        if (!parent || parent.receiver !== active?.resolver?.rooms || parent.bridgeReceiver !== this || !ownNative(this))
          throw Error('Native bridge call did not originate from actual configured rooms');
        call.calledOriginal = true;
        let result;
        try { result = nativeDescriptor.value.call(this, handle, alias); call.returned = true; }
        catch (error) { call.settlement = 'threw'; call.error = String(error); throw error; }
        record({ method: 'Task14.originalNativeBridgeEnteredV7', id: call.id,
          roomCallId: call.roomCallId, handle, alias, calledOriginal: true });
        if (result?.then) result.then(value => { call.settlement = 'fulfilled'; call.value = clone(value); },
          error => { call.settlement = 'rejected'; call.error = String(error); });
        return result;
      }});
      restores.push(() => Object.defineProperty(Bridge.prototype, 'resolveRoomAlias', nativeDescriptor));
      bound = true;
      return { protocol: 'task14.configured-native-sdk-provider.v7',
        pageResolver: 'ConfiguredRoomAliasResolver.resolveRoomAlias',
        applicationBridge: 'ConfiguredSessionRooms.resolveRoomAlias',
        nativeBridge: 'AddonNativeMatrixBridge.resolveRoomAlias',
        nativeBridgeMode: 'pass_through_original', externalLeaf: 'matrix_sdk::Client.resolve_room_alias' };
    },
    async resolveExternal(id, response) {
      const call = nativeCalls.find(item => item.id === id);
      if (!call || call.settlement || !ownNative(call.receiver)) throw Error('Unknown own pending SDK request');
      const receipt = await providerControl('release', { requestId: id, alias: call.alias,
        expectedOutcome: 'success', expectedRoomId: response?.roomId,
        expectedServers: response?.servers || [] });
      record({ method: 'Task14.externalResolverResolved', requestId: id, alias: call.alias,
        response: clone(response), providerReceipt: clone(receipt), samePageResolver: true,
        externalLeaf: 'matrix_sdk::Client.resolve_room_alias' });
      return receipt;
    },
    async settle(id) {
      const call = nativeCalls.find(item => item.id === id);
      if (!call || call.settlement || !ownNative(call.receiver)) throw Error('Unknown own pending SDK request');
      const receipt = await providerControl('release', { requestId: id, alias: call.alias,
        expectedOutcome: 'not_found' });
      record({ method: 'Task14.externalResolverRejectedV7', requestId: id, alias: call.alias,
        providerReceipt: clone(receipt), samePageResolver: true,
        externalLeaf: 'matrix_sdk::Client.resolve_room_alias' });
      return receipt;
    },
    async providerStatus() { return providerControl('status', {}); },
    dispose() {
      if (disposed) return; disposed = true;
      for (const restore of restores.reverse()) restore();
    }
  };
}

export const installTask14JoinOwnerV3 = installTask14JoinOwnerV7;
export const installTask14Observer = installTask14JoinOwnerV7;
