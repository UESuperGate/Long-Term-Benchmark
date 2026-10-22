'use strict';

// Adapter regression only. SDK services and UI records below are synthetic
// external boundaries, never native-runtime benchmark evidence.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require(process.env.LTB_TYPESCRIPT ||
  '/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const { runCase } = require('../tasks16_18.cjs');
const root = path.resolve(__dirname, '../../../..');
const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const providerModule = { exports: {} };
const providerSource = ts.transpileModule(fs.readFileSync(path.join(__dirname, 'Tasks16_18ProviderEvidence.js'), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
new vm.Script(`(function(exports,module){${providerSource}\n})`).runInNewContext()(providerModule.exports, providerModule);

function addProviderEvidence(record, variant) {
  const before = record.checkpoints[0], after = record.checkpoints[1];
  record.deviceUserId = '100'; record.deviceUserParameter = '100';
  record.deviceUserSource = 'AbilityDelegatorRegistry.getArguments().parameters["-s ltbDeviceUser"]';
  const host = { bundleName: record.bundleName, moduleName: 'entry', abilityName: 'EntryAbility' };
  const state = JSON.parse(before.pageStateJson);
  state.contextBinding = { scope: host };
  before.pageStateJson = JSON.stringify(state);
  record.originalModuleBindingJson = JSON.stringify({ monitoredContext: { scope: host } });
  Object.assign(after, { startedAtMs: 11, finishedAtMs: 30, completed: true });
  const providerBundle = 'com.vendor.audio';
  let raw = '  ExtensionRecords:\n    uri [/com.vendor.audio/audio/AudioExtension]\n' +
    '      AbilityRecord ID #42   state #FOREGROUND   start time [1234]\n' +
    '      main name [AudioExtension]\n      bundle name [com.vendor.audio]\n      ability type [UIEXTENSION]\n' +
    '      root host bundle name [' + record.bundleName + ']\n      root host module name [entry]\n' +
    '      root host ability name [EntryAbility]\n      pid: 313\n';
  if (variant === 'provider_wrong_host') raw = raw.replace('[EntryAbility]', '[Wrong]');
  const metadata = { name: providerBundle, applicationInfo: { bundleName: providerBundle, name: providerBundle, isSystemApp: true },
    hapModuleInfos: [{ extensionInfos: [{ name: 'AudioExtension', moduleName: 'audio', bundleName: providerBundle,
      enabled: true, visible: true, extensionTypeName: 'sysPicker/audioPicker' }] }] };
  if (variant === 'provider_different') metadata.name = 'com.other.app';
  if (variant === 'provider_type') metadata.hapModuleInfos[0].extensionInfos[0].extensionTypeName = 'sysPicker/photoPicker';
  if (variant === 'provider_nonsystem') metadata.applicationInfo.isSystemApp = false;
  record.providerCommands = [
    { phase: 'before_picker', command: 'aa dump -e', completed: true, exitCode: 0, startedAtMs: 1, finishedAtMs: 3,
      stdResult: variant === 'provider_old' ? raw : '  ExtensionRecords:\n', pickerStateBeforeJson: before.pickerStateJson,
      pickerStateAfterJson: before.pickerStateJson },
    { phase: 'pending_after', command: 'aa dump -e', completed: true, exitCode: 0, startedAtMs: 20, finishedAtMs: 22,
      stdResult: raw, pickerStateBeforeJson: after.pickerStateBeforeJson, pickerStateAfterJson: after.pickerStateJson },
    { phase: 'pending_metadata', command: 'bm dump -n ' + providerBundle + ' -u 100', completed: true, exitCode: 0, startedAtMs: 31, finishedAtMs: 33,
      stdResult: JSON.stringify(metadata), pickerStateBeforeJson: after.pickerStateBeforeJson, pickerStateAfterJson: after.pickerStateJson }
  ];
  if (variant === 'provider_missing_dump') record.providerCommands.splice(1, 1);
  if (variant === 'provider_missing_metadata') record.providerCommands.pop();
  if (variant === 'provider_resolved') record.providerCommands[2].pickerStateAfterJson =
    record.providerCommands[2].pickerStateAfterJson.replace('pending', 'resolved');
  record.providerEvidenceJson = providerModule.exports.summarizeTasks16To18ProviderEvidence(JSON.stringify(record));
  if (variant === 'provider_wrong_proof_call') {
    const proof = JSON.parse(record.providerEvidenceJson); proof.sdkCallId = 99;
    record.providerEvidenceJson = JSON.stringify(proof);
  }
}

function runtime(taskId, projectName, key, options = {}) {
  const project = path.join(root, 'final_dev_nodes', projectName);
  // Withdrawal regressions execute the immutable, actually audited old gateway,
  // not a synthetic replacement or the newly repaired bootstrap under old givens.
  const auditedSource = path.join(root, 'experiment_results/runtime_transition_20261019/migration_audit/task18_channel_effect_review/sources/arkts');
  const caseSpec = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks', taskId, 'transitions.json'))).cases.find(c => c.key === key);
  const stores = new Map(), calls = [], modules = new Map(), checkpoints = [], preferenceContexts = [], writes = [];
  const preferences = {
    async getPreferences(context, name) {
      preferenceContexts.push(context);
      name = context.preferencesDir ? context.preferencesDir + '/' + name : name;
      if (!stores.has(name)) stores.set(name, new Map());
      const values = stores.get(name);
      return { async get(key, fallback) { return values.has(key) ? values.get(key) : fallback; },
        async put(key, value) { writes.push({ context, key, value }); if (!options.ignoreWrites) values.set(key, value); },
        async flush() { if (options.flush) await options.flush(); } };
    },
    async removePreferencesFromCache() {}
  };
  const sourceBytes = [1, 2, 3, 4];
  const copySources = [];
  const fileApi = { OpenMode: { READ_ONLY: 0 },
    async open() { return { fd: 1 }; }, async close() {}, async stat() { return { size: sourceBytes.length }; },
    async read(_fd, buffer) { new Uint8Array(buffer).set(sourceBytes); return sourceBytes.length; },
    async copyFile(source) { copySources.push(source); throw new Error('No such file or directory'); } };
  const media = { async createAVMetadataExtractor() {
    return { fdSrc: undefined, async fetchMetadata() { return { title: options.title || 'Message Tone' }; }, async release() {} };
  } };
  const sdk = { '@ohos.data.preferences': preferences, '@ohos.file.fs': options.fileApi || fileApi, '@ohos.multimedia.media': media };
  function load(name) {
    if (sdk[name]) return { default: sdk[name] };
    if (modules.has(name)) return modules.get(name);
    const source = fs.readFileSync(path.join(options.auditedLedger ? auditedSource : project, name), 'utf8');
    const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } });
    const module = { exports: {} };
    new vm.Script(`(function(exports,require,module){${compiled.outputText}\n})`).runInNewContext()(module.exports, load, module);
    for (const [className, value] of Object.entries(module.exports)) {
      if (typeof value !== 'function') continue;
      for (const method of Object.getOwnPropertyNames(value.prototype)) {
        if (method === 'constructor' || typeof value.prototype[method] !== 'function') continue;
        const original = value.prototype[method];
        value.prototype[method] = function(...args) {
          calls.push({ class: className, method, args: clone(args) });
          return original.apply(this, args);
        };
      }
    }
    modules.set(name, module.exports);
    return module.exports;
  }
  const native = { context: { filesDir: '/native/files' }, productionCalls: calls, bundleName: 'test.candidate' };
  const abilityContext = { preferencesDir: '/native/base/haps/entry/preferences', area: 1,
    abilityInfo: { bundleName: native.bundleName, moduleName: 'entry' } };
  return { caseSpec, native, stores, copySources, checkpoints, preferenceContexts, writes, abilityContext,
    pinnedStore: () => stores.get(abilityContext.preferencesDir + '/element_x_pinned_messages'),
    runHost: () => runCase({ taskId, caseSpec, project, load,
      trace: (label, data) => checkpoints.push({ label, data }) }),
    run: () => runCase({ taskId, caseSpec, project, load, native,
      trace: (label, data) => checkpoints.push({ label, data }) }) };
}

function uiRecord(request) {
  const node = (id, text = '') => ({ id, text, enabled: true, clickable: true,
    bounds: { left: 0, top: 0, right: 100, bottom: 50 } });
  return { ...request, schemaVersion: 1, observationLevel: 'native_candidate_ui', unsupported: '',
    actions: [{ kind: 'id', value: 'view_in_timeline_$a', before: 'click_before', after: 'after_event' }],
    checkpoints: [
      { label: 'click_before', focusedBundle: request.bundleName,
        nodes: [node('pinned_messages_filled'), node('view_in_timeline_$a')] },
      { label: 'after_event', focusedBundle: request.bundleName,
        nodes: [node('', 'Design team'), node('focused_event_label', 'Focused $a')] }
    ] };
}

for (const variant of ['matching', 'wrong_case', 'unfocused', 'no_before_control', 'wrong_focus', 'storage_mutated',
  'storage_deleted', 'storage_corrupt', 'seed_not_saved', 'no_prepare', 'no_after', 'wrong_context', 'wrong_bundle', 'no_module']) {
  test('real-page record binding: ' + variant, async () => {
    const f = runtime('17_pinned_messages', '17_pinned_messages_final_0_5_3', 'view_in_timeline', { ignoreWrites: variant === 'seed_not_saved' });
    f.native.runTasks16To18UI = async (request, callbacks) => {
      const record = uiRecord(request);
      if (variant === 'no_prepare') return record;
      if (variant === 'wrong_bundle') f.abilityContext.abilityInfo.bundleName = 'other.app';
      if (variant === 'no_module') delete f.abilityContext.abilityInfo.moduleName;
      await callbacks.prepare(f.abilityContext);
      if (variant === 'wrong_case') record.caseId = 'another_case';
      if (variant === 'unfocused') record.checkpoints[1].focusedBundle = 'other.app';
      if (variant === 'no_before_control') record.checkpoints[0].nodes = [];
      if (variant === 'wrong_focus') record.checkpoints[1].nodes[1].text = 'Focused $wrong';
      if (variant === 'storage_mutated') f.pinnedStore().set('room_design_pinned_events', '[]');
      if (variant === 'storage_deleted') f.pinnedStore().delete('room_design_pinned_events');
      if (variant === 'storage_corrupt') f.pinnedStore().set('room_design_pinned_events', '{invalid');
      if (variant !== 'no_after') await callbacks.afterEvent(variant === 'wrong_context' ? { ...f.abilityContext } : f.abilityContext);
      return record;
    };
    const result = await f.run();
    if (['wrong_case', 'unfocused', 'no_before_control', 'seed_not_saved', 'no_prepare', 'no_after',
      'wrong_context', 'wrong_bundle', 'no_module'].includes(variant)) {
      assert.ok(result.unsupported);
    } else {
      assert.equal(result.unsupported, undefined);
      assert.equal(result.observed.focusedEventId, variant === 'wrong_focus' ? '$wrong' : '$a');
      assert.equal(result.invariantChecks[0].passed, !['storage_mutated', 'storage_deleted', 'storage_corrupt'].includes(variant));
      assert.deepEqual(result.observed.effects, variant === 'wrong_focus' ? [] : ['navigate_to_event']);
    }
    assert.ok(f.preferenceContexts.every(context => context === f.abilityContext), 'SDK calls must keep actual context identity');
    assert.ok(f.writes.length <= 1, 'Readback must not create or restore any default rows');
    assert.ok(!f.native.productionCalls.some(call => call.method === 'openPinnedTimeline'), 'Readback must be non-initializing');
    if (variant === 'storage_deleted') assert.equal(f.pinnedStore().has('room_design_pinned_events'), false);
  });
}

test('task17 does not seed ApplicationContext and awaits original flush before UI can open', async () => {
  let release, flushStarted;
  const started = new Promise(resolve => { flushStarted = resolve; });
  const gate = new Promise(resolve => { release = resolve; });
  const f = runtime('17_pinned_messages', '17_pinned_messages_final_0_5_3', 'view_in_timeline', {
    async flush() { flushStarted(); await gate; }
  });
  let opened = false;
  f.native.runTasks16To18UI = async (request, callbacks) => {
    assert.equal(f.preferenceContexts.length, 0, 'No prelaunch ApplicationContext write');
    await callbacks.prepare(f.abilityContext);
    opened = true;
    await callbacks.afterEvent(f.abilityContext);
    return uiRecord(request);
  };
  const running = f.run();
  await started;
  assert.equal(opened, false);
  release();
  const result = await running;
  assert.equal(result.unsupported, undefined);
  assert.equal(opened, true);
  const seed = f.checkpoints.find(item => item.label === 'native_page_storage_seeded').data;
  const after = f.checkpoints.find(item => item.label === 'native_page_storage_after_event').data;
  assert.equal(seed.context.preferencesDir, f.abilityContext.preferencesDir);
  assert.equal(seed.context.moduleName, 'entry');
  assert.equal(after.sameContext, true);
  assert.deepEqual(after.rows, seed.rows);
});

function soundFileBoundary() {
  const files = new Map(), descriptors = new Map();
  let next = 0;
  const bytes = value => {
    const name = typeof value === 'number' ? descriptors.get(value) : value;
    if (!files.has(name)) throw new Error('No such file or directory');
    return files.get(name);
  };
  return { files, api: { OpenMode: { READ_ONLY: 0 },
    async open(name) { bytes(name); const fd = ++next; descriptors.set(fd, name); return { fd }; },
    async close(file) { descriptors.delete(typeof file === 'number' ? file : file.fd); },
    async stat(file) { return { size: bytes(file).length }; },
    async read(fd, buffer) { const data = bytes(fd); new Uint8Array(buffer).set(data); return data.length; },
    async copyFile(source, target) { files.set(target, Uint8Array.from(bytes(source))); },
    unlinkSync(name) { files.delete(name); }
  } };
}

for (const key of ['message_preset', 'message_custom_copy', 'call_preset', 'call_custom_copy', 'latest_pick_wins']) {
  test('audited historical ledger-only native success cannot become an OS channel PASS: ' + key, async () => {
    const io = soundFileBoundary();
    const f = runtime('18_custom_notification_sounds', '18_custom_notification_sounds_final_26_06_1', key,
      { auditedLedger: true, fileApi: io.api, title: key === 'call_custom_copy' ? 'Call Tone' : 'Message Tone' });
    const uris = f.caseSpec.event.values || (f.caseSpec.given.pickedUri ? [f.caseSpec.given.pickedUri] : []);
    f.native.audioSources = {};
    uris.forEach((canonical, index) => {
      const uri = 'file:///unit/source_' + index;
      io.files.set(uri, new Uint8Array([1, 2, 3, index + 4]));
      f.native.audioSources[canonical] = { uri, displayName: f.caseSpec.given.displayName || 'Message Tone' };
    });
    // Untrusted tags and plausible-looking receipts must not create a binding.
    f.native.osChannelReceipt = { verified: true, api: '@ohos.notificationManager.addSlot',
      completed: true, readback: { sound: 'selected' }, consumerVerified: true };
    f.native.observationLevel = 'native_os_channel_verified';
    const result = await f.run();
    assert.match(result.unsupported, /OS channel effect unsupported/);
    assert.ok(result.invariantChecks.every(check => check.passed), 'Domain/copy/ledger checks still run and succeed');
    assert.ok(f.writes.length > 0);
    assert.ok(f.native.productionCalls.some(call => call.class === 'NotificationChannelGateway' && call.method === 'recreateChannel'));
    assert.equal(result.observed.recreateOrder, undefined);
    assert.ok(!result.observed.effects?.some(effect => effect.startsWith('recreate_')));
    if (key.includes('custom_copy') || key === 'latest_pick_wins') assert.ok(result.invariantChecks.some(check =>
      check.description === 'Production copy produces a distinct app-owned file with the selected source bytes' && check.passed));
    if (key === 'latest_pick_wins') {
      assert.deepEqual(result.observed.copyOrder, f.caseSpec.event.values);
      assert.ok(f.checkpoints.some(item => item.label === 'gateway_request_order_diagnostic'));
    }
  });
}

for (const key of ['message_preset', 'call_preset']) {
  test('host args-only gateway success cannot become an OS channel PASS: ' + key, async () => {
    const f = runtime('18_custom_notification_sounds', '18_custom_notification_sounds_final_26_06_1', key, { auditedLedger: true });
    const result = await f.runHost();
    assert.match(result.unsupported, /OS channel effect unsupported/);
    assert.ok(result.invariantChecks.every(check => check.passed));
    assert.ok(!result.observed.effects.some(effect => effect.startsWith('recreate_')));
    assert.ok(f.checkpoints.some(item => item.label === 'after_event' && item.data.calls.some(call => call.name === 'recreate_channel')));
  });
}

for (const key of ['restore_independent_slots', 'message_copy_failure', 'call_copy_failure', 'legacy_migration_guard']) {
  test('non-positive-channel native case keeps its original assertions: ' + key, async () => {
    const io = soundFileBoundary();
    const f = runtime('18_custom_notification_sounds', '18_custom_notification_sounds_final_26_06_1', key, { auditedLedger: true, fileApi: io.api });
    if (f.caseSpec.given.pickedUri) f.native.audioSources = {
      [f.caseSpec.given.pickedUri]: { uri: 'file:///unit/missing-source' }
    };
    const result = await f.run();
    assert.equal(result.unsupported, undefined);
    assert.ok(result.invariantChecks.every(check => check.passed));
    if (key.endsWith('_copy_failure')) {
      assert.equal(result.observed.channelRecreated, false);
      assert.ok(result.invariantChecks.some(check => check.description === 'Native copy rejection makes no preference or channel writes' && check.passed));
      assert.ok(result.evidence.some(item => item.channelAbsenceScope?.includes('not an independently initialized OS channel readback')));
    }
  });
}

test('native copy rejection preserves raw production error and never retries a raw path', async () => {
  const f = runtime('18_custom_notification_sounds', '18_custom_notification_sounds_final_26_06_1', 'message_custom_copy', { auditedLedger: true });
  const uri = 'file://test.candidate/native/cache/42';
  f.native.audioSources = { 'content://media/message/42': { uri, sourcePath: '/native/cache/42', displayName: 'Message Tone' } };
  const result = await f.run();
  assert.match(result.unsupported, /OS channel effect unsupported/);
  assert.equal(result.observed.messageSound, 'system_default');
  assert.equal(result.observed.messageCopyErrorMessage, 'Error: No such file or directory');
  assert.deepEqual(f.copySources, [1], 'The real copier passes the opened descriptor; the adapter must not retry a raw path');
  assert.equal(result.invariantChecks.find(check => check.description === f.caseSpec.invariants[0]).passed, true,
    'A rejected copy preserving the default has not persisted the provider URI');
  assert.equal(result.invariantChecks.find(check => check.description ===
    'Production copy produces a distinct app-owned file with the selected source bytes').passed, false,
  'Copy success and byte equality remain independently required');
  assert.equal(result.invariantChecks.find(check => check.description ===
    'Real persistence and gateway payload/local projection preserve the selected value and untouched other slot').passed, false,
  'A rejected copy does not satisfy successful persistence and channel effects');
  assert.ok(f.checkpoints.some(item => item.label === 'native_sound_event_diagnostics' &&
    item.data.ui.messageCopyErrorMessage === 'Error: No such file or directory'));
});

test('current bootstrap rejects the old SystemDefault/v0 event fixture as NS', async () => {
  const f = runtime('18_custom_notification_sounds', '18_custom_notification_sounds_final_26_06_1', 'message_preset');
  const result = await f.run();
  assert.match(result.unsupported, /GIVEN state/);
  assert.match(result.unsupported, /OS channel effect unsupported/);
  assert.ok(f.checkpoints.some(item => item.label === 'native_sound_setup_failed'));
  assert.ok(!f.native.productionCalls.some(call => call.method === 'selectPreset'));
});

for (const variant of ['same_page', 'storage_mutated', 'different_store', 'multiple_presenters']) {
  test('picker page readback remains NS without a native launch effect: ' + variant, async () => {
    const f = runtime('18_custom_notification_sounds', '18_custom_notification_sounds_final_26_06_1', 'message_picker_launch');
    f.native.runTasks16To18UI = async request => {
      const before = { available: true, instanceCount: 1, instanceId: 1, storeId: 1, calls: [], source: { sha256: 'source-hash' },
        messagePickerToken: 0, messageDialog: true, persisted: { message: 'system_default', call: 'silent' } };
      const after = { ...before, messagePickerToken: 1, messageDialog: false };
      if (variant === 'storage_mutated') after.persisted = { message: 'silent', call: 'silent' };
      if (variant === 'different_store') after.storeId = 2;
      if (variant === 'multiple_presenters') after.instanceCount = 2;
      const pickerBefore = JSON.stringify({ observer: { available: true }, calls: [] });
      const pickerAfter = JSON.stringify({ observer: { available: true }, calls: [pickerCall()] });
      return { ...request, schemaVersion: 1, observationLevel: 'native_candidate_ui', actions: [],
        checkpoints: [{ label: 'launch_audio_picker_before', pageStateJson: JSON.stringify(before), pickerStateJson: pickerBefore },
          { label: 'after_event', pageStateJson: JSON.stringify(after), pickerStateBeforeJson: pickerAfter,
            pickerStateJson: pickerAfter }], unsupported: 'Native picker window not observed' };
    };
    const result = await f.run();
    assert.ok(result.unsupported);
    assert.equal(result.observed.effects, undefined);
    if (['same_page', 'storage_mutated'].includes(variant)) {
      assert.equal(result.observed.messagePickerToken, 1);
      assert.equal(result.observed.messageDialog, 'closed');
      assert.equal(result.invariantChecks[0].passed, variant === 'same_page');
    } else {
      assert.equal(result.observed.messagePickerToken, undefined);
      assert.equal(result.invariantChecks.length, 0);
    }
  });
}

function pickerCall() {
  return { id: 1, api: '@ohos.file.picker.AudioViewPicker.select', status: 'pending', instanceCount: 1,
    startedAtMs: 10, presenterCallsBeforeSelect: [
      { sequence: 1, instanceId: 1, method: 'launchSystemPicker', slot: 'message', enteredAtMs: 8, returnedAtMs: 9, outcome: 'returned' }],
    samePageContext: true, precedingPresenterCall: { method: 'launchSystemPicker', slot: 'message', instanceId: 1 } };
}

for (const variant of ['complete', 'storage_mutated', 'wrong_token', 'unknown_window', 'empty_tree', 'missing_call',
  'resolved', 'resolved_during_read', 'wrong_context', 'wrong_slot', 'no_visible_dialog', 'no_action', 'no_given', 'query_error',
  'embedded', 'embedded_unbound', 'embedded_preexisting', 'nested_dismiss', 'stale_launch', 'launch_after_select',
  'launch_threw', 'wrong_receiver', 'duplicate_launch', 'no_launch_sequence',
  'provider_complete', 'provider_different', 'provider_wrong_host', 'provider_type', 'provider_nonsystem',
  'provider_old', 'provider_missing_dump', 'provider_missing_metadata', 'provider_resolved', 'provider_wrong_proof_call',
  'provider_unbound_anchors', 'provider_preexisting_anchors', 'provider_storage_mutated', 'provider_wrong_token',
  'missing_source_path', 'invalid_source_hash', 'missing_binding', 'duplicate_module_url', 'premounted_binding',
  'unobserved_receiver', 'missing_after_calls']) {
  test('picker effect requires SDK call, original page GIVEN, and system window: ' + variant, async () => {
    const f = runtime('18_custom_notification_sounds', '18_custom_notification_sounds_final_26_06_1', 'message_picker_launch');
    f.native.runTasks16To18UI = async request => {
      const node = id => ({ id, enabled: true, clickable: true, bounds: { left: 0, top: 0, right: 100, bottom: 50 } });
      const before = { available: true, instanceCount: 1, instanceId: 1, storeId: 1, calls: [],
        source: { path: 'entry/src/main/ets/features/NotificationSoundFeature.ets', sha256: 'a'.repeat(64) },
        contextBinding: { scope: { moduleName: 'entry' } },
        originalModuleBinding: { importCompleted: true, receiverObserved: true,
          presenterExport: 'NotificationSettingsPresenter', timing: 'after-mounted-page-positive-controls-before-message-dialog',
          requestedModuleUrl: `@bundle:${request.bundleName}/entry/ets/features/NotificationSoundFeature`,
          readiness: { completed: true, focusedBundle: request.bundleName },
          wrappedNames: ['launchSystemPicker', 'dismissDialog'] },
        messagePickerToken: 0, messageDialog: true, persisted: { message: 'system_default' } };
      if (variant === 'missing_source_path') delete before.source.path;
      if (variant === 'invalid_source_hash') before.source.sha256 = 'invalid';
      if (variant === 'missing_binding') delete before.originalModuleBinding;
      if (variant === 'duplicate_module_url') before.originalModuleBinding.requestedModuleUrl =
        `@bundle:${request.bundleName}/entry_test@entry/ets/features/NotificationSoundFeature`;
      if (variant === 'premounted_binding') before.originalModuleBinding.timing = 'before-startup';
      if (variant === 'unobserved_receiver') before.originalModuleBinding.receiverObserved = false;
      const after = { ...before, messagePickerToken: 1, messageDialog: false };
      const call = pickerCall();
      if (variant === 'wrong_context') call.samePageContext = false;
      if (variant === 'wrong_slot') call.presenterCallsBeforeSelect[0].slot = 'call';
      if (variant === 'nested_dismiss') {
        const dismiss = { sequence: 2, instanceId: 1, method: 'dismissDialog', slot: 'message', enteredAtMs: 8, returnedAtMs: 8, outcome: 'returned' };
        call.presenterCallsBeforeSelect.push(dismiss);
        call.precedingPresenterCall = dismiss;
      }
      if (variant === 'stale_launch') before.calls = clone(call.presenterCallsBeforeSelect);
      if (variant === 'launch_after_select') call.presenterCallsBeforeSelect[0].returnedAtMs = 11;
      if (variant === 'launch_threw') call.presenterCallsBeforeSelect[0].outcome = 'threw';
      if (variant === 'wrong_receiver') call.presenterCallsBeforeSelect[0].instanceId = 2;
      if (variant === 'duplicate_launch') call.presenterCallsBeforeSelect.push({ ...call.presenterCallsBeforeSelect[0], sequence: 2 });
      if (variant === 'no_launch_sequence') delete call.presenterCallsBeforeSelect;
      after.calls = variant === 'missing_after_calls' ? [] : clone(call.presenterCallsBeforeSelect);
      if (variant === 'resolved') call.status = 'resolved';
      if (['storage_mutated', 'provider_storage_mutated'].includes(variant)) after.persisted = { message: 'silent' };
      if (['wrong_token', 'provider_wrong_token'].includes(variant)) after.messagePickerToken = 2;
      if (variant === 'no_given') before.messagePickerToken = 5;
      const pending = { observer: { available: true }, calls: variant === 'missing_call' ? [] : [call] };
      const end = clone(pending);
      if (variant === 'resolved_during_read') end.calls[0].status = 'resolved';
      const beforeFrame = { label: 'launch_audio_picker_before', focusedBundle: request.bundleName,
        nodes: [node('message_sound_picker'), ...(variant === 'no_visible_dialog' ? [] : [node('message_sound_dialog')])],
        pageStateJson: JSON.stringify(before), pickerStateJson: JSON.stringify({ observer: { available: true }, calls: [] }) };
      const afterFrame = { label: 'after_event', focusedBundle: variant === 'unknown_window' ? 'unrelated.app' : 'com.ohos.filepicker',
        nodes: [], focusedNodes: variant === 'empty_tree' ? [] : [node('system_audio')], pageStateJson: JSON.stringify(after),
        pickerStateBeforeJson: JSON.stringify(pending), pickerStateJson: JSON.stringify(end) };
      if (variant.startsWith('embedded') || variant.startsWith('provider')) {
        afterFrame.focusedBundle = request.bundleName;
        beforeFrame.queryResults = ['audiopicker_selected', 'audiopicker_button'].map(id =>
          `audio-extension:${id}:matches=${['embedded_preexisting', 'provider_preexisting_anchors'].includes(variant) ? 1 : 0}`);
        afterFrame.focusedNodes = ['audiopicker_selected', 'audiopicker_button'].map(id =>
          ({ ...node(id), selectorScope: `${['embedded_unbound', 'provider_unbound_anchors'].includes(variant) ? 'audio-unbound' : 'audio-extension'}:${id}` }));
      }
      if (variant === 'query_error') afterFrame.error = 'query failed';
      const record = { ...request, schemaVersion: 1, observationLevel: 'native_candidate_ui', unsupported: '',
        actions: variant === 'no_action' ? [] : [{ kind: 'id', value: 'message_sound_picker', before: beforeFrame.label, after: 'after_event' }],
        checkpoints: [beforeFrame, afterFrame] };
      if (variant.startsWith('provider')) addProviderEvidence(record, variant);
      return record;
    };
    const result = await f.run();
    if (['complete', 'storage_mutated', 'wrong_token', 'nested_dismiss', 'provider_complete',
      'provider_storage_mutated', 'provider_wrong_token'].includes(variant)) {
      assert.equal(result.unsupported, undefined);
      assert.deepEqual(result.observed.effects, ['open_audio_picker']);
      assert.equal(result.invariantChecks[0].passed, !['storage_mutated', 'provider_storage_mutated'].includes(variant));
      assert.equal(result.observed.messagePickerToken, ['wrong_token', 'provider_wrong_token'].includes(variant) ? 2 : 1,
        'Wrong native values must remain failures');
    } else {
      assert.ok(result.unsupported);
      assert.equal(result.observed.effects, undefined);
      if (variant === 'embedded') {
        assert.ok(result.evidence.some(item => item.embeddedPickerAnchors === 'after_event' &&
          item.providerHostIdentityVerified === false), 'Native ancestry is retained without claiming remote provider identity');
        assert.match(result.unsupported, /embeddedProviderIdentity/);
        assert.equal(result.observed.messagePickerToken, 1, 'Real same-page observations remain available');
        assert.equal(result.invariantChecks[0].passed, true, 'Pending same-store readback remains independently observed');
      }
      if (['resolved', 'resolved_during_read', 'missing_call', 'wrong_context', 'wrong_slot'].includes(variant)) {
        assert.equal(result.invariantChecks.length, 0, 'Do not assert pre-return invariant without pending evidence');
      }
    }
  });
}

test('watchdog retains identity-bound partial checkpoints without scoring them or allowing late mutation', async () => {
  const source = fs.readFileSync(path.join(__dirname, '../tasks16_18.cjs'), 'utf8');
  const module = { exports: {} };
  const timers = [];
  new vm.Script(`(function(exports,require,module){${source}\n})`).runInNewContext({
    setTimeout(fn) { timers.push(fn); return timers.length; }, clearTimeout() {}
  })(module.exports, require, module);
  const taskId = '18_custom_notification_sounds';
  const caseSpec = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks', taskId, 'transitions.json'))).cases.find(c => c.key === 'message_picker_launch');
  let release, cancelled = false;
  const pending = new Promise(resolve => { release = resolve; });
  const result = { schemaVersion: 1, taskId, caseId: caseSpec.caseId, key: caseSpec.key, bundleName: 'test',
    checkpoints: [{ label: 'after_event', completed: false, pageStateJson: '{"instanceCount":0,"available":false}' }], actions: [] };
  const native = { bundleName: 'test', runTasks16To18UI: () => pending,
    cancelTasks16To18UI() { cancelled = true; },
    getTasks16To18UIProgress: () => ({ result, stage: 'window_read_begin', livePicker: { calls: [{ status: 'pending' }] } }) };
  const operation = module.exports.runCase({ taskId, caseSpec, native });
  timers[0]();
  const row = await operation;
  assert.equal(cancelled, true);
  assert.match(row.unsupported, /did not settle/);
  assert.equal(Object.keys(row.observed).length, 0);
  assert.equal(row.invariantChecks.length, 0);
  assert.ok(row.evidence.some(item => item.nativePageTransitionPartial?.stage === 'window_read_begin'));
  assert.ok(row.evidence.some(item => item.label === 'native_ui_partial_after_event' && item.data.completed === false));
  const saved = JSON.stringify(row);
  release({ ...result, observationLevel: 'native_candidate_ui' });
  await pending; await Promise.resolve();
  assert.equal(JSON.stringify(row), saved);
});
