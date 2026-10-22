// A controlled SDK timer leaf, scoped only to naturally executed ORIGINAL page
// presenter methods/callbacks. UI, transport and all other SDK timers pass through.
export function installTask14OwnerClockV5(namespace, record) {
  const proto = namespace.JoinRoomByAddressPresenter?.prototype;
  const savedSet = globalThis.setTimeout, savedClear = globalThis.clearTimeout;
  if (!proto || typeof savedSet !== 'function' || typeof savedClear !== 'function') throw Error('Native timer leaf unavailable');
  const timers = [], calls = [], restores = [];
  let owner, depth = 0, now = 0, next = 1000000000, disposed = false;
  const scoped = (receiver, fn) => {
    if (owner && owner !== receiver) throw Error('Timer leaf crossed original page owners');
    owner = receiver; depth++;
    try { return fn(); } finally { depth--; }
  };
  const set = function(callback, delay, ...args) {
    if (!depth) return savedSet(callback, delay, ...args);
    if (typeof callback !== 'function' || !Number.isFinite(delay) || delay < 0) throw Error('Unknown original SDK timer request');
    const timer = { id: ++next, delay, due: now + delay, scheduledAt: now, owner, callback, args, cancelled: false, fired: false };
    timers.push(timer);
    const call = { method: 'setTimeout', id: timer.id, delay, at: now, stack: String(new Error().stack), sameOwner: true };
    calls.push(call); record({ method: 'Task14.ownedSdkTimerLeaf', call }); return timer.id;
  };
  const clear = function(id) {
    const timer = timers.find(item => item.id === id);
    if (!timer) return savedClear(id);
    timer.cancelled = true; calls.push({ method: 'clearTimeout', id, at: now, sameOwner: true });
  };
  try {
    globalThis.setTimeout = set; globalThis.clearTimeout = clear;
    if (globalThis.setTimeout !== set || globalThis.clearTimeout !== clear) throw Error('Original module timer leaf cannot be scoped');
    for (const name of Object.getOwnPropertyNames(proto)) {
      const descriptor = Object.getOwnPropertyDescriptor(proto, name);
      if (name === 'constructor' || typeof descriptor?.value !== 'function' || !descriptor.configurable) continue;
      Object.defineProperty(proto, name, { ...descriptor, value: function(...args) {
        return scoped(this, () => descriptor.value.apply(this, args));
      } });
      restores.push(() => Object.defineProperty(proto, name, descriptor));
    }
  } catch(error) {
    for(const restore of restores.reverse())restore();
    if(globalThis.setTimeout===set)globalThis.setTimeout=savedSet;
    if(globalThis.clearTimeout===clear)globalThis.clearTimeout=savedClear;
    throw error;
  }
  return {
    read: () => ({ protocol: 'task14.same-native-owner-sdk-clock.v5', now, ownerObserved: !!owner,
      ownerCount:owner?1:0,
      globalTimersOutsideOwnerUnchanged: true, calls: JSON.parse(JSON.stringify(calls)),
      timers: timers.map(t => ({ id:t.id,delay:t.delay,due:t.due,scheduledAt:t.scheduledAt,cancelled:t.cancelled,fired:t.fired })) }),
    async advance(milliseconds) {
      if (disposed || !owner || !Number.isFinite(milliseconds) || milliseconds < 0) throw Error('No actual owner/valid clock event');
      const end = now + milliseconds;
      for (let step = 0; step < 1000; step++) {
        const ready = timers.filter(t => !t.cancelled && !t.fired && t.due <= end).sort((a,b)=>a.due-b.due || a.id-b.id)[0];
        if (!ready) { now = end; for(let i=0;i<12;i++) await Promise.resolve();
          if (!timers.some(t=>!t.cancelled&&!t.fired&&t.due<=end)) return; continue; }
        now = ready.due; ready.fired = true;
        const call = { method:'timerCallback',id:ready.id,at:now,sameOwner:ready.owner===owner };
        calls.push(call); record({method:'Task14.ownedSdkTimerLeaf',call});
        scoped(ready.owner, () => ready.callback(...ready.args));
        for(let i=0;i<12;i++) await Promise.resolve();
      }
      throw Error('Owned SDK callback budget exhausted');
    },
    dispose() {
      if (disposed) return; disposed = true;
      for (const restore of restores.reverse()) restore();
      if (globalThis.setTimeout !== set || globalThis.clearTimeout !== clear) throw Error('Timer leaf ownership changed; no foreign restore');
      globalThis.setTimeout = savedSet; globalThis.clearTimeout = savedClear;
    }
  };
}
