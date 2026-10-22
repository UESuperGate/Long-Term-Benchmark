// Read-only pass-through instrumentation of the original Task16 page objects.
export function observeTask16Page(namespace, binding) {
  const Presenter = namespace.IdentityResetPresenter;
  const Manager = namespace.IdentityResetFlowManager;
  const Service = namespace.DemoIdentityResetService;
  const PasswordHandle = namespace.DemoPasswordResetHandle;
  const OidcHandle = namespace.DemoOidcResetHandle;
  if (![Presenter, Manager, Service, PasswordHandle, OidcHandle].every(type => typeof type === 'function')) {
    throw new Error('Original identity reset classes unavailable');
  }

  const receivers = [], managers = [], services = [], handles = [], calls = [], restores = [];
  let disposed = false;
  const id = (list, object) => {
    if (!object) return null;
    if (!list.includes(object)) list.push(object);
    return list.indexOf(object) + 1;
  };
  const managerState = manager => ({
    managerId: id(managers, manager),
    handleState: manager.handleState,
    handleId: id(handles, manager.currentHandle),
    handleKind: manager.currentHandle?.kind,
    handleCancelled: manager.currentHandle?.cancelled,
    resetJobActive: manager.resetJobActive,
    completionWatcherActive: manager.completionWatcherActive,
    cleanupHistory: Array.isArray(manager.cleanupHistory) ? manager.cleanupHistory.slice() : [],
    serviceId: id(services, manager.service),
    authenticationType: manager.service?.authenticationType,
    serviceShouldFail: manager.service?.shouldFail
  });
  const state = presenter => ({
    ...managerState(presenter.manager),
    screen: presenter.screen,
    confirmationVisible: presenter.confirmationVisible,
    password: presenter.password,
    resetAction: presenter.resetAction,
    progressVisible: presenter.progressVisible,
    errorMessage: presenter.errorMessage,
    errorVisible: presenter.errorMessage?.length > 0,
    approvalUrl: presenter.approvalUrl,
    approvalSurface: presenter.approvalSurface,
    oidcOpenCount: presenter.oidcOpenCount,
    completionCount: presenter.completionCount,
    originalManager: Manager.prototype.isPrototypeOf(presenter.manager),
    originalService: Service.prototype.isPrototypeOf(presenter.manager.service),
    originalPasswordHandle: !!presenter.manager.currentHandle &&
      PasswordHandle.prototype.isPrototypeOf(presenter.manager.currentHandle),
    originalOidcHandle: !!presenter.manager.currentHandle &&
      OidcHandle.prototype.isPrototypeOf(presenter.manager.currentHandle)
  });

  function wrap(type, method, list, owner, snapshot) {
    const descriptor = Object.getOwnPropertyDescriptor(type.prototype, method);
    if (!descriptor || !descriptor.configurable || typeof descriptor.value !== 'function') {
      throw new Error('Original method unavailable: ' + owner + '.' + method);
    }
    Object.defineProperty(type.prototype, method, { ...descriptor, value: function(...args) {
      const call = {
        sequence: calls.length + 1,
        owner,
        method,
        instanceId: id(list, this),
        args: args.slice(),
        before: snapshot(this),
        returned: false
      };
      calls.push(call);
      try {
        const result = descriptor.value.apply(this, args);
        call.returned = true;
        call.afterSynchronousReturn = snapshot(this);
        return result;
      } catch (error) {
        call.thrown = String(error);
        throw error;
      }
    } });
    restores.push(() => Object.defineProperty(type.prototype, method, descriptor));
  }

  try {
    for (const method of ['continue', 'dismissConfirmation', 'confirmReset', 'setPassword',
      'submitPassword', 'sessionVerified', 'cancel', 'oidcReturned', 'dispose', 'cleanup']) {
      wrap(Presenter, method, receivers, 'presenter', state);
    }
    for (const method of ['getResetHandle', 'acquireResetHandle', 'cleanupAfterFailure',
      'cancel', 'updateHandleState']) {
      wrap(Manager, method, managers, 'manager', managerState);
    }
    wrap(Service, 'startIdentityReset', services, 'service', service => ({
      authenticationType: service.authenticationType,
      shouldFail: service.shouldFail
    }));
    for (const method of ['resetPassword', 'cancel']) {
      wrap(PasswordHandle, method, handles, 'password_handle', handle => ({
        kind: handle.kind,
        cancelled: handle.cancelled
      }));
    }
    for (const method of ['resetOidc', 'cancel']) {
      wrap(OidcHandle, method, handles, 'oidc_handle', handle => ({
        kind: handle.kind,
        url: handle.url,
        cancelled: handle.cancelled
      }));
    }
  } catch (error) {
    for (const restore of restores.reverse()) restore();
    throw error;
  }

  const publicRead = () => {
    const common = {
      binding,
      instanceCount: receivers.length,
      calls: JSON.parse(JSON.stringify(calls)),
      handles: handles.map((handle, index) => ({
        handleId: index + 1,
        kind: handle.kind,
        url: handle.url,
        cancelled: handle.cancelled
      }))
    };
    if (disposed || receivers.length !== 1) return { ...common, available: false };
    const snapshot = state(receivers[0]);
    const transitions = calls.filter(call => call.owner === 'manager' && call.method === 'updateHandleState' &&
      typeof call.args[0] === 'string').map(call => call.args[0]);
    const initial = calls.find(call => call.owner === 'presenter')?.before?.handleState || snapshot.handleState;
    return {
      ...common,
      ...snapshot,
      stateSequence: [initial, ...transitions],
      instanceId: 1,
      available: snapshot.originalManager && snapshot.originalService
    };
  };

  return {
    read: publicRead,
    configureServiceFailure(value) {
      if (receivers.length !== 1) throw new Error('Original presenter receiver unavailable');
      receivers[0].manager.service.shouldFail = value;
    },
    async invokePresenter(method) {
      if (receivers.length !== 1 || typeof receivers[0][method] !== 'function') {
        throw new Error('Original presenter API unavailable: ' + method);
      }
      return receivers[0][method]();
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      for (const restore of restores.reverse()) restore();
    }
  };
}
