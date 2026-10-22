'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const os = require('node:os');
const crypto = require('node:crypto');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const root = path.resolve(__dirname, '../../../../..');
const source = fs.readFileSync(path.join(__dirname, 'Task08TimelineUI.js'), 'utf8');
const adapter = fs.readFileSync(path.join(__dirname, 'Task08StrictNativeUiAdapter.js'), 'utf8');
const contract = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks/08_threads/transitions.json')));
const candidate = path.join(root, 'experiment_results/runtime_transition_20261021/task08_archived_candidate_prepare_v1_20261021T090705Z/candidate');
function load(file) {
  const module = { exports: {} };
  const js = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  vm.runInNewContext('(function(exports,module){' + js + '\n})')(module.exports, module);
  return module.exports;
}
async function replay(key) {
  const roomModule = load(path.join(candidate, 'entry/src/main/ets/features/RoomTimelineFeature.ets'));
  const threadModule = load(path.join(candidate, 'entry/src/main/ets/features/ThreadTimelineFeature.ets'));
  const room = new roomModule.RoomTimelinePresenter(new roomModule.RoomTimelineGateway());
  const thread = new threadModule.ThreadTimelinePresenter(new threadModule.ThreadTimelineGateway());
  let destroyed = false;
  const actions = [];
  const window = { bundleName: 'host-unit-not-native', hostVerified: true,
    bounds: { left: 0, top: 0, right: 100, bottom: 100 } };
  const driver = {
    async findComponents(query) { return [{
      async getBounds() { return { left: 1, top: 1, right: 90, bottom: 90 }; },
      async getText() { return query.id === 'thread_focus_error' ? thread.lastFocusedError :
        query.id === 'thread_composer' ? thread.composerText : room.composerText; },
      async isEnabled() { return true; }, async isClickable() { return true; },
      async inputText(value) { (query.id === 'room_composer' ? room : thread).setComposerText(value); },
      async clearText() { (query.id === 'room_composer' ? room : thread).setComposerText(''); },
      async click() { actions.push(query.id);
        if (query.id === 'room_send') room.sendMessage();
        else if (query.id === 'room_open_thread_$root') thread.openThread('$root');
        else if (query.id.startsWith('thread_focus_')) thread.focusEvent(query.id.slice('thread_focus_'.length));
        else throw new Error('Unknown host-unit action: ' + query.id);
      }
    }]; }, async delayMs() {}, async pressBack() {}
  };
  const ON = { id(id) { return { id, inWindow() { return this; } }; } };
  const launch = { async start() {}, async check() { return window; },
    async dispose() { destroyed = true; }, read() { return { created: true, destroyed }; } };
  const context = {};
  vm.createContext(context);
  vm.runInContext(source.replace(/^export /gm, ''), context);
  const raw = JSON.parse(await context.runTask08TimelineUI(contract.cases.find(c => c.key === key),
    { role: 'agent', bundleName: window.bundleName, roomModuleUrl: 'room', timelineModuleUrl: 'thread' },
    async url => url === 'room' ? roomModule : threadModule, driver, ON, launch));
  return { raw, actions, thread };
}

test('exact archived candidate retains real root focus; case002 stops before canonical event', async () => {
  const { raw, thread, actions } = await replay('focus_reply');
  assert.equal(raw.fixtureFailure.classification, 'fixture_given_unreachable');
  assert.equal(raw.fixtureFailure.required, null);
  assert.equal(raw.fixtureFailure.actual, '$root');
  assert.equal(raw.frames.find(f => f.label === 'before_event').state.thread.focusedEventId, '$root');
  assert.equal(thread.focusedEventId, '$root');
  assert.equal(raw.eventExecuted, false);
  assert.equal(raw.observed, undefined);
  assert.equal(raw.uiAssertions, undefined);
  assert.deepEqual(raw.invariantChecks, []);
  assert.equal(raw.frames.some(f => f.label === 'after_event'), false);
  assert.equal(actions.includes('thread_focus_$reply'), false);
  assert.equal(raw.frames.some(f => f.state.calls.some(c => c.kind === 'fixture_input')), false);
  assert.equal(raw.launchEvidence.destroyed, true);
});

test('case003 retains genuine reply-click prefix and original candidate failure behavior', async () => {
  const { raw, actions } = await replay('focus_failure_preserves_thread');
  assert.equal(raw.fixtureFailure, undefined);
  assert.equal(raw.failure, undefined);
  assert.equal(raw.frames.find(f => f.label === 'before_event').state.thread.focusedEventId, '$reply');
  assert.equal(raw.observed.focusedEventId, '$reply');
  assert.equal(raw.observed.focusState, 'failure');
  assert.equal(raw.eventExecuted, true);
  assert.equal(actions.includes('thread_focus_$reply'), true);
  assert.notEqual(raw.observed.focusedEventId,
    contract.cases.find(c => c.key === 'focus_failure_preserves_thread').expected.focusedEventId);
});

test('private observer contains no direct focus-state writes or replacement setters', () => {
  assert.doesNotMatch(source, /seedFocusGiven|fixture-focus-input|fixture_input/);
  const ast = ts.createSourceFile('adapter.js', source, ts.ScriptTarget.Latest, true);
  function visit(node) {
    if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.EqualsToken)
      assert.doesNotMatch(node.left.getText(ast), /focusedEventId/);
    ts.forEachChild(node, visit);
  }
  visit(ast);
  assert.doesNotMatch(source, /spec\.expected/);
});

for (const forged of [false, true]) test('unmet given cannot become a pass/fail even with forged later state: ' + forged, async () => {
  const { raw } = await replay('focus_reply');
  if (forged) { raw.eventExecuted = true; raw.observed = { focusedEventId: '$reply' };
    raw.invariantChecks = [{ passed: true }]; }
  const context = {};
  vm.createContext(context);
  vm.runInContext(adapter.replace(/^export /gm, ''), context);
  const result = await context.runTask08StrictCase({ native: { async runTask08StrictUI() { return raw; } },
    sharedRunCase() { throw new Error('Unmet given must never invoke the shared evaluator'); } });
  assert.match(result.unsupported, /^fixture_given_unreachable/);
  assert.equal(Object.keys(result.observed).length, 0);
  assert.equal(result.invariantChecks.length, 0);
});

test('cleanup/environment failures still cannot score an unreachable given', async () => {
  const { raw } = await replay('focus_reply');
  raw.failure = { cleanupError: 'unit environment failure' };
  const context = {};
  vm.createContext(context);
  vm.runInContext(adapter.replace(/^export /gm, ''), context);
  const result = await context.runTask08StrictCase({ native: { async runTask08StrictUI() { return raw; } },
    sharedRunCase() { throw new Error('Must remain NS'); } });
  assert.ok(result.unsupported);
  assert.equal(result.evidence[0].failure.cleanupError, 'unit environment failure');
});

test('successor installer really installs private fixtures and retains original production bytes', () => {
  const { install } = require('./install.cjs');
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'task08-given-unit-'));
  const sha = data => crypto.createHash('sha256').update(data).digest('hex');
  const write = (relative, bytes) => {
    const file = path.join(work, relative);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, bytes);
  };
  try {
    for (const relative of ['AppScope/app.json5', 'entry/src/main/module.json5',
      'entry/src/main/ets/pages/Index.ets', 'entry/src/main/ets/features/ThreadTimelineFeature.ets',
      'entry/src/main/ets/features/RoomTimelineFeature.ets'])
      write(relative, fs.readFileSync(path.join(candidate, relative)));
    write('entry/src/test/native-bundle.js',
      "calls.push({ module: 'ArkUI', method: observation.method, nativeUI: true, observation: snapshot(observation) });\n" +
      "const factoryResult = adapterFactories[group](module.exports, hostShim, module);\n" +
      "if (candidateUI) await bridge.ui.navigate(candidateUI.route);\n" +
      "const adapter = { runCase: context => module.exports.runCase({ ...context, native: bridge, context: {} }) };\n" +
      "try { await bridge.dispose(); } catch (error) {}\n");
    write('entry/src/test/NativeBundle.test.ets', 'export default function nativeBundleTests(): void {}\n');
    const prior = process.env.LTB_TASK08_ROLE;
    process.env.LTB_TASK08_ROLE = 'agent';
    let result;
    try { result = install(work); }
    finally { if (prior === undefined) delete process.env.LTB_TASK08_ROLE; else process.env.LTB_TASK08_ROLE = prior; }
    assert.equal(result.role, 'agent');
    assert.equal(result.productionVariant, 'timeline');
    assert.equal(result.productionUnchanged, true);
    assert.equal(result.candidateGivenSuccessor.replacements.length, 2);
    assert.equal(result.installer.file, path.join(__dirname, 'install.cjs'));
    for (const item of result.production)
      assert.equal(item.sha256, sha(fs.readFileSync(path.join(candidate, item.path))));
    for (const name of ['Task08TimelineUI.js', 'Task08StrictNativeUiAdapter.js']) {
      const fixture = result.fixtures.find(f => f.installedPath.endsWith('/' + name));
      assert.equal(fixture.file, path.join(__dirname, name));
      assert.equal(fixture.sha256, sha(fs.readFileSync(path.join(work, fixture.installedPath))));
    }
  } finally { fs.rmSync(work, { recursive: true, force: true }); }
});
