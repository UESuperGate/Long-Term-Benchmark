'use strict';

// Host adapter regressions only, not native SDK execution or benchmark evidence.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require(process.env.LTB_TYPESCRIPT ||
  '/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');

function observer() {
  const source = fs.readFileSync(path.join(__dirname, 'Tasks16_18NativeUi.js'), 'utf8');
  const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  const module = { exports: {} };
  new vm.Script(`(function(exports,module){${output}\n})`).runInNewContext()(module.exports, module);
  return module.exports;
}

const request = { taskId: '17_pinned_messages', caseId: 'focus', key: 'view_in_timeline', bundleName: 'test', eventId: '$a' };

test('fixture callbacks and original SDK Context stay in memory, with one prepare/readback and progress intact', async () => {
  const api = observer(), bridge = {}, contexts = [];
  const context = { toJSON() { throw new Error('SDK Context serialized'); } };
  const callbacks = {
    toJSON() { throw new Error('Callbacks serialized'); },
    async prepare(actual) { contexts.push(actual); }, async afterEvent(actual) { contexts.push(actual); }
  };
  api.configureTasks16To18UI(async json => {
    assert.deepEqual(JSON.parse(json), request);
    await assert.rejects(api.finishTasks16To18Page(context), /same prepared/);
    await api.prepareTasks16To18Page(context);
    await assert.rejects(api.prepareTasks16To18Page(context), /one original/);
    await assert.rejects(api.finishTasks16To18Page({}), /same prepared/);
    api.publishTasks16To18UI(JSON.stringify({ ...request, checkpoints: [{ completed: false }], actions: [] }), 'fixture');
    await api.finishTasks16To18Page(context);
    await assert.rejects(api.finishTasks16To18Page(context), /same prepared/);
    return json;
  }, 'test', undefined, 'null');
  api.attachTasks16To18UI(bridge, request.taskId, request.key);
  await bridge.runTasks16To18UI(request, callbacks);
  assert.equal(contexts.length, 2);
  assert.ok(contexts.every(actual => actual === context));
  assert.equal(bridge.getTasks16To18UIProgress().result.checkpoints[0].completed, false);
  await assert.rejects(api.prepareTasks16To18Page(context), /No active/);
  bridge.disposeTasks16To18UI();
  await assert.rejects(api.finishTasks16To18Page(context), /No active/);
});

for (const stop of ['cancel', 'dispose']) {
  test('in-flight preparation cannot finish or read after ' + stop, async () => {
    const api = observer(), bridge = {}, context = {};
    let release, notify, reads = 0;
    const started = new Promise(resolve => { notify = resolve; });
    const pending = new Promise(resolve => { release = resolve; });
    api.configureTasks16To18UI(async json => {
      await api.prepareTasks16To18Page(context);
      await api.finishTasks16To18Page(context);
      return json;
    }, 'test', undefined, 'null');
    api.attachTasks16To18UI(bridge, request.taskId, request.key);
    const running = bridge.runTasks16To18UI(request, {
      async prepare(actual) { assert.equal(actual, context); notify(); await pending; },
      async afterEvent() { reads++; }
    });
    await started;
    if (stop === 'cancel') bridge.cancelTasks16To18UI();
    else bridge.disposeTasks16To18UI();
    release();
    await assert.rejects(running, /cancelled during preparation/);
    assert.equal(reads, 0);
    if (stop === 'cancel') bridge.disposeTasks16To18UI();
  });
}

test('task18 does not accept task17 fixture callbacks or call them implicitly', async () => {
  const api = observer(), bridge = {};
  const sound = { ...request, taskId: '18_custom_notification_sounds', key: 'message_picker_launch' };
  api.configureTasks16To18UI(async json => json, 'test', undefined, 'null');
  api.attachTasks16To18UI(bridge, sound.taskId, sound.key);
  await assert.rejects(bridge.runTasks16To18UI(sound, { prepare() {}, afterEvent() {} }), /Unsupported/);
  await bridge.runTasks16To18UI(sound);
  await assert.rejects(api.prepareTasks16To18Page({}), /No active/);
  bridge.disposeTasks16To18UI();
});
