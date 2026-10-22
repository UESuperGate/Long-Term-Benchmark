'use strict';
// Host scaffold regressions, never device semantic results.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const os = require('node:os');
const crypto = require('node:crypto');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const { runCase } = require('./Task12PartialUi.adapter.cjs');
const { install } = require('./Task12PartialUi.install.cjs');
const root = path.resolve(__dirname, '../../../..');
const candidate = path.join(root, 'final_dev_nodes/12_report_room_final_25_05_0');
const feature = 'entry/src/main/ets/features/ReportRoomFeature.ets';
const page = 'entry/src/main/ets/pages/Index.ets';
const spec = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks/12_report_room/transitions.json'))).cases[7];
const sources = [feature, page].map(p => ({ path: p, sha256: crypto.createHash('sha256').update(fs.readFileSync(path.join(candidate, p))).digest('hex') }));
function load(file, cache = {}) {
  if (cache[file]) return cache[file];
  const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }, reportDiagnostics: true });
  assert.equal(compiled.diagnostics.length, 0);
  const context = { exports: {}, console: { info() {} }, require: name => load(path.resolve(path.dirname(file), name + '.js'), cache) };
  vm.runInNewContext(compiled.outputText, context, { filename: file });
  cache[file] = context.exports;
  return context.exports;
}
class Selector {
  constructor(filters = {}) { this.filters = filters; }
  id(id) { return new Selector({ ...this.filters, id }); }
  type(type) { return new Selector({ ...this.filters, type }); }
  text(text) { return new Selector({ ...this.filters, text }); }
  inWindow(bundle) { return new Selector({ ...this.filters, bundle }); }
}
const component = values => ({ id: '', type: 'Text', text: '', enabled: true, focused: false, checkable: false,
  checked: false, async getId() { return this.id; }, async getText() { return this.text; },
  async isEnabled() { return this.enabled; }, async isFocused() { return this.focused; },
  async isCheckable() { return this.checkable; }, async isChecked() { return this.checked; },
  async getBounds() { return { left: 0, top: 0, right: 100, bottom: 20 }; }, ...values });

function lifecycleFixture(onStart, options) {
  const { createTask12PartialLaunchController } = load(path.join(__dirname, 'Task12PartialLaunch.js'));
  let monitor, lifecycle, ticks = 0, foregroundSent = false;
  const log = [];
  const ability = { context: { abilityInfo: { bundleName: 'candidate.test', name: 'EntryAbility', moduleName: 'entry' } } };
  const properties = { id: 15, windowRect: { left: 0, top: 0, width: 500, height: 1000 } };
  const main = { getWindowProperties: () => properties };
  const stage = { getMainWindow: async () => main };
  const tick = () => {
    ticks++;
    if (!foregroundSent && ticks >= (options.foregroundAfter || 1) && !options.neverForeground) {
      foregroundSent = true;
      lifecycle.onWindowStageCreate(ability, stage);
      monitor.onAbilityForeground(ability);
    }
  };
  const launch = createTask12PartialLaunchController({
    applicationContext: {
      on(name, callbacks) { assert.equal(name, 'abilityLifecycle'); log.push('lifecycle:add'); lifecycle = callbacks; return 5; },
      async off(name, id) { assert.equal(id, 5); log.push('lifecycle:remove'); }
    },
    delegator: {
      async addAbilityMonitor(value) { log.push('monitor:add'); monitor = value; },
      async startAbility(want) {
        assert.equal(want.bundleName, 'candidate.test'); log.push('start');
        await onStart();
        if (!options.noCreate) monitor.onAbilityCreate(ability);
        if (!options.foregroundAfter) tick();
      },
      async getCurrentTopAbility() { return options.wrongTop ? { context: { abilityInfo: { ...ability.context.abilityInfo, bundleName: 'other' } } } : ability; },
      async removeAbilityMonitor(value) { assert.equal(value, monitor); log.push('monitor:remove'); }
    },
    async getLastWindow(context) {
      assert.equal(context, ability.context);
      return { getWindowProperties: () => ({ ...properties, id: options.wrongMain ? 99 : properties.id }),
        getUIContext: () => ({ getHostContext: () => ability.context, getRouter: () => ({ getState: () => ({ path: 'pages/', name: options.currentPage || 'Index' }) }) }) };
    }
  }, 'candidate.test');
  return { launch, log, tick, ticks: () => ticks };
}

async function evaluate(raw, sourceRecords = sources) {
  const api = load(path.join(__dirname, 'Task12PartialUiBridge.js'));
  const bridge = { capabilities: { context: { available: true } }, setObservationRecorder() {} };
  api.configureTask12PartialUI(async () => JSON.stringify(raw), 'candidate.test', JSON.stringify(sourceRecords));
  api.attachTask12PartialUI(bridge, spec.taskId, spec.key);
  const runtimeSource = fs.readFileSync(path.join(root, 'scripts/runtime_semantics/arkts_runtime.cjs'), 'utf8');
  const ast = ts.createSourceFile('runtime.cjs', runtimeSource, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
  const shared = ['snapshot', 'compareExpected', 'evaluateCase'].map(name =>
    ast.statements.find(s => ts.isFunctionDeclaration(s) && s.name?.text === name).getText(ast)).join('\n');
  const runtime = fs.readFileSync(path.join(__dirname, 'bundle-runtime.js'), 'utf8').replace('export async function runNativeCase', 'async function runNativeCase');
  const code = ts.transpileModule(fs.readFileSync(path.join(candidate, feature), 'utf8'),
    { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  const context = vm.createContext({ bridge, candidateUI: { productionSource: sources[1] },
    factories: { ['/project/' + feature]: new Function('exports', 'require', 'module', code) },
    metadata: { ['/project/' + feature]: sources[0] }, platformConstants: {},
    adapter: { runCase: args => runCase({ ...args, native: bridge }) }, spec });
  vm.runInContext(shared + '\n' + runtime + '\nactiveNativeContext = bridge;', context);
  const row = JSON.parse(JSON.stringify(await vm.runInContext('evaluateCase(spec.taskId, spec, "/project", adapter)', context)));
  bridge.disposeTask12PartialUI();
  return row;
}

async function probe(options = {}) {
  const types = load(path.join(candidate, feature));
  const ui = load(path.join(__dirname, 'Task12PartialUi.js'));
  let presenter, gateway, nodes = [], launched = false, retryRevealed = !options.offscreenRetry;
  const rootNode = component({ text: 'Community support' });
  const input = component({ id: 'report_room_reason', async inputText(value) { presenter.updateReason(value); refresh(); } });
  const leave = component({ id: 'report_room_leave_toggle', type: 'Toggle', checkable: true,
    async click() { presenter.toggleLeaveRoom(); refresh(); } });
  const submit = component({ id: 'submit_report_room', type: 'Button', async click() {
    presenter.submit(); refresh(); if (options.navigateAfterReport) options.currentPage = 'Home';
  } });
  const retry = component({ id: 'retry_leave_room', type: 'Button', enabled: !options.disabledRetry,
    async getBounds() { return { left: 0, top: retryRevealed ? 0 : 1100, right: 100, bottom: retryRevealed ? 20 : 1150 }; },
    async click() { presenter.retry(); refresh(); } });
  const partial = component({ id: 'report_room_partial_failure', text: 'The room was reported, but leaving failed.' });
  const success = component({ id: 'report_room_success' });
  const scroll = component({ type: 'Scroll', async scrollSearch(selector) {
    if (selector.filters.id !== retry.id) throw new Error('No such scroll target');
    if (options.missingRetry) throw new Error('No native retry control');
    retryRevealed = true; return retry;
  } });
  function refresh() {
    input.text = presenter.reason; leave.checked = presenter.leaveRoom; submit.enabled = presenter.canReport;
    nodes = [rootNode, input, leave, submit, scroll];
    if (presenter.reportAction === 'leave_failed') nodes.push(partial, ...(!options.missingRetry ? [retry] : []));
    if (presenter.reportAction === 'success') nodes.push(success);
  }
  if (options.repeatReportOnRetry) {
    const original = types.ReportRoomPresenter.prototype.retry;
    types.ReportRoomPresenter.prototype.retry = function() {
      this.service.gateway.reportRoom(this.reason);
      return original.call(this);
    };
  }
  const originalGatewayMethods = [types.ReportRoomGateway.prototype.reportRoom, types.ReportRoomGateway.prototype.leaveRoom];
  ui.configureTask12Partial(JSON.stringify({ bundleName: 'candidate.test', moduleName: 'entry',
    productionModuleUrl: '@bundle:candidate.test/entry/ets/features/ReportRoomFeature' }), async url => {
    assert.equal(launched, true); assert.ok(nodes.includes(input));
    assert.equal(url, '@bundle:candidate.test/entry/ets/features/ReportRoomFeature');
    return options.duplicateModule ? load(path.join(candidate, feature)) : types;
  });
  const lifecycle = lifecycleFixture(async () => {
    launched = true; gateway = new types.ReportRoomGateway();
    presenter = new types.ReportRoomPresenter(new types.ReportRoomService(gateway)); refresh();
  }, options);
  const driver = {
    async findWindow({ bundleName, focused }) {
      assert.equal(bundleName, 'candidate.test'); assert.equal(focused, true);
      if (options.neverWindow) return null;
      return { getBundleName: async () => 'candidate.test', isFocused: async () => true,
        getBounds: async () => ({ left: 0, top: 0, right: 500, bottom: 1000 }) };
    },
    async findComponents(selector) {
      assert.equal(selector.filters.bundle, 'candidate.test');
      const found = nodes.filter(n => Object.entries(selector.filters).every(([key, value]) => key === 'bundle' || n[key] === value));
      return found.length ? found : null;
    }, async delayMs() { lifecycle.tick(); }
  };
  const raw = JSON.parse(await ui.runTask12Partial(JSON.stringify(spec), 'candidate.test', driver, new Selector(), lifecycle.launch,
    async () => { if (options.keyboardError) throw new Error('input client detached'); }));
  assert.equal(types.ReportRoomGateway.prototype.reportRoom, originalGatewayMethods[0]);
  assert.equal(types.ReportRoomGateway.prototype.leaveRoom, originalGatewayMethods[1]);
  return { raw, presenter, gateway, lifecycleLog: lifecycle.log };
}

test('full original report/leave failure plus actual same-page retry satisfies expected and invariant', async () => {
  const { raw, gateway } = await probe();
  assert.equal(raw.unsupported, '');
  const row = await evaluate(raw);
  assert.equal(row.status, 'pass', JSON.stringify(row));
  assert.deepEqual(row.observed, spec.expected);
  assert.equal(row.invariantChecks.length, spec.invariants.length);
  assert.equal(row.invariantChecks[0].passed, true);
  assert.equal(row.calls.some(c => c.method === 'constructor'), false);
  assert.equal(row.productionSources.length, 2);
  assert.equal(gateway.reportCalls, 1); assert.equal(gateway.leaveCalls, 2);
  assert.deepEqual(Array.from(gateway.effects), ['report_room', 'leave_room', 'leave_room']);
  assert.equal(raw.frames.find(f => f.label === 'after_event').presenter.reportAction, 'leave_failed');
  assert.equal(raw.frames.find(f => f.label === 'after_invariant_retry').presenter.reportAction, 'success');
  assert.equal(raw.actions.filter(a => a.target === 'retry' && a.kind === 'click').length, 1);
});

test('report duplication during real retry is a scored invariant failure', async () => {
  const { raw } = await probe({ repeatReportOnRetry: true });
  const row = await evaluate(raw);
  assert.equal(row.status, 'fail');
  assert.deepEqual(row.observed, spec.expected, 'Canonical checkpoint must not be overwritten by retry');
  assert.equal(row.invariantChecks[0].passed, false);
});

test('leaving the report page prevents any use of retained presenter as a retry substitute', async () => {
  const { raw, gateway } = await probe({ navigateAfterReport: true });
  assert.equal((await evaluate(raw)).status, 'not_scored');
  assert.equal(raw.invariantEventExecuted, false);
  assert.equal(raw.actions.some(a => a.target === 'retry'), false);
  assert.equal(gateway.leaveCalls, 1);
  assert.match(raw.failure.message, /route is not active/);
});

test('missing/disabled retry and duplicate production module remain honest NS', async () => {
  for (const options of [{ missingRetry: true }, { disabledRetry: true }, { duplicateModule: true }]) {
    const { raw } = await probe(options);
    assert.equal((await evaluate(raw)).status, 'not_scored');
    assert.equal(raw.invariantEventExecuted, false);
    assert.equal(raw.actions.some(a => a.kind === 'click' && a.target === 'retry'), false);
  }
});

test('native scroll reveals retry without altering the canonical failure state', async () => {
  const { raw } = await probe({ offscreenRetry: true });
  assert.equal((await evaluate(raw)).status, 'pass');
  assert.ok(raw.actions.some(a => a.kind === 'scroll_search' && a.target === 'retry' && a.executed));
  assert.equal(raw.frames.find(f => f.label === 'after_event').presenter.leaveCalls, 1);
});

test('boundary fixture changes only existing outcome flags; original gateway logic still runs', async () => {
  const { raw } = await probe({ keyboardError: true });
  assert.equal((await evaluate(raw)).status, 'pass');
  const before = raw.frames.find(f => f.label === 'before_event').presenter;
  assert.equal(before.fixtures[0].mechanism, 'configure_existing_original_gateway_boolean_fields');
  assert.equal(before.fixtures[0].before.reportCalls, 0);
  assert.equal(before.fixtures[0].after.reportCalls, 0);
  assert.equal(before.fixtures[0].after.leaveCalls, 0);
  assert.equal(before.fixtures[0].after.reportAction, 'uninitialized');
  const after = raw.frames.find(f => f.label === 'after_event').presenter;
  assert.deepEqual(after.gatewayCalls.map(c => [c.method, c.result]), [['reportRoom', true], ['leaveRoom', false]]);
  assert.deepEqual(after.serviceCalls[0].args, ['Spam', true, true]);
});

test('source provenance, route, identity and native retry evidence cannot be omitted', async () => {
  const { raw } = await probe();
  assert.equal((await evaluate(raw, sources.slice(0, 1))).status, 'not_scored');
  for (const mutate of [
    v => { v.frames.find(f => f.label === 'after_invariant_retry').presenter.instanceId = 2; },
    v => { v.frames.find(f => f.label === 'after_invariant_retry').windowIdentity.routeName = 'pages/Home'; },
    v => { v.frames.find(f => f.label === 'after_event').controls = []; },
    v => { v.actions = v.actions.filter(a => a.target !== 'retry'); }
  ]) {
    const changed = structuredClone(raw); mutate(changed);
    assert.equal((await evaluate(changed)).status, 'not_scored');
  }
});

test('installer keeps shared transport and has no external CJS dependency', t => {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'task12-partial-'));
  t.after(() => fs.rmSync(work, { recursive: true, force: true }));
  fs.cpSync(path.join(candidate, 'entry/src/main'), path.join(work, 'entry/src/main'), { recursive: true });
  fs.cpSync(path.join(candidate, 'AppScope'), path.join(work, 'AppScope'), { recursive: true });
  const dir = path.join(work, 'entry/src/test'); fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'native-bundle.js'), "import { createNativeContext } from './native-device-platform';\n" + fs.readFileSync(path.join(__dirname, 'bundle-runtime.js'), 'utf8'));
  fs.writeFileSync(path.join(dir, 'NativeBundle.test.ets'), 'export default function nativeBundleTests(): void {}');
  const built = install(work);
  assert.equal(built.productionUnchanged, true);
  assert.equal(built.fixtures.length, 10);
  assert.equal(typeof load(path.join(dir, 'Task12PartialUiAdapter.js')).runTask12PartialCase, 'function');
  const generated = fs.readFileSync(built.bundleFile, 'utf8');
  assert.match(generated, /task12PartialUI \? runTask12PartialCase : module.exports.runCase/);
  assert.match(generated, /await evaluateCase/);
  assert.match(generated, /await bridge.persistRow/);
  assert.doesNotMatch(fs.readFileSync(built.suiteFile, 'utf8'), /\.\.\/main/);
  assert.throws(() => install(work), /already installed/);
});

test('only the partial-failure case is intercepted', () => {
  const bridge = load(path.join(__dirname, 'Task12PartialUiBridge.js'));
  assert.equal(bridge.attachTask12PartialUI({}, '12_report_room', 'blank_reason_disabled'), false);
  assert.equal(bridge.attachTask12PartialUI({}, '12_report_room', 'retry_leave_only'), false);
});
