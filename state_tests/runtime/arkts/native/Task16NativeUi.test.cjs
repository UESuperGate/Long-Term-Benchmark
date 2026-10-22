'use strict';
// Host scaffold only: real feature logic, fake OS/UI transport, no native scores.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const os = require('node:os');
const crypto = require('node:crypto');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const { runCase } = require('./Task16NativeUi.adapter.cjs');
const { install } = require('./Task16NativeUi.install.cjs');
const root = path.resolve(__dirname, '../../../..');
const candidate = path.join(root, 'final_dev_nodes/16_identity_reset_final_0_5_1');
const feature = 'entry/src/main/ets/features/IdentityResetFeature.ets';
const page = 'entry/src/main/ets/pages/Index.ets';
const specs = JSON.parse(fs.readFileSync(path.join(root,
  'experiment_results/runtime_transition_20261020/contract_audit/revision_5_task16/after/transitions.json'))).cases;
const sources = [feature, page].map(p => ({ path: p, sha256: crypto.createHash('sha256').update(fs.readFileSync(path.join(candidate, p))).digest('hex') }));
const plain = v => JSON.parse(JSON.stringify(v));
function load(file, cache = {}) {
  if (cache[file]) return cache[file];
  const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }, reportDiagnostics: true });
  assert.equal(compiled.diagnostics.length, 0);
  const context = { exports: {}, console: { info() {} }, require: name => load(path.resolve(path.dirname(file), name + '.js'), cache) };
  vm.runInNewContext(compiled.outputText, context, { filename: file });
  return cache[file] = context.exports;
}
class Selector {
  constructor(filters = {}) { this.filters = filters; }
  id(id) { return new Selector({ ...this.filters, id }); }
  type(type) { return new Selector({ ...this.filters, type }); }
  text(text) { return new Selector({ ...this.filters, text }); }
  inWindow(bundle) { return new Selector({ ...this.filters, bundle }); }
}
const component = v => ({ id: '', type: 'Text', text: '', enabled: true, checkable: false, checked: false,
  async getId() { return this.id; }, async getText() { return this.text; }, async isEnabled() { return this.enabled; },
  async isCheckable() { return this.checkable; }, async isChecked() { return this.checked; },
  async getBounds() { return { left: 0, top: 0, right: 100, bottom: 20 }; }, ...v });

function lifecycle(onStart, options) {
  const { createTask16LaunchController } = load(path.join(__dirname, 'Task16Launch.js'));
  let monitor, callbacks, foreground = false;
  const events = [], ability = { context: { abilityInfo: { bundleName: 'candidate.test', name: 'EntryAbility', moduleName: 'entry' },
    async terminateSelf() { callbacks.onWindowStageDestroy(ability); monitor.onAbilityDestroy(ability); } } };
  const rect = { left: 0, top: 0, width: 500, height: 1000 };
  const main = { getWindowProperties: () => ({ id: 16, windowRect: rect }) };
  const tick = () => {
    if (!foreground && !options.noForeground) {
      foreground = true;
      callbacks.onWindowStageCreate(ability, { getMainWindow: async () => main });
      monitor.onAbilityForeground(ability);
    }
  };
  return { events, tick, launch: createTask16LaunchController({
    applicationContext: { on(name, cb) { callbacks = cb; events.push('lifecycle:add'); return 16; },
      async off() { events.push('lifecycle:remove'); } },
    delegator: { async addAbilityMonitor(m) { monitor = m; events.push('monitor:add'); },
      async startAbility() { onStart(); monitor.onAbilityCreate(ability); },
      async getCurrentTopAbility() { return ability; }, async removeAbilityMonitor() { events.push('monitor:remove'); } },
    async getLastWindow(context) {
      assert.equal(context, ability.context);
      return { getWindowProperties: () => ({ id: options.wrongWindow ? 22 : 16, windowRect: rect }),
        getUIContext: () => ({ getHostContext: () => context,
          getRouter: () => ({ getState: () => ({ path: 'pages/', name: options.route || 'Index' }) }) }) };
    }, async delay() {}
  }, 'candidate.test') };
}
async function probe(spec, options = {}) {
  const types = load(path.join(candidate, feature)), ui = load(path.join(__dirname, 'Task16NativeUi.js'));
  let presenter, manager, service, nodes = [], launched = false;
  const originals = [types.IdentityResetPresenter.prototype.confirmReset, types.DemoOidcResetHandle.prototype.resetOidc];
  const title = component({ text: 'Reset cryptographic identity' });
  const toggle = component({ id: 'identity_reset_oidc_toggle', type: 'Toggle', checkable: true,
    async click() { service.authenticationType = 'oidc'; this.checked = true; } });
  const continued = component({ type: 'Button', id: 'identity_reset_continue', async click() { presenter.continue(); refresh(); } });
  const confirmation = component({ text: 'Confirm identity reset?' });
  const cancelled = component({ id: 'identity_reset_cancel_confirmation', type: 'Button', text: 'Cancel' });
  const confirm = component({ id: 'identity_reset_confirm', type: 'Button', text: 'Reset identity', enabled: !options.disabledConfirm, async click() {
    const pending = presenter.confirmReset(); refresh(); await pending; refresh();
  } });
  const approval = component({ text: 'Approve the reset with your identity provider.' });
  const url = component({ id: 'identity_reset_oidc_url', text: 'https://id.example/reset' });
  const webview = component({ id: 'identity_reset_oidc_webview', type: 'Web' });
  const completed = component({ id: 'identity_reset_oidc_completed', type: 'Button', text: 'Approval completed' });
  const exit = component({ id: 'identity_reset_exit', type: 'Button', text: 'Exit reset', async click() { await presenter.cancel(); refresh(); } });
  function refresh() {
    nodes = [title, exit];
    if (presenter.screen === 'reset_root') {
      nodes.push(toggle, continued);
      if (presenter.confirmationVisible) nodes.push(confirmation, confirm, cancelled);
    }
    if (presenter.screen === 'reset_oidc') nodes.push(approval, url, webview, completed);
  }
  ui.configureTask16Binding(JSON.stringify({ bundleName: 'candidate.test', moduleName: 'entry',
    productionModuleUrl: '@bundle:candidate.test/entry/ets/features/IdentityResetFeature' }), async imported => {
    assert.equal(launched, true); assert.ok(nodes.includes(continued));
    assert.equal(imported, '@bundle:candidate.test/entry/ets/features/IdentityResetFeature');
    return options.duplicate ? load(path.join(candidate, feature)) : types;
  });
  const life = lifecycle(() => {
    launched = true; service = new types.DemoIdentityResetService();
    manager = new types.IdentityResetFlowManager(service); presenter = new types.IdentityResetPresenter(manager); refresh();
  }, options);
  const driver = {
    async findWindow() { return { getBundleName: async () => 'candidate.test', isFocused: async () => true,
      getBounds: async () => ({ left: 0, top: 0, right: 500, bottom: 1000 }) }; },
    async findComponents(selector) {
      assert.equal(selector.filters.bundle, 'candidate.test');
      const found = nodes.filter(n => Object.entries(selector.filters).every(([k, v]) => k === 'bundle' || n[k] === v));
      return found.length ? found : null;
    }, async delayMs() { life.tick(); }
  };
  const raw = JSON.parse(await ui.runTask16NativeUi(JSON.stringify(spec), 'candidate.test', driver, new Selector(), life.launch));
  assert.equal(types.IdentityResetPresenter.prototype.confirmReset, originals[0]);
  assert.equal(types.DemoOidcResetHandle.prototype.resetOidc, originals[1]);
  raw.productionSources = sources;
  return { raw, presenter, manager, life };
}
async function adapt(spec, raw) {
  return runCase({ taskId: spec.taskId, caseSpec: spec, native: { bundleName: 'candidate.test', runTask16UI: async () => raw }, load: async () => {} });
}

test('OIDC actual original async flow renders the fallback WebView and calls resetOidc', async () => {
  const spec = specs[4], { raw } = await probe(spec), result = await adapt(spec, raw);
  assert.equal(raw.failure, undefined);
  assert.equal(raw.confirmExecuted, true);
  assert.equal(raw.actions.some(action => action.target === 'confirm' && action.executed), true);
  assert.deepEqual(result.observed, spec.expected);
  assert.equal(result.unsupported, undefined);
  assert.deepEqual(result.invariantChecks, spec.invariants.map(description => ({ description, passed: true,
    evidence: 'Actual embedded WebView rendered the approval URL and original OIDC handle.resetOidc executed.' })));
  assert.equal(result.integrationBoundary.externalServicesExecuted, false);
  const after = raw.frames.find(frame => frame.label === 'after_event');
  assert.equal(after.controls.find(item => item.name === 'oidcWebview').visible, true);
  assert.equal(after.controls.find(item => item.name === 'approvalUrl').id, 'identity_reset_oidc_url');
});

test('physical Exit, OIDC return and node destruction share original manager cleanup', async () => {
  const spec = specs[9], { raw, manager } = await probe(spec), result = await adapt(spec, raw);
  assert.equal(raw.failure, undefined);
  assert.deepEqual(result.observed, spec.expected);
  assert.equal(result.unsupported, undefined);
  assert.equal(result.invariantChecks.length, 1);
  assert.equal(result.invariantChecks[0].passed, true);
  assert.equal(manager.currentHandle, undefined);
  const before = raw.frames.find(f => f.label === 'before_event').presenter;
  const after = raw.frames.find(f => f.label === 'after_event').presenter;
  assert.equal(after.handles.find(h => h.handleId === before.handleId).cancelled, true);
  assert.deepEqual(after.cleanupHistory.slice(-3), ['cancel', 'oidc_return', 'node_destroy']);
  assert.equal(after.calls.filter(item => item.owner === 'manager' && item.method === 'cancel').length, 3);
  assert.equal(raw.actions.filter(a => a.target === 'exit').length, 1);
});

test('missing original receiver, disabled confirmation and window loss stay unscored', async () => {
  for (const options of [{ duplicate: true }, { disabledConfirm: true }, { wrongWindow: true }, { noForeground: true }, { route: 'Other' }]) {
    const { raw, life } = await probe(specs[9], options), result = await adapt(specs[9], raw);
    assert.ok(raw.failure);
    assert.deepEqual(result.observed, {});
    assert.ok(result.unsupported);
    if (!options.duplicate) assert.equal(raw.actions.some(a => a.target === 'exit'), false);
    assert.ok(life.events.includes('lifecycle:remove'));
    assert.ok(life.events.includes('monitor:remove'));
  }
});

test('source, context and event receipts cannot be omitted to project UI state', async () => {
  const { raw } = await probe(specs[9]);
  for (const [label, mutate] of [['production sources', r => { r.productionSources = []; }],
    ['action receipts', r => { r.actions = []; }],
    ['manager identity', r => { r.frames.find(f => f.label === 'after_event').presenter.managerId = 8; }],
    ['window identity', r => { r.frames.find(f => f.label === 'after_event').windowIdentity.hostVerified = false; }]]) {
    const altered = plain(raw); mutate(altered);
    assert.deepEqual((await adapt(specs[9], altered)).observed, {}, label);
  }
});

test('observer preserves Promise identity, does not attach reactions or change service configuration', async () => {
  const types = load(path.join(candidate, feature));
  const observerApi = load(path.join(__dirname, 'Task16PageObserver.js'));
  const service = new types.DemoIdentityResetService();
  const manager = new types.IdentityResetFlowManager(service), presenter = new types.IdentityResetPresenter(manager);
  const original = types.IdentityResetPresenter.prototype.confirmReset;
  let originalResult;
  // Test-only identity sentinel around the actual original method.
  types.IdentityResetPresenter.prototype.confirmReset = function(...args) { return originalResult = original.apply(this, args); };
  const observer = observerApi.observeTask16Page(types, {});
  const returned = presenter.confirmReset();
  assert.equal(returned, originalResult);
  await returned;
  assert.equal(service.shouldFail, false);
  assert.equal(service.authenticationType, 'password');
  observer.dispose();
});

test('installer preserves production and shared transport; dependencies are embedded without external require', t => {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-task16-fixture-'));
  t.after(() => fs.rmSync(work, { recursive: true, force: true }));
  for (const relative of ['entry/src/main', 'AppScope']) fs.cpSync(path.join(candidate, relative), path.join(work, relative), { recursive: true });
  const dir = path.join(work, 'entry/src/test'); fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'native-bundle.js'), "import { x } from './native-device-platform';\n" +
    "if (candidateUI) await bridge.ui.navigate(candidateUI.route);\nmodule.exports.runCase({ ...context, native: bridge,\n" +
    'await evaluateCase(); await bridge.persistRow(row); try { await bridge.dispose(); } catch(e) {}');
  fs.writeFileSync(path.join(dir, 'NativeBundle.test.ets'), 'export default function nativeBundleTests(): void {}');
  const built = install(work);
  assert.equal(built.productionUnchanged, true); assert.equal(built.fixtures.length, 10);
  assert.equal(typeof load(path.join(dir, 'Task16NativeUiAdapter.js')).runTask16Case, 'function');
  assert.match(fs.readFileSync(built.bundleFile, 'utf8'), /task16UI \? runTask16Case : module.exports.runCase/);
  assert.match(fs.readFileSync(built.bundleFile, 'utf8'), /await bridge.persistRow/);
  assert.doesNotMatch(fs.readFileSync(built.suiteFile, 'utf8'), /\.\.\/main/);
  assert.throws(() => install(work), /already installed/);
});

test('independent bridge intercepts all ten staged revision5 cases', () => {
  const bridge = load(path.join(__dirname, 'Task16NativeUiBridge.js'));
  bridge.configureTask16UI(async () => '{}', 'candidate.test', '[]');
  for (const spec of specs) {
    const target = { setObservationRecorder(callback) { this.recorder = callback; } };
    assert.equal(bridge.attachTask16UI(target, spec.taskId, spec.key), true);
    target.disposeTask16UI();
  }
  assert.equal(bridge.attachTask16UI({}, '16_identity_reset', 'unknown'), false);
});
