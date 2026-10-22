// Controlled external SDK only. This file never constructs or mutates a presenter.
export function connectTask13ExternalSdk(namespace) {
  const service = namespace.getSessionVerificationService();
  const room = namespace.getRoomIdentityDataSource();
  const ledger = [], callbacks = [], listeners = [], verified = new Set();
  let eventSequence = 0;
  let pendingChallenge;
  const entry = (kind, extra = {}) => {
    const receipt = { sequence: ++eventSequence, kind, ...extra };
    ledger.push(receipt); return receipt;
  };
  const call = async (method, args) => {
    const receipt = entry('call', { method, args, completed: false });
    await Promise.resolve(); receipt.completed = true;
    entry('completion', { callSequence: receipt.sequence, method });
  };
  const port = {
    subscribeVerifiedStatus(listener) { listener('not_verified');
      entry('verified_status_subscribe'); return () => entry('verified_status_unsubscribe'); },
    subscribe(listener) {
      const receipt = entry('sdk_subscribe', { subscriptionId: eventSequence + 1 });
      callbacks.push(listener);
      return () => { const index = callbacks.indexOf(listener); if (index >= 0) callbacks.splice(index, 1);
        entry('sdk_unsubscribe', { subscriptionId: receipt.subscriptionId }); };
    },
    requestUserVerification(userId) { return call('requestUserVerification', [userId]); },
    requestCurrentSessionVerification() { return call('requestCurrentSessionVerification', []); },
    startVerification() { return call('startVerification', []); },
    approveVerification() { return call('approveVerification', []); },
    declineVerification() { return call('declineVerification', []); },
    cancelVerification() { return call('cancelVerification', []); },
    resetVerification(cancelPending) { return call('resetVerification', [cancelPending]); },
    setListener(listener) { entry('incoming_listener', { connected: typeof listener === 'function' }); },
    acknowledgeVerificationRequest(requestId) { return call('acknowledgeVerificationRequest', [requestId]); },
    acceptVerificationRequest() { return call('acceptVerificationRequest', []); },
    isVerified(userId) { entry('is_verified', { userId, value: verified.has(userId) }); return verified.has(userId); }
  };
  service.connect(port);
  room.connectEncryptionService({
    withdrawVerification(userId) { return call('withdrawVerification', [userId]); },
    pinUserIdentity(userId) { return call('pinUserIdentity', [userId]); }
  });
  room.receiveSession('@current:example.org', true);
  room.receiveRoomSync(true, [new namespace.RoomMember('@alice:example.org', 'Alice'),
    new namespace.RoomMember('@bob:example.org', 'Bob')]);
  function identities(alice) {
    entry('identity_input', { alice, bob: 'pinned' });
    room.receiveIdentityChanges([new namespace.IdentityChange('@alice:example.org', alice),
      new namespace.IdentityChange('@bob:example.org', namespace.IdentityState.Pinned)]);
  }
  identities(namespace.IdentityState.Unverified);
  const calls = [], presenters = [], restores = [];
  let currentOwner;
  const ids = new Map();
  const id = value => { if (!value) return null; if (!ids.has(value)) ids.set(value, ids.size + 1); return ids.get(value); };
  function state(presenter) {
    if (!presenter) return null;
    const count = method => ledger.filter(item => item.kind === 'call' && item.method === method).length;
    const requestCalls = ledger.filter(item => item.kind === 'call' && item.method === 'requestUserVerification');
    const resets = ledger.filter(item => item.kind === 'call' && item.method === 'resetVerification');
    return { presenterId: id(presenter), gatewayId: id(presenter.gateway), identityId: id(presenter.identityStore),
      serviceId: id(presenter.gateway.service), roomId: id(presenter.identityStore.room),
      sameService: presenter.gateway.service === service, sameRoom: presenter.identityStore.room === room && presenter.gateway.room === room,
      request: { type: presenter.request.type, userId: presenter.request.userId }, targetUserId: presenter.request.userId,
      step: presenter.step, replyState: presenter.replyState, sas: presenter.sas.slice(),
      identityState: presenter.identityStore.identityState, warningVisible: presenter.identityStore.warningVisible,
      requestCalls: count('requestUserVerification'), currentSessionCalls: count('requestCurrentSessionVerification'),
      startCalls: count('startVerification'), approveCalls: count('approveVerification'), declineCalls: count('declineVerification'),
      cancelCalls: count('cancelVerification'), resetCalls: resets.length,
      userId: requestCalls.length ? requestCalls[requestCalls.length - 1].args[0] : presenter.request.userId,
      cancelPending: resets.length ? resets[resets.length - 1].args[0] : null, error: presenter.error };
  }
  for (const method of ['attach', 'dispose', 'requestVerification', 'startSasVerification', 'acceptChallenge',
    'declineChallenge', 'cancel', 'reset', 'receiveServiceEvent']) {
    const proto = namespace.UserVerificationPresenter.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, method);
    if (!descriptor?.configurable || typeof descriptor.value !== 'function') throw Error('Original page owner method unavailable: ' + method);
    Object.defineProperty(proto, method, { ...descriptor, value: function(...args) {
      if (method === 'attach' && !presenters.includes(this)) presenters.push(this);
      const receipt = { method, sequence: calls.length + 1, presenterId: id(this),
        args: method === 'attach' ? ['production_render_subscription'] : args,
        before: state(this), completed: false };
      calls.push(receipt);
      const previous = currentOwner;
      currentOwner = this;
      let value;
      try { value = descriptor.value.apply(this, args); }
      finally { currentOwner = previous; }
      receipt.after = state(this); receipt.completed = true;
      if (value?.then) value.then(() => { receipt.asyncCompleted = true; receipt.after = state(this); },
        error => { receipt.rejected = String(error); });
      return value;
    } });
    restores.push(() => Object.defineProperty(proto, method, descriptor));
  }
  for (const method of ['requestUserVerification', 'requestCurrentSessionVerification', 'startVerification',
    'approveVerification', 'declineVerification', 'cancelVerification', 'resetVerification']) {
    const proto = namespace.VerificationGateway.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, method);
    if (!descriptor?.configurable || typeof descriptor.value !== 'function') throw Error('Original gateway method unavailable: ' + method);
    Object.defineProperty(proto, method, { ...descriptor, value: function(...args) {
      const receipt = { method, owner: 'gateway', sequence: calls.length + 1,
        gatewayId: id(this), serviceId: id(this.service), presenterId: id(currentOwner),
        sameGatewayReceiver: currentOwner?.gateway === this, sameService: this.service === service,
        args: args.slice(), completed: false };
      calls.push(receipt);
      const value = descriptor.value.apply(this, args); receipt.completed = true;
      if (value?.then) value.then(() => { receipt.asyncCompleted = true; }, error => { receipt.rejected = String(error); });
      return value;
    } });
    restores.push(() => Object.defineProperty(proto, method, descriptor));
  }
  const subscribe = service.subscribe;
  service.subscribe = function(listener) {
    const subscriptionId = listeners.length + 1;
    const subscriber = currentOwner;
    const receipt = entry('production_subscribe', { subscriptionId, presenterId: id(subscriber), serviceId: id(this) }); listeners.push(receipt);
    const unsubscribe = subscribe.call(this, event => {
      const callback = entry('production_callback', { subscriptionId, presenterId: id(subscriber), serviceId: id(this),
        event: { kind: event.kind, sas: event.sas.slice() }, before: state(subscriber) });
      listener(event); callback.after = state(subscriber);
    });
    return () => { entry('production_unsubscribe', { subscriptionId }); unsubscribe(); };
  };
  return {
    identities,
    queueChallenge(sas) {
      pendingChallenge = sas.slice();
      return entry('sdk_pending_data', { sas: pendingChallenge.slice() });
    },
    deliverChallenge() {
      if (!pendingChallenge) throw Error('No queued external SDK challenge');
      const sas = pendingChallenge; pendingChallenge = undefined;
      entry('sdk_event', { event: { kind: 'challenge', sas: sas.slice() }, subscribers: callbacks.length });
      callbacks.slice().forEach(listener => listener(new namespace.VerificationEvent('challenge', sas)));
    },
    emit(kind, sas = []) {
      entry('sdk_event', { event: { kind, sas: sas.slice() }, subscribers: callbacks.length });
      callbacks.slice().forEach(listener => listener(new namespace.VerificationEvent(kind, sas)));
    },
    setVerified(userId, value) { if (value) verified.add(userId); else verified.delete(userId);
      entry('sdk_verified_status', { userId, value }); },
    read() {
      return JSON.parse(JSON.stringify({ available: presenters.length === 1, instanceCount: presenters.length,
        state: presenters.length === 1 ? state(presenters[0]) : null,
        calls, ledger, serviceId: id(service), roomId: id(room),
        requestTypes: { user: namespace.VerificationRequestType.User, currentSession: namespace.VerificationRequestType.CurrentSession },
        sdkState: { encryptedRoom: room.isEncrypted, currentUserId: room.currentUserId,
          verificationAvailable: room.verificationAvailable,
          members: room.members.map(member => ({ userId: member.userId, displayName: member.displayName })),
          identities: room.identities.map(identity => ({ userId: identity.userId, identityState: identity.identityState })) } }));
    },
    dispose() { for (const restore of restores.reverse()) restore(); service.subscribe = subscribe;
      service.disconnect(); }
  };
}
