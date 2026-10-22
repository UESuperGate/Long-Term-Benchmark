'use strict';

// OS transport doubles only. These tests do not constitute native UI evidence.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { install } = require('./Tasks08_11DeviceUi.install.cjs');
const core = import('data:text/javascript;base64,' + fs.readFileSync(path.join(__dirname, 'Tasks08_11DeviceUi.core.js')).toString('base64'));
const binding = import('data:text/javascript;base64,' + fs.readFileSync(path.join(__dirname, 'Tasks08_11DeviceUi.binding.js')).toString('base64'));
const observerModule = import('data:text/javascript;base64,' + fs.readFileSync(path.join(__dirname, 'Tasks08_11RoomObserver.js')).toString('base64'));

test('device entry records SDK enum without substituting FA TYPE_APP', async () => {
  const dataModule = source => 'data:text/javascript;base64,' + Buffer.from(source).toString('base64');
  let source = fs.readFileSync(path.join(__dirname, 'Tasks08_11DeviceUi.js'), 'utf8');
  const imports = {
    '@ohos.app.ability.abilityDelegatorRegistry': 'export default {};',
    '@ohos.window': 'export default { WindowType: { TYPE_APP: 0, TYPE_MAIN: 32 } };',
    '@ohos.UiTest': 'export const Driver = {}; export const ON = {};',
    './Tasks08_11DeviceUi.binding': 'export function createOriginalRoomObserverFactory() { return () => ({}); }',
    './Tasks08_11RoomObserver': 'export function installRoomObserver() {}',
    './Tasks08_11DeviceUi.core': 'export function createDeviceUiAugment(ports) { return async bridge => { bridge.boundMainType = ports.mainWindowType; return bridge; }; }'
  };
  for (const [name, replacement] of Object.entries(imports)) {
    assert.equal(source.split("'" + name + "'").length, 2);
    source = source.replace("'" + name + "'", JSON.stringify(dataModule(replacement)));
  }
  const entry = await import(dataModule(source));
  entry.configureDeviceUi({});
  assert.equal((await entry.augment({})).boundMainType, 32);
});

async function fixture(options = {}) {
  const { createDeviceUiAugment } = await core;
  const log = [];
  const config = { bundleName: 'candidate.test', abilityName: 'EntryAbility', moduleName: 'entry',
    entryRoute: 'pages/Index', allowedRoutes: ['pages/Index'], timeoutMs: options.timeoutMs || 100,
    originalModuleImportMode: options.originalModuleImportMode };
  const ability = { context: { abilityInfo: { bundleName: config.bundleName, name: config.abilityName, moduleName: config.moduleName } } };
  const viewport = { left: 10, top: 20, right: 410, bottom: 820 };
  const bounds = { left: 20, top: 40, right: 120, bottom: 80 };
  let monitor;
  let lifecycle;
  const windowRect = { left: 10, top: 20, width: 400, height: 800 };
  const stage = { getMainWindow: async () => ({ getWindowProperties: () => ({ id: 37, windowRect }) }) };
  let route = { path: 'pages/', name: 'Index' };
  let observer = options.observer || { read: () => ({ available: false }), dispose: () => log.push('observer:dispose') };
  const component = id => ({
    getId: async () => id, getBounds: async () => options.offscreen ? { left: 900, top: 900, right: 1000, bottom: 1000 } : bounds,
    getText: async () => options.text ? options.text(id) : '!room', getType: async () => 'Button', isEnabled: async () => options.enabled !== false,
    isClickable: async () => true, click: async () => { log.push('click:' + id); if (options.onClick) await options.onClick(id); },
    doubleClick: async () => log.push('doubleClick:' + id)
  });
  const uiContext = { getHostContext: () => options.wrongHost ? { abilityInfo: { ...ability.context.abilityInfo, bundleName: 'other.app' } } : ability.context,
    runScopedTask: fn => fn(), getRouter: () => ({ getState: () => route }) };
  const delegator = {
    addAbilityMonitor: async value => { log.push('monitor:add'); monitor = value; },
    startAbility: async want => {
      log.push('ability:start');
      assert.equal(want.bundleName, config.bundleName);
      assert.equal(bridge.roomUpgrade, ['after-page-ready-diagnostic', 'after-page-ready'].includes(options.originalModuleImportMode) ? undefined : observer);
      if (!options.warm) monitor.onAbilityCreate(ability);
      if (!options.noStage) lifecycle.onWindowStageCreate(options.foreignStage ?
        { context: { abilityInfo: { ...ability.context.abilityInfo, bundleName: 'other.app' } } } : ability, stage);
      monitor.onWindowStageCreate(ability);
      monitor.onAbilityForeground(ability);
    },
    getCurrentTopAbility: async () => ability,
    removeAbilityMonitor: async value => { assert.equal(value, monitor); log.push('monitor:remove'); }
  };
  const originalUi = { navigate: () => assert.fail('Stale pre-start UI must not be used') };
  const bridge = { caseId: options.caseId || 'ru_open_successor', ui: originalUi, capabilities: {}, modules: { untouched: true },
    setObservationRecorder: () => log.push('original:recorder'), dispose: async () => log.push('original:dispose') };
  const augment = createDeviceUiAugment({
    getDelegator: () => delegator,
    getApplicationContext: () => ({
      on: (name, callback) => { assert.equal(name, 'abilityLifecycle'); lifecycle = callback; log.push('lifecycle:add'); return 5; },
      off: async (name, id) => { assert.equal(name, 'abilityLifecycle'); assert.equal(id, 5); log.push('lifecycle:remove'); }
    }),
    createDriver: () => ({
      findWindow: async selector => { assert.equal(selector.bundleName, config.bundleName); assert.equal(selector.focused, true);
        return { getBounds: async () => options.wrongGeometry ? { ...viewport, right: 411 } : viewport,
          getBundleName: async () => options.foreignWindow ? 'other.app' : config.bundleName,
          isFocused: async () => !options.unfocused }; },
      findComponents: async selector => {
        assert.equal(selector.bundleName, config.bundleName);
        if (options.hiddenIds?.includes(selector.id)) return [];
        if ('queryResult' in options && (!options.emptyId || options.emptyId === selector.id)) return options.queryResult;
        return options.absent ? [] : options.duplicate ? [component(selector.id), component(selector.id)] : [component(selector.id)];
      }
    }),
    selectorById: (id, bundleName) => ({ id, bundleName }),
    getLastWindow: async context => {
      log.push('window:context'); assert.equal(context, ability.context);
      assert.ok(log.indexOf('ability:start') < log.indexOf('window:context'));
      return { getWindowProperties: () => ({ type: 'windowType' in options ? options.windowType : 32,
        id: options.dialog ? 38 : 37, name: 'candidate-main', windowRect }),
        getUIContext: () => { log.push('window:getUIContext'); return uiContext; } };
    },
    mainWindowType: 'mainWindowType' in options ? options.mainWindowType : 32,
    getInspectorTree: () => options.emptyTree ? {} : ({ width: 114, height: 228,
      $children: [{ $type: 'Column', $attrs: { visibility: 'Visibility.Visible', opacity: 0.75, content: 'raw-inspector-proof' } }] }),
    getInspectorByKey: id => {
      if (options.hiddenIds?.includes(id)) return '';
      if (options.inspectorError) throw new Error('inspector unavailable');
      return options.noInspector ? '' : JSON.stringify({ $attrs: { id, visibility: 'Visibility.Visible', opacity: 0.8 } });
    },
    delay: ms => new Promise(resolve => setTimeout(resolve, Math.min(ms, 2)))
  }, config, async readiness => {
    await Promise.resolve();
    if (['after-page-ready-diagnostic', 'after-page-ready'].includes(options.originalModuleImportMode)) {
      assert.equal(readiness.available, true);
      assert.equal(readiness.anchor.id, 'current_room_id');
    }
    log.push('observer:install');
    if (options.createObserver) observer = await options.createObserver(readiness);
    return observer;
  });
  return { augment, bridge, log, observer, originalUi, setRoute: value => { route = value; } };
}

test('cold lifecycle installs same observer before startup and gets candidate context afterward', async () => {
  const f = await fixture();
  await f.augment(f.bridge);
  assert.deepEqual(f.log.slice(0, 4), ['observer:install', 'lifecycle:add', 'monitor:add', 'ability:start']);
  assert.equal(f.bridge.roomUpgrade, f.observer);
  assert.equal(f.bridge.modules.untouched, true);
  await f.bridge.ui.navigate('pages/Index');
  const records = [];
  f.bridge.setObservationRecorder(event => records.push(event));
  assert.equal(records[0].method, 'observerInstalled');
  assert.ok(records.every(event => event.caseId === f.bridge.caseId));
  const windowRecord = records.find(event => event.method === 'candidateWindow');
  assert.equal(windowRecord.properties.type, 32);
  assert.equal(windowRecord.stageMainWindowId, 37);
  assert.deepEqual(windowRecord.sdkMainEnum, { value: 32, typeOf: 'number' });
  assert.equal(windowRecord.ability.bundleName, 'candidate.test');
  await f.bridge.dispose();
  assert.equal(f.bridge.ui, f.originalUi);
  assert.equal(f.bridge.roomUpgrade, undefined);
  assert.deepEqual(f.log.slice(-4), ['monitor:remove', 'lifecycle:remove', 'observer:dispose', 'original:dispose']);
});

test('main-window ownership works without exported enum; numeric types never substitute for ownership', async () => {
  for (const windowType of [0, 1, 16, undefined]) {
    const f = await fixture({ windowType, mainWindowType: undefined });
    await f.augment(f.bridge);
    assert.equal(f.log.includes('window:getUIContext'), true);
    const records = f.bridge.deviceUi.evidence.filter(event => event.method === 'candidateWindow');
    assert.equal(records.length, 1);
    assert.equal(records[0].properties.type, windowType === undefined ? null : windowType);
    assert.equal(records[0].properties.typeOf, typeof windowType);
    assert.deepEqual(records[0].sdkMainEnum, { value: null, typeOf: 'undefined' });
    await f.bridge.dispose();
  }
});

test('a same-bundle dialog cannot pass the Stage ID check even with identical geometry/route', async () => {
  const f = await fixture({ dialog: true, mainWindowType: undefined, timeoutMs: 5 });
  await assert.rejects(f.augment(f.bridge), /not the observed WindowStage main window/);
  assert.equal(f.log.includes('window:getUIContext'), false);
  assert.equal(f.bridge.roomUpgrade, undefined);
});

test('foreign UIContext is rejected even with a matching Stage window ID', async () => {
  const f = await fixture({ wrongHost: true, timeoutMs: 5 });
  await assert.rejects(f.augment(f.bridge), /UIContext does not belong to the monitored candidate ability/);
  assert.equal(f.log.includes('window:getUIContext'), true);
  assert.equal(f.log.some(value => value.startsWith('click:')), false);
  assert.equal(f.bridge.capabilities.deviceUI.available, false);
  assert.equal(f.bridge.roomUpgrade, undefined);
});

test('missing/foreign stage, foreign or unfocused Driver window and geometry mismatch remain unsupported', async () => {
  for (const options of [{ noStage: true }, { foreignStage: true }, { foreignWindow: true }, { unfocused: true }, { wrongGeometry: true }]) {
    const f = await fixture({ ...options, timeoutMs: 5, mainWindowType: undefined });
    await assert.rejects(f.augment(f.bridge));
    assert.equal(f.log.some(value => value.startsWith('click:')), false);
    assert.equal(f.bridge.capabilities.deviceUI.available, false);
    assert.equal(f.bridge.roomUpgrade, undefined);
    assert.ok(f.log.includes('lifecycle:remove'));
  }
});

test('observed schema uses real transport results and never invents visibility', async () => {
  for (const noInspector of [false, true]) {
    const f = await fixture({ noInspector });
    await f.augment(f.bridge);
    const result = await f.bridge.ui.observe(['successor'], 'candidate_root');
    assert.equal(result.available, true);
    assert.equal(result.snapshot.tree.width, 400);
    assert.equal(result.snapshot.tree.height, 800);
    const control = result.controls[0];
    assert.equal(control.node.$rect, '[10,20],[110,60]');
    assert.equal(control.node.$attrs.content, '!room');
    assert.equal(control.node.$attrs.enabled, true);
    assert.equal(control.node.$attrs.visibility, noInspector ? undefined : 'Visibility.Visible');
    assert.equal(control.node.$attrs.opacity, noInspector ? undefined : 0.8);
    assert.deepEqual(control.unobservedAttributes, noInspector ? ['visibility', 'opacity'] : []);
    await f.bridge.dispose();
  }
});

test('nullish queries are empty, never positive anchors or clickable controls', async () => {
  for (const queryResult of [null, undefined, []]) {
    const f = await fixture({ queryResult, noInspector: true, emptyTree: true });
    await f.augment(f.bridge);
    const observed = await f.bridge.ui.observe(['missing'], 'candidate_root');
    assert.equal(observed.available, false);
    assert.equal(observed.anchor.present, false);
    assert.equal(observed.controls[0].present, null);
    assert.equal(observed.snapshot.completeTree, false);
    assert.equal(observed.snapshot.candidatePageVerified, false);
    await assert.rejects(f.bridge.ui.click('missing'), /exactly one native control/);
    await assert.rejects(f.bridge.ui.sendEvent('missing', 10, {}), /exactly one native control/);
    assert.equal(f.log.some(value => value.startsWith('click:')), false);
    await f.bridge.dispose();
  }
});

test('null query for an absent control retains a real anchor; malformed non-array results reject', async () => {
  const f = await fixture({ queryResult: null, emptyId: 'missing', noInspector: true });
  await f.augment(f.bridge);
  const observed = await f.bridge.ui.observe(['missing'], 'candidate_root');
  assert.equal(observed.available, true);
  assert.equal(observed.anchor.inDriverTree, true);
  assert.equal(observed.controls[0].present, false);
  await f.bridge.dispose();
  const malformed = await fixture({ queryResult: {}, noInspector: true });
  await malformed.augment(malformed.bridge);
  await assert.rejects(malformed.bridge.ui.observe(['missing'], 'candidate_root'), /Unexpected UiTest findComponents result/);
  await malformed.bridge.dispose();
});

test('startup recorder evidence survives row JSON with one lossless inspector tree per snapshot', async () => {
  const f = await fixture();
  await f.augment(f.bridge);
  const calls = [];
  // Mirrors the shared runner's already-existing recorder -> row.calls path.
  f.bridge.setObservationRecorder(observation => calls.push({ module: 'ArkUI', nativeUI: true, method: observation.method, observation }));
  await f.bridge.dispose();
  const persisted = JSON.parse(JSON.stringify({ calls, status: 'not_scored', observed: {} }));
  const startup = persisted.calls.find(call => call.method === 'deviceUiReady').observation.snapshot;
  assert.ok(persisted.calls.some(call => call.method === 'candidateStageCreated'));
  assert.ok(persisted.calls.some(call => call.method === 'candidateWindow'));
  assert.equal(startup.inspectorTree, undefined);
  assert.equal(startup.inspectorTreeField, 'tree');
  assert.deepEqual(startup.tree.$children[0].$attrs, { visibility: 'Visibility.Visible', opacity: 0.75, content: 'raw-inspector-proof' });
  assert.deepEqual(startup.inspectorTreeDimensions, { width: 114, height: 228 });
  assert.equal(startup.tree.width, 400);
  assert.equal(startup.tree.height, 800);
  assert.equal(persisted.status, 'not_scored');
  assert.deepEqual(persisted.observed, {});
});

test('click, doubleClick and action10 call Component only; no navigation success is projected', async () => {
  const f = await fixture();
  await f.augment(f.bridge);
  await f.bridge.ui.click('successor');
  await f.bridge.ui.doubleClick('successor');
  await f.bridge.ui.sendEvent('successor', 10, {});
  assert.deepEqual(f.log.filter(value => /^(click|doubleClick):/.test(value)), ['click:successor', 'doubleClick:successor', 'click:successor']);
  await assert.rejects(f.bridge.ui.sendEvent('successor', 11, {}), /only parameterless click/);
  await assert.rejects(f.bridge.ui.sendEvent('successor', 10, { x: 1 }), /only parameterless click/);
  const actions = f.bridge.deviceUi.evidence.filter(event => event.method === 'afterUiAction');
  assert.equal(actions.length, 3);
  assert.ok(actions.every(event => event.semanticSuccess === null));
  assert.equal(f.bridge.roomUpgrade, f.observer);
  await f.bridge.dispose();
});

test('ambiguous, disabled, offscreen and non-candidate controls cannot be clicked', async () => {
  for (const options of [{ duplicate: true }, { enabled: false }, { offscreen: true }, { wrongRoute: true }]) {
    const f = await fixture(options);
    await f.augment(f.bridge);
    if (options.wrongRoute) f.setRoute({ path: 'pages/', name: 'TestHost' });
    await assert.rejects(f.bridge.ui.click('successor'));
    assert.equal(f.log.some(value => value.startsWith('click:')), false);
    await f.bridge.dispose();
  }
});

test('missing cold create is unsupported and restores observer; never reuses warm UI', async () => {
  const f = await fixture({ warm: true, timeoutMs: 5 });
  await assert.rejects(f.augment(f.bridge), /cold-start\/UIContext unavailable/);
  assert.equal(f.log.includes('window:context'), false);
  assert.equal(f.bridge.roomUpgrade, undefined);
  assert.equal(f.bridge.ui, f.originalUi);
  assert.equal(f.bridge.capabilities.deviceUI.available, false);
  assert.deepEqual(f.log.slice(-3), ['monitor:remove', 'lifecycle:remove', 'observer:dispose']);
});

test('installer changes generated evaluator only and rejects duplicate/non-device installation', () => {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'Tasks08_11DeviceUi-'));
  const write = (file, source) => { const full = path.join(work, file); fs.mkdirSync(path.dirname(full), { recursive: true }); fs.writeFileSync(full, source); };
  try {
    write('AppScope/app.json5', JSON.stringify({ app: { bundleName: 'candidate.test' } }));
    write('entry/src/main/module.json5', JSON.stringify({ module: { name: 'entry', mainElement: 'EntryAbility',
      abilities: [{ name: 'EntryAbility' }], pages: '$profile:main_pages' } }));
    write('entry/src/main/resources/base/profile/main_pages.json', JSON.stringify({ src: ['pages/Index'] }));
    const main = 'entry/src/main/ets/pages/Index.ets';
    write(main, '// candidate byte preservation marker\n');
    const bundleFile = 'entry/src/test/native-bundle.js';
    const bundle = "import { createNativeContext } from './native-device-platform';\n" +
      "import { installConfiguredRoomObserver } from './Tasks08_11RoomObserver';\n" +
      'async function run(bridge) { bridge.roomUpgrade = installConfiguredRoomObserver();\n' +
      'if (candidateUI) await bridge.ui.navigate(candidateUI.route); }\n';
    write(bundleFile, bundle);
    const originalSuite = "import { RoomUpgradePresenter as Tasks08_11Presenter } from '../main/ets/features/RoomUpgradeFeature';\n" +
      "import { configureRoomObserver } from './Tasks08_11RoomObserver';\n" +
      'export default function suite(): void { configureRoomObserver(Tasks08_11Presenter); }\n';
    write('entry/src/test/NativeBundle.test.ets', originalSuite);
    const before = fs.readFileSync(path.join(work, main));
    const report = install(work, { json5: JSON });
    assert.equal(report.config.bundleName, 'candidate.test');
    assert.equal(report.modules.length, 4);
    assert.equal(report.config.productionModuleUrl, '@bundle:candidate.test/entry/ets/features/RoomUpgradeFeature');
    assert.equal(report.config.presenterExport, 'RoomUpgradePresenter');
    assert.equal(report.config.originalModuleImportMode, 'disabled');
    const generated = fs.readFileSync(path.join(work, bundleFile), 'utf8');
    assert.ok(generated.includes('await augment(bridge);'));
    assert.ok(generated.indexOf('await augment(bridge);') < generated.indexOf('await bridge.ui.navigate'));
    assert.equal(generated.includes('bridge.roomUpgrade ='), false);
    const suite = fs.readFileSync(report.suiteFile, 'utf8');
    assert.ok(suite.includes('configureDeviceUi({'));
    assert.equal(suite.includes('../main/ets/features/'), false);
    assert.equal(suite.includes('Tasks08_11Presenter'), false);
    assert.equal(suite.includes('configureRoomObserver'), false);
    assert.deepEqual(fs.readFileSync(path.join(work, main)), before);
    assert.throws(() => install(work, { json5: JSON }), /already installed/);
    for (const mode of ['after-page-ready', 'after-page-ready-diagnostic', 'before-start']) {
      write(bundleFile, bundle);
      write('entry/src/test/NativeBundle.test.ets', originalSuite);
      if (mode === 'before-start') {
        assert.throws(() => install(work, { json5: JSON, originalModuleImportMode: mode }), /pre-start import caused ArkVM fatal/);
      } else {
        assert.equal(install(work, { json5: JSON, originalModuleImportMode: mode }).config.originalModuleImportMode, mode);
      }
      assert.deepEqual(fs.readFileSync(path.join(work, main)), before);
    }
    write(bundleFile, bundle.replace('native-device-platform', 'native-platform'));
    assert.throws(() => install(work, { json5: JSON }), /not Previewer/);
  } finally { fs.rmSync(work, { recursive: true, force: true }); }
});

test('original OHM binder wraps actual imported class without constructing or calling it', async () => {
  const { createOriginalRoomObserverFactory } = await binding;
  const { installRoomObserver } = await observerModule;
  let constructed = 0;
  class RoomUpgradePresenter {
    constructor() { constructed++; }
    roomListPreview() { return 'original preview'; }
  }
  const config = { bundleName: 'candidate.test', moduleName: 'entry',
    productionModuleUrl: '@bundle:candidate.test/entry/ets/features/RoomUpgradeFeature', presenterExport: 'RoomUpgradePresenter',
    originalModuleImportMode: 'after-page-ready-diagnostic', entryRoute: 'pages/Index' };
  const requested = [];
  const original = RoomUpgradePresenter.prototype.roomListPreview;
  const createObserver = createOriginalRoomObserverFactory(config, async url => {
    requested.push(url); return { RoomUpgradePresenter };
  }, installRoomObserver);
  const observer = await createObserver({ available: true, anchor: { id: 'current_room_id', inDriverTree: true }, snapshot: { routeName: 'pages/Index' } });
  assert.deepEqual(requested, [config.productionModuleUrl]);
  assert.equal(constructed, 0);
  assert.equal(observer.read().available, false);
  assert.equal(observer.binding.importCompleted, true);
  assert.equal(observer.binding.receiverObserved, false);
  assert.deepEqual(observer.binding.wrappedNames, ['roomListPreview']);
  assert.equal(observer.binding.prototypeDescriptors.roomListPreview.configurable, true);
  assert.equal(observer.binding.prototypeDescriptors.roomListPreview.valueType, 'function');
  const actual = new RoomUpgradePresenter();
  assert.equal(actual.roomListPreview(), 'original preview');
  assert.equal(observer.read().available, true);
  observer.dispose();
  assert.equal(RoomUpgradePresenter.prototype.roomListPreview, original);
});

test('original OHM binder refuses test namespace, failed import and zero eligible descriptors', async () => {
  const { createOriginalRoomObserverFactory } = await binding;
  const { installRoomObserver } = await observerModule;
  const config = { bundleName: 'candidate.test', moduleName: 'entry',
    productionModuleUrl: '@bundle:candidate.test/entry/ets/features/RoomUpgradeFeature', presenterExport: 'RoomUpgradePresenter',
    originalModuleImportMode: 'after-page-ready-diagnostic', entryRoute: 'pages/Index' };
  const readiness = { available: true, anchor: { id: 'current_room_id', inDriverTree: true }, snapshot: { routeName: 'pages/Index' } };
  assert.throws(() => createOriginalRoomObserverFactory({ ...config,
    productionModuleUrl: '@bundle:candidate.test/entry_test@entry/ets/features/RoomUpgradeFeature' }, () => {}, installRoomObserver), /candidate manifest/);
  await assert.rejects(createOriginalRoomObserverFactory(config, async () => { throw new Error('not installed'); }, installRoomObserver)(readiness), /Original app dynamic import failed.*not installed/);
  class RoomUpgradePresenter {}
  await assert.rejects(createOriginalRoomObserverFactory(config, async () => ({ RoomUpgradePresenter }), installRoomObserver)(readiness), /wrapped no prototype members/);
});

test('default disabled binding never imports or manufactures an observed receiver', async () => {
  const { createOriginalRoomObserverFactory } = await binding;
  const never = () => assert.fail('Disabled binding must not import or instrument');
  const observer = await createOriginalRoomObserverFactory({}, never, never)();
  assert.equal(observer.read().available, false);
  assert.match(observer.read().reason, /disabled after native ArkVM fatal/);
  observer.dispose();
});

test('post-page diagnostic binds only after real transport readiness and never captures a receiver itself', async () => {
  const f = await fixture({ originalModuleImportMode: 'after-page-ready-diagnostic' });
  await f.augment(f.bridge);
  assert.ok(f.log.indexOf('ability:start') < f.log.indexOf('observer:install'));
  assert.ok(f.log.indexOf('window:getUIContext') < f.log.indexOf('observer:install'));
  assert.equal(f.bridge.roomUpgrade.read().available, false);
  const installed = f.bridge.deviceUi.evidence.find(event => event.method === 'observerInstalled');
  assert.equal(installed.beforeAbilityStart, false);
  assert.equal(f.bridge.deviceUi.evidence.filter(event => event.method === 'beforeOriginalModuleImport').length, 1);
  assert.equal(f.log.filter(value => value === 'click:room_list_tombstoned_room').length, 1);
  const capture = f.bridge.deviceUi.evidence.find(event => event.method === 'diagnosticReceiverCapture');
  assert.equal(capture.capturedSelectOldRoom, false);
  assert.equal(capture.semanticVerdict, null);
  assert.match(f.bridge.roomUpgrade.read().reason, /diagnostic only/);
  await f.bridge.dispose();
  const empty = await fixture({ originalModuleImportMode: 'after-page-ready-diagnostic', queryResult: null, noInspector: true });
  await assert.rejects(empty.augment(empty.bridge), /not ready for diagnostic import/);
  assert.equal(empty.log.includes('observer:install'), false);
});

test('explicit diagnostic import still refuses to run without a real page readiness observation', async () => {
  const { createOriginalRoomObserverFactory } = await binding;
  let imports = 0;
  const factory = createOriginalRoomObserverFactory({ bundleName: 'candidate.test', moduleName: 'entry',
    productionModuleUrl: '@bundle:candidate.test/entry/ets/features/RoomUpgradeFeature', presenterExport: 'RoomUpgradePresenter',
    originalModuleImportMode: 'after-page-ready-diagnostic', entryRoute: 'pages/Index' }, async () => { imports++; }, () => {});
  await assert.rejects(factory(), /requires an observed original candidate room page/);
  assert.equal(imports, 0);
});

test('scored opt-in rejects every non-allowlisted case before startup/import, regardless of role', async () => {
  for (const caseId of ['ru_state_003_open_successor', '11_room_upgrade_navigation:final:ru_state_003_open_successor',
    '18_other:final:ru_state_005_room_list_tombstone_preview', 'unknown']) {
    const f = await fixture({ originalModuleImportMode: 'after-page-ready', caseId });
    await assert.rejects(f.augment(f.bridge), /only bound for task11 canonical cases005\/007/);
    assert.deepEqual(f.log, []);
  }
});

test('scored opt-in requires an actual captured receiver and matching rendered room, not click completion', async () => {
  const caseId = 'ru_state_005_room_list_tombstone_preview';
  for (const state of [{ available: false }, { available: true, instanceId: 1, currentRoomId: '!room', calls: [] },
    { available: true, instanceId: 1, currentRoomId: '!different', calls: [{ instanceId: 1, method: 'selectOldRoom' }] }]) {
    const f = await fixture({ originalModuleImportMode: 'after-page-ready', caseId,
      observer: { read: () => state, dispose() {} } });
    await assert.rejects(f.augment(f.bridge), /not established by real setup click/);
    assert.equal(f.log.filter(value => value === 'click:room_list_tombstoned_room').length, 1);
    assert.equal(f.bridge.roomUpgrade, undefined);
  }
});

test('scored opt-in preserves the original observer for base/final/agent without inventing a verdict', async () => {
  for (const role of ['base', 'final', 'agent']) {
    let captured = false;
    const state = { available: true, instanceId: 2, currentRoomId: '!room',
      calls: [{ instanceId: 2, method: 'selectRoom' }] };
    const observer = { read: () => captured ? state : { available: false }, dispose() {} };
    const f = await fixture({ originalModuleImportMode: 'after-page-ready',
      caseId: `11_room_upgrade_navigation:${role}:ru_state_007_predecessor_banner`, observer,
      onClick: () => { captured = true; } });
    await f.augment(f.bridge);
    assert.equal(f.bridge.roomUpgrade, observer);
    assert.equal(f.bridge.roomUpgrade.read(), state);
    const capture = f.bridge.deviceUi.evidence.find(event => event.method === 'setupReceiverCapture');
    assert.equal(capture.semanticVerdict, null);
    assert.equal(capture.canonicalSetupVerified, false);
    assert.equal(capture.capturedSelectOldRoom, false, 'Alternative actual callback names are allowed');
    assert.ok(f.log.indexOf('ability:start') < f.log.indexOf('observer:install'));
    assert.ok(f.log.indexOf('observer:install') < f.log.indexOf('click:room_list_tombstoned_room'));
    await f.bridge.dispose();
  }
});

test('diagnostic mode remains unscored even with successful real-callback transport capture', async () => {
  let captured = false;
  const state = { available: true, instanceId: 1, currentRoomId: '!room',
    calls: [{ instanceId: 1, method: 'selectOldRoom' }] };
  const f = await fixture({ originalModuleImportMode: 'after-page-ready-diagnostic',
    observer: { read: () => captured ? state : { available: false }, dispose() {} },
    onClick: () => { captured = true; } });
  await f.augment(f.bridge);
  assert.equal(f.bridge.deviceUi.evidence.find(event => event.method === 'diagnosticReceiverCapture').capturedSelectOldRoom, true);
  assert.equal(f.bridge.roomUpgrade.read().available, false);
  assert.match(f.bridge.roomUpgrade.read().reason, /diagnostic only/);
  await f.bridge.dispose();
});

test('scored opt-in does not import when the original page root is unobserved', async () => {
  const f = await fixture({ originalModuleImportMode: 'after-page-ready',
    caseId: 'ru_state_005_room_list_tombstone_preview', queryResult: null, noInspector: true });
  await assert.rejects(f.augment(f.bridge), /not ready/);
  assert.equal(f.log.includes('observer:install'), false);
  assert.equal(f.log.some(value => value.startsWith('click:')), false);
});

// Real transpiled production state + OS transport doubles. These assertions
// check evaluator gating, not native rendering or device module-cache behavior.
async function runScoredAdapter(caseId, options = {}) {
  const root = path.resolve(__dirname, '../../../..');
  const taskId = '11_room_upgrade_navigation';
  const { productionLoader } = require('../../../../scripts/runtime_semantics/arkts_runtime.cjs');
  const { runCase } = require('../tasks08_11.cjs');
  const task = JSON.parse(fs.readFileSync(path.join(root, `benchmark_tasks/${taskId}/task.json`)));
  const project = path.join(root, task.arkts.finalPath);
  const load = productionLoader(project, [], []);
  const m = load('entry/src/main/ets/features/RoomUpgradeFeature.ets');
  const p = new m.RoomUpgradePresenter(new m.RoomNavigationGateway());
  const { createOriginalRoomObserverFactory } = await binding;
  const { installRoomObserver } = await observerModule;
  const createObserver = createOriginalRoomObserverFactory({ bundleName: 'candidate.test', moduleName: 'entry',
    entryRoute: 'pages/Index', originalModuleImportMode: 'after-page-ready',
    productionModuleUrl: '@bundle:candidate.test/entry/ets/features/RoomUpgradeFeature', presenterExport: 'RoomUpgradePresenter' },
  async () => m, installRoomObserver);
  const f = await fixture({ caseId, originalModuleImportMode: 'after-page-ready', createObserver,
    hiddenIds: options.hiddenIds,
    text: id => id === 'room_list_tombstoned_room' ? p.roomListPreview(p.oldRoom) : p.currentRoom.roomId,
    onClick: id => {
      if (id === 'room_list_tombstoned_room') p.selectOldRoom();
      else if (id === 'room_list_replacement_room') p.selectReplacementRoom();
      else assert.fail('Unexpected unit transport click: ' + id);
    } });
  try {
    await f.augment(f.bridge);
    const cases = JSON.parse(fs.readFileSync(path.join(root, `benchmark_tasks/${taskId}/transitions.json`))).cases;
    const canonical = cases.find(item => item.caseId === caseId);
    const caseSpec = { ...canonical, given: { ...canonical.given, ...options.given } };
    const result = await runCase({ taskId, project, caseSpec, load, native: f.bridge });
    return { result, canonical, log: f.log.slice(), state: f.bridge.roomUpgrade.read() };
  } finally { await f.bridge.dispose(); }
}

test('005/007 scored handoff runs existing canonical given checks, observations and all invariants', async () => {
  for (const caseId of ['ru_state_005_room_list_tombstone_preview', 'ru_state_007_predecessor_banner']) {
    const { result, canonical, log } = await runScoredAdapter(caseId);
    assert.equal(result.unsupported, undefined);
    assert.deepEqual(result.observed, canonical.expected);
    assert.deepEqual(result.invariantChecks.map(check => check.description), canonical.invariants);
    assert.ok(result.invariantChecks.every(check => check.passed === true));
    assert.ok(result.evidence.some(event => event.label === 'before:event'));
    assert.ok(result.evidence.some(event => event.label === 'after:event'));
    if (caseId.includes('007')) assert.ok(log.includes('click:room_list_replacement_room'));
  }
});

test('successful binding does not score incorrect canonical givens or turn absent UI into a pass', async () => {
  for (const [caseId, given, reason] of [
    ['ru_state_005_room_list_tombstone_preview', { lastMessage: 'not the real history' }, /last message is not established/],
    ['ru_state_005_room_list_tombstone_preview', { successorRoomId: '!wrong' }, /successor metadata is not established/],
    ['ru_state_007_predecessor_banner', { predecessorRoomId: '!wrong' }, /predecessor room is not established/]
  ]) {
    const { result } = await runScoredAdapter(caseId, { given });
    assert.match(result.unsupported, reason);
    assert.equal(result.invariantChecks.length, 0);
  }
  const { result } = await runScoredAdapter('ru_state_007_predecessor_banner',
    { hiddenIds: ['predecessor_room_banner', 'room_beginning_content'] });
  assert.equal(result.unsupported, undefined);
  assert.equal(result.observed.predecessorBannerVisible, false);
  assert.equal(result.invariantChecks[0].passed, false);
  assert.ok(result.notes.some(note => note.kind === 'runtime_contract_mismatch'));
});
