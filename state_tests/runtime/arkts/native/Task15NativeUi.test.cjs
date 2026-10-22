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
const { runCase } = require('./Task15NativeUi.adapter.cjs');
const { install } = require('./Task15NativeUi.install.cjs');
const { fixture } = require('./Task15AccountClient.fixture.cjs');
const root = path.resolve(__dirname, '../../../..');
const candidate = path.join(root, 'final_dev_nodes/15_account_deactivation_final_0_6_3');
const feature = 'entry/src/main/ets/features/AccountDeactivationFeature.ets';
const page = 'entry/src/main/ets/pages/Index.ets';
const spec = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks/15_account_deactivation/transitions.json'))).cases[4];
const loadingSpec = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks/15_account_deactivation/transitions.json'))).cases[5];
const entrySpec = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks/15_account_deactivation/transitions.json'))).cases[0];
const sources = [feature, page, 'entry/src/main/ets/services/AccountClient.ets',
  'entry/src/main/ets/services/NativeAccountClient.ets', 'entry/src/main/ets/components/AccountSessionControls.ets']
  .map(p => ({ path: p, sha256: crypto.createHash('sha256').update(fs.readFileSync(path.join(candidate, p))).digest('hex') }));
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
  const { createTask15LaunchController } = load(path.join(__dirname, 'Task15Launch.js'));
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
  const launch = createTask15LaunchController({
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
        getUIContext: () => ({ getHostContext: () => ability.context }) };
    }
  }, 'candidate.test');
  return { launch, log, tick, ticks: () => ticks };
}

async function probe(options = {}) {
  const selectedSpec = options.entryDiagnostic ? entrySpec : options.loadingDiagnostic ? loadingSpec : spec;
  const account = fixture();
  await account.signedIn();
  account.setResponder(request => request.respond(200, {}));
  const types = account.load(path.join(candidate, feature));
  const ui = load(path.join(__dirname, 'Task15NativeUi.js'));
  let presenter, service, nodes = [], launched = false, formLoaded = false, passwordSettleTicks = 0, keyboardCovered = false;
  const settings = component({ text: 'Settings' }), notifications = component({ type: 'Button', text: 'Notifications' });
  const confirm = component({ type: 'Button', text: 'Confirm deactivation', async click() {
    if (!options.loadingDiagnostic) throw new Error('Must never confirm');
    await presenter.deactivateAccount(false); refresh();
  } });
  const cancel = component({ type: 'Button', text: 'Cancel' });
  const message = component({ text: 'Are you sure you want to deactivate this account?' });
  function refresh() {
    input.text = '*'.repeat(presenter.password.length); // Native password text is masked.
    erase.checked = presenter.eraseData;
    submit.enabled = options.staleSubmit || (options.delayedSubmit && passwordSettleTicks < 3) ? false : presenter.submitEnabled();
    if (formLoaded) nodes = [input, erase, ...(keyboardCovered ? [] : [submit]), ...(presenter.action === 'confirming' && !options.hideConfirmation ? [message, cancel, confirm] : [])];
  }
  const input = component({ id: 'deactivation_password', type: 'TextInput', async inputText(value) {
    if (options.inputError) throw Object.assign(new Error('native keyboard lost focus'), { code: 17000002 });
    if (!options.ignoreInput) presenter.setPassword(value);
    if (options.keyboardOccludesSubmit) { keyboardCovered = true; input.focused = true; }
    refresh();
  } });
  const erase = component({ type: 'Toggle', checkable: true, async click() { presenter.setEraseData(!presenter.eraseData); refresh(); } });
  const submit = component({ id: 'deactivate_submit', type: 'Button', async click() {
    await presenter.deactivateAccount(false); refresh();
  } });
  const entry = component({ id: 'deactivate_account_entry', type: 'Button', async click() { formLoaded = true; refresh(); } });
  if (options.prematureRequest) {
    const original = types.AccountDeactivationPresenter.prototype.deactivateAccount;
    types.AccountDeactivationPresenter.prototype.deactivateAccount = function(isRetry) {
      this.service.deactivateAccount(this.password, this.eraseData);
      return original.call(this, isRetry);
    };
  }
  ui.configureTask15Binding(JSON.stringify({ bundleName: 'candidate.test', moduleName: 'entry',
    productionModuleUrl: '@bundle:candidate.test/entry/ets/features/AccountDeactivationFeature' }), async url => {
    assert.equal(launched, true); assert.equal(formLoaded, true);
    assert.equal(url, '@bundle:candidate.test/entry/ets/features/AccountDeactivationFeature');
    return options.duplicateModule ? { ...types, AccountDeactivationPresenter: class DuplicatePresenter {} } : types;
  });
  const lifecycle = lifecycleFixture(async () => {
    launched = true; service = account.client;
    presenter = new types.AccountDeactivationPresenter(service, service);
    await presenter.loadCapability();
    nodes = [settings, notifications, ...(options.hideEntry ? [] : [entry])];
  }, options);
  let windowQueries = 0;
  const driver = {
    async findWindow({ bundleName, focused }) {
      assert.equal(bundleName, 'candidate.test'); assert.equal(focused, true);
      windowQueries++;
      if (options.neverWindow || windowQueries <= (options.missingWindowQueries || 0)) return null;
      return { getBounds: async () => ({ left: 0, top: 0, right: 500, bottom: 1000 }),
        getBundleName: async () => options.wrongWindowBundle ? 'other' : 'candidate.test', isFocused: async () => !options.unfocusedWindow };
    },
    async findComponents(selector) {
      assert.equal(selector.filters.bundle, 'candidate.test');
      if (!formLoaded && (options.neverRoot || lifecycle.ticks() < (options.rootAfter || 0))) return null;
      const matches = nodes.filter(node => Object.entries(selector.filters).every(([key, value]) => key === 'bundle' || node[key] === value));
      return matches.length ? matches : null;
    }, async delayMs() {
      lifecycle.tick();
      if (options.delayedSubmit && presenter && presenter.password === spec.given.password) {
        passwordSettleTicks++;
        if (passwordSettleTicks >= 3) refresh();
      }
    }
  };
  const dismissKeyboard = options.keyboardOccludesSubmit && !options.noKeyboardCallback ? async () => {
    if (options.keyboardHideError) throw new Error('input method transport failed');
    if (!options.ignoreKeyboardHide) { keyboardCovered = false; input.focused = false; }
    refresh();
  } : undefined;
  const raw = JSON.parse(await ui.runTask15NativeUi(JSON.stringify(selectedSpec), 'candidate.test', driver, new Selector(), lifecycle.launch,
    undefined, undefined, dismissKeyboard));
  for (let i = 0; i < 100 && account.client.isBusy(); i++) await new Promise(resolve => setImmediate(resolve));
  account.dispose();
  return { raw, presenter, service, requests: account.requests, lifecycleLog: lifecycle.log };
}

async function evaluate(raw, sourceRecords = sources, selectedSpec = spec) {
  const api = load(path.join(__dirname, 'Task15NativeUiBridge.js'));
  const bridge = { capabilities: { context: { available: true } }, setObservationRecorder() {} };
  api.configureTask15UI(async () => JSON.stringify(raw), 'candidate.test', JSON.stringify(sourceRecords));
  api.attachTask15UI(bridge, selectedSpec.taskId, selectedSpec.key);
  const runtimeSource = fs.readFileSync(path.join(root, 'scripts/runtime_semantics/arkts_runtime.cjs'), 'utf8');
  const ast = ts.createSourceFile('runtime.cjs', runtimeSource, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
  const shared = ['snapshot', 'compareExpected', 'evaluateCase'].map(name =>
    ast.statements.find(s => ts.isFunctionDeclaration(s) && s.name?.text === name).getText(ast)).join('\n');
  const runtime = fs.readFileSync(path.join(__dirname, 'bundle-runtime.js'), 'utf8').replace('export async function runNativeCase', 'async function runNativeCase');
  const factories = {}, metadata = {};
  for (const source of sources.filter(s => [feature, 'entry/src/main/ets/services/AccountClient.ets'].includes(s.path))) {
    const code = ts.transpileModule(fs.readFileSync(path.join(candidate, source.path), 'utf8'),
      { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
    factories['/project/' + source.path] = new Function('exports', 'require', 'module', code);
    metadata['/project/' + source.path] = source;
  }
  const context = vm.createContext({ bridge, candidateUI: { productionSource: sources[1] },
    factories, metadata, platformConstants: {},
    adapter: { runCase: args => runCase({ ...args, native: bridge }) }, spec: selectedSpec });
  vm.runInContext(shared + '\n' + runtime + '\nactiveNativeContext = bridge;', context);
  const row = JSON.parse(JSON.stringify(await vm.runInContext('evaluateCase(spec.taskId, spec, "/project", adapter)', context)));
  bridge.disposeTask15UI();
  return row;
}

test('actual production receiver and service through physical UI fixture reach complete case005', async () => {
  const { raw, requests } = await probe();
  assert.equal(raw.unsupported, '');
  assert.equal(requests.length, 0);
  const row = await evaluate(raw);
  assert.equal(row.status, 'pass', JSON.stringify(row));
  assert.deepEqual(row.observed, { action: 'confirming', requestCount: 0, confirmationVisible: true });
  assert.equal(row.invariantChecks.length, spec.invariants.length);
  assert.equal(row.invariantChecks[0].passed, true);
  assert.deepEqual(row.productionSources.map(source => source.path).sort(), [feature, page,
    'entry/src/main/ets/services/AccountClient.ets'].sort());
  assert.ok(row.calls.some(call => call.nativeUI));
  assert.equal(row.calls.some(call => call.method === 'constructor'), false);
  assert.equal(raw.frames.find(f => f.label === 'before_event').controls.find(c => c.name === 'password').text, '******');
});

test('native keyboard dismissal reobserves the original submit without bypassing disabled or missing UI', async () => {
  const { raw } = await probe({ keyboardOccludesSubmit: true });
  assert.equal((await evaluate(raw)).status, 'pass');
  assert.ok(raw.actions.some(action => action.kind === 'hide_input_method' && action.executed));
  assert.equal(raw.frames.find(frame => frame.label === 'fixture_after_keyboard_dismissed').presenter.password, 'secret');
  for (const options of [{ noKeyboardCallback: true }, { ignoreKeyboardHide: true },
    { keyboardHideError: true }, { staleSubmit: true }]) {
    const result = await probe({ keyboardOccludesSubmit: true, ...options });
    assert.equal((await evaluate(result.raw)).status, 'not_scored');
    assert.equal(result.raw.actions.some(action => action.target === 'submit' && action.executed), false);
  }
});

test('missing confirmation is a real failed expectation, not relaxed UI coverage', async () => {
  const row = await evaluate((await probe({ hideConfirmation: true })).raw);
  assert.equal(row.status, 'fail');
  assert.ok(row.assertionFailures.some(f => f.path === 'confirmationVisible'));
});

test('immediate external HTTP fixture stays NS without natural modal and input-routing proof', async () => {
  const { raw, requests } = await probe({ loadingDiagnostic: true });
  assert.equal(raw.eventExecuted, true);
  assert.equal(raw.frames.find(f => f.label === 'before_event').presenter.action, 'confirming');
  assert.equal(raw.frames.find(f => f.label === 'before_event').presenter.requestCount, 0);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].body.erase, true);
  assert.deepEqual(raw.frames.find(f => f.label === 'after_event').presenter.serviceCalls[0].args, ['secret', true]);
  assert.equal(raw.loadingObservation.presenterAction, 'success');
  assert.equal(raw.loadingObservation.loadingModalVisible, false);
  assert.equal(raw.loadingObservation.formInputBlocked, 'unproven');
  const row = await evaluate(raw, sources, loadingSpec);
  assert.equal(row.status, 'not_scored');
  assert.deepEqual(row.invariantChecks, []);
  assert.match(row.reason, /No simultaneous natural Loading/);
});

test('entry diagnostic reads original settings without opening form or importing a duplicate presenter', async () => {
  const { raw, requests, lifecycleLog } = await probe({ entryDiagnostic: true });
  assert.equal(raw.eventExecuted, true);
  assert.equal(raw.frames.find(f => f.label === 'before_event').uiObserved, false);
  assert.equal(raw.frames.find(f => f.label === 'after_event').controls.find(c => c.name === 'entry').visible, true);
  assert.equal(raw.frames.some(f => f.presenter?.available), false);
  assert.deepEqual(raw.actions, []);
  assert.equal(requests.length, 0);
  assert.ok(raw.launchEvidence);
  assert.deepEqual(lifecycleLog.slice(-2), ['monitor:remove', 'lifecycle:remove']);
  const row = await evaluate(raw, sources, entrySpec);
  assert.equal(row.status, 'not_scored');
  assert.deepEqual(row.observed, {});
  assert.deepEqual(row.invariantChecks, []);
  assert.match(row.reason, /capability entry\/style\/negative-branch evidence incomplete/);
});

test('entry case requires real login, runtime destructive color and the hidden capability branch', async () => {
  const { raw } = await probe({ entryDiagnostic: true });
  raw.integration = { login: {
    entryVisible: true,
    entryHiddenBeforeLogin: true,
    providerLoginCount: 1,
    entryInspector: { $attrs: { fontColor: '#ffb42318' } }
  } };
  const row = await evaluate(raw, sources, entrySpec);
  assert.equal(row.status, 'pass', JSON.stringify(row));
  assert.deepEqual(row.observed, { deactivateEntryVisible: true, entryStyle: 'destructive' });
  assert.equal(row.invariantChecks.length, 1);
  assert.equal(row.invariantChecks[0].passed, true);

  for (const mutate of [
    value => { value.integration.login.entryInspector.$attrs.fontColor = '#ff007dff'; },
    value => { value.integration.login.entryHiddenBeforeLogin = false; },
    value => { value.integration.login.providerLoginCount = 0; }
  ]) {
    const altered = structuredClone(raw);
    mutate(altered);
    assert.notEqual((await evaluate(altered, sources, entrySpec)).status, 'pass');
  }
});

test('missing entry is not a negative capability result and never inferred as failure', async () => {
  const { raw } = await probe({ entryDiagnostic: true, hideEntry: true });
  assert.equal(raw.readiness.ready, true);
  assert.equal(raw.frames.find(f => f.label === 'after_event').controls.find(c => c.name === 'entry').present, false);
  const row = await evaluate(raw, sources, entrySpec);
  assert.equal(row.status, 'not_scored');
  assert.deepEqual(row.observed, {});
});

test('entry diagnostic rejects missing source/window/root and cannot promote supplied style or invariant booleans', async () => {
  const { raw } = await probe({ entryDiagnostic: true });
  for (const mutate of [
    value => { delete value.frames.find(f => f.label === 'after_event').windowIdentity; },
    value => { value.frames.find(f => f.label === 'after_event').windowIdentity.ability.bundleName = 'foreign'; },
    value => { value.frames.find(f => f.label === 'after_event').controls = []; },
    value => { value.traceDigest = '0'.repeat(64); }
  ]) {
    const altered = structuredClone(raw); mutate(altered);
    const row = await evaluate(altered, sources, entrySpec);
    assert.equal(row.status, 'not_scored');
    assert.deepEqual(row.observed, {});
  }
  assert.deepEqual((await evaluate(raw, [], entrySpec)).observed, {});
  raw.entryStyle = 'destructive'; raw.unsupportedCapabilityHidden = true;
  const row = await evaluate(raw, sources, entrySpec);
  assert.equal(row.status, 'not_scored');
  assert.equal(row.observed.entryStyle, undefined);
  assert.deepEqual(row.invariantChecks, []);
});

test('actual AccountClient holds at native HTTP and failure does not require changing canonical password', async t => {
  const account = fixture(); t.after(() => account.dispose()); await account.signedIn();
  const types = account.load(path.join(candidate, feature));
  const presenter = new types.AccountDeactivationPresenter(account.client, account.client);
  await presenter.loadCapability();
  assert.equal(presenter.canDeactivateAccount, true);
  presenter.setPassword('secret'); presenter.setEraseData(true);
  await presenter.deactivateAccount(false);
  assert.equal(presenter.action, 'confirming');
  const pending = presenter.deactivateAccount(false);
  assert.equal(presenter.action, 'loading', 'Domain pending remains distinct from native modal evidence');
  account.requests[0].respond(401, { session: 'uia' }); await account.waitRequests(2);
  assert.equal(account.requests[1].body.auth.password, 'secret');
  account.requests[1].respond(503, { errcode: 'M_UNKNOWN' }); await pending;
  assert.equal(presenter.action, 'failure');
  assert.equal(presenter.password, 'secret');
  const retry = presenter.deactivateAccount(true);
  account.requests[2].respond(200, {}); await retry;
  assert.equal(presenter.action, 'success');
  assert.equal(account.assets.size, 0);
});

test('early destructive production call violates zero-request invariant and expected count', async () => {
  const row = await evaluate((await probe({ prematureRequest: true })).raw);
  assert.equal(row.status, 'fail');
  assert.equal(row.observed.requestCount, 1);
  assert.equal(row.invariantChecks[0].passed, false);
});

test('test-module duplicate, ignored UI input, and keyboard error remain NS with original diagnostics', async () => {
  for (const options of [{ duplicateModule: true }, { ignoreInput: true }, { inputError: true }]) {
    const { raw } = await probe(options);
    const row = await evaluate(raw);
    assert.equal(row.status, 'not_scored');
    assert.equal(raw.eventExecuted, false);
    assert.ok(raw.failure.stage);
    if (options.inputError) {
      assert.equal(raw.failure.code, 17000002);
      assert.match(row.reason, /fixture_password_input.*native keyboard lost focus/);
    }
  }
});

test('all original source identities, canonical givens and same receiver are mandatory', async () => {
  const { raw } = await probe();
  assert.equal((await evaluate(raw, sources.slice(0, 1))).status, 'not_scored');
  for (const mutate of [
    value => { value.frames.find(f => f.label === 'before_event').presenter.password = ''; },
    value => { value.frames.find(f => f.label === 'after_event').presenter.instanceId = 2; },
    value => { value.frames.find(f => f.label === 'after_event').presenter.serviceId = 2; },
    value => { value.actions = []; }
  ]) {
    const altered = structuredClone(raw); mutate(altered);
    assert.equal((await evaluate(altered)).status, 'not_scored');
  }
});

test('observer preserves Promise identity/throws and restores original methods', t => {
  const { observeTask15Page } = load(path.join(__dirname, 'Task15PageObserver.js'));
  const account = fixture(); t.after(() => account.dispose());
  const types = account.load(path.join(candidate, feature));
  const service = account.client, presenter = new types.AccountDeactivationPresenter(service, service);
  const pending = Promise.resolve();
  types.AccountDeactivationPresenter.prototype.deactivateAccount = function() { return pending; };
  const original = types.AccountDeactivationPresenter.prototype.deactivateAccount;
  const observer = observeTask15Page(types, {});
  assert.equal(presenter.deactivateAccount(false), pending);
  assert.equal(observer.read().instanceCount, 1);
  observer.dispose();
  assert.equal(types.AccountDeactivationPresenter.prototype.deactivateAccount, original);
  const error = new Error('original throw');
  types.AccountDeactivationPresenter.prototype.setPassword = function() { throw error; };
  const second = observeTask15Page(types, {});
  assert.throws(() => presenter.setPassword('secret'), e => e === error);
  assert.equal(second.read().calls[0].returned, false);
  second.dispose();
});

test('observer records original service rejection without replacing or swallowing its Promise', async () => {
  const { observeTask15Page } = load(path.join(__dirname, 'Task15PageObserver.js'));
  const error = Object.assign(new Error('File exists'), { code: 13900015 });
  const rejected = Promise.reject(error);
  rejected.catch(() => {});
  class Service {
    deactivateAccount() { return rejected; }
  }
  class Presenter {
    setPassword() {}
    setEraseData() {}
    deactivateAccount() {}
    submitEnabled() { return false; }
  }
  const observer = observeTask15Page({ AccountClient: Service, AccountDeactivationPresenter: Presenter }, {});
  const service = new Service();
  assert.equal(service.deactivateAccount('secret', true), rejected);
  await Promise.resolve();
  const settlement = observer.read().serviceCalls[0].settlement;
  assert.equal(settlement.status, 'rejected');
  assert.equal(settlement.name, 'Error');
  assert.equal(settlement.message, 'File exists');
  assert.equal(settlement.code, 13900015);
  await assert.rejects(rejected, value => value === error);
  observer.dispose();
});

test('installer edits only generated evaluator and embeds standalone adapter without CJS require', t => {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'task15-ui-'));
  t.after(() => fs.rmSync(work, { recursive: true, force: true }));
  fs.cpSync(path.join(candidate, 'entry/src/main'), path.join(work, 'entry/src/main'), { recursive: true });
  fs.cpSync(path.join(candidate, 'AppScope'), path.join(work, 'AppScope'), { recursive: true });
  const testRoot = path.join(work, 'entry/src/test'); fs.mkdirSync(testRoot, { recursive: true });
  const runtime = fs.readFileSync(path.join(__dirname, 'bundle-runtime.js'), 'utf8');
  fs.writeFileSync(path.join(testRoot, 'native-bundle.js'), "import { createNativeContext } from './native-device-platform';\n" + runtime);
  fs.writeFileSync(path.join(testRoot, 'NativeBundle.test.ets'), 'export default function nativeBundleTests(): void {}');
  const result = install(work);
  assert.equal(result.productionUnchanged, true);
  assert.equal(result.fixtures.length, 12);
  assert.deepEqual(result.sources.sort((a, b) => a.path.localeCompare(b.path)), sources.slice().sort((a, b) => a.path.localeCompare(b.path)));
  const bundle = fs.readFileSync(result.bundleFile, 'utf8');
  assert.match(bundle, /task15UI \? runTask15Case : module.exports.runCase/);
  assert.match(bundle, /await evaluateCase/);
  assert.match(bundle, /await bridge.persistRow/);
  const module = load(path.join(testRoot, 'Task15NativeUiAdapter.js'));
  assert.equal(typeof module.runTask15Case, 'function');
  assert.doesNotMatch(fs.readFileSync(path.join(testRoot, 'Task15NativeUiAdapter.js'), 'utf8'), /require\(/);
  assert.doesNotMatch(fs.readFileSync(result.suiteFile, 'utf8'), /\.\.\/main/);
  assert.throws(() => install(work), /already installed/);
});

test('other Task15 cases stay on old adapter', () => {
  const bridge = load(path.join(__dirname, 'Task15NativeUiBridge.js'));
  assert.equal(bridge.attachTask15UI({}, spec.taskId, 'success_completes'), false);
  assert.throws(() => bridge.attachTask15UI({}, spec.taskId, 'confirm_sends_payload'), /probe\/recorder unavailable/);
  assert.equal(bridge.attachTask15UI({}, '12_report_room', 'blank_reason_disabled'), false);
});

test('startAbility return does not bypass delayed foreground or delayed native main window', async () => {
  for (const options of [{ foregroundAfter: 3 }, { missingWindowQueries: 3 }, { rootAfter: 3 }]) {
    const { raw, lifecycleLog } = await probe(options);
    assert.equal((await evaluate(raw)).status, 'pass');
    assert.equal(raw.readiness.ready, true);
    assert.ok(raw.readiness.attempts.length > 1);
    assert.ok(raw.readiness.attempts.some(attempt => attempt.error || attempt.rootConfirmed === false));
    assert.deepEqual(lifecycleLog, ['lifecycle:add', 'monitor:add', 'start', 'monitor:remove', 'lifecycle:remove']);
    const frame = raw.frames.find(frame => frame.label === 'before_event');
    assert.equal(frame.windowIdentity.stageMainWindowId, frame.windowIdentity.lastWindowId);
    assert.equal(frame.windowIdentity.focused, true);
  }
});

test('missing or foreign launch environment exhausts bounded attempts as NS without UI setup or original import', async () => {
  for (const options of [{ neverWindow: true }, { neverForeground: true }, { noCreate: true }, { neverRoot: true },
    { wrongMain: true }, { wrongTop: true }, { wrongWindowBundle: true }, { unfocusedWindow: true }]) {
    const { raw, lifecycleLog } = await probe(options);
    assert.equal((await evaluate(raw)).status, 'not_scored');
    assert.equal(raw.readiness.ready, false);
    assert.equal(raw.readiness.attempts.length, 40);
    assert.equal(raw.failure.stage, 'await_original_main_window_and_settings');
    assert.equal(raw.eventExecuted, false);
    assert.equal(raw.actions.length, 0);
    assert.equal(raw.frames.some(frame => frame.label === 'observer_installed'), false);
    assert.deepEqual(lifecycleLog.slice(-2), ['monitor:remove', 'lifecycle:remove']);
  }
});

test('native main-window evidence cannot be omitted by the adapter', async () => {
  const { raw } = await probe();
  delete raw.frames.find(frame => frame.label === 'after_event').windowIdentity;
  assert.equal((await evaluate(raw)).status, 'not_scored');
});

test('AccountClient source closure and active session are mandatory; getter-only readiness is insufficient', async () => {
  const { raw } = await probe();
  const incomplete = sources.filter(source => !source.path.endsWith('NativeAccountClient.ets'));
  assert.equal((await evaluate(raw, incomplete)).status, 'not_scored');
  const signedOut = structuredClone(raw);
  signedOut.frames.find(frame => frame.label === 'before_event').presenter.accountSessionActive = false;
  assert.equal((await evaluate(signedOut)).status, 'not_scored');
});

test('read-only production enabled result never substitutes for the disabled native submit', async () => {
  const { raw } = await probe({ staleSubmit: true });
  assert.equal((await evaluate(raw)).status, 'not_scored');
  assert.equal(raw.submitReadiness.ready, false);
  assert.equal(raw.submitReadiness.attempts.length, 10);
  assert.equal(raw.eventExecuted, false);
  assert.equal(raw.actions.some(action => action.target === 'submit'), false);
  const before = raw.frames.find(frame => frame.label === 'before_event');
  assert.equal(before.presenter.password, 'secret');
  assert.equal(before.presenter.eraseData, true);
  assert.equal(before.presenter.action, 'uninitialized');
  assert.equal(before.presenter.submitEnabledRead.value, true);
  assert.equal(before.controls.find(control => control.name === 'submit').enabled, false);
  assert.equal(before.presenter.renderCalls.length, 0, 'Evaluator read must not masquerade as page rendering');
  assert.equal(before.presenter.serviceCalls.length, 0);
  assert.match(raw.failure.message, /"enabled":false/);
});

test('delayed actual UI enabled state is re-observed before the physical submit click', async () => {
  const { raw } = await probe({ delayedSubmit: true });
  assert.equal((await evaluate(raw)).status, 'pass');
  assert.equal(raw.submitReadiness.ready, true);
  assert.ok(raw.submitReadiness.attempts.some(attempt => attempt.enabled === false));
  const before = raw.frames.find(frame => frame.label === 'before_event');
  assert.equal(before.controls.find(control => control.name === 'submit').enabled, true);
  assert.ok(before.presenter.renderCalls.some(call => call.returned && call.value === true));
});
