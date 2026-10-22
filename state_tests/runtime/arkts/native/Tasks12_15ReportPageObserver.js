// Evaluator instrumentation only. Configure the exact original class imported
// by pages/Index, install after page readiness but before UI fixture actions,
// and never construct a presenter.
let configured;
let installed;

export function configureTasks12ReportPage(Presenter) {
  if (installed) throw new Error('Cannot reconfigure an active page observer');
  configured = Presenter;
}

export function installTasks12ReportPageObserver() {
  if (installed) throw new Error('Report page observer already installed');
  const prototype = configured && configured.prototype;
  const instances = [];
  const calls = [];
  const restores = [];
  let disposed = false;
  let unavailable = '';
  if (!prototype) unavailable = 'Original page presenter class was not configured';
  const methods = ['updateReason', 'toggleLeaveRoom'];
  const descriptors = methods.map(name => prototype && Object.getOwnPropertyDescriptor(prototype, name));
  const getter = prototype && Object.getOwnPropertyDescriptor(prototype, 'canReport');
  if (prototype && (!getter || typeof getter.get !== 'function' ||
    descriptors.some(descriptor => !descriptor || !descriptor.configurable || typeof descriptor.value !== 'function'))) {
    unavailable = 'Original page presenter observation methods/getter are unavailable';
  }
  if (!unavailable) {
    methods.forEach((method, index) => {
      const descriptor = descriptors[index];
      Object.defineProperty(prototype, method, { ...descriptor, value: function(...args) {
        if (!instances.includes(this)) instances.push(this);
        const call = { instanceId: instances.indexOf(this) + 1, sequence: calls.length + 1,
          method, value: method === 'updateReason' ? args[0] : undefined, completed: false };
        calls.push(call);
        // Deliberately no async wrapper: preserve return/Promise identity and throws.
        const result = descriptor.value.apply(this, args);
        call.completed = true;
        return result;
      } });
      restores.push(() => Object.defineProperty(prototype, method, descriptor));
    });
  }
  const observer = {
    read() {
      if (disposed || unavailable || instances.length !== 1) return {
        available: false, reason: unavailable || (disposed ? 'Observer disposed' :
          'Expected exactly one original page presenter receiver'), instanceCount: instances.length, calls: calls.map(call => ({ ...call }))
      };
      const presenter = instances[0];
      return { available: true, instanceId: 1, instanceCount: 1, reason: presenter.reason,
        leaveRoom: presenter.leaveRoom, canReport: getter.get.call(presenter),
        calls: calls.map(call => ({ ...call })) };
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      for (const restore of restores.reverse()) restore();
      if (installed === observer) installed = undefined;
    }
  };
  installed = observer;
  return observer;
}

export function readTasks12ReportPage() {
  return installed ? installed.read() : { available: false, reason: 'Page observer not installed', calls: [] };
}
