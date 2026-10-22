'use strict';

// SDK boundary regression tests, not device evidence or benchmark outcomes.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require(process.env.LTB_TYPESCRIPT ||
  '/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const providerModule = { exports: {} };
const providerSource = ts.transpileModule(fs.readFileSync(path.join(__dirname, 'Tasks16_18ProviderEvidence.js'), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
new vm.Script(`(function(exports,module){${providerSource}\n})`).runInNewContext()(providerModule.exports, providerModule);

function fixture(findComponents, fixtureHooks = {}) {
  const selector = { inWindow(bundle) { return { ...this, bundle }; }, id(value) { return { ...this, kind: 'id', value }; },
    type(value) { return { ...this, kind: 'type', value }; }, text(value) { return { ...this, kind: 'text', value }; },
    within(parent) { return { ...this, parent }; } };
  const progress = [], shellCalls = [];
  let pageReads = 0;
  const window = { async getBundleName() { return 'test'; }, async getTitle() { return 'test'; },
    async getBounds() { return { left: 0, top: 0, right: 100, bottom: 100 }; } };
  const driver = { findComponents, async findWindow() { return window; }, async delayMs() {} };
  const delegator = { async addAbilityMonitor() {}, async startAbility() {},
    getAppContext() { return { getApplicationContext() {
      if (fixtureHooks.appContextRead) fixtureHooks.appContextRead();
      return fixtureHooks.applicationContext;
    } }; },
    async waitAbilityMonitor() { return { context: fixtureHooks.context || {} }; }, async removeAbilityMonitor() {},
    async executeShellCommand(command, timeoutSecs) {
      shellCalls.push({ command, timeoutSecs });
      return fixtureHooks.shell ? fixtureHooks.shell(command, timeoutSecs) : { exitCode: 0, stdResult: '  ExtensionRecords:\n' };
    } };
  const sdk = { '@ohos.UiTest': { Driver: { create: () => driver }, ON: selector },
    '@ohos.file.fs': { default: {
      renameSync(source, destination) { return fixtureHooks.fileRename(source, destination); },
      statSync(file) { return fixtureHooks.fileStat(file); },
      readTextSync(file, options) { return fixtureHooks.fileRead(file, options); }
    } },
    '@ohos.util': { default: { TextEncoder: class { encodeInto(text) { return new TextEncoder().encode(text); } } } },
    '@ohos.security.cryptoFramework': { default: { createMd() {
      const hash = require('node:crypto').createHash('sha256');
      return { async update(blob) { hash.update(blob.data); }, async digest() { return { data: hash.digest() }; } };
    } } },
    './Tasks16_18ProviderEvidence': providerModule.exports,
    '@ohos.app.ability.abilityDelegatorRegistry': { default: { getAbilityDelegator: () => delegator,
      getArguments: () => ({ parameters: fixtureHooks.parameters || { '-s ltbDeviceUser': '100' } }) } },
    './Tasks16_18NativeUi': { async readTasks16To18Page() { pageReads++; return '{"available":false,"instanceCount":0}'; },
      readTasks16To18Picker() { return fixtureHooks.picker ? JSON.stringify(fixtureHooks.picker()) : '{"observer":{"available":false},"calls":[]}'; },
      publishTasks16To18UI(json, stage) { progress.push({ result: JSON.parse(json), stage }); },
      async prepareTasks16To18Page(context) { await fixtureHooks.prepare(context); },
      async finishTasks16To18Page(context) { await fixtureHooks.afterEvent(context); },
      async bindTasks16To18OriginalPage(context, readinessJson) {
        const ready = JSON.parse(readinessJson);
        if (!ready.nodes.some(node => node.id === 'message_sound_row')) throw new Error('Positive message control unavailable before import');
        if (fixtureHooks.bind) {
          const binding = await fixtureHooks.bind(context, ready);
          if (binding) return JSON.stringify(binding);
        }
        return '{"importCompleted":true}';
      },
      tasks16To18UICancelled() { return false; } } };
  const source = fs.readFileSync(path.join(__dirname, 'Tasks16_18TransitionsUI.test.ets'), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } });
  const module = { exports: {} };
  new vm.Script(`(function(exports,require,module){${compiled.outputText}\n})`).runInNewContext({
    console: { info: line => { if (fixtureHooks.info) fixtureHooks.info(line); } }
  })(module.exports,
    name => { if (!sdk[name]) throw new Error('Unbound SDK: ' + name); return sdk[name]; }, module);
  return { api: module.exports, driver, selector, progress, shellCalls, pageReads: () => pageReads };
}

for (const value of [null, undefined, []]) {
  test('empty UiTest query normalizes only nullish arrays: ' + String(value), async () => {
    const f = fixture(async () => value);
    const found = await f.api.findTasks16To18Components(f.driver, f.selector);
    assert.equal(Array.isArray(found), true);
    assert.equal(found.length, 0);
  });
}

test('query errors propagate and matched components keep their identity', async () => {
  const error = new Error('real query failure');
  const f = fixture(async () => { throw error; });
  await assert.rejects(f.api.findTasks16To18Components(f.driver, f.selector), actual => actual === error);
  const components = [{ actual: true }];
  f.driver.findComponents = async () => components;
  assert.equal(await f.api.findTasks16To18Components(f.driver, f.selector), components);
});

for (const seedFails of [false, true]) {
  test('task17 prepares actual ability Context before Open and preserves partial progress: seedFails=' + seedFails, async () => {
    const context = { toJSON() { throw new Error('Context must never be serialized'); } };
    const events = [];
    let list = false, focused = false;
    const node = (id, text, type, action) => ({
      async getId() { return id; }, async getText() { return text; }, async getType() { return type; },
      async getBounds() { return { left: 0, top: 0, right: 100, bottom: 50 }; },
      async isEnabled() { return true; }, async isClickable() { return !!action; },
      async click() { action(); }
    });
    const f = fixture(async query => {
      const nodes = list ? [node('pinned_messages_filled', '', 'List'),
        node('view_in_timeline_$a', 'View in timeline', 'Button', () => { events.push('focus'); list = false; focused = true; })] :
        [node('', 'Design team', 'Text'), node('focused_event_label', focused ? 'Focused $a' : '12 members', 'Text'),
          node('open_pinned_messages', 'Open', 'Button', () => { events.push('open'); list = true; })];
      const found = [];
      for (const n of nodes) {
        if (query.kind === 'id' && await n.getId() === query.value ||
          query.kind === 'type' && await n.getType() === query.value) found.push(n);
      }
      return found;
    }, {
      context,
      async prepare(actual) { assert.equal(actual, context); events.push('prepare'); if (seedFails) throw new Error('seed readback failed'); },
      async afterEvent(actual) { assert.equal(actual, context); events.push('after'); }
    });
    const result = await f.api.probeTasks16To18Transition({ taskId: '17_pinned_messages', caseId: 'focus',
      key: 'view_in_timeline', eventId: '$a', bundleName: 'test', emitChunks: false });
    assert.equal(f.shellCalls.length, 0, 'Task17 callbacks never trigger task18 shell diagnostics');
    assert.deepEqual(events, seedFails ? ['prepare'] : ['prepare', 'open', 'focus', 'after']);
    assert.equal(result.actions.length, seedFails ? 0 : 2);
    assert.ok(result.checkpoints.some(item => item.label === 'after_event' && item.completed));
    assert.ok(f.progress.some(item => item.stage === 'page_fixture_prepare_begin'));
    if (seedFails) assert.match(result.unsupported, /seed readback failed/);
    else {
      assert.equal(result.unsupported, '');
      assert.ok(f.progress.some(item => item.stage === 'page_fixture_readback_end'));
      assert.ok(f.progress.some(item => item.stage === 'checkpoint_begin' && item.result.checkpoints.some(c => !c.completed)));
    }
  });
}

test('all-null UI queries retain before/after raw checkpoints, never fabricate a root or click', async () => {
  const f = fixture(async () => null);
  const result = await f.api.probeTasks16To18Transition({ taskId: '18_custom_notification_sounds',
    caseId: 'picker', key: 'message_picker_launch', bundleName: 'test', emitChunks: false });
  assert.match(result.unsupported, /root was not established/);
  assert.equal(result.actions.length, 0);
  assert.deepEqual(Array.from(result.checkpoints, item => item.label),
    ['candidate_entry', 'candidate_entry_1', 'candidate_entry_2', 'candidate_entry_3', 'candidate_entry_4', 'candidate_entry_5', 'after_event']);
  assert.ok(result.checkpoints.every(item => item.nodes.length === 0 && item.focusedNodes.length === 0));
});

for (const parameters of [{}, { ltbDeviceUser: '100' }, { '-s ltbDeviceUser': '0' }, { '-s ltbDeviceUser': '107' },
  { '-s ltbDeviceUser': '100;id' }, { '-s ltbDeviceUser': '-1' }, { '-s ltbDeviceUser': '0100' }]) {
  test('UI reads only the explicit -s-prefixed inventory user: ' + JSON.stringify(parameters), async () => {
    const f = fixture(async () => [], { parameters });
    const result = await f.api.probeTasks16To18Transition({ taskId: '18_custom_notification_sounds', caseId: 'picker',
      key: 'message_picker_launch', bundleName: 'test', emitChunks: false });
    const valid = ['0', '107'].includes(parameters['-s ltbDeviceUser']);
    assert.equal(result.deviceUserId, valid ? parameters['-s ltbDeviceUser'] : undefined);
    assert.equal(result.deviceUserParameter, parameters['-s ltbDeviceUser']);
    assert.equal(Boolean(result.deviceUserError), !valid);
    assert.ok(f.progress.some(item => item.stage === 'device_user_parameter'));
    assert.equal(f.shellCalls.length, 0);
  });
}

test('snapshot error preserves partial native window evidence instead of returning no checkpoints', async () => {
  const f = fixture(async () => { throw new Error('SDK query failed'); });
  const result = await f.api.probeTasks16To18Transition({ taskId: '18_custom_notification_sounds',
    caseId: 'picker', key: 'message_picker_launch', bundleName: 'test', emitChunks: false });
  assert.match(result.unsupported, /SDK query failed/);
  assert.equal(result.actions.length, 0);
  assert.ok(result.checkpoints.length >= 2);
  assert.equal(result.checkpoints[0].focusedBundle, 'test');
  assert.match(result.checkpoints[0].error, /SDK query failed/);
});

test('null actionable-control query yields explicit unavailable control, not length error or fake click', async () => {
  const title = { async getBounds() { return { left: 0, top: 0, right: 100, bottom: 50 }; },
    async getId() { return ''; }, async getType() { return 'Text'; }, async getText() { return 'Notifications'; },
    async isEnabled() { return true; }, async isClickable() { return false; } };
  const f = fixture(async query => query.kind === 'text' && query.value === 'Notifications' ? [title] : null);
  const result = await f.api.probeTasks16To18Transition({ taskId: '18_custom_notification_sounds',
    caseId: 'picker', key: 'message_picker_launch', bundleName: 'test', emitChunks: false });
  assert.match(result.unsupported, /root was not established within bounded initial readiness/);
  assert.equal(result.actions.length, 0);
  assert.ok(result.checkpoints.some(item => item.label === 'candidate_entry'));
  assert.ok(result.checkpoints.some(item => item.label === 'after_event'));
});

for (const variant of ['stale_window_once', 'stale_title_once', 'missing_root_once', 'wrong_focus_once',
  'permanent_stale', 'unknown_error', 'post_event_stale']) {
  test('initial candidate readiness is bounded and never masks event errors: ' + variant, async () => {
    let windowReads = 0, binds = 0, selected = false, eventError = false;
    const stale = 'Display 0Window 10dose not exist on current UI! Check if the UI has changed after you got the window object';
    const node = (id, text = '') => ({ async getId() { return id; }, async getText() { return text; },
      async getType() { return 'Button'; }, async isEnabled() { return true; }, async isClickable() { return true; },
      async getBounds() { return { left: 0, top: 0, right: 100, bottom: 50 }; },
      async click() { if (id === 'message_sound_picker') selected = true; } });
    const f = fixture(async query => {
      if (variant === 'missing_root_once' && windowReads === 1) return [];
      if (query.value === 'Notifications') return [node('', 'Notifications')];
      if (['message_sound_row', 'message_sound_picker', 'message_sound_dialog'].includes(query.value)) return [node(query.value)];
      return [];
    }, { async bind(_context, ready) {
      binds++;
      assert.equal(ready.focusedBundle, 'test'); assert.equal(ready.completed, true);
      assert.equal(ready.error, undefined);
      assert.equal(ready.initialReadiness, 'focused_candidate_and_visible_root_controls');
      if (variant.endsWith('_once')) assert.ok(windowReads >= 2, 'No import before a positive retry frame');
    } });
    f.driver.findWindow = async () => {
      windowReads++;
      const sample = windowReads;
      return {
        async getBundleName() {
          if (variant === 'permanent_stale' || variant === 'stale_window_once' && sample === 1) throw new Error(stale);
          if (variant === 'unknown_error' && sample === 1) throw new Error('Permission denied in UiTest');
          if (variant === 'post_event_stale' && selected && !eventError) { eventError = true; throw new Error(stale); }
          return variant === 'wrong_focus_once' && sample === 1 ? 'launcher' : 'test';
        },
        async getTitle() { if (variant === 'stale_title_once' && sample === 1) throw new Error(stale); return ''; }
      };
    };
    const result = await f.api.probeTasks16To18Transition({ taskId: '18_custom_notification_sounds', caseId: 'picker',
      key: 'message_picker_launch', bundleName: 'test', emitChunks: false });
    const entries = result.checkpoints.filter(frame => frame.label.startsWith('candidate_entry'));
    if (variant.endsWith('_once')) {
      assert.equal(result.unsupported, ''); assert.equal(binds, 1); assert.equal(entries.length, 2);
      assert.equal(entries[1].initialReadiness, 'focused_candidate_and_visible_root_controls');
      if (variant.startsWith('stale')) {
        assert.equal(entries[0].completed, false); assert.match(entries[0].error, /Window 10dose/);
        assert.equal(entries[0].initialReadiness, 'transient_stale_initial_window');
        assert.ok(f.progress.some(item => item.stage === 'candidate_root_stale_window'));
      }
    } else if (variant === 'permanent_stale') {
      assert.equal(entries.length, 6); assert.equal(binds, 0); assert.equal(result.actions.length, 0);
      assert.ok(entries.every(frame => !frame.completed && frame.error));
      assert.match(result.unsupported, /bounded initial readiness/);
    } else if (variant === 'unknown_error') {
      assert.equal(entries.length, 1); assert.equal(binds, 0); assert.equal(result.actions.length, 0);
      assert.match(result.unsupported, /Permission denied/);
    } else {
      assert.equal(entries.length, 1); assert.equal(binds, 1); assert.equal(result.actions.length, 2);
      assert.match(result.unsupported, /Window 10dose/);
      const failed = result.checkpoints.find(frame => frame.label === 'launch_audio_picker_after');
      assert.equal(failed.completed, false); assert.match(failed.error, /Window 10dose/);
      assert.equal(failed.initialReadiness, undefined, 'Never classify an event-stage stale handle as initial readiness');
      assert.equal(result.checkpoints.find(frame => frame.label === 'after_event').completed, true,
        'A later successful frame must not erase the event-stage error');
    }
  });
}

test('picker uses bounded keyed queries, not full-host scans, and publishes zero-instance evidence early', async () => {
  let dialog = false, picker = false, queries = 0, properties = 0;
  const nodes = (id, text) => ({
    async getId() { properties++; return id; }, async getText() { properties++; return text || ''; },
    async getType() { properties++; return id.includes('button') ? 'Button' : 'Text'; },
    async getBounds() { properties++; return { left: 0, top: 0, right: 100, bottom: 50 }; },
    async isEnabled() { properties++; return true; }, async isClickable() { properties++; return true; },
    async click() { if (id === 'message_sound_row') dialog = true; if (id === 'message_sound_picker') { dialog = false; picker = true; } }
  });
  const f = fixture(async query => {
    queries++;
    assert.ok(query.kind === 'id' || query.kind === 'text', 'full-window/type scans are forbidden for task18');
    if (query.value === 'Notifications') return [nodes('', 'Notifications')];
    if (query.value === 'message_sound_row') return [nodes(query.value)];
    if (dialog && ['message_sound_dialog', 'message_sound_picker'].includes(query.value)) return [nodes(query.value)];
    if (picker && query.parent?.value === 'UIExtensionComponent') return [nodes(query.value)];
    return null;
  });
  const result = await f.api.probeTasks16To18Transition({ taskId: '18_custom_notification_sounds',
    caseId: 'picker', key: 'message_picker_launch', bundleName: 'test', emitChunks: false });
  assert.equal(result.unsupported, '');
  assert.equal(result.actions.length, 2);
  assert.ok(queries <= 10, 'bounded selector query count: ' + queries);
  assert.ok(properties <= 48, 'bounded component-property IPC count including pre-import readiness: ' + properties);
  assert.equal(f.pageReads(), 3, 'Only entry identity and canonical before/after storage reads');
  const after = result.checkpoints.find(item => item.label === 'after_event');
  assert.equal(after.focusedBundle, 'test', 'host-window UIExtension must not trigger repeated whole-tree polling');
  assert.equal(after.focusedNodes.length, 2);
  assert.ok(after.focusedNodes.every(node => node.selectorScope.startsWith('audio-extension:')));
  const identity = f.progress.find(item => item.stage === 'page_read_end');
  assert.equal(JSON.parse(identity.result.checkpoints[0].pageStateJson).instanceCount, 0,
    'No inferred same-page identity from class source hash');
  assert.ok(f.progress.some(item => item.stage === 'action_completed' && item.result.actions.length === 2));
  assert.equal(f.shellCalls.length, 1, 'No after-dump command is run without an observed pending SDK call');
  assert.match(result.providerCommands[1].error, /No single pending/);
});

for (const variant of ['pending', 'resolved_during_dump', 'sdk_error', 'nonzero']) {
  test('same-run provider commands retain raw output and bounded pending snapshots: ' + variant, async () => {
    let dialog = false, selected = false, status = 'pending', dumpCount = 0;
    const node = (id, text = '') => ({ async getId() { return id; }, async getText() { return text; },
      async getType() { return 'Button'; }, async isEnabled() { return true; }, async isClickable() { return true; },
      async getBounds() { return { left: 0, top: 0, right: 100, bottom: 50 }; },
      async click() { if (id === 'message_sound_row') dialog = true; if (id === 'message_sound_picker') selected = true; } });
    const raw = '  ExtensionRecords:\n  raw transport sentinel\n';
    const f = fixture(async query => {
      if (query.value === 'Notifications') return [node('', 'Notifications')];
      if (query.value === 'message_sound_row') return [node(query.value)];
      if (dialog && ['message_sound_dialog', 'message_sound_picker'].includes(query.value)) return [node(query.value)];
      return [];
    }, {
      picker() { return { observer: { available: true }, calls: selected ? [{ id: 1, status }] : [] }; },
      async shell(command, timeout) {
        assert.equal(timeout, 3);
        if (command === 'bm dump -n com.ohos.filepicker') return { exitCode: 0, stdResult: '{}' };
        dumpCount++;
        if (dumpCount === 2) {
          assert.equal(selected, true);
          if (variant === 'resolved_during_dump') status = 'resolved';
          if (variant === 'sdk_error') throw new Error('SDK command timed out');
        } else assert.equal(selected, false);
        return { exitCode: variant === 'nonzero' ? 1 : 0, stdResult: raw };
      }
    });
    const result = await f.api.probeTasks16To18Transition({ taskId: '18_custom_notification_sounds', caseId: 'picker',
      key: 'message_picker_launch', bundleName: 'test', emitChunks: false });
    assert.deepEqual(f.shellCalls.map(call => call.command), ['aa dump -e', 'aa dump -e']);
    const after = result.providerCommands[1];
    assert.equal(JSON.parse(after.pickerStateBeforeJson).calls[0].status, 'pending');
    assert.equal(JSON.parse(after.pickerStateAfterJson).calls[0].status, variant === 'resolved_during_dump' ? 'resolved' : 'pending');
    assert.ok(after.finishedAtMs >= after.startedAtMs);
    if (variant === 'sdk_error') { assert.match(after.error, /timed out/); assert.equal(after.completed, false); }
    else { assert.equal(after.stdResult, raw); assert.equal(after.exitCode, variant === 'nonzero' ? 1 : 0); }
    const partial = f.progress.find(item => item.stage === 'provider_command_begin:pending_after:aa dump -e');
    assert.equal(partial.result.providerCommands[1].completed, false, 'Publish before awaiting the SDK');
    assert.equal(result.actions.length, 2);
    assert.equal(JSON.parse(result.providerEvidenceJson).providerIdentityVerified, false);
  });
}

test('provider metadata command is selected from the same-run exact-host record while SDK select remains pending', async () => {
  let selected = false, startedAtMs = 0;
  const provider = 'com.vendor.music';
  const host = { bundleName: 'test', moduleName: 'entry', abilityName: 'EntryAbility' };
  const node = (id, text = '') => ({ async getId() { return id; }, async getText() { return text; },
    async getType() { return 'Button'; }, async isEnabled() { return true; }, async isClickable() { return true; },
    async getBounds() { return { left: 0, top: 0, right: 100, bottom: 50 }; },
    async click() { if (id === 'message_sound_picker') { selected = true; startedAtMs = Date.now(); } } });
  const raw = '  ExtensionRecords:\n    uri [/' + provider + '/audio/AudioExtension6]\n' +
    '      AbilityRecord ID #210   state #FOREGROUND   start time [12345]\n' +
    '      main name [AudioExtension]\n      bundle name [' + provider + ']\n      ability type [UIEXTENSION]\n' +
    '      root host bundle name [test]\n      root host module name [entry]\n' +
    '      root host ability name [EntryAbility]\n      pid: 1862\n';
  const f = fixture(async query => query.value === 'Notifications' ? [node('', 'Notifications')] : [node(query.value)], {
    async bind() { return { monitoredContext: { scope: host } }; },
    picker() { return { observer: { available: true }, calls: selected ? [{ id: 1, status: 'pending',
      api: '@ohos.file.picker.AudioViewPicker.select', startedAtMs, samePageContext: true }] : [] }; },
    async shell(command, timeoutSecs) {
      assert.equal(timeoutSecs, 3);
      if (command === 'aa dump -e') return { exitCode: 0, stdResult: selected ? raw : '  ExtensionRecords:\n' };
      assert.equal(command, 'bm dump -n ' + provider + ' -u 100');
      assert.equal(selected, true);
      return { exitCode: 0, stdResult: JSON.stringify({ name: provider,
        applicationInfo: { bundleName: provider, name: provider, isSystemApp: true },
        hapModuleInfos: [{ extensionInfos: [{ name: 'AudioExtension', bundleName: provider, moduleName: 'audio',
          enabled: true, visible: true, extensionTypeName: 'sysPicker/audioPicker' }] }] }) };
    }
  });
  const result = await f.api.probeTasks16To18Transition({ taskId: '18_custom_notification_sounds', caseId: 'picker',
    key: 'message_picker_launch', bundleName: 'test', emitChunks: false });
  assert.equal(result.unsupported, '');
  assert.deepEqual(f.shellCalls.map(call => call.command), ['aa dump -e', 'aa dump -e', 'bm dump -n ' + provider + ' -u 100']);
  const evidence = JSON.parse(result.providerEvidenceJson);
  assert.equal(evidence.providerIdentityVerified, true);
  assert.equal(evidence.matchedRecord.providerBundle, provider);
  assert.equal(evidence.installedProvider.declaration.extensionTypeName, 'sysPicker/audioPicker');
});

for (const variant of ['complete', 'missing', 'wrong_nonce', 'wrong_digest', 'settled', 'permission', 'wrong_type',
  'wrong_context', 'module_cache', 'fs_permission', 'oversize', 'short_read', 'wrong_host_path', 'partial_json_once', 'rename_failure']) {
  test('native host response preserves bounded actual SDK observations: ' + variant, async () => {
    let selected = false, startedAtMs = 0, request, status = 'pending', polls = 0, appContextReads = 0, fileText, renames = 0;
    const nonce = 'a'.repeat(32), provider = 'com.vendor.music';
    const host = { bundleName: 'test', moduleName: 'entry', abilityName: 'EntryAbility' };
    const applicationContext = {
      get applicationInfo() { assert.equal(this, applicationContext); return { name: variant === 'wrong_context' ? 'wrong' : 'test' }; },
      get cacheDir() { assert.equal(this, applicationContext); return variant === 'module_cache' ? '/data/storage/el2/base/haps/entry/cache' : '/data/storage/el2/base/cache'; }
    };
    const node = (id, text = '') => ({ async getId() { return id; }, async getText() { return text; },
      async getType() { return 'Button'; }, async isEnabled() { return true; }, async isClickable() { return true; },
      async getBounds() { return { left: 0, top: 0, right: 100, bottom: 50 }; },
      async click() { if (id === 'message_sound_picker') { selected = true; startedAtMs = Date.now(); } } });
    const raw = '  ExtensionRecords:\n    uri [/' + provider + '/audio/AudioExtension6]\n' +
      '      AbilityRecord ID #210   state #FOREGROUND   start time [12345]\n' +
      '      main name [AudioExtension]\n      bundle name [' + provider + ']\n      ability type [UIEXTENSION]\n' +
      '      root host bundle name [test]\n      root host module name [entry]\n' +
      '      root host ability name [EntryAbility]\n      pid: 1862\n';
    const f = fixture(async query => query.value === 'Notifications' ? [node('', 'Notifications')] : [node(query.value)], {
      parameters: { '-s ltbDeviceUser': '107', '-s ltbExecutionNonce': nonce, '-s ltbProviderHostBridge': '1' },
      applicationContext, appContextRead() { appContextReads++; },
      fileRename(source, destination) {
        assert.equal(source, applicationContext.cacheDir + '/Tasks16_18_provider_' + nonce + '.json.tmp');
        assert.equal(destination, applicationContext.cacheDir + '/Tasks16_18_provider_' + nonce + '.json');
        renames++;
        if (variant === 'rename_failure') throw new Error('Native rename failed');
      },
      async bind() { return { monitoredContext: { scope: host } }; },
      picker() { return { observer: { available: true }, calls: selected ? [{ id: 1, status,
        api: '@ohos.file.picker.AudioViewPicker.select', startedAtMs, samePageContext: true }] : [] }; },
      info(line) { if (line.startsWith('ARKTS_16_18_PROVIDER_REQUEST ')) request = JSON.parse(line.slice(29)); },
      async shell(command) {
        if (command === 'aa dump -e') return { exitCode: 0, stdResult: selected ? raw : '  ExtensionRecords:\n' };
        if (command.startsWith('bm ')) return { exitCode: 0, stdResult: 'error: failed to get information and the parameters may be wrong.\n' };
        throw new Error('No shell file reads are allowed: ' + command);
      },
      fileStat(file) {
        if (file.endsWith('.json')) { assert.equal(renames, 1); return { size: Buffer.byteLength(fileText) }; }
        assert.equal(file, applicationContext.cacheDir + '/Tasks16_18_provider_' + nonce + '.json.tmp');
        assert.ok(request); polls++;
        if (variant === 'missing') throw Object.assign(new Error('No such file'), { code: 13900002 });
        if (variant === 'fs_permission') throw Object.assign(new Error('Permission denied'), { code: 13900013 });
        const data = { name: provider, applicationInfo: { bundleName: provider, name: provider, isSystemApp: true },
          hapModuleInfos: [{ extensionInfos: [{ name: 'AudioExtension', bundleName: provider, moduleName: 'audio',
            enabled: true, visible: true, extensionTypeName: variant === 'wrong_type' ? 'sysPicker/photoPicker' : 'sysPicker/audioPicker' }] }] };
        const stdResult = variant === 'permission' ? 'permission denied' : JSON.stringify(data);
        const response = { version: 2, transport: 'hdc_provider_metadata_app_cache_v2', request: { ...request },
          command: 'bm dump -n ' + provider + ' -u 107', exitCode: variant === 'permission' ? 1 : 0, stderr: '', stdResult,
          stdoutSha256: require('node:crypto').createHash('sha256').update(stdResult).digest('hex'),
          stdoutBytes: Buffer.byteLength(stdResult), stdoutCharacters: stdResult.length,
          host: { serial: 'test', role: 'final', requestLogPid: '1234', receivedAtMs: 100, startedAtMs: 101, finishedAtMs: 102 } };
        if (variant === 'wrong_nonce') response.request.nonce = 'b'.repeat(32);
        if (variant === 'wrong_digest') response.stdoutSha256 = 'b'.repeat(64);
        if (variant === 'wrong_host_path') response.request.hostResponsePath = '/data/local/tmp/wrong.json';
        if (variant === 'settled') status = 'resolved';
        fileText = JSON.stringify(response);
        if (variant === 'partial_json_once' && polls === 1) fileText = '{"version":';
        return { size: variant === 'oversize' ? 3 * 1024 * 1024 + 1 : Buffer.byteLength(fileText) };
      },
      fileRead(file, options) {
        assert.equal(file, applicationContext.cacheDir + '/Tasks16_18_provider_' + nonce + '.json' + (renames ? '' : '.tmp'));
        assert.equal(options.length, Buffer.byteLength(fileText)); assert.equal(options.encoding, 'utf-8');
        return variant === 'short_read' ? fileText.slice(1) : fileText;
      }
    });
    const result = await f.api.probeTasks16To18Transition({ taskId: '18_custom_notification_sounds',
      caseId: 'ns_state_003_message_picker_launch', key: 'message_picker_launch', bundleName: 'test', emitChunks: false });
    const proof = JSON.parse(result.providerEvidenceJson);
    assert.equal(proof.providerIdentityVerified, ['complete', 'partial_json_once'].includes(variant), JSON.stringify({ proof, samples: result.providerCommands }));
    const sample = result.providerCommands.find(item => item.phase === 'pending_metadata_host');
    assert.ok(sample); assert.equal(polls, ['missing', 'short_read'].includes(variant) ? 16 :
      variant === 'partial_json_once' ? 2 : ['wrong_context', 'module_cache'].includes(variant) ? 0 : 1);
    assert.equal(appContextReads, 1);
    assert.ok(f.shellCalls.every(item => !item.command.startsWith('cat ')));
    assert.ok(f.progress.some(item => item.stage === 'provider_host_request_begin' && !item.result.providerCommands.at(-1).completed));
    assert.ok(f.progress.some(item => item.stage === 'provider_host_response_end'));
    assert.equal(JSON.parse(sample.pickerStateAfterJson).calls[0].status, variant === 'settled' ? 'resolved' : 'pending');
    if (variant === 'missing') { assert.equal(sample.completed, false); assert.match(sample.error, /16 reads/); }
    if (['wrong_nonce', 'wrong_digest'].includes(variant)) assert.match(sample.error, /identity, raw digest/);
    if (['complete', 'settled', 'permission', 'wrong_type'].includes(variant)) assert.equal(sample.completed, true);
    if (['wrong_context', 'module_cache'].includes(variant)) assert.match(sample.error, /Actual application cache context/);
    if (variant === 'fs_permission') { assert.match(sample.error, /Permission denied/); assert.equal(sample.lastPollErrorCode, 13900013); }
    if (variant === 'oversize') assert.match(sample.error, /bounded transport size/);
    if (variant === 'short_read') { assert.match(sample.error, /16 reads/); assert.match(sample.lastPollError, /length changed/); }
    if (variant === 'rename_failure') { assert.match(sample.error, /Native rename failed/); assert.notEqual(sample.responseRenamed, true); }
    if (['wrong_nonce', 'wrong_digest', 'missing', 'short_read'].includes(variant)) assert.equal(renames, 0);
    if (variant === 'complete') {
      assert.equal(sample.responseFileBytes, Buffer.byteLength(fileText));
      assert.equal(request.hostResponsePath, '/data/app/el2/107/base/test/cache/Tasks16_18_provider_' + nonce + '.json');
    }
  });
}
