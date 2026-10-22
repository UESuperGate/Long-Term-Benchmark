'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { productionLoader } = require('../../../scripts/runtime_semantics/arkts_runtime.cjs');
const { createScheduler, evaluateClockCase, runReport, CASE } = require('./Task14Clock.cjs');
const { runMutations, FEATURE } = require('./Task14Clock.mutations.cjs');
const ROOT = path.resolve(__dirname, '../../..');
const json = file => JSON.parse(fs.readFileSync(path.join(ROOT, file)));
const task = json('benchmark_tasks/14_join_room_by_address/task.json');
const project = path.join(ROOT, task.arkts.finalPath);
const spec = () => json('benchmark_tasks/14_join_room_by_address/transitions.json').cases.find(item => item.caseId === CASE);
const point = (row, label) => row.checkpoints.find(item => item.label === label).state;

function scored(row, status) {
  assert.equal(row.status, status, row.reason || JSON.stringify(row.assertionFailures));
  assert.deepEqual(row.missingObservations, []);
  assert.deepEqual(row.missingInvariants, []);
  assert.ok(row.productionSources.length > 0);
  assert.ok(row.calls.some(call => call.method === 'updateAddress'));
  assert.equal(row.clock.nativeRuntimeExecuted, false);
  assert.equal(row.observationLevel, 'host_transpiled_production');
}

test('unchanged final establishes given and executes exact virtual 299/300 boundary then stale response', async () => {
  const row = await evaluateClockCase(project, spec());
  scored(row, 'pass');
  assert.deepEqual(row.observed, { address: '#team:example.org', addressStateBefore300ms: 'unknown', resolveAfterMs: 300 });
  const initial = point(row, 'before:event');
  assert.equal(initial.virtualTimeMs, 0);
  assert.equal(initial.state.address, '');
  assert.equal(initial.state.addressState, 'unknown');
  assert.equal(initial.state.requestCount, 0);
  assert.ok(initial.givenChecks.every(check => check.established));
  assert.equal(point(row, 'boundary:299').virtualTimeMs, 299);
  assert.equal(point(row, 'boundary:299').state.requestCount, 0);
  assert.equal(point(row, 'boundary:300').virtualTimeMs, 300);
  assert.equal(point(row, 'boundary:300').state.requestCount, 1);
  assert.equal(point(row, 'resolver:requested').calledAt, 300);
  assert.equal(point(row, 'invariant:second-edit').state.address, '#other:example.org');
  assert.equal(point(row, 'invariant:stale-response').state.addressState, 'unknown');
  assert.ok(row.checkpoints.findIndex(p => p.label === 'after:event') < row.checkpoints.findIndex(p => p.label === 'invariant:second-edit'));
  assert.deepEqual(row.invariantChecks.map(check => check.description), spec().invariants);
  assert.ok(row.invariantChecks.every(check => check.passed));
  assert.ok(row.boundaryChecks.every(check => check.passed));
});

test('changing expected does not drive delay, state, or resolver observations', async () => {
  const poisoned = spec();
  poisoned.expected = { address: 'invented', addressStateBefore300ms: 'resolving', resolveAfterMs: 100 };
  const row = await evaluateClockCase(project, poisoned);
  scored(row, 'fail');
  assert.deepEqual(row.observed, { address: '#team:example.org', addressStateBefore300ms: 'unknown', resolveAfterMs: 300 });
  assert.deepEqual(row.assertionFailures.map(item => item.path), Object.keys(poisoned.expected));
});

test('unestablished canonical given does not execute event or become semantic failure', async () => {
  const changed = spec();
  changed.given.address = '#different:example.org';
  const row = await evaluateClockCase(project, changed);
  assert.equal(row.status, 'not_scored');
  assert.match(row.reason, /given not established/);
  assert.ok(!row.calls.some(call => call.method === 'updateAddress'));
});

test('five generated production mutants fail from executed evidence', async () => {
  const report = await runMutations(project, spec());
  assert.equal(report.original.unchanged, true);
  assert.equal(report.temporaryCandidatesRemoved, true);
  assert.equal(report.detected, 5);
  for (const { result } of report.mutations) scored(result, 'fail');
  const row = id => report.mutations.find(item => item.mutation === id).result;
  assert.equal(row('wrong100').observed.resolveAfterMs, 100);
  assert.equal(row('wrong100').observed.addressStateBefore300ms, 'resolving');
  for (const id of ['wrong600', 'two300serial']) {
    assert.equal(row(id).observed.resolveAfterMs, 600);
    assert.equal(point(row(id), 'boundary:300').state.requestCount, 0);
  }
  assert.equal(row('stateResolvingearly').observed.addressStateBefore300ms, 'resolving');
  assert.equal(row('stateResolvingearly').observed.resolveAfterMs, 300);
  assert.deepEqual(row('staleresponse').observed, spec().expected);
  assert.equal(row('staleresponse').invariantChecks[0].passed, false);
  assert.equal(row('staleresponse').invariantChecks[0].observed.afterStale.addressState, 'room_found');
});

test('scheduler does not patch process globals and clocks are independent', async () => {
  const globalTimeout = globalThis.setTimeout, globalDate = globalThis.Date;
  const a = createScheduler(), b = createScheduler();
  let fired = 0;
  a.timerEnvironment.setTimeout(() => fired++, 300);
  await b.clock.tickAsync(300);
  assert.equal(fired, 0);
  assert.equal(a.clock.now, 0);
  await a.clock.tickAsync(300);
  assert.equal(fired, 1);
  assert.equal(globalThis.setTimeout, globalTimeout);
  assert.equal(globalThis.Date, globalDate);
  a.clock.reset(); b.clock.reset();
});

test('loader default uses real timers and optional environment rejects unrelated capabilities', async () => {
  assert.throws(() => productionLoader(project, [], [], { Promise }), /Unsupported production timer environment member/);
  const { JoinRoomByAddressPresenter, JoinRoomNavigator } = productionLoader(project, [], [])(FEATURE);
  let requests = 0;
  const presenter = new JoinRoomByAddressPresenter({ resolveRoomAlias: () => { requests++; } }, new JoinRoomNavigator());
  const pending = presenter.updateAddress('invalid');
  assert.equal(presenter.addressState, 'unknown');
  await pending;
  assert.equal(presenter.addressState, 'invalid');
  assert.equal(requests, 0);
});

test('missing base entry remains unscored without fabricated observations', async () => {
  const row = await evaluateClockCase(path.join(ROOT, task.arkts.basePath), spec());
  assert.equal(row.status, 'not_scored');
  assert.match(row.reason, /cannot be bound/);
  assert.deepEqual(row.observed, {});
});

test('unavailable scheduler dependency remains unscored with all expectations missing', async () => {
  const previous = process.env.LTB_FAKE_TIMERS;
  try {
    process.env.LTB_FAKE_TIMERS = '/nonexistent/Task14Clock/fake-timers';
    const row = await evaluateClockCase(project, spec());
    assert.equal(row.status, 'not_scored');
    assert.equal(row.observationLevel, 'not_executed');
    assert.deepEqual(row.missingObservations, Object.keys(spec().expected));
    assert.deepEqual(row.missingInvariants, spec().invariants);
    assert.equal(row.calls.length, 0);
  } finally {
    if (previous === undefined) delete process.env.LTB_FAKE_TIMERS;
    else process.env.LTB_FAKE_TIMERS = previous;
  }
});

test('native bundle shared functions remain extractable without scheduler dependencies', () => {
  const ts = require(process.env.LTB_TYPESCRIPT || '/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
  const file = path.join(ROOT, 'scripts/runtime_semantics/arkts_runtime.cjs');
  const ast = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
  for (const name of ['snapshot', 'compareExpected', 'evaluateCase']) {
    const declaration = ast.statements.find(item => ts.isFunctionDeclaration(item) && item.name?.text === name);
    assert.ok(declaration);
    assert.doesNotMatch(declaration.getText(ast), /timerEnvironment|fake-timers|Task14Clock/);
  }
});

test('same fixture executes original archived agent API and retains early-resolving mismatch', async t => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'Task14Clock-agent-'));
  t.after(() => fs.rmSync(temporary, { recursive: true, force: true }));
  const features = 'entry/src/main/ets/features';
  fs.mkdirSync(path.dirname(path.join(temporary, features)), { recursive: true });
  fs.cpSync(path.join(ROOT, task.arkts.basePath, features), path.join(temporary, features), { recursive: true });
  const patch = path.join(ROOT, 'experiment_results/new_tasks_opencode_minimax_m3_20261015_semantic_repair/provenance/patches/arkts_14_join_room_by_address.patch');
  execFileSync('git', ['apply', '--include=entry/src/main/ets/features/*', patch], { cwd: temporary, stdio: 'pipe' });
  const row = await evaluateClockCase(temporary, spec());
  scored(row, 'fail');
  assert.equal(row.observed.resolveAfterMs, 300);
  assert.equal(row.observed.addressStateBefore300ms, 'resolving');
  assert.ok(row.invariantChecks.every(check => check.passed));
});

test('independent report retains every canonical ID/digest and never promotes unexecuted cases', async () => {
  const report = await runReport(project, 'final');
  const canonical = json('benchmark_tasks/14_join_room_by_address/transitions.json');
  assert.deepEqual(report.semantic.cases.map(row => [row.caseId, row.traceDigest]), canonical.cases.map(row => [row.caseId, row.traceDigest]));
  assert.equal(report.semantic.passed, 1);
  assert.equal(report.semantic.failed, 0);
  assert.equal(report.semantic.notScored, 8);
  assert.equal(report.diagnostics.promotion, 'not_promoted');
  assert.ok(report.semantic.cases.filter(row => row.caseId !== CASE).every(row => row.status === 'not_scored' && row.calls.length === 0));
});
