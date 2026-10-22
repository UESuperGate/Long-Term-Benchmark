// Evaluator instrumentation only. Receivers must come from original page calls.
const copy = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));

export function installTask14Observer(namespace, record = () => {}) {
  const Presenter = namespace.JoinRoomByAddressPresenter;
  if (typeof Presenter !== 'function' || !Presenter.prototype) throw new Error('Original JoinRoomByAddressPresenter unavailable');
  const restores = [];
  const receivers = [];
  const calls = [];
  const projections = new Map();
  let active;
  let disposed = false;
  const descriptors = Object.getOwnPropertyDescriptors(Presenter.prototype);
  const wrappedNames = [];
  for (const [name, descriptor] of Object.entries(descriptors)) {
    if (name === 'constructor' || !descriptor.configurable) continue;
    const original = typeof descriptor.value === 'function' ? descriptor.value : descriptor.get;
    if (typeof original !== 'function') continue;
    const invoke = function(...args) {
      active = this;
      if (!receivers.includes(this)) receivers.push(this);
      const call = { instanceId: receivers.indexOf(this) + 1, method: name, args: copy(args.map(value =>
        typeof value === 'function' ? '[callback]' : value)) };
      calls.push(call);
      record({ method: 'Task14.originalPresenterCall', available: true, call });
      try {
        const returned = original.apply(this, args);
        // Retain only naturally executed projections; read() never calls one.
        if (name === 'visibleAddressState') projections.set(this, returned);
        return returned;
      } catch (error) { call.error = String(error); throw error; }
    };
    Object.defineProperty(Presenter.prototype, name, typeof descriptor.value === 'function' ?
      { ...descriptor, value: invoke } : { ...descriptor, get: invoke });
    restores.push(() => Object.defineProperty(Presenter.prototype, name, descriptor));
    wrappedNames.push(name);
  }
  if (!wrappedNames.length) throw new Error('Original presenter has no instrumentable members');
  const pending = [];
  const navigation = [];
  const boundNavigators = new Set();
  const bindNavigator = nav => {
    if (!nav || Number.isFinite(nav.openRoomCount) || boundNavigators.has(nav)) return;
    boundNavigators.add(nav);
    for (const name of ['openRoom', 'back']) {
      if (typeof nav[name] !== 'function') throw new Error('Original navigation port is unbound: ' + name);
      const own = Object.getOwnPropertyDescriptor(nav, name);
      const original = nav[name];
      Object.defineProperty(nav, name, { configurable: true, writable: true, value: function(...args) {
        navigation.push({ receiver: this, method: name, args: copy(args) });
        record({ method: 'Task14.originalNavigationRequested', available: true, name, args: copy(args) });
        return original.apply(this, args);
      } });
      restores.push(() => own ? Object.defineProperty(nav, name, own) : delete nav[name]);
    }
  };
  let resolverBinding;
  const stateName = value => value === 'not_found' ? 'room_not_found' : value;
  return {
    binding: { namespaceExports: Object.keys(namespace), wrappedNames,
      descriptors: Object.fromEntries(Object.entries(descriptors).map(([name, d]) => [name,
        { configurable: d.configurable, enumerable: d.enumerable, writable: d.writable,
          valueType: typeof d.value, getter: typeof d.get === 'function' }])) },
    read() {
      if (!active) return { available: false, reason: 'No original page presenter call has executed since binding' };
      const nav = active.navigator;
      bindNavigator(nav);
      const state = active.addressState ?? active.state;
      return copy({ available: true, instanceId: receivers.indexOf(active) + 1, instanceCount: receivers.length,
        address: active.address, addressState: stateName(state),
        internalAddressState: stateName(active.internalAddressState ?? state),
        visibleAddressState: stateName(projections.get(active)), validationRequested: active.validationRequested,
        closed: active.closed ?? active.dismissed,
        addressFlowVisible: nav?.addressFlowVisible ??
          (typeof active.dismissed === 'boolean' && typeof active.joined === 'boolean' ? !active.dismissed && !active.joined : undefined),
        navigationCount: nav?.openRoomCount ?? navigation.filter(call => call.receiver === nav && call.method === 'openRoom').length,
        pendingNavigation: active.pendingNavigation, calls,
        resolverRequests: pending.map(request => ({ id: request.id, alias: request.alias, settled: request.settled,
          samePageResolver: request.receiver === (active.resolver ?? active.gateway) })) });
    },
    bindExternalResolver(resolverNamespace) {
      if (resolverBinding) throw new Error('Resolver boundary already bound');
      const Class = resolverNamespace.SessionRoomAliasResolver || resolverNamespace.DemoRoomAliasResolver ||
        resolverNamespace.HttpRoomAliasResolver || resolverNamespace.DemoRoomGateway;
      if (typeof Class !== 'function') throw new Error('Original page external resolver export unavailable');
      const method = ['resolveRoomAlias', 'resolve'].find(name => typeof Class.prototype[name] === 'function');
      const descriptor = method && Object.getOwnPropertyDescriptor(Class.prototype, method);
      if (!descriptor?.configurable) throw new Error('External resolver boundary is not configurable');
      Object.defineProperty(Class.prototype, method, { ...descriptor, value: function(alias) {
        const request = { id: pending.length + 1, alias, receiver: this, settled: false };
        const promise = new Promise((resolve, reject) => { request.resolve = resolve; request.reject = reject; });
        pending.push(request);
        record({ method: 'Task14.externalResolverRequested', available: true, requestId: request.id, alias,
          boundary: Class.name + '.' + method, originalDirectoryIOExecuted: false });
        return promise;
      } });
      restores.push(() => Object.defineProperty(Class.prototype, method, descriptor));
      resolverBinding = { className: Class.name, method };
      return copy(resolverBinding);
    },
    settle(requestId) {
      const request = pending.find(item => item.id === requestId);
      if (!request || request.settled || !active || request.receiver !== (active.resolver ?? active.gateway))
        throw new Error('Pending request is not owned by the original page presenter');
      request.settled = true;
      record({ method: 'Task14.externalResolverRejected', available: true, requestId, alias: request.alias });
      request.reject(new Error('Evaluator external directory lookup failed'));
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      // Complete external work before restoring wrappers; no presenter reset.
      for (const request of pending) if (!request.settled) {
        request.settled = true;
        request.reject(new Error('Evaluator external directory fixture disposed'));
      }
      for (const restore of restores.reverse()) restore();
    }
  };
}
