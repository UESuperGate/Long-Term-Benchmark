import fileFs from '@ohos.file.fs';
import preferences from '@ohos.data.preferences';
import router from '@ohos.router';
import { UIContext } from '@ohos.arkui.UIContext';
import { createEntryAssertion } from './entry-assertion';

let sequence = 0;

function renderedNode(node, id) {
  if (!node || !node.$attrs || node.$attrs.id !== id ||
      node.$attrs.visibility !== 'Visibility.Visible' || typeof node.$type !== 'string') return false;
  const rect = String(node.$rect || '').match(/^\[\s*([-\d.]+),\s*([-\d.]+)\],\s*\[\s*([-\d.]+),\s*([-\d.]+)\]$/);
  return !!rect && Number(rect[3]) > Number(rect[1]) && Number(rect[4]) > Number(rect[2]) &&
    (node.$attrs.opacity === undefined || Number(node.$attrs.opacity) > 0);
}

function compactControl(inspection) {
  const node = inspection.node;
  const attrs = node && node.$attrs;
  return { selector: { kind: 'arkui_id', value: inspection.id }, present: inspection.present,
    node: node ? { type: node.$type, nativeId: node.$ID, bounds: node.$rect,
      visible: renderedNode(node, inspection.id), enabled: attrs && attrs.enabled,
      label: attrs && attrs.label, text: attrs && attrs.text, isOn: attrs && attrs.isOn,
      focused: attrs && attrs.focused, placeholder: attrs && attrs.placeholder } : null };
}

function failure(error) {
  return { available: false, error: String(error), code: error && error.code,
    stack: error && String(error.stack || '').slice(0, 600) };
}

function removeSandbox(directory) {
  try { fileFs.rmdirSync(directory); return; }
  catch (error) {
    if (typeof fileFs.listFileSync !== 'function' || typeof fileFs.lstatSync !== 'function') throw error;
    for (const name of fileFs.listFileSync(directory)) {
      if (!name || name === '.' || name === '..' || name.includes('/')) throw new Error('Unsafe sandbox directory entry');
      const child = directory + '/' + name;
      if (fileFs.lstatSync(child).isDirectory()) removeSandbox(child);
      else fileFs.unlinkSync(child);
    }
    fileFs.rmdirSync(directory);
  }
}

// The registry contains native ES imports, never JavaScript service substitutes.
export function nativePlatformModules() {
  return {
    '@ohos.file.fs': { default: fileFs },
    '@ohos.data.preferences': { default: preferences },
    '@ohos.router': { default: router }
  };
}

export async function createNativeContext(caseId, sandboxRoot = '', candidateRoute = '', applicationContext = null) {
  const id = 'ltb_native_' + Date.now() + '_' + (++sequence);
  const capabilities = {};
  let context;
  let uiContext;
  try { uiContext = UIContext.resolveUIContext(); }
  catch (error) { capabilities.uiContext = failure(error); }
  try {
    context = applicationContext || uiContext.getHostContext();
    capabilities.context = { available: !!context && !!context.cacheDir,
      origin: applicationContext ? 'device AbilityDelegator.getAppContext' : 'UIContext.getHostContext', cacheDir: context && context.cacheDir,
      filesDir: context && context.filesDir, preferencesDir: context && context.preferencesDir };
  } catch (error) { capabilities.context = failure(error); }
  const parent = sandboxRoot || (context && context.cacheDir);
  let sandbox = '';
  try {
    if (typeof parent !== 'string' || !parent.startsWith('/') || parent.includes('[PC')) {
      throw new Error('Native context has no usable absolute cacheDir');
    }
    sandbox = parent + '/' + id;
    fileFs.mkdirSync(sandbox);
    capabilities.filesystem = { available: true, sandbox,
      operations: Object.fromEntries(['mkdirSync', 'openSync', 'writeSync', 'readSync', 'copyFileSync', 'readTextSync', 'unlinkSync', 'rmdirSync',
        'open', 'write', 'read', 'stat', 'copyFile', 'listFileSync', 'lstatSync']
        .map(name => [name, typeof fileFs[name] === 'function'])) };
  } catch (error) { capabilities.filesystem = failure(error); sandbox = ''; }
  const preferenceNames = [];
  let observationRecorder = null;
  let returnRoute = '';
  let observationSequence = 0;
  return {
    caseId, context, sandbox, capabilities, fs: fileFs, preferences,
    setObservationRecorder(callback) { observationRecorder = callback; },
    modules: nativePlatformModules(),
    preferenceName: id,
    async openPreferences() {
      if (!capabilities.context.available) throw new Error('Native application context unavailable');
      const store = await preferences.getPreferences(context, { name: id });
      preferenceNames.push(id);
      return store;
    },
    async reopenPreferences() {
      preferences.removePreferencesFromCacheSync(context, id);
      return preferences.getPreferences(context, { name: id });
    },
    ui: {
      snapshot() {
        if (typeof getInspectorTree !== 'function') throw new Error('ArkUI inspector unavailable');
        if (!uiContext) throw new Error('ArkUI UIContext unavailable');
        let tree;
        let route;
        uiContext.runScopedTask(() => { tree = getInspectorTree(); route = uiContext.getRouter().getState(); });
        const routeName = route && String(route.path || '') + String(route.name || '');
        const candidateRouteVerified = !!candidateRoute && routeName === candidateRoute;
        const children = tree && (tree.$children || tree.children);
        const completeTree = Array.isArray(children) && children.length > 0;
        return { tree, route, completeTree, candidateRouteVerified,
          candidatePageVerified: candidateRouteVerified && completeTree };
      },
      inspect(id) {
        if (!uiContext || typeof getInspectorByKey !== 'function') throw new Error('ArkUI keyed inspection unavailable');
        let raw;
        uiContext.runScopedTask(() => { raw = getInspectorByKey(id); });
        return { id, node: raw ? JSON.parse(raw) : null };
      },
      observe(ids, anchorId) {
        const snapshot = this.snapshot();
        const anchor = this.inspect(anchorId);
        const available = Boolean(snapshot.candidateRouteVerified && renderedNode(anchor.node, anchorId));
        const controls = ids.map(id => {
          const inspection = this.inspect(id);
          return { ...inspection, present: available ? !!inspection.node && Object.keys(inspection.node).length > 0 : null };
        });
        const observation = { available, anchor, snapshot, controls,
          reason: available ? '' : 'Candidate route and a rendered positive-control anchor are required before absence can be observed' };
        if (observationRecorder) observationRecorder({ method: 'observe', ...observation });
        return observation;
      },
      async probeEntry(targetId, anchorId) {
        const observationId = id + '_entry_' + (++observationSequence);
        const capture = () => {
          const observation = this.observe([targetId], anchorId);
          return { capturedAt: Date.now(), available: observation.available,
            route: observation.snapshot.route, candidateRouteVerified: observation.snapshot.candidateRouteVerified,
            viewport: { width: Number(observation.snapshot.tree && observation.snapshot.tree.width),
              height: Number(observation.snapshot.tree && observation.snapshot.tree.height) },
            fullTreeAvailable: observation.snapshot.completeTree,
            anchor: compactControl({ ...observation.anchor, present: !!observation.anchor.node }),
            target: compactControl(observation.controls[0]) };
        };
        const before = capture();
        const action = { api: 'sendEventByKey', selector: { kind: 'arkui_id', value: targetId },
          action: 10, params: {}, attempted: false, delivered: null };
        if (before.available) {
          action.attempted = true;
          action.attemptedAt = Date.now();
          try { action.delivered = this.sendEvent(targetId, 10, {}); }
          catch (error) { action.error = String(error); }
          await new Promise(resolve => setTimeout(resolve, 100));
        }
        const after = capture();
        const rejectedAbsentSelector = before.available && after.available &&
          before.target.present === false && after.target.present === false &&
          action.attempted && action.delivered === false;
        const check = (name, observed, paths) => ({ id: name, expected: true, observed,
          passed: observed === null ? null : observed === true,
          evidence: paths.map(pointer => ({ observationId, pointer })) });
        const prerequisiteChecks = [
          check('candidate_route_mounted', before.candidateRouteVerified && after.candidateRouteVerified,
            ['/before/route', '/after/route']),
          check('positive_anchor_rendered', before.available && after.available,
            ['/before/anchor', '/after/anchor']),
          check('required_selector_present', before.available && after.available ?
            before.target.present && after.target.present : null, ['/before/target', '/after/target']),
          check('native_entry_action_delivered', action.attempted && typeof action.delivered === 'boolean' ?
            action.delivered : null, ['/action'])
        ];
        const proof = { schemaVersion: 1, kind: 'native_ui_entry_probe',
          backend: 'native_previewer_arkui', caseId, instanceId: id, observationId, candidateRoute,
          before, action, after, prerequisiteChecks, available: before.available && after.available,
          selectorReachability: rejectedAbsentSelector ? 'absent_action_rejected' : 'unestablished',
          taskEntryReachable: null, givenEstablished: null, semanticVerdict: null };
        if (observationRecorder) observationRecorder({ method: 'probeEntry', ...proof });
        return proof;
      },
      async navigate(url) {
        if (!uiContext) throw new Error('ArkUI UIContext unavailable');
        if (!returnRoute) {
          const state = uiContext.getRouter().getState();
          returnRoute = String(state.path || '') + String(state.name || '');
        }
        await uiContext.getRouter().pushUrl({ url });
        await new Promise(resolve => setTimeout(resolve, 100));
      },
      sendEvent(id, action, params) {
        if (typeof sendEventByKey !== 'function') throw new Error('ArkUI event injection unavailable');
        if (!uiContext) throw new Error('ArkUI UIContext unavailable');
        let result;
        uiContext.runScopedTask(() => { result = sendEventByKey(id, action, JSON.stringify(params || {})); });
        if (observationRecorder) observationRecorder({ method: 'sendEvent', id, action, delivered: result });
        return result;
      }
    },
    async dispose() {
      try {
        for (const name of preferenceNames) await preferences.deletePreferences(context, name);
      } finally {
        try {
          if (returnRoute && uiContext) {
            uiContext.getRouter().back({ url: returnRoute });
            await new Promise(resolve => setTimeout(resolve, 100));
          }
        } finally { if (sandbox) removeSandbox(sandbox); }
      }
    }
  };
}

export async function probeNativePlatform(sandboxRoot, entryRequestJson = '') {
  const entry = entryRequestJson ? JSON.parse(entryRequestJson) : null;
  const bridge = await createNativeContext(entry ? `${entry.binding.taskId}:${entry.binding.role}:${entry.spec.caseId}` : 'platform_probe',
    sandboxRoot, entry ? entry.policy.route : 'pages/Index');
  const result = { capabilities: bridge.capabilities, modules: Object.keys(bridge.modules),
    runtimeScope: 'Previewer platform probe; no candidate UI or full device service claim' };
  try {
    if (!bridge.sandbox) throw new Error('No native filesystem sandbox');
    const source = bridge.sandbox + '/original.txt';
    const copy = bridge.sandbox + '/copy.txt';
    const file = fileFs.openSync(source, fileFs.OpenMode.CREATE | fileFs.OpenMode.READ_WRITE);
    try { fileFs.writeSync(file.fd, 'native-filesystem-proof'); }
    finally { fileFs.closeSync(file); }
    const reader = fileFs.openSync(source, fileFs.OpenMode.READ_ONLY);
    const bytes = new ArrayBuffer(64);
    let length;
    try { length = fileFs.readSync(reader.fd, bytes); }
    finally { fileFs.closeSync(reader); }
    const observed = String.fromCharCode(...new Uint8Array(bytes).slice(0, length));
    if (observed !== 'native-filesystem-proof') throw new Error('Native read round trip differed');
    result.filesystem = { available: true, source, observed };
    try {
      fileFs.copyFileSync(source, copy);
      result.copy = { available: true, destination: copy };
    } catch (error) { result.copy = failure(error); }
    try {
      await fileFs.copyFile(source, copy + '.async');
      result.asyncCopy = { available: true, destination: copy + '.async' };
    } catch (error) { result.asyncCopy = failure(error); }
  } catch (error) { result.filesystem = failure(error); }
  try {
    if (!bridge.sandbox) throw new Error('No native filesystem sandbox');
    const source = bridge.sandbox + '/async-original.txt';
    const expected = 'native-async-filesystem-proof';
    const writer = await fileFs.open(source, fileFs.OpenMode.CREATE | fileFs.OpenMode.READ_WRITE);
    let written;
    try { written = await fileFs.write(writer.fd, expected); }
    finally { await fileFs.close(writer.fd); }
    const stat = await fileFs.stat(source);
    const reader = await fileFs.open(source, fileFs.OpenMode.READ_ONLY);
    const bytes = new ArrayBuffer(64);
    let length;
    try { length = await fileFs.read(reader.fd, bytes); }
    finally { await fileFs.close(reader.fd); }
    const observed = String.fromCharCode(...new Uint8Array(bytes).slice(0, length));
    if (observed !== expected || written !== expected.length || stat.size !== expected.length) {
      throw new Error('Native async bytes, write count or stat size differed');
    }
    result.asyncFilesystem = { available: true, source, observed, written, size: stat.size,
      operations: ['open', 'write', 'close', 'stat', 'read'] };
  } catch (error) { result.asyncFilesystem = failure(error); }
  try {
    const store = await bridge.openPreferences();
    await store.put('proof', 'native-preferences-proof');
    await store.flush();
    const reopened = await bridge.reopenPreferences();
    const observed = await reopened.get('proof', 'missing');
    if (observed !== 'native-preferences-proof') throw new Error('Native preferences reopen differed');
    result.preferences = { available: true, observed, name: bridge.preferenceName };
  } catch (error) { result.preferences = failure(error); }
  try { result.ui = { available: true, ...bridge.ui.snapshot() }; }
  catch (error) { result.ui = failure(error); }
  try {
    await bridge.ui.navigate(entry ? entry.policy.route : 'pages/Index');
    result.candidateUI = { available: true, ...bridge.ui.snapshot() };
    if (entry) {
      const probes = [];
      for (const selector of entry.policy.entryIds) probes.push(await bridge.ui.probeEntry(selector, entry.policy.anchorId));
      result.entryAssertion = createEntryAssertion(entry.spec, entry.policy, entry.binding, probes);
    } else {
    result.controlProbes = ['report_room_reason', 'submit_report_room', 'leave_room', 'report_room_leave_toggle'].map(id => bridge.ui.inspect(id));
    const anchorId = result.controlProbes.find(item => item.id === 'leave_room' && item.node) ? 'leave_room' : 'report_room_reason';
    result.rootObservation = bridge.ui.observe(['report_room_reason', 'submit_report_room'], anchorId);
    result.entryProbe = await bridge.ui.probeEntry('submit_report_room', anchorId);
    const toggle = result.controlProbes.find(item => item.id === 'report_room_leave_toggle');
    if (toggle.node) {
      const delivered = bridge.ui.sendEvent('report_room_leave_toggle', 10, {});
      await new Promise(resolve => setTimeout(resolve, 100));
      result.toggleInteraction = { delivered, before: toggle.node.$attrs,
        after: bridge.ui.inspect('report_room_leave_toggle').node.$attrs };
    }
    }
  } catch (error) { result.candidateUI = failure(error); }
  // The host verifies filesystem effects before removing its whole temp tree.
  result.sandbox = bridge.sandbox;
  const json = JSON.stringify(result);
  const chunks = Math.ceil(json.length / 1800);
  for (let index = 0; index < chunks; index++) console.info('ARKTS_NATIVE_PLATFORM_CHUNK ' +
    JSON.stringify({ index, chunks, text: json.slice(index * 1800, (index + 1) * 1800) }));
  return 'executed';
}
