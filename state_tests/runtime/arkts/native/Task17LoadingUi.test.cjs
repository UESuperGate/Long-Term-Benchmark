'use strict';
// Evaluator host regressions. Synthetic native frame/UI/Preferences transport
// is not device evidence; all feature/repository methods below are original.
const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), os = require('node:os'), crypto = require('node:crypto');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const { runCase } = require('./Task17LoadingUi.adapter.cjs'), { install } = require('./Task17LoadingUi.install.cjs');
const root = path.resolve(__dirname, '../../../..'), candidate = path.join(root, 'final_dev_nodes/17_pinned_messages_final_0_5_3');
const feature = 'entry/src/main/ets/features/PinnedMessagesFeature.ets', page = 'entry/src/main/ets/pages/Index.ets';
const spec = require(path.join(root, 'benchmark_tasks/17_pinned_messages/transitions.json')).cases[0];
const sources = [feature, page].map(p => ({ path: p, sha256: crypto.createHash('sha256').update(fs.readFileSync(path.join(candidate, p))).digest('hex') }));
function load(file, modules = {}, cache = {}) {
  if (cache[file]) return cache[file];
  const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }, reportDiagnostics: true });
  assert.equal(compiled.diagnostics.length, 0);
  const context = { exports: {}, console: { info() {} }, require: name => {
    if (modules[name]) return modules[name];
    if (!name.startsWith('.')) throw new Error('Unbound OS dependency: ' + name);
    return load(path.resolve(path.dirname(file), name + '.js'), modules, cache);
  } };
  vm.runInNewContext(compiled.outputText, context, { filename: file });
  return cache[file] = context.exports;
}
class Selector {
  constructor(filters = {}) { this.filters = filters; }
  id(id) { return new Selector({ ...this.filters, id }); }
  text(text) { return new Selector({ ...this.filters, text }); }
  inWindow(bundle) { return new Selector({ ...this.filters, bundle }); }
}
const component = v => ({ id: '', text: '', enabled: true,
  async getId() { return this.id; }, async getText() { return this.text; }, async isEnabled() { return this.enabled; },
  async getBounds() { return { left: 0, top: 0, right: 100, bottom: 20 }; }, ...v });
async function probe(options = {}) {
  let disk = options.preexisting ? '[{"eventId":"$a","sender":"Alice","body":"Alpha"}]' : undefined, cached = disk;
  const sdkCalls = [], writes = [], store = {
    async has() { return cached !== undefined; }, async get(key, fallback) { return cached === undefined ? fallback : cached; },
    async put(...args) { writes.push(args); cached = args[1]; },
    async flush() { writes.push(['flush']); if (!options.skipFlush) disk = cached; }
  };
  const preferences = { getPreferences(context, name) { sdkCalls.push({ context, name }); return Promise.resolve(store); },
    async removePreferencesFromCache(context, name) {
      sdkCalls.push({ context, name });
      cached = options.corruptReopen ? '[{"eventId":"$other","sender":"Other","body":"Wrong"}]' : disk;
    } };
  Object.defineProperty(preferences, 'getPreferences', { configurable: false, writable: false });
  const originalSdk = preferences.getPreferences;
  const types = load(path.join(candidate, feature), { '@ohos.data.preferences': { default: preferences } });
  const ui = load(path.join(__dirname, 'Task17LoadingUi.js'));
  let presenter, nodes = [], screen = 'room_timeline', launched = false, monitor, lifecycle, foreground = false;
  let queued = [], openReturned;
  const context = { abilityInfo: { bundleName: 'candidate.test', moduleName: 'entry', name: 'EntryAbility' }, preferencesDir: '/real-ability-scope',
    toJSON() { throw new Error('SDK context must never be serialized'); } };
  const ability = { context }, title = component({ text: 'Design team' }), banner = component({ id: 'pinned_messages_banner' });
  const focus = component({ id: 'focused_event_label', text: '12 members' });
  const open = component({ id: 'open_pinned_messages', enabled: !options.disabledOpen, async click() {
    screen = 'pinned_messages'; presenter.setPermission(true);
    openReturned = presenter.openPinnedMessages(context); refresh();
    await openReturned; refresh();
  } });
  const back = component({ id: 'pinned_messages_back', async click() { screen = 'room_timeline'; if (options.wrongRoom) focus.text = 'Other room'; refresh(); } });
  function refresh() {
    nodes = screen === 'room_timeline' ? [title, banner, focus, open] : [back,
      component({ id: 'pinned_messages_' + presenter.listState })];
  }
  const properties = { id: 17, windowRect: { left: 0, top: 0, width: 500, height: 1000 } };
  const frame = cb => { cb.onFrame(10); cb.onIdle(20); };
  const uiContext = {
    getHostContext: () => context,
    getRouter: () => ({ getState: () => ({ path: 'pages/', name: options.wrongRoute ? 'Other' : 'Index' }) }),
    runScopedTask(fn) { fn(); },
    getComponentUtils: () => ({ getRectangleById(id) {
      if (!nodes.some(n => n.id === id)) throw new Error('Node not laid out');
      return { size: { width: 100, height: 20 }, screenOffset: { x: 0, y: 0 } };
    } }),
    postFrameCallback(cb) {
      if (options.missedFrame) queued.push(cb);
      else queueMicrotask(() => frame(cb));
    }
  };
  const main = { getWindowProperties: () => properties, getUIContext: () => uiContext };
  const { createTask17LaunchController } = load(path.join(__dirname, 'Task17LoadingLaunch.js'));
  const launch = createTask17LaunchController({
    applicationContext: { on(name, cb) { lifecycle = cb; return 17; }, async off() {} },
    delegator: { async addAbilityMonitor(cb) { monitor = cb; }, async removeAbilityMonitor() {},
      async startAbility() {
        presenter = new types.PinnedMessagesListPresenter(new types.PinnedMessagesRepository()); refresh(); launched = true;
        monitor.onAbilityCreate(ability);
      }, async getCurrentTopAbility() { return ability; } },
    async getLastWindow(c) { assert.equal(c, context); return main; }
  }, 'candidate.test');
  launch.getInspectorTree = () => {
    if (options.invalidInspector) return 'native inspector unavailable: raw diagnostic text';
    const tree = { $children: nodes.map(n => ({ $type: 'Column',
      $attrs: { id: n.id, visibility: options.hiddenLoading && n.id === 'pinned_messages_loading' ? 'Visibility.Hidden' : 'Visibility.Visible' } })) };
    return options.objectInspector ? tree : JSON.stringify(tree);
  };
  ui.configureTask17Loading(JSON.stringify({ bundleName: 'candidate.test', moduleName: 'entry',
    productionModuleUrl: '@bundle:candidate.test/entry/ets/features/PinnedMessagesFeature' }), async url => {
    assert.ok(launched); assert.ok(nodes.includes(open));
    assert.equal(url, '@bundle:candidate.test/entry/ets/features/PinnedMessagesFeature');
    return options.duplicate ? load(path.join(candidate, feature), { '@ohos.data.preferences': { default: preferences } }) : types;
  });
  const driver = {
    async findWindow() { return { getBundleName: async () => 'candidate.test', isFocused: async () => true,
      getBounds: async () => ({ left: 0, top: 0, right: 500, bottom: 1000 }) }; },
    async findComponents(selector) {
      const found = nodes.filter(n => Object.entries(selector.filters).every(([k, v]) => k === 'bundle' || n[k] === v));
      return found.length ? found : null;
    }, async delayMs() {
      if (!foreground) { foreground = true; lifecycle.onWindowStageCreate(ability, { getMainWindow: async () => main }); monitor.onAbilityForeground(ability); }
      const pending = queued; queued = []; for (const cb of pending) frame(cb);
    }
  };
  if (options.alreadyStarted) {
    await launch.start();
    await driver.delayMs();
  }
  const raw = JSON.parse(await ui.runTask17LoadingUi(JSON.stringify(spec), 'candidate.test', driver, new Selector(),
    launch, preferences, Boolean(options.alreadyStarted)));
  assert.equal(preferences.getPreferences, originalSdk);
  assert.ok(sdkCalls.every(call => call.context === context));
  raw.productionSources = sources;
  return { raw, writes, sdkCalls };
}
const adapt = raw => runCase({ taskId: spec.taskId, caseSpec: spec, native: { bundleName: raw.bundleName, runTask17LoadingUI: async () => raw }, load: async () => {} });

test('JS SDK boundary forwards the exact imported module and return without an ArkTS namespace value', async () => {
  const preferences = Object.freeze({ getPreferences() { throw new Error('Wrapper must not call SDK itself'); } });
  const driver = {}, selectors = {}, launch = {}, returned = Promise.resolve('raw-native-result');
  let calls = 0;
  const api = load(path.join(__dirname, 'Task17LoadingNativeSdk.js'), {
    '@ohos.data.preferences': { default: preferences },
    './Task17LoadingUi': { runTask17LoadingUi(...args) {
      calls++;
      assert.equal(args.length, 6);
      assert.deepEqual(args.slice(0, 2), ['case-json', 'candidate.test']);
      assert.equal(args[2], driver); assert.equal(args[3], selectors); assert.equal(args[4], launch);
      assert.equal(args[5], preferences);
      return returned;
    } }
  });
  assert.equal(api.runTask17LoadingNativeSdk('case-json', 'candidate.test', driver, selectors, launch), returned);
  await returned;
  assert.equal(calls, 1);
  const suite = fs.readFileSync(path.join(__dirname, 'Task17LoadingUiSuite.ets'), 'utf8');
  assert.doesNotMatch(suite, /@ohos\.data\.preferences/);
  assert.match(suite, /runTask17LoadingNativeSdk/);
});

test('host natural frame transport binds original Loading and actual same-page Back without holding SDK Promise', async () => {
  const { raw, writes } = await probe();
  assert.equal(raw.failure, undefined);
  const result = await adapt(raw);
  assert.equal(result.unsupported, undefined, JSON.stringify(result));
  assert.deepEqual(result.observed, spec.expected);
  assert.equal(result.invariantChecks[0].passed, true);
  assert.equal(writes.length, 2, 'Only original initialization put and flush execute');
  assert.equal(raw.loadingFrames.nativePromisePending, 'unproven');
  assert.equal(raw.observer.bindings.getPreferences.available, false);
  assert.equal(raw.observer.calls.some(c => c.method === 'getPreferences'), false, 'Native Promise and immutable SDK descriptor are untouched');
  assert.equal(raw.persistence.before.present, false);
  assert.equal(raw.persistence.after.present, true);
  assert.equal(raw.persistence.after.cacheEvicted, true);
  assert.deepEqual(raw.persistence.evaluatorDataWrites, []);
});
test('strict runtime classification reuses one live launch without a second start', async () => {
  const { raw, writes } = await probe({ alreadyStarted: true });
  assert.equal(raw.failure, undefined);
  const result = await adapt(raw);
  assert.equal(result.unsupported, undefined, JSON.stringify(result));
  assert.deepEqual(result.observed, spec.expected);
  assert.equal(writes.length, 2);
  assert.equal(raw.launchEvidence.events.filter(event => event.method === 'startRequested').length, 1);
});
test('immediate completion without a qualifying rendered frame remains NS despite domain Loading', async () => {
  const { raw } = await probe({ missedFrame: true });
  assert.equal(raw.failure, undefined);
  assert.ok(raw.observer.calls.some(c => c.method === 'openPinnedMessages' && c.state?.listState === 'loading'));
  const result = await adapt(raw);
  assert.match(result.unsupported, /no qualifying natural same-page loading frame/);
  assert.deepEqual(result.observed, {});
});
test('actual object inspector transport is accepted without string coercion and raw payload is retained', async () => {
  const { raw } = await probe({ objectInspector: true });
  const result = await adapt(raw);
  assert.equal(result.unsupported, undefined);
  assert.ok(raw.loadingFrames.frames.length > 0);
  for (const frame of raw.loadingFrames.frames) {
    assert.equal(frame.inspector.rawType, 'object');
    assert.equal(frame.inspector.parsed, true);
    assert.deepEqual(frame.inspector.rawValue, frame.tree);
  }
});
test('non-JSON inspector string preserves exact raw diagnostic and measurements, never loading PASS', async () => {
  const { raw } = await probe({ invalidInspector: true });
  assert.equal(raw.failure, undefined);
  assert.ok(raw.loadingFrames.frames.length > 0);
  for (const frame of raw.loadingFrames.frames) {
    assert.equal(frame.inspector.rawType, 'string');
    assert.equal(frame.inspector.rawValue, 'native inspector unavailable: raw diagnostic text');
    assert.equal(frame.inspector.parsed, false);
    assert.ok(frame.inspector.parseError);
    assert.equal(frame.tree, undefined);
    assert.ok(frame.rectangles);
    assert.ok(frame.observer);
  }
  assert.match((await adapt(raw)).unsupported, /no qualifying natural same-page loading frame/);
});
test('original empty-store initialization persists via actual repository methods, never preseeded by probe', async () => {
  const { raw, writes } = await probe({ emptyStore: true });
  assert.equal(raw.failure, undefined);
  assert.equal(writes.length, 2);
  assert.equal(writes[0][0], 'room_design_pinned_events');
  assert.equal(JSON.parse(writes[0][1])[0].eventId, '$rules');
  assert.deepEqual(writes[1], ['flush']);
});
test('preexisting key, missing durable flush and corrupt reopened contents do not satisfy equivalent I/O proof', async () => {
  for (const options of [{ preexisting: true }, { skipFlush: true }, { corruptReopen: true }]) {
    const { raw } = await probe(options), result = await adapt(raw);
    assert.ok(result.unsupported);
    assert.deepEqual(result.observed, {});
    if (options.preexisting) assert.equal(raw.actions.length, 0, 'Never clear preexisting data to obtain a cold fixture');
  }
});
test('disabled Open, duplicate module, hidden loading and wrong route cannot manufacture coverage', async () => {
  for (const options of [{ disabledOpen: true }, { duplicate: true }, { hiddenLoading: true }, { wrongRoute: true }]) {
    const { raw } = await probe(options), result = await adapt(raw);
    assert.ok(result.unsupported);
    assert.deepEqual(result.observed, {});
    if (options.disabledOpen) assert.equal(raw.actions.length, 0);
  }
});
test('complete loading evidence with a wrong physical Back destination keeps a false invariant', async () => {
  const { raw } = await probe({ wrongRoom: true }), result = await adapt(raw);
  assert.equal(result.unsupported, undefined);
  assert.deepEqual(result.observed, spec.expected);
  assert.equal(result.invariantChecks[0].passed, false);
});
test('native layout/context/provenance and SDK bindings cannot be omitted', async () => {
  const { raw } = await probe();
  for (const mutate of [r => { r.productionSources = []; }, r => { r.actions = []; },
    r => { r.observer.bindings.persistPinnedState.available = false; },
    r => { for (const f of r.loadingFrames.frames) f.rectangles = {}; },
    r => { for (const f of r.loadingFrames.frames) f.windowIdentity.lastWindowId = 999; }]) {
    const changed = JSON.parse(JSON.stringify(raw)); mutate(changed);
    assert.deepEqual((await adapt(changed)).observed, {});
  }
});
test('readback needs identical context, exact ordering and original operation/return/presenter correlation', async () => {
  const { raw } = await probe();
  for (const mutate of [r => { delete r.persistence; }, r => { r.persistence.after.sameAbilityContext = false; },
    r => { r.persistence.after.context.preferencesDir = '/wrong-scope'; },
    r => { r.persistence.after.cacheEvicted = false; },
    r => { delete r.persistence.originalCompletion; },
    r => { r.persistence.before.sequence = r.persistence.after.sequence; },
    r => { r.persistence.operations[3].completed = false; },
    r => { r.observer.calls.find(c => c.method === 'persistPinnedState' && c.phase === 'entered').repositoryId = 9; },
    r => { r.observer.calls.find(c => c.method === 'openPinnedTimeline' && c.phase === 'fulfilled').resolvedMessages[0].body = 'wrong'; },
    r => { r.observer.calls.find(c => c.method === 'openPinnedMessages' && c.phase === 'fulfilled').state.pinnedMessages[0].sender = 'wrong'; }]) {
    const changed = JSON.parse(JSON.stringify(raw)); mutate(changed);
    const result = await adapt(changed);
    assert.ok(result.unsupported);
    assert.deepEqual(result.observed, {});
  }
});
test('independent installer leaves production/shared transport unchanged and is scoped only to loading', t => {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-task17-loading-'));
  t.after(() => fs.rmSync(work, { recursive: true, force: true }));
  for (const relative of ['entry/src/main', 'AppScope']) fs.cpSync(path.join(candidate, relative), path.join(work, relative), { recursive: true });
  const dir = path.join(work, 'entry/src/test'); fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'native-bundle.js'), "import { x } from './native-device-platform';\n" +
    "if (candidateUI) await bridge.ui.navigate(candidateUI.route);\nmodule.exports.runCase({ ...context, native: bridge,\n" +
    'await evaluateCase(); await bridge.persistRow(row); try { await bridge.dispose(); } catch(e) {}');
  fs.writeFileSync(path.join(dir, 'NativeBundle.test.ets'), 'export default function nativeBundleTests(): void {}');
  const built = install(work);
  assert.equal(built.productionUnchanged, true);
  assert.ok(built.fixtures.some(f => f.installedPath.endsWith('/Task17LoadingNativeSdk.js')));
  assert.ok(built.fixtures.some(f => f.installedPath.endsWith('/Task17LoadingNativeSdk.d.ts')));
  assert.equal(typeof load(path.join(dir, 'Task17LoadingUiAdapter.js')).runTask17LoadingCase, 'function');
  assert.match(fs.readFileSync(built.bundleFile, 'utf8'), /await bridge.persistRow/);
  assert.doesNotMatch(fs.readFileSync(built.suiteFile, 'utf8'), /\.\.\/main/);
  const bridge = load(path.join(__dirname, 'Task17LoadingUiBridge.js'));
  assert.equal(bridge.attachTask17LoadingUI({}, spec.taskId, 'view_in_timeline'), false);
  assert.throws(() => install(work), /already installed/);
});
