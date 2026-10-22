// Configure ONLY the existing original gateway's declared result flags.
// All business methods below are pass-through instrumentation, never replacements.
export function observeTask12Partial(namespace, binding) {
  const Presenter = namespace.ReportRoomPresenter, Service = namespace.ReportRoomService, Gateway = namespace.ReportRoomGateway;
  if (![Presenter, Service, Gateway].every(type => typeof type === 'function')) throw new Error('Original report classes unavailable');
  const presenters = [], services = [], gateways = [], calls = [], serviceCalls = [], gatewayCalls = [], restores = [], fixtures = [];
  let disposed = false;
  const id = (list, value) => { if (!list.includes(value)) list.push(value); return list.indexOf(value) + 1; };
  const snapshot = presenter => {
    const service = presenter.service, gateway = service && service.gateway;
    return { reason: presenter.reason, leaveRoom: presenter.leaveRoom, reportAction: presenter.reportAction,
      serviceId: service && id(services, service), gatewayId: gateway && id(gateways, gateway),
      originalService: !!service && Service.prototype.isPrototypeOf(service),
      originalGateway: !!gateway && Gateway.prototype.isPrototypeOf(gateway),
      roomExists: gateway && gateway.roomExists, reportShouldFail: gateway && gateway.reportShouldFail,
      leaveShouldFail: gateway && gateway.leaveShouldFail, reportCalls: gateway && gateway.reportCalls,
      leaveCalls: gateway && gateway.leaveCalls, lastReportReason: gateway && gateway.lastReportReason,
      effects: gateway && Array.isArray(gateway.effects) ? gateway.effects.slice() : undefined };
  };
  const wrap = (proto, method, receivers, target, presenter) => {
    const descriptor = Object.getOwnPropertyDescriptor(proto, method);
    if (!descriptor || typeof descriptor.value !== 'function' || !descriptor.configurable) throw new Error('Original method binding unavailable: ' + method);
    Object.defineProperty(proto, method, { ...descriptor, value: function(...args) {
      const call = { instanceId: id(receivers, this), method, args: args.slice(), returned: false, sequence: target.length + 1 };
      if (presenter) call.before = snapshot(this);
      target.push(call);
      const result = descriptor.value.apply(this, args);
      call.returned = true;
      if (typeof result === 'boolean' || typeof result === 'string') call.result = result;
      if (presenter) call.after = snapshot(this);
      return result;
    } });
    restores.push(() => Object.defineProperty(proto, method, descriptor));
  };
  try {
    for (const method of ['updateReason', 'toggleLeaveRoom', 'submit', 'retry']) wrap(Presenter.prototype, method, presenters, calls, true);
    wrap(Service.prototype, 'execute', services, serviceCalls, false);
    for (const method of ['reportRoom', 'leaveRoom']) wrap(Gateway.prototype, method, gateways, gatewayCalls, false);
  } catch (error) { for (const restore of restores.reverse()) restore(); throw error; }
  const read = () => {
    const common = { binding, instanceCount: presenters.length, calls: calls.map(c => ({ ...c })),
      serviceCalls: serviceCalls.map(c => ({ ...c })), gatewayCalls: gatewayCalls.map(c => ({ ...c })), fixtures: fixtures.slice() };
    if (disposed || presenters.length !== 1) return { ...common, available: false, reason: 'Exactly one live original page receiver required' };
    const state = snapshot(presenters[0]);
    return { ...common, ...state, instanceId: 1, available: state.originalService && state.originalGateway &&
      typeof state.reason === 'string' && typeof state.leaveRoom === 'boolean' && typeof state.reportAction === 'string' &&
      typeof state.reportShouldFail === 'boolean' && typeof state.leaveShouldFail === 'boolean' && state.roomExists === true &&
      Number.isInteger(state.reportCalls) && Number.isInteger(state.leaveCalls) && Array.isArray(state.effects) };
  };
  return { read,
    configureResults(reportResult, leaveResult, phase) {
      const before = read();
      if (!before.available || !['success', 'failure'].includes(reportResult) || !['success', 'failure'].includes(leaveResult)) {
        throw new Error('Original same-page gateway cannot establish requested outcomes');
      }
      if (!['canonical_given', 'invariant_retry_recovery'].includes(phase)) throw new Error('Unknown boundary fixture phase');
      const gateway = presenters[0].service.gateway;
      for (const name of ['reportShouldFail', 'leaveShouldFail']) {
        const d = Object.getOwnPropertyDescriptor(gateway, name);
        if (!d || !d.writable || typeof d.value !== 'boolean') throw new Error('Original gateway outcome is not a writable own data field: ' + name);
      }
      gateway.reportShouldFail = reportResult === 'failure';
      gateway.leaveShouldFail = leaveResult === 'failure';
      const after = snapshot(presenters[0]);
      fixtures.push({ phase, mechanism: 'configure_existing_original_gateway_boolean_fields', before: {
        reportShouldFail: before.reportShouldFail, leaveShouldFail: before.leaveShouldFail,
        reportCalls: before.reportCalls, leaveCalls: before.leaveCalls, reportAction: before.reportAction },
        after, reportResult, leaveResult });
      return read();
    },
    dispose() { if (disposed) return; disposed = true; for (const restore of restores.reverse()) restore(); }
  };
}
