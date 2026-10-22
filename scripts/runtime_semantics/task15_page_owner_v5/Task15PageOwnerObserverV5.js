// Passive, postloaded ORIGINAL classes only. No constructor, setter or getter
// is invoked by read(). A real page lifecycle/render must reveal its receiver.
export const TASK15_PAGE_OWNER_PROTOCOL = 'task15.arkts.same-original-page-owner.v5';

export function observeTask15OriginalPageOwnerV5(namespace, binding, episodeId) {
  const Presenter = namespace.AccountDeactivationPresenter, Service = namespace.AccountClient;
  if (typeof Presenter !== 'function' || typeof Service !== 'function') throw Error('Original native classes unavailable');
  const receivers = [], services = [], calls = [], ownerCalls = [], serviceCalls = [], restores = [];
  const submit = typeof Presenter.prototype.submitEnabled === 'function' ? 'submitEnabled' : 'canSubmit';
  let disposed = false;
  const id = (values, receiver) => {
    if (!values.includes(receiver)) values.push(receiver);
    return values.indexOf(receiver) + 1;
  };
  const fields = receiver => {
    const service = receiver.service ?? receiver.client, serviceId = service ? id(services, service) : null;
    return { password: receiver.password, eraseData: receiver.eraseData,
      action: namespace.DEACTIVATION_SUCCEEDED !== undefined && receiver.action === namespace.DEACTIVATION_SUCCEEDED ? 'success' : receiver.action,
      rawAction: receiver.action, requestCount: serviceCalls.filter(call => call.instanceId === serviceId).length };
  };
  const wrap = (prototype, method, records, kind) => {
    const descriptor = Object.getOwnPropertyDescriptor(prototype, method);
    if (!descriptor?.configurable || typeof descriptor.value !== 'function') throw Error('Original method cannot be passively observed: ' + method);
    Object.defineProperty(prototype, method, { ...descriptor, value: function(...args) {
      const isService = kind === 'service';
      // Only production lifecycle/render calls acquire a page owner. A direct setter or
      // an evaluator read cannot manufacture this acquisition.
      if (kind === 'render' || kind === 'lifecycle') id(receivers, this);
      const instanceId = isService ? id(services, this) : receivers.indexOf(this) + 1;
      const call = { method, instanceId, sequence: records.length + 1, args: args.slice(),
        stack: String(new Error().stack), returned: false };
      if (!isService) call.before = fields(this);
      records.push(call);
      const result = descriptor.value.apply(this, args);
      call.returned = true;
      if (kind === 'render') call.diagnosticGetterValue = result;
      if (!isService) call.after = fields(this);
      if (isService && result && typeof result.then === 'function') {
        result.then(() => { call.settlement = { status: 'fulfilled' }; }, error => {
          call.settlement = { status: 'rejected', message: String(error) };
        });
      }
      return result;
    } });
    restores.push(() => Object.defineProperty(prototype, method, descriptor));
  };
  try {
    wrap(Presenter.prototype, submit, ownerCalls, 'render');
    for (const name of ['loadCapability', 'refreshAvailability']) {
      if (typeof Presenter.prototype[name] === 'function') wrap(Presenter.prototype, name, ownerCalls, 'lifecycle');
    }
    for (const name of ['setPassword', 'setEraseData', 'deactivateAccount', 'closeDialogs'])
      wrap(Presenter.prototype, name, calls, 'presenter');
    if (typeof Presenter.prototype.openForm === 'function') wrap(Presenter.prototype, 'openForm', calls, 'presenter');
    wrap(Service.prototype, 'deactivateAccount', serviceCalls, 'service');
  } catch (error) { for (const restore of restores.reverse()) restore(); throw error; }
  return {
    read() {
      const value = { protocol: TASK15_PAGE_OWNER_PROTOCOL, episodeId, binding,
        observerMode: 'pass_through_original_page_owner', readScope: 'original_receiver_fields_only',
        instanceCount: receivers.length, available: !disposed && receivers.length === 1,
        calls, ownerCalls, serviceCalls };
      if (value.available) {
        const receiver = receivers[0], service = receiver.service ?? receiver.client;
        Object.assign(value, { state: fields(receiver), instanceId: 1, serviceId: services.indexOf(service) + 1,
          originalService: !!service && Service.prototype.isPrototypeOf(service),
          acquisition: { kind: 'production_page_lifecycle_or_render', ownerCallSequence: ownerCalls.find(call => call.instanceId === 1).sequence } });
      }
      // Deep copy preserves the actual before-frame while async calls settle.
      return JSON.parse(JSON.stringify(value));
    },
    dispose() { if (disposed) return; disposed = true; for (const restore of restores.reverse()) restore(); }
  };
}
