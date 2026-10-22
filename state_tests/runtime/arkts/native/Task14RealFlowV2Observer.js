// Transparent production-prototype tracing for Task14 real_flow_v2.
const clone = value => {
  if (value === undefined) return undefined;
  try { return JSON.parse(JSON.stringify(value)); }
  catch (_) { return String(value); }
};

export function installTask14RealFlowV2Observer(modules, record = () => {}) {
  const { chat, routes, runtime, joinObserver } = modules;
  const restores = [];
  const calls = [];
  const receivers = new WeakMap();
  let receiverSequence = 0;
  let sequence = 0;
  let disposed = false;

  const receiverId = value => {
    if (!receivers.has(value)) receivers.set(value, ++receiverSequence);
    return receivers.get(value);
  };
  const tags = (owner, value) => ({
    exportedStartChatPresenter: value === runtime.startChatPresenter,
    exportedStartDMService: value === runtime.startDMService,
    exportedRoomGateway: value === runtime.roomGateway,
    exportedChatNavigator: value === runtime.chatNavigator,
    navigatorRoutePort: owner === 'HarmonyRoutePort' && runtime.chatNavigator?.routes === value,
    ownsExportedGateway: value?.gateway === runtime.roomGateway,
    ownsExportedStartDM: value?.startDM === runtime.startDMService,
    ownsExportedNavigator: value?.navigator === runtime.chatNavigator
  });
  const state = (owner, value) => {
    if (owner === 'StartChatPresenter') return clone({ query: value.query, busy: value.busy, error: value.error });
    if (owner === 'CreateRoomPresenter') return clone({ name: value.name, topic: value.topic,
      memberIds: value.memberIds, busy: value.busy, error: value.error, createdRoomId: value.createdRoomId });
    if (owner === 'RoomPresenter') return clone({ room: value.room, busy: value.busy, error: value.error });
    return undefined;
  };
  const emit = event => {
    calls.push(event);
    record({ method: 'Task14.realFlowProductionCall', available: true, call: clone(event) });
  };
  const wrap = (Class, owner, method) => {
    const proto = Class?.prototype;
    const descriptor = proto && Object.getOwnPropertyDescriptor(proto, method);
    if (typeof descriptor?.value !== 'function' || descriptor.configurable !== true)
      throw new Error(owner + '.' + method + ' is not transparently instrumentable');
    const original = descriptor.value;
    Object.defineProperty(proto, method, { ...descriptor, value: function(...args) {
      const id = receiverId(this);
      const callId = ++sequence;
      const started = { sequence: callId, phase: 'call', owner, method, receiverId: id,
        receiverTags: tags(owner, this), args: clone(args), before: state(owner, this) };
      emit(started);
      let returned;
      try { returned = original.apply(this, args); }
      catch (error) {
        emit({ sequence: ++sequence, originSequence: callId, phase: 'throw', owner, method,
          receiverId: id, error: String(error), after: state(owner, this) });
        throw error;
      }
      if (returned && typeof returned.then === 'function') {
        returned.then(value => emit({ sequence: ++sequence, originSequence: callId, phase: 'fulfilled', owner, method,
          receiverId: id, value: clone(value), after: state(owner, this) }), error =>
          emit({ sequence: ++sequence, originSequence: callId, phase: 'rejected', owner, method,
            receiverId: id, error: String(error), after: state(owner, this) }));
      } else {
        emit({ sequence: ++sequence, originSequence: callId, phase: 'returned', owner, method,
          receiverId: id, value: clone(returned), after: state(owner, this) });
      }
      return returned;
    } });
    restores.push(() => Object.defineProperty(proto, method, descriptor));
  };

  [
    [chat.StartChatPresenter, 'StartChatPresenter', 'createRoom'],
    [chat.StartChatPresenter, 'StartChatPresenter', 'selectPerson'],
    [chat.StartDMService, 'StartDMService', 'execute'],
    [chat.DemoRoomGateway, 'DemoRoomGateway', 'findDirectRoom'],
    [chat.DemoRoomGateway, 'DemoRoomGateway', 'createDirectRoom'],
    [chat.DemoRoomGateway, 'DemoRoomGateway', 'createRoom'],
    [chat.DemoRoomGateway, 'DemoRoomGateway', 'getRoom'],
    [chat.CreateRoomPresenter, 'CreateRoomPresenter', 'submit'],
    [chat.RoomPresenter, 'RoomPresenter', 'load'],
    [routes.RouterChatNavigator, 'RouterChatNavigator', 'openCreateRoom'],
    [routes.RouterChatNavigator, 'RouterChatNavigator', 'openRoom'],
    [routes.RouterChatNavigator, 'RouterChatNavigator', 'back'],
    [runtime.HarmonyRoutePort, 'HarmonyRoutePort', 'push'],
    [runtime.HarmonyRoutePort, 'HarmonyRoutePort', 'replace'],
    [runtime.HarmonyRoutePort, 'HarmonyRoutePort', 'returnToStart']
  ].forEach(item => wrap(...item));

  const matching = (owner, method, after = 0) => calls.filter(call =>
    call.sequence > after && call.owner === owner && call.method === method);
  return {
    checkpoint: () => sequence,
    calls: () => clone(calls),
    join: joinObserver,
    matching,
    async waitFor(owner, method, after, phase = 'fulfilled', timeoutMs = 5000) {
      const deadline = Date.now() + timeoutMs;
      do {
        const found = matching(owner, method, after).find(call => call.phase === phase);
        if (found) return clone(found);
        const failed = matching(owner, method, after).find(call => ['throw', 'rejected'].includes(call.phase));
        if (failed) throw new Error(owner + '.' + method + ' failed: ' + failed.error);
        await new Promise(resolve => setTimeout(resolve, 25));
      } while (Date.now() < deadline);
      throw new Error('Timed out waiting for ' + owner + '.' + method + ' ' + phase);
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      joinObserver.dispose();
      for (const restore of restores.reverse()) restore();
    }
  };
}
