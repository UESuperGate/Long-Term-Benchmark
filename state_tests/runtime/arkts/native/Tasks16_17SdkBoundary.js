// Evaluator-owned external SDK inputs only. Never constructs a feature owner.
export function createIdentitySdkControl() {
  const calls = [], requests = [], passwords = [], oidc = [], verified = new Set(), handles = [];
  const pending = (kind, list, details = {}) => {
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    const record = { sequence: calls.length + 1, kind, ...details, delivered: false };
    calls.push(record);
    list.push({ record, resolve, reject });
    return promise;
  };
  const port = {
    startIdentityReset() { return pending('start_identity_reset', requests); },
    subscribeVerification(listener) {
      verified.add(listener);
      calls.push({ sequence: calls.length + 1, kind: 'subscribe_verification' });
      listener(false);
      return () => {
        verified.delete(listener);
        calls.push({ sequence: calls.length + 1, kind: 'unsubscribe_verification' });
      };
    }
  };
  const deliver = (list, index, value, error) => {
    const item = list[index];
    if (!item || item.record.delivered) throw new Error('External request missing/already delivered');
    item.record.delivered = true;
    item.record.deliverySequence = calls.length + 1;
    calls.push({ sequence: calls.length + 1, kind: error ? 'external_rejection' : 'external_response',
      requestSequence: item.record.sequence });
    if (error) item.reject(new Error(error));
    else item.resolve(value);
  };
  const handle = kind => {
    const handleOrdinal = handles.length + 1;
    let passwordIndex, oidcIndex;
    const raw = {
      kind, url: 'https://id.example/reset',
      resetPassword(password) {
        passwordIndex = passwords.length;
        return pending('reset_password', passwords, { password, handleOrdinal });
      },
      resetOidc() {
        oidcIndex = oidc.length;
        return pending('reset_oidc', oidc, { handleOrdinal });
      },
      async cancel() {
        calls.push({ sequence: calls.length + 1, kind: 'cancel_reset_handle', handleOrdinal });
        for (const [list, index] of [[passwords, passwordIndex], [oidc, oidcIndex]]) {
          if (index !== undefined && !list[index].record.delivered) {
            list[index].record.cancelled = true;
            deliver(list, index, undefined, 'External SDK operation cancelled');
          }
        }
      },
      destroy() { calls.push({ sequence: calls.length + 1, kind: 'destroy_reset_handle', handleOrdinal }); }
    };
    handles.push(raw);
    return raw;
  };
  return { port, calls, requests, passwords, oidc, handles,
    deliverHandle(index, kind) { const raw = kind === undefined ? undefined : handle(kind); deliver(requests, index, raw); return raw; },
    failStart(index) { deliver(requests, index, undefined, 'Controlled external SDK start error'); },
    passwordResult(index, failed = false) { deliver(passwords, index, undefined, failed ? 'Controlled external SDK password error' : undefined); },
    oidcResult(index) { deliver(oidc, index); },
    verification(value) {
      calls.push({ sequence: calls.length + 1, kind: 'verification_status', verified: value, subscriberCount: verified.size });
      for (const listener of [...verified]) listener(value);
    }
  };
}

export function createPinnedSdkControl() {
  const calls = [], itemListeners = new Set(), syncListeners = new Set();
  let allowed = false, opening, failUnpin = false, items = [], roomItems = [];
  const timeline = {
    subscribeItems(listener) {
      itemListeners.add(listener);
      calls.push({ sequence: calls.length + 1, kind: 'subscribe_timeline_items' });
      return () => itemListeners.delete(listener);
    },
    async unpinEvent(eventId) {
      const call = { sequence: calls.length + 1, kind: 'unpin_event', eventId, failed: failUnpin, completed: false };
      calls.push(call);
      call.completed = true;
      if (failUnpin) throw new Error('Controlled external unpin failure');
      call.returned = true;
      return true;
    },
    close() { calls.push({ sequence: calls.length + 1, kind: 'close_timeline' }); }
  };
  const port = {
    roomId: '!runtime:test',
    pinnedEventsTimeline() {
      if (opening) throw new Error('Only one outstanding external open permitted');
      const call = { sequence: calls.length + 1, kind: 'open_pinned_timeline', delivered: false };
      calls.push(call);
      return new Promise((resolve, reject) => { opening = { resolve, reject, call }; });
    },
    async canPinUnpin() {
      calls.push({ sequence: calls.length + 1, kind: 'can_pin_unpin', allowed });
      return allowed;
    },
    subscribeSync(listener) { syncListeners.add(listener); return () => syncListeners.delete(listener); },
    async loadTimeline(focusedEventId) {
      calls.push({ sequence: calls.length + 1, kind: 'room_timeline', focusedEventId,
        eventIds: roomItems.map(item => item.eventId) });
      return roomItems.map(item => ({ ...item }));
    }
  };
  const rows = ids => ids.map(eventId => ({ eventId, sender: 'SDK', body: eventId === '$a' ? 'Alpha' : 'Beta' }));
  return { port, calls,
    prepareRoom(ids) { roomItems = [{ eventId: '$parent', sender: 'SDK', body: 'Parent room event' }, ...rows(ids)]; },
    permission(value) {
      allowed = value;
      calls.push({ sequence: calls.length + 1, kind: 'room_sync_permission', allowed });
      for (const listener of [...syncListeners]) listener();
    },
    openResult(failed = false) {
      if (!opening) throw new Error('No actual SDK open request');
      const request = opening; opening = undefined; request.call.delivered = true;
      calls.push({ sequence: calls.length + 1, kind: 'external_open_result', failed });
      if (failed) request.reject(new Error('Controlled external timeline failure'));
      else request.resolve(timeline);
    },
    emitItems(ids) {
      if (!itemListeners.size) throw new Error('No production subscription consumes SDK items');
      items = rows(ids);
      calls.push({ sequence: calls.length + 1, kind: 'sdk_timeline_items', eventIds: ids.slice() });
      for (const listener of [...itemListeners]) listener(items.map(item => ({ ...item })));
    },
    setUnpinFailure(value) { failUnpin = value; },
    read() { return { calls: calls.map(call => ({ ...call })), itemSubscriberCount: itemListeners.size,
      syncSubscriberCount: syncListeners.size, pinnedEventIds: items.map(item => item.eventId) }; }
  };
}

// Pass-through observation only: returns original methods/promises, never writes
// a feature field, supplies a handle or calls a feature event.
export function observePageOwner(types, taskId, sdkPort, sdkHandles = [], hooks = {}) {
  const owners = [], calls = [], restores = [], ids = new Map(), managerTransitions = [];
  const managerInvocations = [], activeInvocations = [];
  let invocationSequence = 0;
  const identity = value => {
    if (value === undefined || value === null) return null;
    if (!ids.has(value)) ids.set(value, ids.size + 1);
    return ids.get(value);
  };
  const presenterType = taskId === '16_identity_reset' ? types.IdentityResetPresenter : types.PinnedMessagesListPresenter;
  if (taskId === '16_identity_reset') {
    const target = types.IdentityResetFlowManager.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(target, 'updateHandleState');
    if (!descriptor?.configurable || typeof descriptor.value !== 'function') throw new Error('Manager observation unavailable');
    Object.defineProperty(target, 'updateHandleState', { ...descriptor, value: function(value) {
      managerTransitions.push({ managerId: identity(this), from: this.handleState, to: value });
      return descriptor.value.call(this, value);
    } });
    restores.push(() => Object.defineProperty(target, 'updateHandleState', descriptor));
    if (hooks.capture) {
      const method = Object.getOwnPropertyDescriptor(target, 'getResetHandle');
      if (!method?.configurable || typeof method.value !== 'function') throw new Error('Original manager invocation unavailable');
      const wrapped = function(...args) {
        const call = { invocationId: ++invocationSequence, method: 'getResetHandle',
          parentInvocationId: activeInvocations[activeInvocations.length - 1] || null,
          scope: hooks.scope(), managerId: identity(this), serviceId: identity(this.service),
          originalMethodId: identity(method.value), publicMethodId: identity(wrapped),
          sdkPortId: identity(this.service.port), stateAtEntry: this.handleState,
          pendingAtEntryId: identity(this.pendingHandle), handleAtEntryId: identity(this.currentHandle),
          stack: String(new Error('original manager invocation').stack), settled: false };
        managerInvocations.push(call);
        hooks.capture({ kind: 'manager', method: 'getResetHandle', receiver: this, publicMethod: wrapped });
        const returned = method.value.apply(this, args);
        call.returnOperationId = identity(returned);
        call.pendingAfterReturnId = identity(this.pendingHandle);
        call.stateAfterReturn = this.handleState;
        if (returned?.then) returned.then(value => {
          call.settled = true; call.settlementSequence = ++invocationSequence;
          call.returnedHandleId = identity(value); call.returnedSdkHandleId = identity(value?.sdkHandle);
        }, error => { call.settled = true; call.error = String(error); });
        return returned;
      };
      Object.defineProperty(target, 'getResetHandle', { ...method, value: wrapped });
      restores.push(() => Object.defineProperty(target, 'getResetHandle', method));
    }
  }
  const snapshot = owner => taskId === '16_identity_reset' ? {
    ownerId: identity(owner), managerId: identity(owner.manager),
    serviceId: identity(owner.manager.service), sdkPortId: identity(owner.manager.service.port),
    sdkPortMatches: owner.manager.service.port === sdkPort,
    serviceAvailable: owner.manager.service.available, disposed: owner.disposed,
    handleId: identity(owner.manager.currentHandle), sdkHandleId: identity(owner.manager.currentHandle?.sdkHandle),
    sdkHandleMatches: sdkHandles.includes(owner.manager.currentHandle?.sdkHandle),
    sdkHandleOrdinal: sdkHandles.indexOf(owner.manager.currentHandle?.sdkHandle) + 1,
    handleKind: owner.manager.currentHandle?.kind, handleState: owner.manager.handleState,
    confirmationVisible: owner.confirmationVisible, screen: owner.screen, password: owner.password,
    resetAction: owner.resetAction, progressVisible: owner.progressVisible, errorMessage: owner.errorMessage,
    approvalUrl: owner.approvalUrl, approvalSurface: owner.approvalSurface,
    completionCount: owner.completionCount, resetJobActive: owner.manager.resetJobActive,
    parentNavigationId: identity(owner.navigation), parentCompletionCount: owner.navigation.completionCount,
    parentCompleted: owner.navigation.completed,
    completionWatcherActive: owner.manager.completionWatcherActive, cleanupHistory: owner.manager.cleanupHistory.slice()
  } : {
    ownerId: identity(owner), repositoryId: identity(owner.repository), parentTimelineId: identity(owner.parent),
    providerId: identity(owner.provider), providerRepositoryMatches: owner.provider.repository === owner.repository,
    roomServiceId: identity(owner.repository.room), sdkPortId: identity(owner.repository.room?.port),
    sdkPortMatches: owner.repository.room?.port === sdkPort && owner.parent.room === owner.repository.room,
    serviceAvailable: owner.repository.room !== undefined, disposed: owner.disposed,
    activeTimelineId: identity(owner.repository.timeline), listState: owner.listState,
    eventIds: owner.pinnedMessages.map(item => item.eventId), canPinUnpin: owner.canPinUnpin,
    errorMessage: owner.errorMessage, retryEnabled: owner.retryEnabled,
    parentEventIds: owner.parent.items.map(item => item.eventId), focusedEventId: owner.parent.focusedEventId,
    focusedIndex: owner.parent.focusedIndex
  };
  for (const method of Object.getOwnPropertyNames(presenterType.prototype)) {
    const descriptor = Object.getOwnPropertyDescriptor(presenterType.prototype, method);
    if (method === 'constructor' || typeof descriptor?.value !== 'function' || !descriptor.configurable) continue;
    const original = descriptor.value;
    const wrapped = function(...args) {
      if (!owners.includes(this)) owners.push(this);
      const call = { sequence: calls.length + 1, invocationId: ++invocationSequence,
        originalMethodId: identity(original), publicMethodId: identity(wrapped),
        scope: hooks.scope ? hooks.scope() : 'runtime', method, before: snapshot(this),
        stack: String(new Error('original owner observation').stack) };
      calls.push(call);
      if (hooks.capture) hooks.capture({ kind: 'presenter', method, receiver: this, publicMethod: wrapped });
      activeInvocations.push(call.invocationId);
      let returned;
      try { returned = original.apply(this, args); }
      finally { activeInvocations.pop(); }
      call.afterReturn = snapshot(this);
      if (returned?.then) returned.then(() => { call.afterSettlement = snapshot(this); },
        error => { call.error = String(error); call.afterSettlement = snapshot(this); });
      return returned;
    };
    Object.defineProperty(presenterType.prototype, method, { ...descriptor, value: wrapped });
    restores.push(() => Object.defineProperty(presenterType.prototype, method, descriptor));
  }
  return {
    read() { return { ownerCount: owners.length, current: owners.length ? snapshot(owners[owners.length - 1]) : null,
      owners: owners.map(snapshot), managerTransitions: managerTransitions.map(item => ({ ...item })),
      managerInvocations: JSON.parse(JSON.stringify(managerInvocations)),
      calls: JSON.parse(JSON.stringify(calls)) }; },
    dispose() { for (const restore of restores.reverse()) restore(); }
  };
}
