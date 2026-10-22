'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const { install } = require('./Task08StrictNativeUi.install.cjs');

function compile(file) {
  const module = { exports: {} };
  const output = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
  }).outputText;
  new vm.Script(`(function(exports,require,module){${output}\n})`).runInNewContext({})(
    module.exports, require, module);
  return module.exports;
}

const adapter = compile(path.join(__dirname, 'Task08StrictNativeUiAdapter.js'));
const nativeUiSource = fs.readFileSync(path.join(__dirname, 'Task08StrictNativeUi.js'), 'utf8');
const spec = {
  taskId: '08_threads', caseId: 'thread_state_001_open', key: 'open_thread',
  traceDigest: 'a'.repeat(64), invariants: ['thread route opens']
};

function raw(variant = 'final') {
  return {
    taskId: spec.taskId, caseId: spec.caseId, key: spec.key, traceDigest: spec.traceDigest,
    role: variant, productionVariant: variant, entryExecuted: true, eventExecuted: true,
    frames: [{ label: 'before_event' }, { label: 'after_event' }], actions: [{ executed: true }],
    basePositiveControl: variant === 'base' ? {
      roomRendered: true, roomSendCompleted: true, requestedAction: 'open_thread', routeAvailable: false
    } : undefined,
    finalPositiveControl: variant === 'base' ? undefined : {
      threadOpened: true, rootVisible: true, replyVisible: true
    },
    uiAssertions: variant === 'base' ? undefined : { threadSurface: true, rootVisible: true, replyVisible: true }
  };
}

async function execute(receipt) {
  let calls = 0;
  const domain = { observed: { route: 'thread' }, invariantChecks: [{ description: spec.invariants[0], passed: true }] };
  const result = await adapter.runTask08StrictCase({ caseSpec: spec,
    native: { runTask08StrictUI: async () => receipt },
    sharedRunCase: async () => { calls += 1; return domain; } });
  return { result, calls, domain };
}

test('complete UI receipt delegates exactly once to the shared evaluator', async () => {
  const receipt = raw();
  const { result, calls, domain } = await execute(receipt);
  assert.equal(calls, 1);
  assert.equal(result, domain);
  assert.equal(result.evidence[0], receipt);
  assert.equal(result.observationLevel, 'openharmony_api23_original_application_ui_and_shared_production_domain');
  assert.equal(result.invariantChecks[0].passed, true);
});

test('native probe reuses one verified candidate window for all control inspections', () => {
  assert.match(nativeUiSource, /verifiedWindow = await launch\.check\(driver\)/);
  assert.match(nativeUiSource, /const bounds = await node\.getBounds\(\), viewport = verifiedWindow\.bounds/);
  const inspectBody = nativeUiSource.slice(nativeUiSource.indexOf('async function inspect(name)'),
    nativeUiSource.indexOf('async function capture(label)'));
  assert.doesNotMatch(inspectBody, /launch\.check/);
  assert.match(nativeUiSource, /await launch\.dispose\(\)[\s\S]*result\.launchEvidence = launch\.read\(\)/);
});

test('native probe conditionally dismisses the real input method and resolves repeated reply rows precisely', () => {
  assert.match(nativeUiSource, /const stableText = \{ threadRoot: '\$root', threadReply: '\$reply' \}/);
  assert.match(nativeUiSource, /await node\.getText\(\) === stableText\[name\]/);
  assert.match(nativeUiSource, /if \(\(!node \|\| !control\.visible \|\| !control\.enabled\) && inputPending\)/);
  assert.match(nativeUiSource, /await node\.inputText\(value\); inputPending = true/);
  assert.match(nativeUiSource, /await driver\.pressBack\(\)[\s\S]*for \(let attempt = 0; attempt < 20; attempt\+\+\)/);
  assert.match(nativeUiSource, /kind: 'key', target: 'inputMethod', value: 'Back'/);
  assert.match(nativeUiSource, /bounds\.top === replyBounds\.top && bounds\.bottom === replyBounds\.bottom/);
});

test('approved focus-failure predicate requires canonical null and preserves other conditions', () => {
  // Predicate unit only, not a native runtime receipt.
  const start = nativeUiSource.indexOf("} else if (spec.key === 'focus_failure_preserves_thread')");
  const end = nativeUiSource.indexOf("} else if (spec.key === 'send_thread_message')", start);
  const expression = nativeUiSource.slice(start, end).match(/failedFocusPreserved: ([\s\S]*?) };/)[1];
  const predicate = new vm.Script(expression);
  const state = { focusState: 'failure', focusedEventId: null, threadRootId: '$root', threadEvents: ['$root', '$reply'] };
  const evaluate = change => predicate.runInNewContext({ state: { ...state, ...change }, spec: { expected: { focusedEventId: null } } });
  assert.equal(evaluate({}), true);
  for (const change of [{ focusedEventId: '$reply' }, { focusedEventId: undefined },
    { focusState: 'success' }, { threadRootId: '$other' }, { threadEvents: ['$root'] }]) {
    assert.equal(evaluate(change), false);
  }
});

for (const [name, mutate, pattern] of [
  ['missing event receipt', value => { value.eventExecuted = false; }, /replay incomplete/],
  ['runtime failure', value => { value.failure = { message: 'original page failed' }; }, /original page failed/],
  ['incomplete final controls', value => { value.uiAssertions.replyVisible = false; }, /UI assertions are incomplete/]
]) {
  test('incomplete final runtime evidence remains unscored: ' + name, async () => {
    const receipt = raw();
    mutate(receipt);
    const { result, calls } = await execute(receipt);
    assert.equal(calls, 0);
    assert.match(result.unsupported, pattern);
    assert.equal(result.invariantChecks.length, 0);
  });
}

test('mutated base room positive control remains unscored instead of becoming semantic fail', async () => {
  const receipt = raw('base');
  receipt.basePositiveControl.roomSendCompleted = false;
  const { result, calls } = await execute(receipt);
  assert.equal(calls, 0);
  assert.match(result.unsupported, /positive control is incomplete/);
  assert.equal(result.invariantChecks.length, 0);
});

test('base common-entry proof leaves unreachable post-state and invariants unknown without domain projection', async () => {
  const receipt = raw('base');
  receipt.eventExecuted = false; receipt.prefixExecuted = true;
  receipt.entryFailure = { classification: 'required_feature_entry_missing' };
  const { result, calls } = await execute(receipt);
  assert.equal(calls, 0);
  assert.equal(JSON.stringify(result.observed), '{}');
  assert.equal(result.invariantChecks.length, 0);
  assert.equal(result.evidence[0].eventExecuted, false);
  assert.equal(result.unsupported, undefined);
});

test('legacy base projection is withdrawn instead of delegating to fabricated later states', async () => {
  const { result, calls } = await execute(raw('base'));
  assert.equal(calls, 0);
  assert.match(result.unsupported, /projected post-state is withdrawn/);
  assert.equal(result.invariantChecks.length, 0);
});

test('native timeline keeps actual SDK relation absence and never invokes a separate domain copy', async () => {
  const receipt = raw('timeline');
  receipt.bundleName = 'actual.candidate';
  receipt.verifiedWindow = { hostVerified: true, bundleName: receipt.bundleName };
  receipt.launchEvidence = { created: true, destroyed: true };
  receipt.productionSources = [{ path: 'entry/src/main/ets/pages/Index.ets', sha256: 'a'.repeat(64) }];
  receipt.observed = { threadRootId: null };
  receipt.invariantChecks = [{ description: spec.invariants[0], passed: false }];
  const { result, calls } = await execute(receipt);
  assert.equal(calls, 0);
  assert.equal(result.observed.threadRootId, null);
  assert.equal(result.invariantChecks[0].passed, false);
  receipt.launchEvidence.destroyed = false;
  assert.match((await execute(receipt)).result.unsupported, /receipt incomplete/);
});

function fixture(variant) {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'task08-strict-install-'));
  const write = (relative, value) => {
    const file = path.join(work, relative);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, value);
  };
  write('AppScope/app.json5', JSON.stringify({ app: { bundleName: `com.elementx.task08.${variant}` } }));
  write('entry/src/main/module.json5', JSON.stringify({ module: { name: 'entry' } }));
  write('entry/src/main/ets/pages/Index.ets', '@Entry\n@Component\nstruct Index { build() { Text(\'Task08\') } }\n');
  const feature = variant === 'base' ? 'RoomTimelineFeature' : 'ThreadFeature';
  write(`entry/src/main/ets/features/${feature}.ets`, 'export class BoundTask08Feature {}\n');
  write('entry/src/test/native-bundle.js',
    "calls.push({ module: 'ArkUI', method: observation.method, nativeUI: true, observation: snapshot(observation) });\n" +
    "const factoryResult = adapterFactories[group](module.exports, hostShim, module);\n" +
    "if (candidateUI) await bridge.ui.navigate(candidateUI.route);\n" +
    "const adapter = { runCase: context => module.exports.runCase({ ...context, native: bridge, context: {} }) };\n" +
    "try { await bridge.dispose(); } catch (error) {}\n");
  write('entry/src/test/NativeBundle.test.ets', 'export default function nativeBundleTests(): void {}\n');
  return work;
}

function digest(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

for (const variant of ['base', 'final']) {
  test(`installer binds ${variant} production without modifying entry/src/main`, () => {
    const work = fixture(variant);
    try {
      const page = path.join(work, 'entry/src/main/ets/pages/Index.ets');
      const before = digest(page);
      const previous = process.env.LTB_TASK08_ROLE;
      process.env.LTB_TASK08_ROLE = variant;
      let result;
      try { result = install(work); }
      finally {
        if (previous === undefined) delete process.env.LTB_TASK08_ROLE;
        else process.env.LTB_TASK08_ROLE = previous;
      }
      assert.equal(result.role, variant);
      assert.equal(result.productionVariant, variant);
      assert.equal(result.productionUnchanged, true);
      assert.equal(digest(page), before);
      assert.equal(result.sources.length, 2);
      assert.equal(result.fixtures.length, 10);
      assert.ok(result.fixtures.some(item => item.installedPath.endsWith('/Task08TimelineUI.js')));
      const bundle = fs.readFileSync(result.bundleFile, 'utf8');
      const suite = fs.readFileSync(result.suiteFile, 'utf8');
      assert.match(bundle, /task08SharedRunCase/);
      assert.match(bundle, /runTask08StrictCase/);
      assert.match(bundle, /disposeTask08StrictUI/);
      assert.match(suite, /configureTask08StrictBinding/);
      assert.ok(suite.includes(`\\"productionVariant\\":\\"${variant}\\"`));
      assert.doesNotMatch(suite, /from ['"].*entry\/src\/main/);
    } finally { fs.rmSync(work, { recursive: true, force: true }); }
  });
}

test('agent role is bound to the candidate variant and never to a fixed base/final path', () => {
  const work = fixture('final');
  const previous = process.env.LTB_TASK08_ROLE;
  process.env.LTB_TASK08_ROLE = 'agent';
  try {
    const result = install(work);
    assert.equal(result.role, 'agent');
    assert.equal(result.productionVariant, 'final');
    assert.match(result.config.productionModuleUrl, /^@bundle:com\.elementx\.task08\.final\/entry\//);
    assert.equal(JSON.stringify(result).includes('final_dev_nodes/08_threads'), false);
  } finally {
    if (previous === undefined) delete process.env.LTB_TASK08_ROLE;
    else process.env.LTB_TASK08_ROLE = previous;
    fs.rmSync(work, { recursive: true, force: true });
  }
});

test('agent importing an alternate production implementation cannot receive base failures from a partial binding', () => {
  const work = fixture('base');
  const previous = process.env.LTB_TASK08_ROLE;
  process.env.LTB_TASK08_ROLE = 'agent';
  try {
    const page = path.join(work, 'entry/src/main/ets/pages/Index.ets');
    fs.writeFileSync(page, "import { AlternatePresenter } from '../features/AlternateImplementation';\n" + fs.readFileSync(page, 'utf8'));
    const before = digest(page);
    assert.throws(() => install(work), /adapter_binding_incomplete.*AlternateImplementation/);
    assert.equal(digest(page), before);
  } finally {
    if (previous === undefined) delete process.env.LTB_TASK08_ROLE;
    else process.env.LTB_TASK08_ROLE = previous;
    fs.rmSync(work, { recursive: true, force: true });
  }
});

test('timeline API resolves original module imports rather than gold feature filenames', () => {
  const work = fixture('base'), previous = process.env.LTB_TASK08_ROLE;
  process.env.LTB_TASK08_ROLE = 'agent';
  try {
    const page = path.join(work, 'entry/src/main/ets/pages/Index.ets');
    fs.writeFileSync(page, "import { ThreadTimelinePresenter } from '../features/CustomThread';\n" +
      "import { RoomTimelinePresenter } from '../features/RoomTimelineFeature';\n@Entry struct Index {}\n");
    fs.writeFileSync(path.join(work, 'entry/src/main/ets/features/CustomThread.ets'), 'export class ThreadTimelinePresenter {}');
    const before = digest(page), result = install(work);
    assert.equal(result.role, 'agent'); assert.equal(result.productionVariant, 'timeline');
    assert.match(result.config.timelineModuleUrl, /ets\/features\/CustomThread$/);
    assert.equal(result.sources.length, 3); assert.equal(digest(page), before);
  } finally {
    if (previous === undefined) delete process.env.LTB_TASK08_ROLE; else process.env.LTB_TASK08_ROLE = previous;
    fs.rmSync(work, { recursive: true, force: true });
  }
});
