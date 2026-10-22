// Evaluator-only read instrumentation. Import the SAME production class as the
// candidate page, install before mounting it, and dispose after unmounting it.
// Calls, receiver, return value (including Promise identity) and throws are
// preserved. No room, gateway or presenter state is assigned here.
let configuredPresenter;

export function configureRoomObserver(Presenter) { configuredPresenter = Presenter; }

export function installConfiguredRoomObserver() { return installRoomObserver(configuredPresenter); }

export function installRoomObserver(Presenter) {
  const prototype = Presenter && Presenter.prototype;
  if (!prototype) throw new Error('Candidate room presenter export is unavailable');
  const restores = [];
  const instances = [];
  const stateOwners = [];
  const gateways = [];
  const calls = [];
  const retainedRooms = new Map();
  let active;
  let reading = false;
  const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
  function remember(receiver, method) {
    if (reading) return;
    active = receiver;
    if (!instances.includes(receiver)) instances.push(receiver);
    calls.push({ instanceId: instances.indexOf(receiver) + 1, method });
  }
  for (const name of Object.getOwnPropertyNames(prototype)) {
    if (name === 'constructor') continue;
    const descriptor = Object.getOwnPropertyDescriptor(prototype, name);
    if (!descriptor.configurable) continue;
    const replacement = { ...descriptor };
    if (typeof descriptor.value === 'function') {
      replacement.value = function(...args) {
        remember(this, name);
        return descriptor.value.apply(this, args);
      };
    } else if (typeof descriptor.get === 'function') {
      replacement.get = function() {
        remember(this, name);
        return descriptor.get.call(this);
      };
    } else continue;
    Object.defineProperty(prototype, name, replacement);
    restores.push(() => Object.defineProperty(prototype, name, descriptor));
  }
  return {
    read() {
      if (!active) return { available: false, reason: 'No original candidate presenter call has executed since observer installation.' };
      reading = true;
      try {
        const p = active;
        const owner = p.store || p;
        if (!stateOwners.includes(owner)) stateOwners.push(owner);
        if (!gateways.includes(p.gateway)) gateways.push(p.gateway);
        const current = typeof p.currentRoom === 'function' ? p.currentRoom() : p.currentRoom || p.room;
        for (const room of [current, p.oldRoom, p.replacementRoom]) {
          if (room && room.roomId) retainedRooms.set(room.roomId, room);
        }
        const rooms = [];
        for (const [roomId, reference] of retainedRooms) {
          const room = p.store && typeof p.store.getRoom === 'function' ? p.store.getRoom(roomId) : reference;
          if (!room) continue;
          rooms.push({ roomId, history: clone(room.history || (room === p.room ? p.history : undefined)),
            predecessorRoom: clone(room.predecessorRoom || room.predecessor || null),
            successorRoom: clone(room.successorRoom || room.successor || null) });
        }
        return { available: true, instanceId: instances.indexOf(p) + 1,
          stateOwnerId: stateOwners.indexOf(owner) + 1, gatewayId: gateways.indexOf(p.gateway) + 1,
          currentRoomId: current && current.roomId, navigationState: p.navigationState,
          rooms, navigationCount: p.gateway && p.gateway.navigationCount,
          lastOpenedRoomId: p.gateway && p.gateway.lastOpenedRoomId, calls: clone(calls) };
      } finally { reading = false; }
    },
    dispose() { for (const restore of restores.reverse()) restore(); }
  };
}
