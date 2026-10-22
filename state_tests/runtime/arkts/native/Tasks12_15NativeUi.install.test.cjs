'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const vm = require('node:vm');
const crypto = require('node:crypto');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const { install } = require('./Tasks12_15NativeUi.install.cjs');
const { runCase } = require('../tasks12_15.cjs');
const root = path.resolve(__dirname, '../../../..');
const spec = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks/12_report_room/transitions.json'))).cases.find(c => c.key === 'blank_reason_disabled');
const featurePath = 'entry/src/main/ets/features/ReportRoomFeature.ets';
const pagePath = 'entry/src/main/ets/pages/Index.ets';
const candidate = path.join(root, 'final_dev_nodes/12_report_room_final_25_05_0');
const sources = [featurePath, pagePath].map(p => ({ path: p,
  sha256: crypto.createHash('sha256').update(fs.readFileSync(path.join(candidate, p))).digest('hex') }));

function generated(t) {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'task12-ui-install-'));
  t.after(() => fs.rmSync(work, { recursive: true, force: true }));
  const testRoot = path.join(work, 'entry/src/test');
  fs.mkdirSync(testRoot, { recursive: true });
  fs.cpSync(path.join(candidate, 'entry/src/main'), path.join(work, 'entry/src/main'), { recursive: true });
  fs.mkdirSync(path.join(work, 'AppScope'));
  fs.copyFileSync(path.join(candidate, 'AppScope/app.json5'), path.join(work, 'AppScope/app.json5'));
  fs.writeFileSync(path.join(testRoot, 'native-bundle.js'), "import { createNativeContext } from './native-device-platform';\n" +
    'if (candidateUI) await bridge.ui.navigate(candidateUI.route);\ntry { await bridge.dispose(); } catch(error) {}\n');
  fs.writeFileSync(path.join(testRoot, 'NativeBundle.test.ets'), 'export default function nativeBundleTests(): void {}\n');
  return { work, testRoot };
}

test('installer changes only generated evaluator and retains native canonical row transport', t => {
  const f = generated(t), result = install(f.work);
  assert.equal(result.productionUnchanged, true);
  assert.equal(result.fixtures.length, 8);
  assert.deepEqual(result.presenterSource, sources[0]);
  const bundle = fs.readFileSync(result.bundleFile, 'utf8');
  assert.match(bundle, /if \(!tasks12To15UI && candidateUI\)/);
  assert.match(bundle, /finally \{ if \(bridge.disposeTasks12To15UI\)/);
  assert.doesNotMatch(bundle, /from ['"].*\.ets/);
  const suite = fs.readFileSync(result.suiteFile, 'utf8');
  assert.doesNotMatch(suite, /from ['"]\.\.\/main\/ets\/features\//);
  assert.match(suite, /configureTasks12ReportPageBinding/);
  assert.ok(result.binding.productionModuleUrl.endsWith('/entry/ets/features/ReportRoomFeature'));
  assert.match(suite, /runTasks12To15NativeUi\(JSON.parse\(caseJson\) as NativeUiCase, bundleName\)/);
  assert.throws(() => install(f.work), /already installed/);
});

test('missing export is not replaced and changed lifecycle fails before file writes', t => {
  const f = generated(t);
  fs.unlinkSync(path.join(f.work, featurePath));
  assert.equal(install(f.work).presenterSource, null);
  assert.doesNotMatch(fs.readFileSync(path.join(f.testRoot, 'NativeBundle.test.ets'), 'utf8'), /import \{ ReportRoomPresenter/);
  const second = generated(t);
  fs.writeFileSync(path.join(second.testRoot, 'native-bundle.js'), "import { createNativeContext } from './native-device-platform';\n");
  assert.throws(() => install(second.work), /lifecycle changed/);
  assert.equal(fs.existsSync(path.join(second.testRoot, 'Tasks12_15NativeUiBridge.js')), false);
});

function bridgeApi() {
  const exports = {};
  const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, 'Tasks12_15NativeUiBridge.js'), 'utf8'),
    { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  vm.runInNewContext(code, { exports });
  return exports;
}

function raw(enabled = false) {
  const frame = (label, sequence) => ({ label, sequence, sessionId: 'native-session', bundleName: 'candidate.test',
    observed: { reason: '   ', leaveRoom: true, canReport: false, submitEnabled: enabled },
    controls: [
      { selector: 'report reason', present: true, visible: true, text: '   ' },
      { selector: 'leave preference', present: true, visible: true, checked: true },
      { selector: 'report submit', present: true, visible: true, enabled }
    ], presenterEvidence: { available: true, instanceId: 1, instanceCount: 1, reason: '   ', leaveRoom: true, canReport: false,
      calls: [{ completed: true, method: 'updateReason', value: '   ' }, { completed: true, method: 'toggleLeaveRoom' }] } });
  return { taskId: spec.taskId, caseId: spec.caseId, traceDigest: spec.traceDigest, sessionId: 'native-session',
    entryExecuted: true, eventExecuted: true, prerequisite: { rootConfirmed: true },
    frames: [frame('before_event', 3), frame('after_event', 4)],
    actions: [{ executed: true, sessionId: 'native-session', sequence: 1, kind: 'input', value: '   ' },
      { executed: true, sessionId: 'native-session', sequence: 2, kind: 'click', target: 'report_room_leave_toggle' }] };
}

async function throughSharedEvaluator(probe, configuredSources = sources) {
  const api = bridgeApi();
  const bridge = { capabilities: { context: { available: true } }, setObservationRecorder() {} };
  api.configureTasks12To15UI(async () => JSON.stringify(probe), 'candidate.test', JSON.stringify(configuredSources));
  assert.equal(api.attachTasks12To15UI(bridge, spec.taskId, spec.key), true);
  const original = fs.readFileSync(path.join(root, 'scripts/runtime_semantics/arkts_runtime.cjs'), 'utf8');
  const ast = ts.createSourceFile('runtime.cjs', original, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
  const shared = ['snapshot', 'compareExpected', 'evaluateCase'].map(name =>
    ast.statements.find(s => ts.isFunctionDeclaration(s) && s.name?.text === name).getText(ast)).join('\n');
  const runtime = fs.readFileSync(path.join(__dirname, 'bundle-runtime.js'), 'utf8').replace('export async function runNativeCase', 'async function runNativeCase');
  const feature = '/project/' + featurePath;
  const factoryCode = ts.transpileModule(fs.readFileSync(path.join(candidate, featurePath), 'utf8'),
    { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  const context = vm.createContext({ bridge, candidateUI: { productionSource: sources[1] },
    factories: { [feature]: new Function('exports', 'require', 'module', factoryCode) },
    metadata: { [feature]: sources[0] }, platformConstants: {},
    adapter: { runCase: args => runCase({ ...args, native: bridge }) }, spec });
  vm.runInContext(shared + '\n' + runtime + '\nactiveNativeContext = bridge;', context);
  const row = JSON.parse(JSON.stringify(await vm.runInContext('evaluateCase(spec.taskId, spec, "/project", adapter)', context)));
  bridge.disposeTasks12To15UI();
  assert.equal(bridge.runTasks12To15UI, undefined);
  return row;
}

test('real shared evaluateCase receives UI calls/source hashes and complete canonical fields', async () => {
  const row = await throughSharedEvaluator(raw());
  assert.equal(row.status, 'pass');
  assert.equal(row.productionSources.length, 2);
  assert.ok(row.productionSources.every(source => sources.some(expected => expected.path === source.path && expected.sha256 === source.sha256)));
  assert.ok(row.calls.some(call => call.nativeUI && call.observation.available));
  assert.equal(row.calls.some(call => call.method === 'constructor'), false);
  assert.equal(row.checkpoints.length, 2);
  assert.equal(row.invariantChecks[0].passed, true);
});

test('wrong enabled UI remains fail through unchanged evaluateCase', async () => {
  const row = await throughSharedEvaluator(raw(true));
  assert.equal(row.status, 'fail');
  assert.equal(row.assertionFailures[0].path, 'submitEnabled');
});

test('incomplete native transition exposes collection stage and retains full failure diagnostics', async () => {
  const data = raw();
  data.eventExecuted = false;
  data.frames = [];
  data.failure = { stage: 'fixture_reason_input', message: 'Error: native input failed', code: 17000002,
    stack: 'original native stack', presenterEvidence: { available: true, instanceId: 1 } };
  const row = await throughSharedEvaluator(data);
  assert.equal(row.status, 'not_scored');
  assert.match(row.reason, /fixture_reason_input: Error: native input failed/);
  assert.deepEqual(row.evidence[0].nativePageTransition.failure, data.failure);
});

test('zero receivers, wrong givens, source absence and cross-instance frames remain NS', async () => {
  assert.equal((await throughSharedEvaluator(raw(), sources.slice(0, 1))).status, 'not_scored');
  for (const mutate of [
    data => { data.frames[0].presenterEvidence = { available: false, calls: [] }; },
    data => { data.frames[0].observed.reason = ''; },
    data => { data.frames[1].presenterEvidence.instanceId = 2; },
    data => { data.actions = []; }
  ]) {
    const data = raw(); mutate(data);
    const row = await throughSharedEvaluator(data);
    assert.equal(row.status, 'not_scored');
  }
});

test('other canonical cases are never attached to this UI branch', () => {
  const api = bridgeApi();
  assert.equal(api.attachTasks12To15UI({}, '12_report_room', 'leave_failure_is_partial'), false);
  assert.equal(api.attachTasks12To15UI({}, '14_join_room_by_address', 'entry_opens_address_flow'), false);
});
