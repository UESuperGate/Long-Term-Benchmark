'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const ts = require(process.env.LTB_TYPESCRIPT ||
  '/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const { install } = require('./Tasks16_18NativeUi.install.cjs');
const root = path.resolve(__dirname, '../../../..');

function generatedProject(t) {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'Tasks16_18_install_test_'));
  t.after(() => fs.rmSync(work, { recursive: true, force: true }));
  const testRoot = path.join(work, 'entry/src/test');
  fs.mkdirSync(testRoot, { recursive: true });
  fs.cpSync(path.join(root, 'final_dev_nodes/18_custom_notification_sounds_final_26_06_1/entry/src/main'),
    path.join(work, 'entry/src/main'), { recursive: true });
  fs.cpSync(path.join(root, 'final_dev_nodes/18_custom_notification_sounds_final_26_06_1/AppScope'),
    path.join(work, 'AppScope'), { recursive: true });
  const bundleFile = path.join(testRoot, 'native-bundle.js');
  const suiteFile = path.join(testRoot, 'NativeBundle.test.ets');
  fs.writeFileSync(bundleFile, "import { createNativeContext } from './native-device-platform';\n" +
    'if (candidateUI) await bridge.ui.navigate(candidateUI.route);\ntry { await bridge.dispose(); } catch(error) {}\n');
  fs.writeFileSync(suiteFile, 'export default function nativeBundleTests(): void {}\n');
  return { work, testRoot, bundleFile, suiteFile };
}

test('installer touches generated evaluator files only and binds .ets from ArkTS entry', t => {
  const f = generatedProject(t);
  const original = fs.readFileSync(path.join(f.work, 'entry/src/main/ets/features/NotificationSoundFeature.ets'));
  const result = install(f.work);
  assert.equal(result.productionUnchanged, true);
  assert.ok(result.production.length > 0);
  assert.equal(result.fixtures.length, 5);
  assert.ok(result.fixtures.every(item => /^[a-f0-9]{64}$/.test(item.sha256)));
  assert.deepEqual(fs.readFileSync(path.join(f.work, result.presenterSource.path)), original);
  const bundle = fs.readFileSync(f.bundleFile, 'utf8'), suite = fs.readFileSync(f.suiteFile, 'utf8');
  assert.match(bundle, /attachTasks16To18UI\(bridge, taskId, caseSpec.key\)/);
  assert.match(bundle, /if \(!tasks16To18UI && candidateUI\)/);
  assert.match(bundle, /finally \{ if \(bridge.disposeTasks16To18UI\)/);
  assert.doesNotMatch(bundle, /from ['"].*(?:\.ets|TransitionsUI)/);
  assert.match(suite, /probeTasks16To18Transition/);
  assert.doesNotMatch(suite, /from ['"].*main\/ets\/features/);
  assert.doesNotMatch(suite, /Tasks16_18Presenter/);
  assert.equal(result.originalModule.moduleUrl, '@bundle:com.qingyu.elementx.notificationsounds.final/entry/ets/features/NotificationSoundFeature');
  assert.match(suite, /Tasks16_18Picker.AudioViewPicker/);
  assert.match(suite, /abilityDelegatorRegistry.getArguments\(\).bundleName/);
  assert.throws(() => install(f.work), /already installed/);
});

test('installer rejects changed lifecycle before writing fixtures', t => {
  const f = generatedProject(t);
  fs.writeFileSync(f.bundleFile, "import { createNativeContext } from './native-device-platform';\n");
  assert.throws(() => install(f.work), /lifecycle changed/);
  assert.equal(fs.existsSync(path.join(f.testRoot, 'Tasks16_18NativeUi.js')), false);
});

test('legacy candidate without sound presenter installs raw UI probe without inventing a class', t => {
  const f = generatedProject(t);
  fs.unlinkSync(path.join(f.work, 'entry/src/main/ets/features/NotificationSoundFeature.ets'));
  const result = install(f.work);
  assert.equal(result.presenterSource, null);
  assert.equal(result.originalModule.moduleUrl, null);
  assert.doesNotMatch(fs.readFileSync(f.suiteFile, 'utf8'), /from ['"].*main\/ets\/features/);
});

function observer() {
  const source = fs.readFileSync(path.join(__dirname, 'Tasks16_18NativeUi.js'), 'utf8');
  const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  const module = { exports: {} };
  new vm.Script(`(function(exports,module){${output}\n})`).runInNewContext()(module.exports, module);
  return module.exports;
}

function binding(bundleName = 'test') {
  return { bundleName, moduleName: 'entry', abilityName: 'EntryAbility', feature: 'NotificationSoundFeature',
    moduleUrl: `@bundle:${bundleName}/entry/ets/features/NotificationSoundFeature`, presenterExport: 'NotificationSettingsPresenter',
    importTiming: 'after-mounted-page-positive-controls-before-message-dialog' };
}

function readiness(bundleName = 'test') {
  return { focusedBundle: bundleName, completed: true, nodes: [
    { text: 'Notifications', bounds: { left: 0, top: 0, right: 100, bottom: 50 } },
    { id: 'message_sound_row', enabled: true, clickable: true, bounds: { left: 0, top: 60, right: 100, bottom: 110 } }
  ] };
}

async function bindPage(api, bridge, context, bundleName = 'test') {
  await bridge.runTasks16To18UI({ taskId: '18_custom_notification_sounds', key: 'message_picker_launch', caseId: 'test', bundleName });
  return api.bindTasks16To18OriginalPage(context, JSON.stringify(readiness(bundleName)));
}

test('observer preserves original calls, Promise identity and same-page store receiver', async () => {
  const api = observer(), completion = Promise.resolve('original');
  let created = 0, loadedStore;
  class Presenter {
    constructor() {
      created++;
      this.snapshot = { messageSound: 'original' };
      this.pendingMessageSoundPickerLaunch = 0;
      this.showMessageSoundDialog = true;
      this.store = { async load(context) { loadedStore = this; assert.equal(context.kind, 'real-context-test-double'); return { saved: 'unchanged' }; } };
    }
    load() { return completion; }
    launchSystemPicker(slot) { assert.equal(slot, 'message'); this.pendingMessageSoundPickerLaunch++; this.showMessageSoundDialog = false; return completion; }
    fail() { throw new Error('original throw'); }
  }
  const original = Presenter.prototype.launchSystemPicker;
  api.configureTasks16To18UI(async json => json, 'candidate.test', JSON.stringify(binding('candidate.test')),
    '{"sha256":"source-hash"}', undefined, async () => ({ NotificationSettingsPresenter: Presenter }));
  const bridge = {};
  assert.equal(api.attachTasks16To18UI(bridge, '18_custom_notification_sounds', 'message_picker_launch'), true);
  assert.equal(created, 0, 'observer must not create a substitute presenter');
  const context = { kind: 'real-context-test-double' };
  await bindPage(api, bridge, context, 'candidate.test');
  const pagePresenter = new Presenter();
  assert.equal(pagePresenter.load(), completion);
  const before = JSON.parse(await api.readTasks16To18Page(context));
  assert.equal(pagePresenter.launchSystemPicker('message'), completion);
  assert.throws(() => pagePresenter.fail(), /original throw/);
  const after = JSON.parse(await api.readTasks16To18Page(context));
  assert.equal(before.instanceId, after.instanceId);
  assert.equal(after.messagePickerToken, 1);
  assert.equal(after.messageDialog, false);
  assert.equal(loadedStore, pagePresenter.store);
  assert.deepEqual(before.persisted, after.persisted);
  new Presenter().load();
  assert.equal(JSON.parse(await api.readTasks16To18Page({})).available, false, 'multiple instances must not be merged');
  bridge.disposeTasks16To18UI();
  assert.equal(Presenter.prototype.launchSystemPicker, original);
});

test('non-UI canonical cases do not activate page instrumentation', () => {
  const api = observer(), bridge = {};
  assert.equal(api.attachTasks16To18UI(bridge, '18_custom_notification_sounds', 'message_custom_copy'), false);
  assert.equal(bridge.runTasks16To18UI, undefined);
});

test('native picker observer forwards original context/args/Promise and records pending/settled states', async () => {
  const api = observer(), context = {}, options = { maxSelectNumber: 1 };
  let resolve, receiver, argumentsSeen;
  const completion = new Promise(done => { resolve = done; });
  class Presenter { load() {} launchSystemPicker() {} }
  class AudioViewPicker {
    constructor(context) { this.context = context; }
    select(...args) { receiver = this; argumentsSeen = args; return completion; }
  }
  const original = AudioViewPicker.prototype.select;
  api.configureTasks16To18UI(async json => json, 'test', JSON.stringify(binding()), 'null', AudioViewPicker,
    async () => ({ NotificationSettingsPresenter: Presenter }));
  const bridge = {};
  api.attachTasks16To18UI(bridge, '18_custom_notification_sounds', 'message_picker_launch');
  await bindPage(api, bridge, context);
  const p = new Presenter(); p.load(context); p.launchSystemPicker('message');
  const picker = new AudioViewPicker(context);
  assert.equal(picker.select(options), completion);
  assert.equal(receiver, picker);
  assert.equal(argumentsSeen[0], options);
  const pending = JSON.parse(api.readTasks16To18Picker()).calls[0];
  assert.equal(pending.status, 'pending');
  assert.equal(pending.samePageContext, true);
  assert.equal(pending.precedingPresenterCall.slot, 'message');
  resolve(['file://actual-result']); await completion; await Promise.resolve();
  assert.equal(JSON.parse(api.readTasks16To18Picker()).calls[0].status, 'resolved');
  assert.equal(pending.status, 'pending', 'serialized checkpoint must not mutate later');
  bridge.disposeTasks16To18UI();
  assert.equal(AudioViewPicker.prototype.select, original);
});

test('picker errors and callback overloads are not disguised as pending successful launches', async () => {
  for (const mode of ['throw', 'reject', 'callback']) {
    const api = observer(), error = new Error('native error');
    let forwardedCallback;
    class Presenter { load() {} launchSystemPicker() {} }
    class AudioViewPicker {
      constructor(context) { this.context = context; }
      select(callback) {
        if (mode === 'throw') throw error;
        if (mode === 'reject') return Promise.reject(error);
        forwardedCallback = callback;
      }
    }
    api.configureTasks16To18UI(async json => json, 'test', JSON.stringify(binding()), 'null', AudioViewPicker,
      async () => ({ NotificationSettingsPresenter: Presenter }));
    const bridge = {}; api.attachTasks16To18UI(bridge, '18_custom_notification_sounds', 'message_picker_launch');
    await bindPage(api, bridge, {});
    const p = new Presenter(); p.load({}); p.launchSystemPicker('message');
    const picker = new AudioViewPicker({}), callback = () => {};
    if (mode === 'throw') assert.throws(() => picker.select(), actual => actual === error);
    else if (mode === 'reject') await assert.rejects(picker.select(), actual => actual === error);
    else { assert.equal(picker.select(callback), undefined); assert.equal(forwardedCallback, callback); }
    const call = JSON.parse(api.readTasks16To18Picker()).calls[0];
    assert.equal(call.status, { throw: 'threw', reject: 'rejected', callback: 'non_promise' }[mode]);
    assert.equal(call.samePageContext, false);
    bridge.disposeTasks16To18UI();
  }
});

test('in-flight progress is synchronously recoverable, identity checked, immutable and frozen on cancellation', async () => {
  const api = observer();
  let release;
  const completion = new Promise(resolve => { release = resolve; });
  api.configureTasks16To18UI(async () => completion, 'test', 'null', 'null');
  const bridge = {}; api.attachTasks16To18UI(bridge, '18_custom_notification_sounds', 'message_picker_launch');
  const request = { taskId: '18_custom_notification_sounds', caseId: 'case', key: 'message_picker_launch', bundleName: 'test' };
  const run = bridge.runTasks16To18UI(request);
  const result = { ...request, checkpoints: [{ label: 'after_event', completed: false,
    pageStateJson: '{"instanceCount":0,"available":false}' }], actions: [] };
  api.publishTasks16To18UI(JSON.stringify(result), 'page_read_end');
  assert.throws(() => api.publishTasks16To18UI(JSON.stringify({ ...result, caseId: 'other' }), 'wrong'), /does not belong/);
  const saved = bridge.getTasks16To18UIProgress();
  assert.equal(saved.stage, 'page_read_end');
  saved.result.checkpoints[0].completed = true;
  assert.equal(bridge.getTasks16To18UIProgress().result.checkpoints[0].completed, false);
  bridge.cancelTasks16To18UI();
  assert.equal(api.tasks16To18UICancelled(), true);
  api.publishTasks16To18UI(JSON.stringify({ ...result, checkpoints: [] }), 'late');
  assert.equal(bridge.getTasks16To18UIProgress().stage, 'page_read_end');
  release(JSON.stringify(result)); await run;
  bridge.disposeTasks16To18UI();
  assert.equal(api.tasks16To18UICancelled(), true, 'late probes must stop even after bridge disposal');
});

test('post-load import waits for positive controls, captures pre-existing page only on its real event, and never invents load', async () => {
  const api = observer(), context = { kind: 'actual monitored object' };
  let imports = 0, instances = 0, loads = 0;
  class Presenter {
    constructor() { instances++; this.snapshot = {}; this.store = { async load(actual) { assert.equal(actual, context); return { unchanged: true }; } }; }
    load() { loads++; }
    showDialog() { this.showMessageSoundDialog = true; }
    dismissDialog() { this.showMessageSoundDialog = false; }
    launchSystemPicker(slot) { this.dismissDialog(slot); this.pendingMessageSoundPickerLaunch = 1; }
  }
  const original = Presenter.prototype.showDialog;
  const mounted = new Presenter(); mounted.load();
  class Picker { constructor(context) { this.context = context; } select() { return new Promise(() => {}); } }
  api.configureTasks16To18UI(async json => json, 'test', JSON.stringify(binding()), 'null', Picker, async url => {
    imports++; assert.equal(url, binding().moduleUrl); return { NotificationSettingsPresenter: Presenter };
  });
  const bridge = {}; api.attachTasks16To18UI(bridge, '18_custom_notification_sounds', 'message_picker_launch');
  assert.equal(imports, 0); assert.equal(Presenter.prototype.showDialog, original);
  await bridge.runTasks16To18UI({ taskId: '18_custom_notification_sounds', key: 'message_picker_launch', caseId: 'test', bundleName: 'test' });
  await assert.rejects(api.bindTasks16To18OriginalPage(context, JSON.stringify({ ...readiness(), nodes: [] })), /positive controls/);
  assert.equal(imports, 0, 'unsafe pre-ready import must never execute');
  const info = JSON.parse(await api.bindTasks16To18OriginalPage(context, JSON.stringify(readiness())));
  assert.equal(imports, 1); assert.equal(info.importCompleted, true); assert.equal(info.receiverObserved, false);
  assert.equal(JSON.parse(await api.readTasks16To18Page(context)).instanceCount, 0);
  mounted.showDialog('message'); mounted.launchSystemPicker('message');
  new Picker(context).select();
  const observed = JSON.parse(await api.readTasks16To18Page(context));
  assert.equal(observed.instanceCount, 1); assert.equal(observed.available, true);
  assert.equal(observed.originalModuleBinding.receiverObserved, true);
  assert.equal(observed.calls.some(call => call.method === 'load'), false);
  const call = JSON.parse(api.readTasks16To18Picker()).calls[0];
  assert.equal(call.samePageContext, true); assert.equal(call.contextEvidence.observedLoadCall, false);
  assert.equal(call.precedingPresenterCall.method, 'dismissDialog', 'Do not rewrite the real immediately preceding nested call');
  assert.deepEqual(call.presenterCallsBeforeSelect.map(item => item.method), ['showDialog', 'launchSystemPicker', 'dismissDialog']);
  assert.deepEqual(call.presenterCallsBeforeSelect.map(item => item.sequence), [1, 2, 3]);
  assert.ok(call.presenterCallsBeforeSelect.every(item => item.outcome === 'returned' && item.returnedAtMs <= call.startedAtMs));
  assert.equal(instances, 1); assert.equal(loads, 1, 'binding cannot replay original load');
  assert.equal(JSON.parse(await api.readTasks16To18Page({ ...context })).available, false);
  bridge.disposeTasks16To18UI();
  assert.equal(Presenter.prototype.showDialog, original);
});

for (const variant of ['same_scope', 'other_preferences', 'missing_ability']) {
  test('picker context evidence uses actual monitored scope without a load call: ' + variant, async () => {
    const api = observer();
    const context = { abilityInfo: { bundleName: 'test', name: 'EntryAbility', moduleName: 'entry' },
      filesDir: '/app/entry/files', preferencesDir: '/app/entry/preferences', cacheDir: '/app/entry/cache' };
    const pickerContext = JSON.parse(JSON.stringify(context));
    if (variant === 'other_preferences') pickerContext.preferencesDir = '/app/preferences';
    if (variant === 'missing_ability') delete pickerContext.abilityInfo;
    class Presenter { launchSystemPicker() {} }
    class Picker { constructor(context) { this.context = context; } select() { return new Promise(() => {}); } }
    api.configureTasks16To18UI(async json => json, 'test', JSON.stringify(binding()), 'null', Picker,
      async () => ({ NotificationSettingsPresenter: Presenter }));
    const bridge = {}; api.attachTasks16To18UI(bridge, '18_custom_notification_sounds', 'message_picker_launch');
    await bindPage(api, bridge, context);
    new Presenter().launchSystemPicker('message'); new Picker(pickerContext).select();
    const call = JSON.parse(api.readTasks16To18Picker()).calls[0];
    assert.equal(call.samePageContext, variant === 'same_scope');
    assert.equal(call.contextEvidence.exactMonitoredContext, false);
    assert.equal(call.contextEvidence.observedLoadCall, false);
    bridge.disposeTasks16To18UI();
  });
}

test('test-module OHM URLs are rejected rather than used as an original-page fallback', () => {
  const api = observer();
  assert.throws(() => api.configureTasks16To18UI(async json => json, 'test', JSON.stringify({ ...binding(),
    moduleUrl: '@bundle:test/entry_test@entry/ets/features/NotificationSoundFeature' }), 'null'), /candidate manifest/);
});

test('original module import failure has no copied-class fallback', async () => {
  const api = observer(); let imports = 0;
  api.configureTasks16To18UI(async json => json, 'test', JSON.stringify(binding()), 'null', undefined,
    async () => { imports++; throw new Error('native import failed'); });
  const bridge = {}; api.attachTasks16To18UI(bridge, '18_custom_notification_sounds', 'message_picker_launch');
  await assert.rejects(bindPage(api, bridge, {}), /native import failed/);
  const observed = JSON.parse(await api.readTasks16To18Page({}));
  assert.equal(observed.available, false); assert.equal(observed.instanceCount, 0);
  assert.equal(imports, 1); assert.equal(observed.originalModuleBinding.importCompleted, false);
  bridge.disposeTasks16To18UI();
});
