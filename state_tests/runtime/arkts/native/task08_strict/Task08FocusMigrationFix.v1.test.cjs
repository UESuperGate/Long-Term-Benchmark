'use strict';

// Host-transpiled production domain regression only, not ArkVM/UI calibration.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const childProcess = require('node:child_process');
const os = require('node:os');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const root = path.resolve(__dirname, '../../../../..');
const audit = path.join(root, 'experiment_results/runtime_transition_20261021/task08_arkts_focus_migration_fix_v1_20261021T083933Z');
const relative = 'final_dev_nodes/08_threads_final_25_08_4/entry/src/main/ets/features/ThreadFeature.ets';
const pageRelative = 'final_dev_nodes/08_threads_final_25_08_4/entry/src/main/ets/pages/Index.ets';
const current = fs.readFileSync(path.join(root, relative), 'utf8');
const before = fs.readFileSync(path.join(audit, 'before', relative), 'utf8');
const contract = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks/08_threads/transitions.json')));
const spec = contract.cases.find(c => c.key === 'focus_failure_preserves_thread');

function production(source) {
  const output = ts.transpileModule(source, { fileName: 'ThreadFeature.ts', reportDiagnostics: true,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, strict: true } });
  assert.equal((output.diagnostics || []).filter(d => d.category === ts.DiagnosticCategory.Error).length, 0);
  const module = { exports: {} };
  new vm.Script(`(function(exports,module){${output.outputText}\n})`).runInNewContext({})(module.exports, module);
  const { ThreadPresenter, ThreadGateway } = module.exports;
  return new ThreadPresenter(new ThreadGateway());
}

const plain = value => JSON.parse(JSON.stringify(value));
function run(source) {
  const p = production(source);
  p.openThread(spec.given.threadRootId);
  assert.equal(p.focusEvent(spec.given.focusedEventId), true);
  assert.equal(p.focusedEventId, '$reply');
  p.setComposerText('draft'); p.setReplyTarget('$reply');
  const baseline = plain({ surface: p.surface, root: p.threadRootId, events: p.threadEvents,
    main: p.mainRoomEvents, text: p.composerText, target: p.replyTargetId, send: p.sendState,
    attempts: p.gateway.attempts, effect: p.gateway.lastEffect });
  const timeline = p.threadEvents, main = p.mainRoomEvents, gateway = p.gateway;
  assert.equal(p.focusEvent(spec.event.eventId), false);
  assert.equal(p.focusState, spec.expected.focusState);
  assert.equal(p.surface, baseline.surface);
  assert.equal(p.threadRootId, baseline.root);
  assert.equal(p.threadEvents, timeline); assert.equal(p.mainRoomEvents, main); assert.equal(p.gateway, gateway);
  assert.deepEqual(plain(p.threadEvents), spec.expected.visibleEvents);
  assert.deepEqual(plain({ surface: p.surface, root: p.threadRootId, events: p.threadEvents,
    main: p.mainRoomEvents, text: p.composerText, target: p.replyTargetId, send: p.sendState,
    attempts: p.gateway.attempts, effect: p.gateway.lastEffect }), baseline);
  return p;
}

test('actual repaired presenter clears prior successful focus on missing event only', () => {
  assert.equal(run(current).focusedEventId, spec.expected.focusedEventId);
});

test('retained original production is a negative control, not silently repaired in test', () => {
  const p = run(before);
  assert.equal(p.focusedEventId, '$reply');
  assert.notEqual(p.focusedEventId, spec.expected.focusedEventId);
});

test('real success after failure restores the requested focus and success state', () => {
  const p = run(current);
  assert.equal(p.focusEvent('$root'), true);
  assert.equal(p.focusedEventId, '$root'); assert.equal(p.focusState, 'success');
  assert.equal(p.focusEvent('$reply'), true);
  assert.equal(p.focusedEventId, '$reply');
});

test('failure with no prior focus and repeated failure remain null without discarding context', () => {
  const p = production(current);
  p.openThread('$root');
  for (let n = 0; n < 2; n++) {
    assert.equal(p.focusEvent('$missing'), false);
    assert.equal(p.focusedEventId, null); assert.equal(p.focusState, 'failure');
    assert.equal(p.threadRootId, '$root'); assert.deepEqual(plain(p.threadEvents), ['$root', '$reply']);
  }
});

test('complete-source rollback and destructive-recovery mutants are detected', () => {
  const stale = current.replace('      this.focusedEventId = null;\n', '');
  assert.notEqual(run(stale).focusedEventId, null);
  const destructive = current.replace('      this.focusedEventId = null;', '      this.focusedEventId = null;\n      this.threadEvents = [];');
  assert.throws(() => run(destructive));
});

test('existing page focus label expression safely receives null without claiming UI execution', () => {
  const page = fs.readFileSync(path.join(root, pageRelative), 'utf8');
  const expression = page.match(/Text\(`Focus: \$\{([^}]+)\}`\)/)[1];
  const evaluate = new vm.Script(`(function(){return (${expression});})`).runInNewContext({});
  const p = run(current);
  assert.equal(evaluate.call(p), 'failure');
  assert.equal(evaluate.call({ focusedEventId: '$reply', focusState: 'success' }), '$reply');
  assert.equal(evaluate.call({ focusedEventId: '', focusState: 'idle' }), 'idle');
});

test('private approved-null invariant binding rejects stale production and the old incompatible equality', async () => {
  const adapterFile = path.join(root, 'state_tests/runtime/arkts/tasks08_11.cjs');
  const original = fs.readFileSync(adapterFile, 'utf8');
  const oldCheck = 'equal(before.visibleEvents, after.visibleEvents) && before.focusedEventId === after.focusedEventId';
  const newCheck = "equal(before.visibleEvents, after.visibleEvents) && before.threadRootId === after.threadRootId && mainUnchanged && after.focusState === 'failure' && after.focusedEventId === null";
  assert.equal(original.split(oldCheck).length, 2);
  const revised = original.replace(oldCheck, newCheck);
  async function evaluate(adapterSource, productionSource) {
    const module = { exports: {} };
    new vm.Script(`(function(exports,require,module){${adapterSource}\n})`).runInThisContext()(module.exports, require, module);
    const p = production(productionSource);
    return module.exports.runCase({ taskId: '08_threads', caseSpec: spec,
      project: path.join(root, 'final_dev_nodes/08_threads_final_25_08_4'),
      load: async () => ({ ThreadPresenter: p.constructor, ThreadGateway: p.gateway.constructor }) });
  }
  const fixed = await evaluate(revised, current);
  assert.equal(fixed.unsupported, undefined);
  assert.equal(fixed.observed.focusedEventId, null);
  assert.equal(fixed.invariantChecks[0].description, spec.invariants[0]);
  assert.equal(fixed.invariantChecks[0].passed, true);
  assert.equal((await evaluate(original, current)).invariantChecks[0].passed, false);
  const stale = await evaluate(revised, before);
  assert.equal(stale.observed.focusedEventId, '$reply');
  assert.equal(stale.invariantChecks[0].passed, false);
});

test('new migration patch reconstructs both exact after files from retained before', () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'task08-fix-patch-unit-'));
  try {
    for (const name of [relative, pageRelative]) {
      const destination = path.join(temporary, name);
      fs.mkdirSync(path.dirname(destination), { recursive: true });
      fs.copyFileSync(path.join(audit, 'before', name), destination);
    }
    const patch = path.join(audit, 'migration-fix.patch');
    const result = childProcess.spawnSync('git', ['apply', patch], { cwd: temporary, encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    for (const name of [relative, pageRelative]) {
      assert.deepEqual(fs.readFileSync(path.join(temporary, name)), fs.readFileSync(path.join(audit, 'after', name)));
      assert.deepEqual(fs.readFileSync(path.join(root, name)), fs.readFileSync(path.join(audit, 'after', name)));
    }
  } finally { fs.rmSync(temporary, { recursive: true, force: true }); }
});
