// Pass-through instrumentation on the postloaded original app classes only.
export function observeTask15Page(namespace, binding) {
  const Presenter = namespace.AccountDeactivationPresenter;
  const Service = namespace.AccountClient || namespace.DemoAccountService;
  const productionClient = typeof namespace.AccountClient === 'function';
  if (typeof Presenter !== 'function' || typeof Service !== 'function') throw new Error('Original presenter/service exports unavailable');
  const receivers = [], services = [], calls = [], serviceCalls = [], renderCalls = [], restore = [];
  const submitName = typeof Presenter.prototype.submitEnabled === 'function' ? 'submitEnabled' : 'canSubmit';
  const submitDescriptor = Object.getOwnPropertyDescriptor(Presenter.prototype, submitName);
  let disposed = false;
  const id = (list, receiver) => {
    if (!list.includes(receiver)) list.push(receiver);
    return list.indexOf(receiver) + 1;
  };
  function fields(receiver) {
    const service = receiver.service ?? receiver.client;
    const serviceId = service && id(services, service);
    return { password: receiver.password, eraseData: receiver.eraseData,
      action: namespace.DEACTIVATION_SUCCEEDED !== undefined && receiver.action === namespace.DEACTIVATION_SUCCEEDED ? 'success' : receiver.action,
      rawAction: receiver.action,
      requestCount: productionClient ? serviceCalls.filter(call => call.instanceId === serviceId).length : service && service.requestCount,
      requestCountOrigin: productionClient ? 'pass_through_since_observer_install' : 'legacy_demo_counter',
      accountSessionActive: productionClient ? !!service && service.userId().length > 0 : undefined,
      serviceId,
      originalService: !!service && Service.prototype.isPrototypeOf(service) };
  }
  function wrap(prototype, name, records, list, presenter) {
    const descriptor = Object.getOwnPropertyDescriptor(prototype, name);
    if (!descriptor || !descriptor.configurable || typeof descriptor.value !== 'function') throw new Error('Original observation method unavailable: ' + name);
    Object.defineProperty(prototype, name, { ...descriptor, value: function(...args) {
      const call = { instanceId: id(list, this), method: name, args: args.slice(), sequence: records.length + 1, returned: false };
      records.push(call);
      if (presenter) call.before = fields(this);
      // Preserve synchronous throws and exact Promise identity. "returned" is
      // not an assertion that an async method has settled.
      const result = descriptor.value.apply(this, args);
      call.returned = true;
      if (!presenter && result && typeof result.then === 'function') {
        result.then(() => { call.settlement = { status: 'fulfilled' }; }, error => {
          call.settlement = { status: 'rejected', name: error && error.name,
            message: error && error.message ? error.message : String(error), code: error && error.code };
        });
      }
      if (name === submitName) call.value = result;
      if (presenter) call.after = fields(this);
      return result;
    } });
    restore.push(() => Object.defineProperty(prototype, name, descriptor));
  }
  try {
    for (const name of ['setPassword', 'setEraseData', 'deactivateAccount']) wrap(Presenter.prototype, name, calls, receivers, true);
    wrap(Service.prototype, 'deactivateAccount', serviceCalls, services, false);
    if (submitDescriptor && typeof submitDescriptor.value === 'function') wrap(Presenter.prototype, submitName, renderCalls, receivers, true);
  } catch (error) {
    for (const undo of restore.reverse()) undo();
    throw error;
  }
  return {
    read() {
      const base = { binding, instanceCount: receivers.length,
        calls: calls.map(call => ({ ...call })), serviceCalls: serviceCalls.map(call => ({ ...call })),
        renderCalls: renderCalls.map(call => ({ ...call })) };
      if (disposed || receivers.length !== 1) return { ...base, available: false, reason: 'Exactly one live original page receiver required' };
      const state = fields(receivers[0]);
      // Diagnostic read of the ORIGINAL pure method, not an enabled UI flag.
      // Bypass our wrapper so this never pretends the page re-evaluated it.
      let submitEnabledRead;
      if (submitDescriptor && typeof submitDescriptor.value === 'function') {
        try {
          submitEnabledRead = { source: 'evaluator_read_original_submitEnabled', value: submitDescriptor.value.call(receivers[0]) };
        } catch (error) {
          submitEnabledRead = { source: 'evaluator_read_original_submitEnabled', error: String(error) };
        }
      }
      const available = state.originalService && typeof state.password === 'string' && typeof state.eraseData === 'boolean' &&
        typeof state.action === 'string' && Number.isInteger(state.requestCount) && state.requestCount >= 0;
      return { ...base, ...state, submitEnabledRead, available, instanceId: 1 };
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      for (const undo of restore.reverse()) undo();
    }
  };
}
