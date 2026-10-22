// This file is appended to a generated ES module and compiled into Ark bytecode.
// The adapters use this clock only to measure real elapsed debounce time.
const performance = { now: () => Date.now() };
let activeNativeContext = null;

function nativeModuleBinding(request, calls) {
  const bridge = activeNativeContext;
  const binding = bridge && bridge.modules[request];
  if (!binding) return null;
  const native = binding.default;
  const methods = new Map();
  const proxy = new Proxy({}, { get(_target, property) {
    // Promise assimilation probes this protocol member, not a native service.
    if (property === 'then' && native[property] === undefined) return undefined;
    const contextRequired = request === '@ohos.data.preferences';
    if ((contextRequired && !bridge.capabilities.context.available) || native[property] === undefined) {
      calls.push({ module: request, method: String(property), unavailableNativeService: true });
      throw new Error('Native API unavailable in this runtime: ' + request + '.' + String(property));
    }
    if (typeof native[property] !== 'function') return native[property];
    if (!methods.has(property)) methods.set(property, function(...args) {
      const call = { module: request, method: String(property), nativeService: true, args: snapshot(args) };
      calls.push(call);
      try { return native[property].apply(native, args); }
      catch (error) { call.error = String(error); throw error; }
    });
    return methods.get(property);
  } });
  return new Proxy({}, { get(_target, property) { return property === 'default' ? proxy : proxy[property]; } });
}
function normalize(name) {
  const parts = [];
  for (const part of name.split('/')) {
    if (!part || part === '.') continue;
    if (part === '..') parts.pop();
    else parts.push(part);
  }
  return '/' + parts.join('/');
}

function deepEqual(a, b) {
  if (Object.is(a, b)) return true;
  if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object') return false;
  if (Object.getPrototypeOf(a) !== Object.getPrototypeOf(b)) return false;
  const prototype = Object.getPrototypeOf(a);
  if (prototype !== Object.prototype && prototype !== Array.prototype && prototype !== null) {
    throw new Error('Native util shim only supports plain records, arrays and primitives');
  }
  if (Array.isArray(a) && a.length !== b.length) return false;
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every(key =>
    Object.prototype.hasOwnProperty.call(b, key) && deepEqual(a[key], b[key]));
}

function hostShim(name) {
  if (name === 'node:fs') return { existsSync: name => Object.prototype.hasOwnProperty.call(factories, normalize(name)) };
  if (name === 'node:path') return { join: (...parts) => normalize(parts.join('/')) };
  if (name === 'node:util') return { isDeepStrictEqual: deepEqual };
  if (name === 'node:timers/promises') return { setTimeout: milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds)) };
  throw new Error('Unsupported native adapter dependency: ' + name);
}

function productionLoader(project, evidence, calls) {
  const cache = new Map();
  const nativeModules = new Map();
  const bridge = activeNativeContext;
  const getNativeContext = () => {
    if (!bridge || !bridge.capabilities.context.available || !bridge.context) {
      calls.push({ module: 'ArkUI', method: 'getContext', unavailableNativeService: true });
      throw new Error('Actual native application context unavailable');
    }
    calls.push({ module: 'ArkUI', method: 'getContext', nativeService: true });
    return bridge.context;
  };
  if (activeNativeContext) activeNativeContext.productionCalls = calls;
  if (activeNativeContext && typeof candidateUI !== 'undefined' && candidateUI) {
    activeNativeContext.setObservationRecorder(observation => {
      calls.push({ module: 'ArkUI', method: observation.method, nativeUI: true, observation: snapshot(observation) });
      if (observation.available && !evidence.some(item => item.path === candidateUI.productionSource.path)) {
        evidence.push(candidateUI.productionSource);
      }
    });
  }
  function load(request, parent = project) {
    if (request.startsWith('@ohos.') || request.startsWith('@kit.')) {
      if (!nativeModules.has(request)) {
        const binding = nativeModuleBinding(request, calls);
        if (binding) { nativeModules.set(request, binding); return binding; }
        const constants = platformConstants[request] || {};
        const unavailable = new Proxy({}, { get(_target, property) {
          if (Object.prototype.hasOwnProperty.call(constants, property)) return constants[property];
          if (property === 'then') return undefined;
          calls.push({ module: request, method: String(property), unavailableNativeService: true });
          throw new Error('Native service invocation has no runtime binding: ' + request + '.' + String(property));
        } });
        nativeModules.set(request, new Proxy({ default: unavailable }, { get(_target, property) {
          if (property === 'default') return unavailable;
          return unavailable[property];
        } }));
      }
      return nativeModules.get(request);
    }
    if (request.startsWith('@') || request.startsWith('node:')) throw new Error('Unbound platform dependency: ' + request);
    const stem = normalize(parent + '/' + request);
    const file = [stem, stem + '.ets', stem + '.ts', stem + '/index.ets'].find(name => factories[name]);
    if (!file || !file.startsWith(project + '/')) {
      const error = new Error('Production module not bundled: ' + request);
      error.code = 'MODULE_NOT_FOUND';
      throw error;
    }
    if (cache.has(file)) return cache.get(file).exports;
    evidence.push(metadata[file]);
    const module = { exports: {} };
    cache.set(file, module);
    factories[file](module.exports, name => load(name, file.slice(0, file.lastIndexOf('/'))), module, getNativeContext);
    for (const [name, exported] of Object.entries(module.exports)) {
      if (typeof exported !== 'function' || !exported.prototype) continue;
      for (const method of Object.getOwnPropertyNames(exported.prototype)) {
        if (method === 'constructor') continue;
        const descriptor = Object.getOwnPropertyDescriptor(exported.prototype, method);
        if (typeof descriptor.value !== 'function') continue;
        const original = descriptor.value;
        Object.defineProperty(exported.prototype, method, { ...descriptor, value: function(...args) {
          const entry = { module: metadata[file].path, class: name, method, args: snapshot(args) };
          calls.push(entry);
          try {
            const result = original.apply(this, args);
            entry.returned = result instanceof Promise ? '[promise]' : snapshot(result);
            return result;
          } catch (error) { entry.error = String(error); throw error; }
        } });
      }
      const exportDescriptor = Object.getOwnPropertyDescriptor(module.exports, name);
      if (exportDescriptor.writable || exportDescriptor.set) {
        module.exports[name] = new Proxy(exported, { construct(target, args, newTarget) {
          calls.push({ module: metadata[file].path, class: name, method: 'constructor', args: snapshot(args) });
          return Reflect.construct(target, args, newTarget);
        } });
      }
    }
    return module.exports;
  }
  return request => load(request);
}

export async function runNativeCase(taskId, role, caseId) {
  const caseSpec = contracts[taskId].cases.find(item => item.caseId === caseId);
  const number = Number(taskId.slice(0, 2));
  const group = number <= 11 ? 'tasks08_11' : number <= 15 ? 'tasks12_15' : 'tasks16_18';
  const module = { exports: {} };
  adapterFactories[group](module.exports, hostShim, module);
  if (activeNativeContext) throw new Error('Native cases cannot share an active sandbox');
  const bridge = await createNativeContext(taskId + ':' + role + ':' + caseId, platformSandboxRoot, candidateUI && candidateUI.route || '');
  let row;
  activeNativeContext = bridge;
  try {
    if (candidateUI) await bridge.ui.navigate(candidateUI.route);
    const adapter = { runCase: context => module.exports.runCase({ ...context, native: bridge,
      context: { native: bridge, productionCalls: bridge.productionCalls } }) };
    row = await evaluateCase(taskId, caseSpec, '/projects/' + role + '/' + taskId, adapter);
    row.nativeBridge = { capabilities: bridge.capabilities, sandbox: bridge.sandbox,
      candidateUIVerified: row.calls.some(call => call.nativeUI && call.observation.available),
      applicationContextAvailable: bridge.capabilities.context.available };
  } finally {
    activeNativeContext = null;
    try { await bridge.dispose(); }
    catch (error) {
      if (!row) throw error;
      row.status = 'not_scored';
      row.reason = 'Native sandbox cleanup failed: ' + String(error);
    }
  }
  const json = JSON.stringify({ taskId, role, ...row });
  if (bridge.persistRow) {
    const artifact = await bridge.persistRow(json);
    console.info('ARKTS_NATIVE_ROW_FILE ' + JSON.stringify({ taskId, role, caseId, ...artifact }));
  } else {
    // Previewer has no device filesystem transport; preserve complete chunk validation.
    const chunks = Math.ceil(json.length / 1800);
    for (let index = 0; index < chunks; index++) {
      console.info('ARKTS_NATIVE_ROW ' + JSON.stringify({ taskId, role, caseId, index, chunks, text: json.slice(index * 1800, (index + 1) * 1800) }));
    }
  }
  console.info('ARKTS_NATIVE_BUNDLE_EXECUTED ' + taskId + ' ' + role + ' ' + caseId);
  return 'executed';
}
