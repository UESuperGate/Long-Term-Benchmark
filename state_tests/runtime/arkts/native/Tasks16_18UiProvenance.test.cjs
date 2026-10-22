'use strict';

// Local recorder/loader regression, not device evidence. Execute the actual
// feature with unit-test SDK/UI boundaries through the unchanged shared gate.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const { runCase } = require('../tasks16_18.cjs');
const root = path.resolve(__dirname, '../../../..');
const feature = 'entry/src/main/ets/features/NotificationSoundFeature.ets';
const project = path.join(root, 'final_dev_nodes/18_custom_notification_sounds_final_26_06_1');
const taskId = '18_custom_notification_sounds';
const spec = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks', taskId, 'transitions.json')))
  .cases.find(item => item.key === 'message_picker_launch');
const copy = value => JSON.parse(JSON.stringify(value));
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
function factory(source) {
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020 } }).outputText;
  return new Function('exports', 'require', 'module', code);
}
function exportsOf(create, require = () => { throw new Error('Unexpected dependency'); }) {
  const module = { exports: {} };
  create(module.exports, require, module);
  return module.exports;
}

async function evaluate(mode) {
  const bytes = fs.readFileSync(path.join(project, feature), 'utf8');
  const source = { path: feature, sha256: hash(bytes) };
  if (mode === 'missing_source') delete source.path;
  const createFeature = factory(bytes);
  const stored = new Map();
  const types = exportsOf(createFeature, name => ({ default: name === '@ohos.data.preferences' ? {
    async getPreferences() { return {
      async get(key, fallback) { return stored.has(key) ? stored.get(key) : fallback; },
      async put(key, value) { stored.set(key, value); }, async flush() {}
    }; }
  } : {} }));
  const api = exportsOf(factory(fs.readFileSync(path.join(__dirname, 'Tasks16_18NativeUi.js'), 'utf8')));
  const bundleName = 'unit.notifications.test';
  const context = { abilityInfo: { bundleName, moduleName: 'entry', name: 'EntryAbility' },
    filesDir: '/unit/files', preferencesDir: '/unit/preferences', cacheDir: '/unit/cache' };
  // The mounted page owns this instance before observation begins.
  const presenter = new types.NotificationSettingsPresenter(new types.NotificationSoundStore(),
    new types.NotificationSoundCopier(), new types.NotificationChannelGateway());
  await presenter.load(context);
  let resolve;
  const pending = new Promise(done => { resolve = done; });
  class AudioViewPicker { constructor(scope) { this.context = scope; } select() { return pending; } }
  const node = (id, text = '') => ({ id, text, enabled: true, clickable: true,
    bounds: { left: 0, top: 0, right: 100, bottom: 50 } });
  const readiness = { label: 'candidate_entry', focusedBundle: bundleName, completed: true,
    nodes: [node('', 'Notifications'), node('message_sound_row')] };
  const binding = { bundleName, moduleName: 'entry', abilityName: 'EntryAbility', feature: 'NotificationSoundFeature',
    presenterExport: 'NotificationSettingsPresenter', moduleUrl: `@bundle:${bundleName}/entry/ets/features/NotificationSoundFeature`,
    importTiming: 'after-mounted-page-positive-controls-before-message-dialog' };
  const original = types.NotificationSettingsPresenter.prototype.launchSystemPicker;
  const recorder = function() {};
  const bridge = { modules: {}, capabilities: { context: { available: true } }, setObservationRecorder: recorder };
  const probe = async json => {
    const request = JSON.parse(json);
    await api.bindTasks16To18OriginalPage(context, JSON.stringify(readiness));
    presenter.showDialog('message');
    const before = { label: 'launch_audio_picker_before', focusedBundle: bundleName,
      nodes: [node('message_sound_dialog'), node('message_sound_picker')],
      pageStateJson: await api.readTasks16To18Page(context), pickerStateJson: api.readTasks16To18Picker() };
    presenter.launchSystemPicker('message');
    if (mode === 'wrong_token') presenter.pendingMessageSoundPickerLaunch++;
    assert.equal(new AudioViewPicker(context).select(), pending);
    const after = { label: 'after_event', focusedBundle: 'com.ohos.filepicker', completed: true,
      nodes: [], focusedNodes: [node('system_audio')], pickerStateBeforeJson: api.readTasks16To18Picker(),
      pageStateJson: await api.readTasks16To18Page(context), pickerStateJson: api.readTasks16To18Picker() };
    return JSON.stringify({ ...request, schemaVersion: 1, observationLevel: 'native_candidate_ui',
      checkpoints: [readiness, before, after],
      actions: [{ kind: 'id', value: 'message_sound_picker', before: before.label, after: after.label }] });
  };
  let imports = 0;
  api.configureTasks16To18UI(probe, bundleName, JSON.stringify(binding), JSON.stringify(source), AudioViewPicker,
    async url => { imports++; assert.equal(url, binding.moduleUrl); return mode === 'duplicate_class' ?
      exportsOf(createFeature, () => ({ default: {} })) : types; });
  api.attachTasks16To18UI(bridge, taskId, spec.key);
  if (mode === 'missing_recorder') bridge.setObservationRecorder = recorder;
  if (mode === 'recorder_throws') {
    const attach = bridge.setObservationRecorder;
    bridge.setObservationRecorder = function() { attach.call(this, () => { throw new Error('recorder failure'); }); };
  }
  const runtimeSource = fs.readFileSync(path.join(root, 'scripts/runtime_semantics/arkts_runtime.cjs'), 'utf8');
  const ast = ts.createSourceFile('runtime.cjs', runtimeSource, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
  const shared = ['snapshot', 'compareExpected', 'evaluateCase'].map(name =>
    ast.statements.find(s => ts.isFunctionDeclaration(s) && s.name?.text === name).getText(ast)).join('\n');
  const runtime = fs.readFileSync(path.join(__dirname, 'bundle-runtime.js'), 'utf8')
    .replace('export async function runNativeCase', 'async function runNativeCase');
  const page = 'entry/src/main/ets/pages/Index.ets';
  let loads = 0;
  const sandbox = vm.createContext({ bridge, spec, taskId,
    candidateUI: { productionSource: { path: page, sha256: hash(fs.readFileSync(path.join(project, page))) } },
    factories: { ['/project/' + feature]: (...args) => { loads++; createFeature(...args); } },
    metadata: { ['/project/' + feature]: source }, platformConstants: {},
    adapter: { runCase: args => runCase({ ...args, native: bridge,
      load() { loads++; throw new Error('Original-page adapter must not load another module'); } }) }, setTimeout, clearTimeout });
  try {
    vm.runInContext(shared + '\n' + runtime + '\nactiveNativeContext = bridge;', sandbox);
    const row = copy(await vm.runInContext('evaluateCase(taskId, spec, "/project", adapter)', sandbox));
    return { row, loads, imports };
  } finally {
    resolve([]);
    bridge.disposeTasks16To18UI();
    assert.equal(bridge.setObservationRecorder, recorder);
    assert.equal(types.NotificationSettingsPresenter.prototype.launchSystemPicker, original);
  }
}

test('same-page observer supplies calls and source provenance without another load or presenter', async () => {
  const { row, loads, imports } = await evaluate('complete');
  assert.equal(row.status, 'pass', row.reason);
  assert.equal(loads, 0);
  assert.equal(imports, 1);
  const page = 'entry/src/main/ets/pages/Index.ets';
  assert.deepEqual(row.productionSources, [{ path: page, sha256: hash(fs.readFileSync(path.join(project, page))) }]);
  assert.ok(row.calls.every(call => call.observation.productionSource.path === feature &&
    call.observation.productionSource.sha256 === hash(fs.readFileSync(path.join(project, feature))) &&
    call.observation.originalModuleUrl === '@bundle:unit.notifications.test/entry/ets/features/NotificationSoundFeature'));
  const calls = row.calls.filter(call => call.nativeUI).map(call => call.observation.actualCall).sort((a, b) => a.sequence - b.sequence);
  assert.deepEqual(calls.map(call => call.method), ['showDialog', 'launchSystemPicker', 'dismissDialog']);
  assert.ok(calls.every(call => call.instanceId === 1 && call.outcome === 'returned'));
  assert.ok(row.calls.every(call => call.nativeUI), 'Source registration must not invoke or construct the loader copy');
  assert.ok(row.checkpoints.some(item => item.label === 'native_ui_launch_audio_picker_before'));
  assert.ok(row.checkpoints.some(item => item.label === 'native_ui_after_event'));
  const raw = row.evidence.find(item => item.nativePageTransition).nativePageTransition;
  assert.equal(JSON.parse(raw.checkpoints.at(-1).pickerStateJson).calls[0].contextEvidence.observedLoadCall, false);
});

for (const mode of ['missing_recorder', 'duplicate_class', 'missing_source', 'recorder_throws']) {
  test('provenance gap stays not_scored: ' + mode, async () => {
    const { row } = await evaluate(mode);
    assert.equal(row.status, 'not_scored');
    if (mode === 'missing_recorder') {
      assert.equal(row.calls.length, 0);
      assert.match(row.reason, /Incomplete runtime evidence/);
    }
    if (mode === 'duplicate_class') assert.equal(row.calls.length, 0);
    if (mode === 'missing_source') {
      assert.equal(row.calls.length, 0);
      assert.match(row.reason, /production source\/module\/call provenance/);
    }
    if (mode === 'recorder_throws') assert.match(row.reason, /recorder failed/);
  });
}

test('real wrong token is still a semantic fail through the unchanged gate', async () => {
  const { row } = await evaluate('wrong_token');
  assert.equal(row.status, 'fail', row.reason);
  assert.equal(row.observed.messagePickerToken, 2);
  assert.ok(row.assertionFailures.some(item => item.path === 'messagePickerToken'));
});
