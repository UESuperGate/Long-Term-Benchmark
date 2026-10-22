'use strict';

// Host evaluator regressions. Synthetic UI/SDK boundaries are not device proof.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const vm = require('node:vm');
const crypto = require('node:crypto');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const { install } = require('./Task13NativeUi.install.cjs');
const root = path.resolve(__dirname, '../../../..');
const candidate = path.join(root, 'final_dev_nodes/13_user_verification_final_25_03_2');
const featurePath = 'entry/src/main/ets/features/UserVerificationFeature.ets';
const pagePath = 'entry/src/main/ets/pages/Index.ets';
const spec = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks/13_user_verification/transitions.json'))).cases.find(c => c.key === 'profile_routes_user_request');
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const sources = [featurePath, pagePath].map(p => ({ path: p, sha256: digest(fs.readFileSync(path.join(candidate, p))) }));
const config = { bundleName: 'test.candidate', moduleName: 'entry', abilityName: 'EntryAbility',
  moduleUrl: '@bundle:test.candidate/entry/ets/features/UserVerificationFeature', sources };

function compile(file, modules = {}) {
  const module = { exports: {} };
  const output = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
  }).outputText;
  new vm.Script(`(function(exports,require,module){${output}\n})`).runInNewContext({ setTimeout, clearTimeout })(module.exports,
    name => { if (!modules[name]) throw new Error('Unbound module: ' + name); return modules[name]; }, module);
  return module.exports;
}

function generated(t) {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'task13-independent-'));
  t.after(() => fs.rmSync(work, { recursive: true, force: true }));
  const testRoot = path.join(work, 'entry/src/test');
  fs.mkdirSync(testRoot, { recursive: true });
  fs.cpSync(path.join(candidate, 'entry/src/main'), path.join(work, 'entry/src/main'), { recursive: true });
  fs.cpSync(path.join(candidate, 'AppScope'), path.join(work, 'AppScope'), { recursive: true });
  fs.writeFileSync(path.join(testRoot, 'native-bundle.js'), "import { createNativeContext } from './native-device-platform';\n" +
    'const adapterFactories = {tasks08_11: 1, tasks12_15: 2, tasks16_18: 3};\n' +
    'if (candidateUI) await bridge.ui.navigate(candidateUI.route);\ntry { await bridge.dispose(); } catch (error) {}\n');
  fs.writeFileSync(path.join(testRoot, 'NativeBundle.test.ets'), 'export default function nativeBundleTests(): void {}\n');
  return { work, testRoot };
}

test('installer edits generated evaluator only, adds no factory or static original-class import', t => {
  const f = generated(t), result = install(f.work);
  assert.equal(result.productionUnchanged, true);
  assert.equal(result.fixtures.length, 3);
  assert.deepEqual(result.config.sources, sources.slice().sort((a, b) => a.path.localeCompare(b.path)));
  const bundle = fs.readFileSync(result.bundleFile, 'utf8'), suite = fs.readFileSync(result.suiteFile, 'utf8');
  assert.match(bundle, /const adapterFactories = \{tasks08_11: 1, tasks12_15: 2, tasks16_18: 3\}/);
  assert.match(bundle, /attachTask13UI\(bridge, taskId, caseSpec.key\)/);
  assert.match(bundle, /disposeTask13UI/);
  assert.doesNotMatch(suite, /from ['"].*main\/ets/);
  assert.match(suite, /configureTask13UI/);
  assert.throws(() => install(f.work), /already installed/);
});

test('changed bundle lifecycle is rejected before writes and missing source is not invented', t => {
  const f = generated(t);
  fs.writeFileSync(path.join(f.testRoot, 'native-bundle.js'), "import { createNativeContext } from './native-device-platform';");
  assert.throws(() => install(f.work), /lifecycle changed/);
  assert.equal(fs.existsSync(path.join(f.testRoot, 'Task13NativeUi.js')), false);
  const g = generated(t);
  fs.unlinkSync(path.join(g.work, featurePath));
  assert.deepEqual(install(g.work).config.sources, sources.filter(s => s.path === pagePath));
});

function nativeRun(variant = 'matching') {
  const api = compile(path.join(__dirname, 'Task13NativeUi.js'));
  const original = compile(path.join(candidate, featurePath));
  const presenter = new original.UserVerificationPresenter(
    new original.VerificationRequest(original.VerificationRequestType.User, spec.given.profileUserId),
    new original.VerificationGateway(), new original.IdentityStateStore(spec.given.profileUserId, original.IdentityState.VerificationViolation));
  const descriptor = Object.getOwnPropertyDescriptor(original.UserVerificationPresenter.prototype, 'requestVerification');
  const frame = label => ({ label, bundleName: config.bundleName, focusedBundle: config.bundleName,
    completed: true, profileUserId: spec.given.profileUserId, route: { name: 'Index', path: 'pages/', index: 1 },
    controls: [{ id: 'verify_user_action', text: 'Verify Alice', visible: true, enabled: true, clickable: true }] });
  const observations = [], checkpoints = [];
  const bridge = { setObservationRecorder() {} };
  let ready = false, imports = 0;
  api.configureTask13UI(async () => {
    const before = frame('before_event');
    ready = true;
    await api.installTask13AfterReady(JSON.stringify(before));
    before.pageEvidenceJson = api.readTask13Page();
    if (variant === 'unbound') {
      const other = compile(path.join(candidate, featurePath));
      new other.UserVerificationPresenter(presenter.request, presenter.gateway, presenter.identityStore).requestVerification();
    } else {
      presenter.requestVerification();
      if (variant === 'multiple') new original.UserVerificationPresenter(presenter.request, presenter.gateway, presenter.identityStore).requestVerification();
    }
    const after = frame('after_event');
    after.controls = [{ id: 'verification_remote_accepted', visible: true, enabled: true, clickable: true }];
    after.pageEvidenceJson = api.readTask13Page();
    const result = { taskId: spec.taskId, caseId: spec.caseId, key: spec.key, traceDigest: spec.traceDigest,
      bundleName: config.bundleName, frames: [before, after], unsupported: '',
      actions: [{ id: 'verify_user_action', executed: true, before: 'before_event', after: 'after_event' }] };
    if (variant === 'wrong_identity') result.traceDigest = 'wrong';
    if (variant === 'incomplete') after.completed = false;
    if (variant === 'no_action') result.actions = [];
    if (variant === 'wrong_action_frame') result.actions[0].before = 'another_frame';
    if (variant === 'wrong_given') before.profileUserId = '@other:example.org';
    return JSON.stringify(result);
  }, JSON.stringify(config), async url => {
    assert.equal(ready, true, 'Original module import must follow mounted profile readiness');
    assert.equal(url, config.moduleUrl); imports++; return original;
  });
  api.attachTask13UI(bridge, spec.taskId, spec.key);
  bridge.setObservationRecorder(value => observations.push(value));
  return { api, bridge, original, presenter, observations, checkpoints, imports: () => imports,
    run: () => bridge.evaluateTask13UI({ taskId: spec.taskId, caseSpec: spec,
      trace: (label, state) => checkpoints.push({ label, state }) }),
    dispose() { bridge.disposeTask13UI(); assert.deepEqual(Object.getOwnPropertyDescriptor(original.UserVerificationPresenter.prototype, 'requestVerification'), descriptor); } };
}

test('real production receiver/request/gateway is observed; waiting branch is never invented as navigation', async () => {
  const f = nativeRun();
  const result = await f.run();
  assert.deepEqual(JSON.parse(JSON.stringify(result.observed)), { request: { type: 'user', userId: spec.given.profileUserId } });
  assert.equal(result.observed.route, undefined);
  assert.match(result.unsupported, /navigation route and non-self GIVEN/);
  assert.equal(result.invariantChecks[0].passed, true);
  assert.equal(f.presenter.gateway.requestUserCalls, 1);
  assert.equal(f.presenter.gateway.requestCurrentSessionCalls, 0);
  assert.equal(f.imports(), 1);
  const page = result.evidence[0].nativePageTransition.frames[1].pageEvidence;
  assert.equal(page.calls[0].before.step, 'initial');
  assert.equal(page.calls[0].after.step, 'awaiting_other_device_response');
  assert.equal(page.calls[1].sameGatewayReceiver, true);
  assert.equal(page.calls[1].parentSequence, page.calls[0].sequence);
  assert.equal(f.observations.length, 1);
  f.dispose();
});

for (const variant of ['unbound', 'multiple', 'wrong_identity', 'incomplete', 'no_action', 'wrong_action_frame', 'wrong_given']) {
  test('missing original-page prerequisite cannot become a request result: ' + variant, async () => {
    const f = nativeRun(variant), result = await f.run();
    assert.ok(result.unsupported);
    assert.equal(result.observed.request, undefined);
    assert.equal(result.invariantChecks.length, 0);
    f.dispose();
  });
}

test('unchanged shared evaluateCase receives actual arrays and keeps route missing as NS', async () => {
  const f = nativeRun();
  const evaluator = fs.readFileSync(path.join(root, 'scripts/runtime_semantics/arkts_runtime.cjs'), 'utf8');
  const ast = ts.createSourceFile('runtime.cjs', evaluator, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
  const shared = ['snapshot', 'compareExpected', 'evaluateCase'].map(name =>
    ast.statements.find(s => ts.isFunctionDeclaration(s) && s.name?.text === name).getText(ast)).join('\n');
  const runtime = fs.readFileSync(path.join(__dirname, 'bundle-runtime.js'), 'utf8').replace('export async function runNativeCase', 'async function runNativeCase');
  const context = vm.createContext({ bridge: f.bridge, spec, candidateUI: { productionSource: sources[1] },
    factories: {}, metadata: {}, platformConstants: {},
    adapter: { runCase: args => f.bridge.evaluateTask13UI(args) } });
  vm.runInContext(shared + '\n' + runtime + '\nactiveNativeContext = bridge;', context);
  const row = await vm.runInContext('evaluateCase(spec.taskId, spec, "/project", adapter)', context);
  assert.equal(row.status, 'not_scored');
  assert.deepEqual(Array.from(row.missingObservations), ['route']);
  assert.equal(row.invariantChecks[0].passed, true);
  assert.equal(row.productionSources[0].sha256, sources[1].sha256);
  assert.equal(row.calls[0].nativeUI, true);
  assert.equal(row.checkpoints.length, 2);
  assert.equal(row.calls.some(c => c.method === 'constructor'), false, 'No domain factory or second presenter was executed by the bridge');
  f.dispose();
});

test('postload import rejects fabricated readiness and only the assigned case attaches', async () => {
  const api = compile(path.join(__dirname, 'Task13NativeUi.js'));
  let imports = 0;
  api.configureTask13UI(async () => { await api.installTask13AfterReady('{}'); return '{}'; }, JSON.stringify(config), async () => { imports++; return {}; });
  assert.equal(api.attachTask13UI({}, '12_report_room', 'blank_reason_disabled'), false);
  const bridge = { setObservationRecorder() {} };
  api.attachTask13UI(bridge, spec.taskId, spec.key);
  const result = await bridge.evaluateTask13UI({ taskId: spec.taskId, caseSpec: spec, trace() {} });
  assert.match(result.unsupported, /actual profile/);
  assert.equal(imports, 0);
  bridge.disposeTask13UI();
});

for (const failure of ['', 'no_control', 'click_error', 'frame_error', 'frame_string', 'frame_circular']) {
  test('actual UiTest program orders launch/readiness/import/click and retains partial frames: ' + (failure || 'normal'), async () => {
    const api = compile(path.join(__dirname, 'Task13NativeUi.js'));
    const original = compile(path.join(candidate, featurePath));
    const p = new original.UserVerificationPresenter(new original.VerificationRequest(original.VerificationRequestType.User, spec.given.profileUserId),
      new original.VerificationGateway(), new original.IdentityStateStore(spec.given.profileUserId, original.IdentityState.VerificationViolation));
    const events = [], progress = [];
    const frameFailure = failure === 'frame_string' ? 'original SDK frame error' :
      Object.assign(new Error('original SDK frame error'), { code: 17000001, errorInfo: { operation: 'findWindow' } });
    if (failure === 'frame_circular') frameFailure.circular = frameFailure;
    const context = { abilityInfo: { bundleName: config.bundleName, moduleName: config.moduleName },
      toJSON() { throw new Error('SDK Context cannot be cloned'); } };
    const selector = { id(value) { return { ...this, kind: 'id', value }; }, text(value) { return { ...this, kind: 'text', value }; },
      inWindow(bundle) { return { ...this, bundle }; } };
    const bounds = { left: 0, top: 0, right: 100, bottom: 100 };
    const component = (id, text, clickable) => ({
      async getId() { return id; }, async getText() { return text; }, async getType() { return clickable ? 'Button' : 'Text'; },
      async getBounds() { return bounds; }, async isEnabled() { return true; }, async isClickable() { return clickable; },
      async click() { events.push('click'); if (failure === 'click_error') throw new Error('original SDK click error'); p.requestVerification(); }
    });
    const driver = {
      async findWindow() {
        if (failure.startsWith('frame_')) throw frameFailure;
        return { async getBundleName() { return config.bundleName; }, async getBounds() { return bounds; } };
      },
      async findComponents(query) {
        assert.equal(query.bundle, config.bundleName);
        if (query.kind === 'text' && query.value === spec.given.profileUserId) return [component('', spec.given.profileUserId, false)];
        if (query.value === 'verify_user_action' && p.step === 'initial' && failure !== 'no_control') return [component(query.value, 'Verify Alice', true)];
        if (['verification_remote_accepted', 'cancel_verification'].includes(query.value) && p.step !== 'initial') return [component(query.value, query.value, true)];
        return null;
      }
    };
    const delegator = { async addAbilityMonitor() {}, async startAbility(want) { events.push('launch'); assert.equal(want.moduleName, 'entry'); },
      async waitAbilityMonitor() { return { context }; }, async removeAbilityMonitor() { events.push('cleanup_monitor'); } };
    const native = compile(path.join(__dirname, 'Task13UiTest.ets'), {
      '@ohos.UiTest': { Driver: { create: () => driver }, ON: selector },
      '@ohos.app.ability.abilityDelegatorRegistry': { default: { getAbilityDelegator: () => delegator } },
      '@ohos.window': { default: { async getLastWindow(actual) {
        assert.equal(actual, context);
        return { getUIContext() { return { runScopedTask(fn) { fn(); }, getRouter() { return { getState() { return { name: 'Index', path: 'pages/', index: 1 }; } }; } }; } };
      } } },
      './Task13NativeUi': { ...api, publishTask13UI(json) { progress.push(JSON.parse(json)); api.publishTask13UI(json); } }
    });
    api.configureTask13UI((caseJson, configJson) => native.runTask13UI(JSON.parse(caseJson), JSON.parse(configJson)),
      JSON.stringify(config), async () => { events.push('module_import'); return original; });
    const bridge = { setObservationRecorder() {} };
    api.attachTask13UI(bridge, spec.taskId, spec.key);
    const traces = [];
    const result = await bridge.evaluateTask13UI({ taskId: spec.taskId, caseSpec: spec, trace: (label, value) => traces.push({ label, value }) });
    if (!failure) {
      assert.deepEqual(events, ['launch', 'module_import', 'click', 'cleanup_monitor']);
      assert.equal(result.observed.request.userId, spec.given.profileUserId);
      const raw = result.evidence[0].nativePageTransition;
      assert.equal(raw.frames[0].label, 'candidate_ready');
      assert.equal(raw.frames.at(-1).route.name, 'Index');
      assert.equal(raw.frames.at(-1).pageEvidence.calls[0].before.step, 'initial');
      assert.equal(raw.frames.at(-1).pageEvidence.calls[0].after.step, 'awaiting_other_device_response');
    } else {
      assert.equal(result.observed.request, undefined);
      assert.equal(events.at(-1), 'cleanup_monitor');
      if (failure === 'no_control') assert.equal(events.includes('module_import'), false);
      else if (failure.startsWith('frame_')) {
        assert.match(result.unsupported, /original SDK frame error/);
        assert.equal(events.includes('module_import'), false);
        assert.equal(events.includes('click'), false);
        const raw = result.evidence[0].nativePageTransition;
        for (const frame of raw.frames) {
          assert.equal(frame.completed, false);
          assert.equal(frame.errorDetails.message, 'original SDK frame error');
          assert.equal(frame.errorDetails.stack, frameFailure.stack || '');
          if (failure === 'frame_error') {
            const info = JSON.parse(frame.errorDetails.errorInfo);
            assert.equal(info.code, 17000001);
            assert.equal(info.errorInfo.operation, 'findWindow');
          } else if (failure === 'frame_circular') assert.match(frame.errorDetails.errorInfo, /serialization:/);
          else assert.equal(JSON.parse(frame.errorDetails.errorInfo), frameFailure);
        }
        assert.ok(progress.some(value => value.frames.some(frame => frame.errorDetails?.message === 'original SDK frame error')));
      }
      else assert.match(result.unsupported, /original SDK click error/);
    }
    assert.ok(result.unsupported, 'No logical-route/current-user inference even after the real call chain');
    assert.ok(progress.some(value => value.frames.some(f => !f.completed)));
    assert.ok(traces.some(t => t.label === 'task13_after_event'));
    bridge.disposeTask13UI();
  });
}
