'use strict';
// Local evaluator tests only: transport doubles never count as device UI proof.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '../../../..');
const { productionLoader } = require('../../../../scripts/runtime_semantics/arkts_runtime.cjs');
const { install } = require('./Task14DeviceUi.install.cjs');
const contract = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks/14_join_room_by_address/transitions.json')));
const task = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks/14_join_room_by_address/task.json')));
const data = source => 'data:text/javascript;base64,' + Buffer.from(source).toString('base64');
const urls = new Map();
function url(file) {
  if (urls.has(file)) return urls.get(file);
  const source = fs.readFileSync(path.join(__dirname, file), 'utf8').replace(/from '\.\/(Task14[^']+)'/g,
    (_, name) => 'from ' + JSON.stringify(url(name + '.js')));
  const result = data(source); urls.set(file, result); return result;
}
const loadModule = file => import(url(file));
const freshProduction = () => productionLoader(path.join(root, task.arkts.finalPath), [], [])('entry/src/main/ets/features/JoinRoomByAddressFeature.ets');
const caseFor = key => contract.cases.find(spec => spec.key === key);
const config = { mode: 'after-page-ready', bundleName: 'actual.candidate', moduleName: 'entry', abilityName: 'EntryAbility',
  entryRoute: 'pages/Index', allowedRoutes: ['pages/Index'], presenterLoadedByEntry: true,
  productionModuleUrl: '@bundle:actual.candidate/entry/ets/features/JoinRoomByAddressFeature', productionSources: [] };

test('observer does not create a receiver; retains return/throw/Promise identity and restores descriptors', async () => {
  const { installTask14Observer } = await loadModule('Task14PageObserver.js');
  const promise = Promise.resolve('unchanged');
  let constructions = 0;
  class JoinRoomByAddressPresenter {
    constructor() { constructions++; this.addressState = 'unknown'; }
    updateAddress() { return promise; }
    visibleAddressState() { return this.addressState; }
    throws() { throw new Error('original error'); }
  }
  const before = Object.getOwnPropertyDescriptors(JoinRoomByAddressPresenter.prototype);
  const observer = installTask14Observer({ JoinRoomByAddressPresenter });
  assert.equal(constructions, 0);
  assert.equal(observer.read().available, false);
  const original = new JoinRoomByAddressPresenter();
  assert.equal(original.updateAddress(), promise);
  assert.throws(() => original.throws(), /original error/);
  const length = observer.read().calls.length;
  assert.equal(observer.read().calls.length, length, 'Reading must not synthesize calls');
  assert.equal(observer.read().visibleAddressState, undefined);
  original.visibleAddressState();
  assert.equal(observer.read().visibleAddressState, 'unknown');
  observer.dispose(); observer.dispose();
  assert.deepEqual(Object.getOwnPropertyDescriptors(JoinRoomByAddressPresenter.prototype), before);
});

async function scenario(key, options = {}) {
  const { runTask14Transition } = await loadModule('Task14DeviceUi.suite.js');
  const m = freshProduction();
  const nav = new m.JoinRoomNavigator();
  const p = new m.JoinRoomByAddressPresenter(new m.DemoRoomAliasResolver(), nav);
  let displayed = 'unknown', imported = false;
  const actions = [], imports = [], records = [], traces = [];
  const refresh = () => { displayed = p.visibleAddressState(); };
  const controls = names => Object.fromEntries(Object.keys(names).map(name => {
    const form = nav.addressFlowVisible;
    const rootControl = ['root', 'search', 'entry', 'create', 'dmAlice', 'dmBob', 'dmCharlie'].includes(name);
    let present = rootControl ? !form : form;
    if (name.startsWith('dm')) present = !form && Boolean(options.people);
    if (name === 'invalid') present = form && displayed === 'invalid' && !options.hideError;
    if (name === 'notFound') present = form && displayed === 'room_not_found' && !options.hideError;
    if (name === 'resolving') present = form && displayed === 'resolving';
    return [name, { selector: names[name][0], name, present, visible: present, enabled: true, focused: false, clickable: true,
      id: names[name][0].id || '', inspectorMatches: present ? 1 : 0,
      bounds: { left: 10, top: 40, right: 390, bottom: 90 },
      text: name === 'input' ? p.address : name === 'search' ? options.searchText || '' : name }];
  }));
  const session = {
    observe: async (label, selectors) => ({ label, available: true, routeName: 'pages/Index', windowId: 10,
      stackLength: 1, tree: { unitTransportDouble: true }, controls: controls(selectors) }),
    action: async (kind, control, value) => {
      actions.push({ kind, name: control.name, value });
      if (control.name === 'entry') { nav.showJoinRoomByAddress(); refresh(); }
      else if (kind === 'input') {
        assert.equal(imported, true, 'Input captures original receiver only after page-ready binding');
        p.updateAddress(value).then(refresh);
        displayed = 'unknown';
      } else if (control.name === 'continue') { p.continue(); refresh(); }
      else if (control.name === 'cancel') { p.dismiss(); refresh(); }
      else assert.fail('Unexpected transport event');
    },
    delay: ms => new Promise(resolve => setTimeout(resolve, ms))
  };
  session.observeBracketed = async (label, selectors, readState) => {
    const stateBefore = readState();
    const view = await session.observe(label, selectors);
    view.tree = { $type: 'Column', $children: Object.values(view.controls).filter(c => c.present).map((c, i) => ({
      $type: c.selector.type || (['search', 'input'].includes(c.name) ? 'TextInput' : 'Button'), $ID: i + 1,
      $rect: '[10,40],[390,90]', $attrs: { id: c.id, content: c.selector.text, visibility: 'Visibility.Visible', opacity: 1 }
    })) };
    return { ...view, stateBefore, stateAfter: readState(), bracketEnd: { tree: view.tree, windowId: view.windowId, routeName: view.routeName } };
  };
  const original = caseFor(key);
  const spec = { ...original, given: { ...original.given, ...options.given } };
  const result = await runTask14Transition(spec, { ...config, ...options.config }, session, async requested => {
    imports.push(requested); imported = true;
    assert.equal(nav.addressFlowVisible, key !== 'entry_opens_address_flow');
    return m;
  }, event => records.push(event), (label, state) => traces.push({ label, state }));
  return { result, records, traces, actions, imports, p, nav, spec };
}

test('entry uses actual receiver and preserves the final missing-DM invariant failure', async () => {
  const { result, actions, imports, traces } = await scenario('entry_opens_address_flow');
  assert.equal(result.unsupported, undefined);
  assert.deepEqual(result.observed, caseFor('entry_opens_address_flow').expected);
  assert.equal(result.invariantChecks[0].passed, false);
  assert.match(result.notes[0].reason, /no existing Alice/);
  assert.equal(imports.length, 1);
  assert.deepEqual(actions.map(action => action.name), ['entry', 'cancel']);
  assert.ok(traces.some(event => event.label === 'before:event'));
  assert.ok(traces.some(event => event.label === 'after:event'));
});

test('clickable people controls never certify genuine create-room/DM actions', async () => {
  const { result } = await scenario('entry_opens_address_flow', { people: true });
  assert.deepEqual(result.observed, caseFor('entry_opens_address_flow').expected);
  assert.match(result.unsupported, /local selection is not a DM action/);
  assert.equal(result.invariantChecks.length, 0);
  assert.equal(result.unsupportedInvariants.length, 1);
  assert.ok(result.notes.some(note => note.kind === 'actual_feature_migration_gap'));
  assert.ok(result.evidence.some(e => e.label === 'Task14.partialActionAvailability' && e.data.controlsAvailable));
});

test('invalid input uses real production state and observed error, not a missing model getter', async () => {
  const { result, p, actions } = await scenario('invalid_after_continue');
  assert.equal(result.unsupported, undefined);
  assert.deepEqual(result.observed, caseFor('invalid_after_continue').expected);
  assert.equal(result.invariantChecks[0].passed, true);
  assert.equal(p.validationRequested, true);
  assert.deepEqual(actions.map(action => action.name), ['entry', 'input', 'continue']);
  const hidden = await scenario('invalid_after_continue', { hideError: true });
  assert.equal(hidden.result.unsupported, undefined);
  assert.equal(hidden.result.observed.addressState, 'invalid');
  assert.equal(hidden.result.observed.errorVisible, false, 'UI absence must not mirror the internal state');
});

test('not-found holds only the same-page external resolver, validates pending given and performs retry input', async () => {
  const resolverModuleUrl = '@bundle:actual.candidate/entry/ets/features/JoinRoomRuntime';
  const { result, actions, records, imports, p } = await scenario('not_found_recovers', {
    config: { resolverModuleUrl }
  });
  assert.equal(result.unsupported, undefined);
  assert.deepEqual(result.observed, caseFor('not_found_recovers').expected);
  assert.equal(result.invariantChecks[0].passed, true);
  assert.equal(p.address, '#retry:example.org');
  assert.deepEqual(actions.map(action => action.name), ['entry', 'input', 'continue', 'input']);
  assert.equal(records.filter(event => event.method === 'Task14.externalResolverRequested').length, 1);
  const givens = records.find(event => event.method === 'Task14.givenChecks');
  assert.ok(givens.checks.every(check => check.established));
  const rejected = records.find(event => event.method === 'Task14.externalResolverRejected');
  assert.equal(rejected.alias, '#missing:example.org');
  assert.deepEqual(imports, [config.productionModuleUrl, resolverModuleUrl]);
});

test('bad givens stay unsupported; separate-page entry is not imported before its production module loads', async () => {
  const wrong = await scenario('invalid_after_continue', { given: { validationRequested: true } });
  assert.match(wrong.result.unsupported, /Canonical given not established: validationRequested/);
  assert.equal(wrong.actions.some(action => action.name === 'continue'), false);
  const notLoaded = await scenario('entry_opens_address_flow', { config: { presenterLoadedByEntry: false } });
  assert.match(notLoaded.result.unsupported, /not in the already-loaded/);
  assert.equal(notLoaded.imports.length, 0);
  const badSearch = await scenario('entry_opens_address_flow', { searchText: 'active search' });
  assert.match(badSearch.result.unsupported, /Canonical given not established: searchActive/);
  assert.equal(badSearch.imports.length, 0);
});

test('independent installer changes only generated evaluator, leaves shared adapters/factories untouched', () => {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'Task14DeviceUi-'));
  const write = (file, value) => { const full = path.join(work, file); fs.mkdirSync(path.dirname(full), { recursive: true }); fs.writeFileSync(full, value); };
  try {
    fs.cpSync(path.join(root, task.arkts.finalPath, 'entry/src/main'), path.join(work, 'entry/src/main'), { recursive: true });
    fs.cpSync(path.join(root, task.arkts.finalPath, 'AppScope'), path.join(work, 'AppScope'), { recursive: true });
    const bundle = "import { createNativeContext } from './native-device-platform';\nconst factories = { untouched: true };\n" +
      "async function run() { if (candidateUI) await bridge.ui.navigate(candidateUI.route);\n" +
      'const adapter = { runCase: context => module.exports.runCase({ ...context, native: bridge, context: { native: bridge } }) }; }\n';
    write('entry/src/test/native-bundle.js', bundle);
    write('entry/src/test/NativeBundle.test.ets', 'export default function nativeBundleTests(): void {}');
    const report = install(work, { mode: 'after-page-ready' });
    assert.equal(report.productionUnchanged, true);
    assert.equal(report.config.presenterLoadedByEntry, true);
    assert.equal(report.config.peopleModuleUrl, undefined, 'New DM flow must not bind the legacy Selected observer');
    assert.match(report.config.productionModuleUrl, /\/entry\/ets\/features\/JoinRoomByAddressFeature$/);
    assert.match(report.config.resolverModuleUrl, /\/entry\/ets\/features\/JoinRoomRuntime$/,
      'Device resolver fixture must bind the resolver class instantiated by the real page');
    assert.equal(report.fixtures.length, 12);
    for (const name of ['Task14RealFlowV2Observer.js', 'Task14RealFlowV2Frame.js',
      'Task14RealFlowV2.suite.js', 'Task14RealFlowV2.adapter.js']) {
      assert.ok(report.fixtures.some(item => item.path.endsWith('/' + name)));
    }
    const generated = fs.readFileSync(report.bundleFile, 'utf8');
    assert.ok(generated.includes('bridge.evaluateTask14UI || module.exports.runCase'));
    assert.ok(generated.includes('const factories = { untouched: true };'));
    assert.ok(!generated.includes('require('));
    assert.throws(() => install(work), /already installed/);
    for (const source of report.production) assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(work, source.path))).digest('hex'), source.sha256);
  } finally { fs.rmSync(work, { recursive: true, force: true }); }
});

test('installer can bind a reviewed candidate owner class without changing production', () => {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'Task14DeviceUi-owner-'));
  const write = (file, value) => { const full = path.join(work, file); fs.mkdirSync(path.dirname(full), { recursive: true }); fs.writeFileSync(full, value); };
  try {
    fs.cpSync(path.join(root, task.arkts.finalPath, 'entry/src/main'), path.join(work, 'entry/src/main'), { recursive: true });
    fs.cpSync(path.join(root, task.arkts.finalPath, 'AppScope'), path.join(work, 'AppScope'), { recursive: true });
    const old = path.join(work, 'entry/src/main/ets/features/JoinRoomByAddressFeature.ets');
    const renamed = path.join(work, 'entry/src/main/ets/features/CandidateOwner.ets');
    fs.copyFileSync(old, renamed);
    fs.writeFileSync(renamed, fs.readFileSync(renamed, 'utf8').replaceAll('JoinRoomByAddressPresenter', 'CandidateOwner'));
    write('entry/src/test/native-bundle.js', "import { createNativeContext } from './native-device-platform';\n" +
      "async function run() { if (candidateUI) await bridge.ui.navigate(candidateUI.route);\n" +
      'const adapter = { runCase: context => module.exports.runCase({ ...context, native: bridge, context: { native: bridge } }) }; }\n');
    write('entry/src/test/NativeBundle.test.ets', 'export default function nativeBundleTests(): void {}');
    const report = install(work, { mode: 'after-page-ready', presenterClass: 'CandidateOwner' });
    assert.equal(report.config.presenterClass, 'CandidateOwner');
    assert.match(report.config.presenterSourcePath, /CandidateOwner\.ets$/);
    assert.equal(report.productionUnchanged, true);
  } finally { fs.rmSync(work, { recursive: true, force: true }); }
});

async function coreFixture(options = {}) {
  const { startTask14Page } = await loadModule('Task14DeviceUi.core.js');
  const events = [], actions = [];
  let monitor, lifecycle;
  const info = { bundleName: config.bundleName, moduleName: config.moduleName, name: config.abilityName };
  const ability = { context: { abilityInfo: info } };
  const viewport = { left: 0, top: 20, right: 400, bottom: 820 };
  const properties = { id: 13, windowRect: { left: 0, top: 20, width: 400, height: 800 } };
  const tree = options.tree || { $type: 'Column', $children: [{ $type: 'TextInput', $attrs: { id: 'room_address_input',
    visibility: 'Visibility.Visible', ...(options.noOpacity ? {} : { opacity: 1 }) } }] };
  const component = {
    getId: async () => 'room_address_input', getText: async () => '#example:server', getType: async () => 'TextInput',
    getBounds: async () => ({ left: 10, top: 40, right: 390, bottom: 90 }),
    isEnabled: async () => true, isFocused: async () => false, isClickable: async () => true,
    inputText: async value => actions.push(['input', value]), click: async () => actions.push(['click'])
  };
  const ports = {
    getDelegator: () => ({
      addAbilityMonitor: async m => { monitor = m; events.push('monitor'); },
      removeAbilityMonitor: async () => { events.push('remove'); },
      startAbility: async () => {
        events.push('start'); monitor.onAbilityCreate(ability); monitor.onAbilityForeground(ability);
        lifecycle.onWindowStageCreate(ability, { getMainWindow: async () => ({ getWindowProperties: () => properties }) });
      },
      getCurrentTopAbility: async () => ability
    }),
    getApplicationContext: () => ({ on: (name, value) => { lifecycle = value; events.push('lifecycle'); return 4; },
      off: async () => events.push('off') }),
    getLastWindow: async () => ({ getWindowProperties: () => options.dialog ? { ...properties, id: 14 } : properties,
      getUIContext: () => ({ getHostContext: () => options.foreign ? { abilityInfo: { ...info, bundleName: 'foreign' } } : ability.context,
        getRouter: () => ({ getState: () => ({ path: 'pages/', name: 'Index' }), getLength: () => 1 }),
        runScopedTask: fn => fn() }) }),
    createDriver: () => ({ findWindow: async () => ({ getBundleName: async () => config.bundleName,
      isFocused: async () => true, getBounds: async () => viewport }),
      findComponents: async spec => options.components ? options.components(spec) : 'query' in options ? options.query : [component] }),
    getInspectorTree: () => options.emptyTree ? {} : tree,
    selector: spec => spec,
    delay: async () => { if (options.dialog || options.foreign || options.emptyTree) throw new Error('Stop bounded startup: ' + events[events.length - 1]); }
  };
  return { start: () => startTask14Page(ports, config, event => events.push(event.method)), events, actions };
}

test('independent native core requires positive original stage/tree and dispatches actual Component input', async () => {
  const f = await coreFixture();
  const session = await f.start();
  const frame = await session.observe('form', { input: [{ id: 'room_address_input' }] });
  assert.equal(frame.controls.input.visible, true);
  assert.equal(frame.controls.input.enabled, true);
  assert.equal(frame.windowId, 13);
  await session.action('input', frame.controls.input, 'not-a-room');
  assert.deepEqual(f.actions, [['input', 'not-a-room']]);
  assert.ok(f.events.indexOf('lifecycle') < f.events.indexOf('start'));
  await session.release();
  assert.deepEqual(f.events.slice(-2), ['remove', 'off']);
});

test('nullish queries and missing opacity never become positive UI evidence', async () => {
  for (const query of [null, undefined, []]) {
    const f = await coreFixture({ query });
    const session = await f.start();
    const frame = await session.observe('form', { input: [{ id: 'room_address_input' }], absent: [{ id: 'missing' }] });
    assert.equal(frame.controls.input.visible, undefined, 'Inspector-only presence does not prove Driver visibility');
    assert.equal(frame.controls.absent.visible, false);
    await assert.rejects(session.action('input', frame.controls.input, 'x'), /absent\/disabled/);
    await session.release();
  }
  const f = await coreFixture({ noOpacity: true });
  const session = await f.start();
  const frame = await session.observe('form', { input: [{ id: 'room_address_input' }] });
  assert.equal(frame.controls.input.present, true);
  assert.equal(frame.controls.input.visible, undefined);
  await session.release();
});

test('foreign context/dialog/empty original tree reject before a suite import can run', async () => {
  for (const options of [{ dialog: true }, { foreign: true }, { emptyTree: true }]) {
    const f = await coreFixture(options);
    await assert.rejects(f.start(), /Stop bounded startup/);
    assert.deepEqual(f.events.slice(-2), ['remove', 'off']);
    assert.deepEqual(f.actions, []);
  }
});

test('adapter defaults disabled and does not manufacture source calls or start the app', async () => {
  const { evaluateTask14UI } = await loadModule('Task14DeviceUi.adapter.js');
  const traces = [];
  const result = await evaluateTask14UI({ taskId: contract.taskId, caseSpec: caseFor('invalid_after_continue'),
    load: () => assert.fail('Disabled mode cannot load a domain fixture'), trace: label => traces.push(label) },
  { ...config, mode: 'disabled' }, {}, () => assert.fail('No native operation expected'));
  assert.match(result.unsupported, /disabled/);
  assert.deepEqual(traces, ['before:binding', 'before:event', 'after:event']);
  assert.equal(result.invariantChecks.length, 0);
});

test('live ancestry requires unique Driver geometry and observes original ancestor action separately', async () => {
  const attrs = { visibility: 'Visibility.Visible', opacity: 1 };
  const label = { $type: 'Text', $ID: 3, $rect: '[20,50],[80,70]', $attrs: { ...attrs, content: 'Alice' } };
  const row = { $type: 'Row', $ID: 2, $rect: '[10,40],[390,90]', $attrs: attrs, $children: [label] };
  const tree = { $type: 'Column', $children: [row] };
  const clicks = [];
  const component = (type, bounds, clickable) => ({
    getId: async () => '', getText: async () => type === 'Text' ? 'Alice' : '', getType: async () => type,
    getBounds: async () => bounds, isEnabled: async () => true, isFocused: async () => false,
    isClickable: async () => clickable, click: async () => clicks.push(type)
  });
  const text = component('Text', { left: 20, top: 50, right: 80, bottom: 70 }, false);
  const action = component('Row', { left: 10, top: 40, right: 390, bottom: 90 }, true);
  const unrelated = component('Row', { left: 10, top: 140, right: 390, bottom: 190 }, true);
  const f = await coreFixture({ tree, components: spec => spec.type === 'Text' ? [text] : [action, unrelated] });
  const session = await f.start();
  const selectors = { person: [{ type: 'Text', text: 'Alice', actionAncestor: true }] };
  const frame = await session.observe('people', selectors);
  assert.equal(frame.controls.person.clickable, false, 'Do not rewrite Text clickability');
  assert.equal(frame.controls.person.actionAncestor.clickable, true);
  assert.equal(frame.controls.person.actionAncestor.selector.inspectorId, 2);
  await session.action('click', frame.controls.person.actionAncestor);
  assert.deepEqual(clicks, ['Row']);
  row.$ID = 4;
  await assert.rejects(session.action('click', frame.controls.person.actionAncestor), /ancestor changed/);
  await session.release();
  const ambiguous = await coreFixture({ tree, components: spec => spec.type === 'Text' ? [text] : [action, action] });
  const other = await ambiguous.start();
  await assert.rejects(other.observe('people', selectors), /Ambiguous original UI selector/);
  await other.release();
});

test('ancestor visibility, enabled state and anchor geometry cannot be assumed', async () => {
  const { findActionAncestor } = await loadModule('Task14AncestorObserver.js');
  const label = { $type: 'Text', $ID: 3, $rect: '[20,50],[80,70]' };
  const tree = { $type: 'Row', $ID: 2, $rect: '[10,40],[390,90]', $children: [label] };
  const bounds = { left: 20, top: 50, right: 80, bottom: 70 };
  for (const failure of [{ visible: undefined }, { visible: false }, { enabled: false }, { clickable: false }, { present: false }]) {
    assert.equal(await findActionAncestor(tree, label, bounds, async () =>
      ({ present: true, visible: true, enabled: true, clickable: true, ...failure })), undefined);
  }
  assert.equal(await findActionAncestor(tree, label, { ...bounds, left: 30 }, async () => assert.fail('Geometry mismatch')), undefined);
});

test('historical Selected observer captures its original receiver; this is not the repaired DM flow', async () => {
  const { observePeopleSelection } = await loadModule('Task14AncestorObserver.js');
  const historical = path.join(root, 'experiment_results/runtime_transition_20261020/task14_repair/real_flow_v2/before/final');
  const source = 'entry/src/main/ets/features/CreateRoomBase.ets';
  assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(historical, source))).digest('hex'),
    '78adfd5c19c4b22de4012d6e962efc54e6855e6ba309fd59bc3fc40789977541');
  const m = productionLoader(historical, [], [])(source);
  const presenter = new m.CreateRoomBasePresenter();
  const original = Object.getOwnPropertyDescriptor(m.CreateRoomBasePresenter.prototype, 'selectPerson');
  const observer = observePeopleSelection(m, () => {});
  assert.deepEqual(observer.read(), []);
  assert.equal(presenter.selectPerson('Bob'), undefined);
  assert.equal(presenter.selectedPerson, 'Bob');
  assert.equal(observer.read()[0].before, '');
  assert.equal(observer.read()[0].after, 'Bob');
  assert.equal(observer.read()[0].receiverId, 1);
  observer.dispose();
  assert.deepEqual(Object.getOwnPropertyDescriptor(m.CreateRoomBasePresenter.prototype, 'selectPerson'), original);
});

function returnedFrame() {
  const tree = { $type: 'Column', $children: [{ $type: 'TextInput', $ID: 10, $rect: '[10,40],[390,90]',
    $attrs: { id: 'people_search_input', visibility: 'Visibility.Visible', opacity: 1 } }] };
  const state = { available: true, instanceId: 1, instanceCount: 1, addressFlowVisible: false };
  return { routeName: 'pages/Index', windowId: 13, tree, stateBefore: { ...state }, stateAfter: { ...state },
    bracketEnd: { tree: JSON.parse(JSON.stringify(tree)), routeName: 'pages/Index', windowId: 13 },
    controls: { search: { selector: { id: 'people_search_input' }, id: 'people_search_input', present: true, visible: true,
      inspectorMatches: 1, bounds: { left: 10, top: 40, right: 390, bottom: 90 } },
    input: { selector: { id: 'room_address_input' }, present: false, visible: false, inspectorMatches: 0 } } };
}

const returnedIdentity = { routeName: 'pages/Index', windowId: 13, instanceId: 1 };

test('bounded acquisition rejects captured mixed-page pattern and accepts only a fresh consistent frame', async () => {
  const { acquireReturnedFrame } = await loadModule('Task14FrameAcquisition.js');
  const stale = returnedFrame(), good = returnedFrame();
  stale.tree.$children[0].$attrs.id = 'room_address_input';
  const samples = [stale, good], records = [];
  const result = await acquireReturnedFrame({ observeBracketed: async () => samples.shift(),
    delay: () => assert.fail('No business delay or fixture event allowed') }, {}, () => {}, returnedIdentity,
  item => records.push(item), { now: () => 0 });
  assert.equal(result, good, 'Return the newly acquired frame, never relabel the stale one');
  assert.equal(records.length, 2);
  assert.equal(records[0].assessment.consistent, false);
  assert.equal(records[0].frame.tree.$children[0].$attrs.id, 'room_address_input');
  assert.equal(records[1].assessment.consistent, true);
});

test('returned acquisition remains unsupported for stale, ambiguous, present-address or wrong-receiver evidence', async () => {
  const { acquireReturnedFrame } = await loadModule('Task14FrameAcquisition.js');
  for (const change of [
    f => { f.tree.$children[0].$attrs.id = 'room_address_input'; },
    f => { f.tree.$children.push(f.tree.$children[0]); f.bracketEnd.tree = f.tree; },
    f => { f.controls.input.present = true; },
    f => { f.controls.search.visible = undefined; },
    f => { f.stateBefore.addressFlowVisible = true; },
    f => { f.stateAfter.addressFlowVisible = true; },
    f => { f.stateAfter.instanceId = 2; },
    f => { f.bracketEnd.windowId = 14; },
    f => { f.controls.search.bounds.left = 25; }
  ]) {
    const sample = returnedFrame(); change(sample);
    let count = 0;
    await assert.rejects(acquireReturnedFrame({ observeBracketed: async () => { count++; return sample; } },
      {}, () => {}, returnedIdentity, () => {}, { maxAttempts: 2, now: () => 0 }), /Bounded returned-start-chat/);
    assert.equal(count, 2);
  }
  await assert.rejects(acquireReturnedFrame({ observeBracketed: async () => { throw new Error('Ambiguous original UI selector'); } },
    {}, () => {}, returnedIdentity, () => {}), /Ambiguous original UI selector/);
});

test('acquisition time bound rejects even a consistent frame arriving after deadline', async () => {
  const { acquireReturnedFrame } = await loadModule('Task14FrameAcquisition.js');
  let time = 0;
  await assert.rejects(acquireReturnedFrame({ observeBracketed: async () => { time = 5001; return returnedFrame(); } },
    {}, () => {}, returnedIdentity, () => {}, { now: () => time }), /Bounded returned-start-chat/);
});

test('bracketed core captures both inspector snapshots and rejects unavailable Driver absence', async () => {
  const f = await coreFixture();
  const session = await f.start();
  const sample = await session.observeBracketed('bracket', { input: [{ id: 'room_address_input' }] }, () => ({ addressFlowVisible: false }));
  assert.deepEqual(sample.tree, sample.bracketEnd.tree);
  assert.equal(sample.stateBefore.addressFlowVisible, false);
  assert.equal(sample.stateAfter.addressFlowVisible, false);
  await session.release();
  const missing = await coreFixture({ query: null });
  const other = await missing.start();
  await assert.rejects(other.observeBracketed('bracket', { input: [{ id: 'room_address_input' }] }, () => ({})), /Driver inventory unavailable/);
  await other.release();
});

function formFrame() {
  const frame = returnedFrame();
  frame.tree.$children[0].$attrs.id = 'room_address_input';
  frame.bracketEnd.tree = JSON.parse(JSON.stringify(frame.tree));
  frame.controls.input = { ...frame.controls.search, id: 'room_address_input', selector: { id: 'room_address_input' } };
  frame.controls.search = { selector: { id: 'people_search_input' }, present: false, visible: false, inspectorMatches: 0 };
  frame.stateBefore.addressFlowVisible = true;
  frame.stateAfter.addressFlowVisible = true;
  return frame;
}

test('join bracket rejects the captured old-root/new-Driver mixture, then captures actual form', async () => {
  const { acquirePageFrame } = await loadModule('Task14FrameAcquisition.js');
  const mixed = formFrame(); mixed.tree = returnedFrame().tree;
  const good = formFrame(), samples = [mixed, good], records = [];
  const result = await acquirePageFrame({ observeBracketed: async () => samples.shift() }, {}, () => {}, returnedIdentity,
    e => records.push(e), { now: () => 0, phase: 'after:event' });
  assert.equal(result, good);
  assert.equal(records[0].assessment.consistent, false);
  assert.equal(records[1].assessment.surface, 'form');
});

test('coherent wrong surface and business values are returned immediately, never polled until expected', async () => {
  const { acquirePageFrame } = await loadModule('Task14FrameAcquisition.js');
  for (const sample of [returnedFrame(), formFrame()]) {
    sample.stateBefore.addressState = 'invalid'; sample.stateAfter.addressState = 'invalid';
    sample.stateBefore.address = 'not expected'; sample.stateAfter.address = 'not expected';
    let count = 0;
    const result = await acquirePageFrame({ observeBracketed: async () => { count++; return sample; } },
      {}, () => {}, returnedIdentity, () => {}, { now: () => 0, phase: 'after:event' });
    assert.equal(result, sample);
    assert.equal(count, 1);
    assert.equal(result.stateAfter.addressState, 'invalid');
    assert.equal(result.stateAfter.address, 'not expected');
  }
});

test('stable receiver/UI disagreement is terminal and cannot become a retry-to-pass', async () => {
  const { acquirePageFrame } = await loadModule('Task14FrameAcquisition.js');
  const sample = returnedFrame();
  sample.stateBefore.addressFlowVisible = true; sample.stateAfter.addressFlowVisible = true;
  let count = 0;
  await assert.rejects(acquirePageFrame({ observeBracketed: async () => { count++; return sample; } },
    {}, () => {}, returnedIdentity, () => {}, { now: () => 0 }), /Stable original receiver\/UI surface disagreement/);
  assert.equal(count, 1);
});

test('setup permits no bound receiver but still requires a consistent UI bracket', async () => {
  const { acquirePageFrame } = await loadModule('Task14FrameAcquisition.js');
  const sample = returnedFrame();
  sample.stateBefore = undefined; sample.stateAfter = undefined;
  const result = await acquirePageFrame({ observeBracketed: async () => sample }, {}, () => undefined,
    { routeName: 'pages/Index', stateRequired: false }, () => {}, { now: () => 0 });
  assert.equal(result, sample);
  assert.equal(result.stateAfter, undefined);
});

test('null filtered queries need an independent populated window inventory, never assumed absence', async () => {
  const component = { getId: async () => 'room_address_input', getType: async () => 'TextInput',
    getText: async () => '#example:server', getBounds: async () => ({ left: 10, top: 40, right: 390, bottom: 90 }),
    isEnabled: async () => true, isFocused: async () => false, isClickable: async () => true };
  let inventories = 0;
  const f = await coreFixture({ components: spec => {
    if (Object.keys(spec).length) return null;
    inventories++; return [component];
  } });
  const session = await f.start();
  const frame = await session.observeBracketed('inventory', {
    input: [{ id: 'room_address_input' }], missing: [{ id: 'people_search_input' }]
  }, () => ({}));
  assert.equal(frame.controls.input.present, true, 'Null cannot hide a component independently found in the window');
  assert.equal(frame.controls.input.visible, true);
  assert.equal(frame.controls.missing.present, false);
  assert.equal(inventories, 1);
  assert.ok(f.events.includes('Task14.driverInventory'));
  await session.release();
  for (const empty of [[], null, undefined]) {
    const unavailable = await coreFixture({ components: spec => Object.keys(spec).length ? null : empty });
    const other = await unavailable.start();
    await assert.rejects(other.observeBracketed('inventory', { missing: [{ id: 'missing' }] }, () => ({})), /Driver inventory unavailable/);
    await other.release();
  }
});

test('real-flow-v2 dispatch is limited to case001', () => {
  const source = fs.readFileSync(path.join(__dirname, 'Task14DeviceUi.js'), 'utf8');
  assert.match(source,
    /config\.realFlowV2 === true && caseSpec\.caseId === 'jr_state_001_entry_opens_address_flow'/);
  assert.match(source,
    /evaluateTask14RealFlowV2\(args, config, ports, record\) : evaluateTask14UI/);
});
