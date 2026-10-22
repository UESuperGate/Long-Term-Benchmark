'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const { runCase, treeHasText } = require('./Task16Revision5.adapter.cjs');
const { compareExpected } = require('../../../scripts/runtime_semantics/arkts_runtime.cjs');

const root = path.resolve(__dirname, '../../..');
const canonicalContract = path.join(root, 'benchmark_tasks/16_identity_reset/transitions.json');
const auditedContract = path.join(root,
  'experiment_results/runtime_transition_20261020/contract_audit/revision_5_task16/after/transitions.json');
assert.deepEqual(fs.readFileSync(canonicalContract), fs.readFileSync(auditedContract));
const contract = JSON.parse(fs.readFileSync(canonicalContract));
const finalFeature = path.join(root,
  'final_dev_nodes/16_identity_reset_final_0_5_1/entry/src/main/ets/features/IdentityResetFeature.ets');
const baseFeature = path.join(root,
  '16_identity_reset_base_0_5_0/entry/src/main/ets/features/SecureBackupBase.ets');

function compile(file) {
  const source = fs.readFileSync(file, 'utf8');
  const result = ts.transpileModule(source, { reportDiagnostics: true,
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } });
  assert.equal((result.diagnostics || []).filter(item => item.category === ts.DiagnosticCategory.Error).length, 0);
  const module = { exports: {} };
  vm.runInNewContext(`(function(exports, module) {${result.outputText}\n})`, { Promise, Error, console })(module.exports, module);
  return module.exports;
}

function page(title) {
  return { completeTree: true, candidateRouteVerified: true, route: { path: 'pages/', name: 'Index' },
    tree: { $attrs: {}, $children: [{ $attrs: { text: title }, $children: [] }] } };
}

function rawUi(spec) {
  const common = { taskId: spec.taskId, caseId: spec.caseId, traceDigest: spec.traceDigest,
    entryExecuted: true, confirmExecuted: true, eventExecuted: true, frames: [] };
  const beforeConfirmation = { label: 'before_confirmation', presenter: { handleState: 'uninitialized' }, controls: [] };
  if (spec.key === 'oidc_handle_routes_and_resets') {
    const before = { label: 'before_event', presenter: { handleState: 'uninitialized' }, controls: [] };
    const after = { label: 'after_event', presenter: { handleState: 'success', approvalUrl: 'https://id.example/reset',
      approvalSurface: 'embedded_webview', calls: [{ owner: 'oidc_handle', method: 'resetOidc', returned: true }] },
    controls: [{ name: 'oidcWebview', present: true, visible: true, enabled: true }] };
    return { ...common, frames: [before, after] };
  }
  const before = { label: 'before_event', presenter: { handleState: 'success', resetJobActive: true,
    completionWatcherActive: true }, controls: [] };
  const after = { label: 'after_event', presenter: { handleState: 'uninitialized', resetJobActive: false,
    completionWatcherActive: false }, controls: [] };
  return { ...common, frames: [beforeConfirmation, before, after] };
}

function rawBaseUi() {
  const controls = (enabled = false) => [
    { name: 'root', present: true, visible: true },
    { name: 'finalTitle', present: false, visible: false },
    { name: 'finalEntry', present: false, visible: false },
    { name: 'enableBackup', present: true, visible: true, enabled: true, clickable: true },
    { name: 'enabledState', present: enabled, visible: enabled }
  ];
  return { observationLevel: 'native_candidate_ui', entryExecuted: true, eventExecuted: true,
    positiveControl: 'Backup state: enabled', actions: [{ target: 'enableBackup', executed: true }],
    frames: [{ label: 'before_event', windowIdentity: { hostVerified: true }, controls: controls(false) },
      { label: 'after_event', windowIdentity: { hostVerified: true }, controls: controls(true) }] };
}

test('shape and tree helpers are strict', () => {
  assert.equal(treeHasText(page('Chat backup').tree, 'Chat backup'), true);
  assert.equal(treeHasText(page('Chat backup').tree, 'Reset cryptographic identity'), false);
});

test('all ten final revision5 transitions match expected values and invariants', async () => {
  for (const spec of contract.cases) {
    const result = await runCase({ taskId: contract.taskId, caseSpec: spec, evaluatorRole: 'final', project: '/arbitrary/candidate',
      load: async request => {
        assert.equal(request, 'entry/src/main/ets/features/IdentityResetFeature.ets');
        return compile(finalFeature);
      },
      native: { ui: { snapshot: () => page('Reset cryptographic identity') },
        runTask16UI: async () => rawUi(spec) }, trace() {} });
    const comparison = compareExpected(spec.expected, result.observed);
    assert.deepEqual(comparison, { failures: [], missing: [] }, spec.caseId);
    assert.equal(result.invariantChecks.length, spec.invariants.length, spec.caseId);
    assert.equal(result.invariantChecks.every(item => item.passed), true, spec.caseId);
    if (spec.key === 'handle_failure_recovers') {
      assert.deepEqual(result.observed.stateSequence,
        ['uninitialized', 'loading', 'failure', 'uninitialized', 'loading']);
    }
  }
});

test('OIDC UI binding rejects the obsolete webview observer name', async () => {
  const spec = contract.cases.find(item => item.key === 'oidc_handle_routes_and_resets');
  const raw = rawUi(spec);
  raw.frames.find(frame => frame.label === 'after_event').controls[0].name = 'webview';
  const result = await runCase({ taskId: contract.taskId, caseSpec: spec, evaluatorRole: 'final',
    project: '/arbitrary/candidate', load: async () => compile(finalFeature),
    native: { ui: { snapshot: () => page('Reset cryptographic identity') },
      runTask16UI: async () => raw }, trace() {} });
  assert.equal(result.invariantChecks.some(item => !item.passed), true);
});

test('OIDC UI binding rejects the obsolete generic handle owner', async () => {
  const spec = contract.cases.find(item => item.key === 'oidc_handle_routes_and_resets');
  const raw = rawUi(spec);
  raw.frames.find(frame => frame.label === 'after_event').presenter.calls[0].owner = 'handle';
  const result = await runCase({ taskId: contract.taskId, caseSpec: spec, evaluatorRole: 'final',
    project: '/arbitrary/candidate', load: async () => compile(finalFeature),
    native: { ui: { snapshot: () => page('Reset cryptographic identity') },
      runTask16UI: async () => raw }, trace() {} });
  assert.equal(result.observed.pollEffect, null);
  assert.equal(result.invariantChecks.some(item => !item.passed), true);
});

test('OIDC UI binding rejects a missing real before-event frame', async () => {
  const spec = contract.cases.find(item => item.key === 'oidc_handle_routes_and_resets');
  const raw = rawUi(spec);
  raw.frames = raw.frames.filter(frame => frame.label !== 'before_event');
  await assert.rejects(runCase({ taskId: contract.taskId, caseSpec: spec, evaluatorRole: 'final',
    project: '/arbitrary/candidate', load: async () => compile(finalFeature),
    native: { ui: { snapshot: () => page('Reset cryptographic identity') },
      runTask16UI: async () => raw }, trace() {} }), /Original-page OIDC transition incomplete/);
});

test('OIDC UI binding rejects a missing physical-confirm receipt', async () => {
  const spec = contract.cases.find(item => item.key === 'oidc_handle_routes_and_resets');
  const raw = rawUi(spec);
  raw.confirmExecuted = false;
  await assert.rejects(runCase({ taskId: contract.taskId, caseSpec: spec, evaluatorRole: 'final',
    project: '/arbitrary/candidate', load: async () => compile(finalFeature),
    native: { ui: { snapshot: () => page('Reset cryptographic identity') },
      runTask16UI: async () => raw }, trace() {} }), /Original-page OIDC transition incomplete/);
});

test('all ten base prefixes preserve real evidence without fabricating canonical post-state', async () => {
  for (const spec of contract.cases) {
    const result = await runCase({ taskId: contract.taskId, caseSpec: spec, evaluatorRole: 'base', project: '/arbitrary/candidate',
      load: async request => {
        assert.equal(request, 'entry/src/main/ets/features/SecureBackupBase.ets');
        return compile(baseFeature);
      }, native: { runTask16BaseUI: async () => rawBaseUi() }, trace() {} });
    const comparison = compareExpected(spec.expected, result.observed);
    assert.ok(comparison.missing.length > 0, spec.caseId);
    assert.deepEqual(result.observed, {});
    assert.deepEqual(result.invariantChecks, []);
    assert.equal(result.evidence.some(item => item.kind === 'native_base_entry_absence'), true);
  }
});

test('agent role classifies behavior from the runtime entry and not the project path', async () => {
  const spec = contract.cases[0];
  const base = rawBaseUi();
  base.classification = 'feature_entry_absent';
  const result = await runCase({ taskId: contract.taskId, caseSpec: spec, evaluatorRole: 'agent',
    project: '/contains/final/in/name', load: async () => { throw new Error('agent base must not load a named base module'); },
    native: { runTask16BaseUI: async () => base }, trace() {} });
  assert.equal(result.evidence.some(item => item.kind === 'native_candidate_entry_classification'), true);
  assert.deepEqual(result.invariantChecks, []);
});

test('candidate entry bridge records real runtime classification and restores recorder', async () => {
  const bridgeModule = compile(path.join(root, 'state_tests/runtime/arkts/native/Task16BaseEntryBridge.js'));
  const raw = { entryExecuted: true, eventExecuted: true, classification: 'feature_entry_absent',
    frames: [{ label: 'before_event' }, { label: 'after_event' }], actions: [{ executed: true }] };
  const sources = [{ path: 'entry/src/main/ets/pages/Index.ets', sha256: 'a'.repeat(64) }];
  bridgeModule.configureTask16BaseEntry(async () => JSON.stringify(raw), 'candidate.test', JSON.stringify(sources));
  const original = function(callback) { this.upstream = callback; };
  const bridge = { setObservationRecorder: original };
  assert.equal(bridgeModule.attachTask16BaseEntry(bridge, contract.taskId), true);
  const observations = [];
  bridge.setObservationRecorder(value => observations.push(value));
  const returned = await bridge.runTask16BaseUI();
  assert.equal(JSON.stringify(returned.productionSources), JSON.stringify(sources));
  assert.equal(observations[0].method, 'Task16.runtimeEntryClassification');
  assert.equal(observations[0].classification, 'feature_entry_absent');
  bridge.disposeTask16BaseUI();
  assert.equal(bridge.setObservationRecorder, original);
});

test('base-absent launch cleanup defers same-bundle termination but removes observers', async () => {
  const { createTask16LaunchController } = compile(path.join(root,
    'state_tests/runtime/arkts/native/Task16Launch.js'));
  const events = [];
  const ability = { context: { abilityInfo: { bundleName: 'candidate.test', name: 'EntryAbility', moduleName: 'entry' },
    async terminateSelf() { events.push('terminate'); } } };
  let monitor, lifecycle;
  const launch = createTask16LaunchController({
    applicationContext: { on(_name, value) { lifecycle = value; return 16; },
      async off() { events.push('lifecycle:remove'); } },
    delegator: { async addAbilityMonitor(value) { monitor = value; },
      async startAbility() { monitor.onAbilityCreate(ability); monitor.onAbilityForeground(ability); },
      async removeAbilityMonitor() { events.push('monitor:remove'); } },
    async delay() {}
  }, 'candidate.test');
  await launch.start();
  lifecycle.onWindowStageCreate(ability, {});
  await launch.dispose({ deferTermination: true });
  assert.equal(events.includes('terminate'), false);
  assert.deepEqual(events, ['monitor:remove', 'lifecycle:remove']);
  assert.equal(launch.read().events.some(item => item.method === 'terminationDeferredToExternalUninstall'), true);
});

test('entry classifier hands the same live window to UI and cleans up without terminating the harness', async () => {
  const { createTask16LaunchLease } = compile(path.join(root, 'state_tests/runtime/arkts/native/Task16Launch.js'));
  const events = [], frame = { stageMainWindowId: 16 };
  const leases = createTask16LaunchLease(bundleName => {
    events.push(['factory', bundleName]);
    return { async start() { events.push('start'); }, async check() { return frame; },
      read() { return frame; }, async dispose(options) { events.push(['dispose', options.deferTermination]); } };
  });
  const classifier = leases.acquire('candidate.test');
  await classifier.start();
  classifier.retain();
  await classifier.dispose();
  assert.equal(events.some(item => Array.isArray(item) && item[0] === 'dispose'), false);
  const ui = leases.acquire('candidate.test');
  await ui.start();
  assert.equal(await ui.check({}), frame);
  assert.equal(ui.read(), classifier.read());
  await ui.dispose();
  await leases.release('candidate.test');
  assert.deepEqual(events, [['factory', 'candidate.test'], 'start', ['dispose', true]]);
});

test('domain-only classification lease is released by awaited bridge disposal', async () => {
  const { createTask16LaunchLease } = compile(path.join(root, 'state_tests/runtime/arkts/native/Task16Launch.js'));
  let cleaned = false;
  const leases = createTask16LaunchLease(() => ({ async start() {}, read() {},
    async dispose(options) { await Promise.resolve(); assert.equal(options.deferTermination, true); cleaned = true; } }));
  const classifier = leases.acquire('candidate.test');
  await classifier.start();
  classifier.retain();
  await classifier.dispose();
  const bridgeModule = compile(path.join(root, 'state_tests/runtime/arkts/native/Task16BaseEntryBridge.js'));
  bridgeModule.configureTask16BaseEntry(async () => '{}', 'candidate.test', '[]', bundle => leases.release(bundle));
  const bridge = { setObservationRecorder() {} };
  bridgeModule.attachTask16BaseEntry(bridge, contract.taskId);
  await bridge.disposeTask16BaseUI();
  assert.equal(cleaned, true);
});

test('present-entry classifier captures a new after frame and retains the live launch', async () => {
  const { runTask16BaseEntry } = compile(path.join(root, 'state_tests/runtime/arkts/native/Task16BaseEntry.js'));
  const events = [];
  const selector = value => ({ value, inWindow() { return this; }, text(text) { this.value = text; return this; } });
  const ON = { text: selector, id: selector, type: selector };
  let samples = 0;
  const driver = { async findComponents(query) {
    if (!['Reset cryptographic identity', 'identity_reset_continue'].includes(query.value)) return [];
    return [{ async getBounds() { return { left: 0, top: 0, right: 100, bottom: 100 }; },
      async isEnabled() { return true; }, async isClickable() { return true; },
      async getId() { return query.value; }, async getText() { return query.value; },
      async getType() { return 'Button'; } }];
  } };
  const launch = { async start() {}, async check() { samples++; }, read() { return { lastReady: { sample: samples } }; },
    retain() { events.push('retain'); }, async dispose() { events.push('dispose'); } };
  const raw = JSON.parse(await runTask16BaseEntry('candidate.test', driver, ON, launch, true));
  assert.equal(raw.classification, 'feature_entry_present');
  assert.deepEqual(raw.frames.map(frame => frame.windowIdentity.sample), [1, 2]);
  assert.deepEqual(events, ['retain', 'dispose']);
});

test('revision5 installer awaits launch release for standalone agent controls without changing production', t => {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'ltb-task16-lease-test-'));
  t.after(() => fs.rmSync(work, { recursive: true, force: true }));
  const origin = path.join(root, 'final_dev_nodes/16_identity_reset_final_0_5_1');
  for (const relative of ['entry/src/main', 'AppScope']) {
    fs.cpSync(path.join(origin, relative), path.join(work, relative), { recursive: true });
  }
  const dir = path.join(work, 'entry/src/test');
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'native-bundle.js'),
    'if (candidateUI) await bridge.ui.navigate(candidateUI.route);\n' +
    'module.exports.runCase({ ...context, native: bridge,\n' +
    'try { await bridge.dispose(); } catch (error) {}');
  fs.writeFileSync(path.join(dir, 'NativeBundle.test.ets'), 'export default function nativeBundleTests(): void {}');
  const installed = require('./native/Task16Revision5.install.cjs').install(work, 'agent');
  assert.equal(installed.productionUnchanged, true);
  assert.match(fs.readFileSync(path.join(dir, 'native-bundle.js'), 'utf8'), /await bridge\.disposeTask16BaseUI\(\)/);
  assert.match(fs.readFileSync(path.join(dir, 'NativeBundle.test.ets'), 'utf8'), /, releaseTask16Launch\);/);
  for (const item of installed.production) {
    assert.deepEqual(fs.readFileSync(path.join(work, item.path)), fs.readFileSync(path.join(origin, item.path)));
  }
});
