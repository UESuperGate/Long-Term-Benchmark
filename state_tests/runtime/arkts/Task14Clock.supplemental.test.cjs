'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { mergeReports, mergeFiles } = require('./Task14Clock.supplemental.cjs');
const { CASE } = require('./Task14Clock.cjs');
const ROOT = path.resolve(__dirname, '../../..');
const PRIMARY = path.join(ROOT, 'experiment_results/runtime_transition_20261019/context-repair/prior-reports/arkts_14_final_before_clock_supplement.json');
const SUPPLEMENT = path.join(ROOT, 'experiment_results/runtime_transition_20261019/task14-clock-review/arkts_14_final_clock.json');
const primary = JSON.parse(fs.readFileSync(PRIMARY));
const supplemental = JSON.parse(fs.readFileSync(SUPPLEMENT));
const clone = value => JSON.parse(JSON.stringify(value));
const target = report => report.semantic.cases.find(row => row.caseId === CASE);
const point = (report, label) => target(report).checkpoints.find(p => p.label === label).state;
const syncEvidence = report => { target(report).evidence = target(report).checkpoints.map(p =>
  ({ label: p.label, data: clone(p.state), observationLevel: 'host_transpiled_production' })); };

test('promotes only original NS002 and preserves every other row, entry FAIL, and compile evidence', async () => {
  const before = JSON.stringify(primary), incoming = JSON.stringify(supplemental);
  const result = await mergeReports(primary, supplemental);
  assert.equal(target(result).status, 'pass');
  assert.equal(target(result).observationLevel, 'host_transpiled_production');
  assert.equal(target(result).clockSupplemental.nativeRuntimeExecuted, false);
  for (const row of primary.semantic.cases.filter(r => r.caseId !== CASE))
    assert.deepEqual(result.semantic.cases.find(r => r.caseId === row.caseId), row);
  assert.equal(result.semantic.cases[0].status, 'fail');
  assert.equal(result.semantic.cases[0].invariantChecks[0].passed, false);
  assert.deepEqual(result.compile, primary.compile);
  assert.deepEqual(result.runtimeCompile, primary.runtimeCompile);
  assert.deepEqual(result.nativeEvidence, primary.nativeEvidence);
  assert.equal(result.semantic.passed, primary.semantic.passed + 1);
  assert.equal(result.semantic.failed, primary.semantic.failed);
  assert.equal(result.semantic.notScored, primary.semantic.notScored - 1);
  assert.equal(result.diagnostics.hostClockSupplemental[0].preservedRows.length, 8);
  assert.equal(result.diagnostics.hostClockSupplemental[0].canonicalCase.given.address, '');
  assert.equal(JSON.stringify(primary), before);
  assert.equal(JSON.stringify(supplemental), incoming);
});

const rejectionCases = [
  ['changed task', (_, s) => { s.taskId = '15_other'; }],
  ['role mismatch', (_, s) => { s.role = 'base'; }],
  ['target mismatch', (_, s) => { s.target = path.join(ROOT, '14_join_room_by_address_base_25_02_0'); }],
  ['primary target mismatch', p => { p.provenance.original = ROOT; }],
  ['primary source override', p => { p.provenance.sourceOverride = true; }],
  ['full contract hash', (_, s) => { s.contractSha256 = '0'.repeat(64); }],
  ['contract artifact hash', (_, s) => { s.provenance.canonicalContract.sha256 = '0'.repeat(64); }],
  ['case002 trace', (_, s) => { target(s).traceDigest = '0'.repeat(64); }],
  ['unselected case trace', (_, s) => { s.semantic.cases[0].traceDigest = '0'.repeat(64); }],
  ['duplicate canonical case', (_, s) => { s.semantic.cases[8] = clone(s.semantic.cases[0]); }],
  ['missing canonical case', (_, s) => { s.semantic.cases.pop(); }],
  ['count mismatch', (_, s) => { s.semantic.passed++; }],
  ['fixture hash', (_, s) => { s.provenance.fixture.sha256 = '0'.repeat(64); }],
  ['fixture identity despite valid unrelated hash', (_, s) => { s.provenance.fixture = clone(s.provenance.loader); }],
  ['loader hash', (_, s) => { s.provenance.loader.sha256 = '0'.repeat(64); }],
  ['source hash', (_, s) => { target(s).productionSources[0].sha256 = '0'.repeat(64); }],
  ['source path', (_, s) => { target(s).productionSources[0].path = '../foreign.ets'; }],
  ['primary source hash', p => { target(p).productionSources[0].sha256 = '0'.repeat(64); }],
  ['clock entry hash', (_, s) => { target(s).clock.dependency.sha256 = '0'.repeat(64); }],
  ['clock package hash', (_, s) => { target(s).clock.dependency.packageSha256 = '0'.repeat(64); }],
  ['clock version', (_, s) => { target(s).clock.dependency.version = '0.0.0'; }],
  ['clock path', (_, s) => { target(s).clock.dependency.path = s.provenance.loader.path; }],
  ['wall-clock time domain', (_, s) => { target(s).clock.timeDomain = 'wall_clock'; }],
  ['global timer patch', (_, s) => { target(s).clock.globalTimersModified = true; }],
  ['native row scope', (_, s) => { target(s).observationLevel = 'native_candidate_ui_and_production_state'; }],
  ['native report scope', (_, s) => { s.runtime = 'arkvm'; }],
  ['native observation scope', (_, s) => { s.observationScope = 'real native UI'; }],
  ['native runtime credit', (_, s) => { s.diagnostics.nativeRuntimeExecuted = true; }],
  ['native production credit', (_, s) => { s.diagnostics.nativeProductionExecuted = true; }],
  ['compile credit', (_, s) => { s.compile.passed = true; }],
  ['native compile attachment', (_, s) => { s.runtimeCompile = { passed: true }; }],
  ['unsupported invariant', (_, s) => { target(s).unsupportedInvariants = [{ description: 'unobserved' }]; }],
  ['missing invariant', (_, s) => { target(s).invariantChecks = []; }],
  ['duplicate invariant', (_, s) => { target(s).invariantChecks.push(clone(target(s).invariantChecks[0])); }],
  ['false invariant passed tag', (_, s) => { target(s).invariantChecks[0].passed = false; }],
  ['missing invariant observations', (_, s) => { delete target(s).invariantChecks[0].observed; }],
  ['noncanonical given', (_, s) => { point(s, 'before:event').state.address = '#old:example.org'; syncEvidence(s); }],
  ['fabricated given tag', (_, s) => { point(s, 'before:event').givenChecks[0].actual = 'different'; syncEvidence(s); }],
  ['given starts resolving', (_, s) => { point(s, 'before:event').state.addressState = 'resolving'; syncEvidence(s); }],
  ['noncanonical edit', (_, s) => { point(s, 'event:update-address').rawInput = '#team:example.org'; syncEvidence(s); }],
  ['t299 request', (_, s) => { point(s, 'boundary:299').state.requestCount = 1; syncEvidence(s); }],
  ['t299 early resolving', (_, s) => { point(s, 'boundary:299').state.addressState = 'resolving'; syncEvidence(s); }],
  ['rounded actual request time', (_, s) => { point(s, 'resolver:requested').calledAt = 302; syncEvidence(s); }],
  ['requested delay instead of actual call', (_, s) => {
    point(s, 'resolver:requested').requestedDelayMs = 300;
    delete point(s, 'resolver:requested').calledAt; syncEvidence(s);
  }],
  ['missing actual request checkpoint', (_, s) => {
    target(s).checkpoints = target(s).checkpoints.filter(p => p.label !== 'resolver:requested'); syncEvidence(s);
  }],
  ['t300 no request', (_, s) => { point(s, 'boundary:300').state.requestCount = 0; syncEvidence(s); }],
  ['wrong requested alias', (_, s) => { point(s, 'resolver:requested').alias = '#foreign:example.org'; syncEvidence(s); }],
  ['stale response preceded canonical event', (_, s) => { point(s, 'invariant:stale-response').virtualTimeMs = 0; syncEvidence(s); }],
  ['stale response writes state', (_, s) => { point(s, 'invariant:stale-response').state.addressState = 'room_found'; syncEvidence(s); }],
  ['missing actual stale completion', (_, s) => { delete target(s).invariantChecks[0].observed.response; }],
  ['missing production event call', (_, s) => { target(s).calls = target(s).calls.filter(c => c.method !== 'updateAddress'); }],
  ['native service access', (_, s) => { target(s).calls[0].unavailableNativeService = true; }],
  ['internally consistent invented call rejected by replay', (_, s) => {
    target(s).calls.push({ module: target(s).productionSources[0].path, class: 'JoinRoomByAddressPresenter', method: 'invented', args: [] });
  }],
  ['another case selected', (_, s) => { s.diagnostics.selectedCaseIds.push(s.semantic.cases[0].caseId); }],
  ['another case carries pretend evidence', (_, s) => { s.semantic.cases[0].calls.push({ method: 'invented' }); }],
  ['incoming already promoted', (_, s) => { s.diagnostics.promotion = 'promoted'; }],
  ['primary previous promotion audit', p => { p.diagnostics.hostClockSupplemental = [{ caseId: CASE }]; }]
];

for (const [name, tamper] of rejectionCases) test('rejects ' + name, async () => {
  const p = clone(primary), s = clone(supplemental);
  tamper(p, s);
  await assert.rejects(mergeReports(p, s));
});

test('rejects repeated promotion and any already-scored target', async () => {
  const promoted = await mergeReports(primary, supplemental);
  await assert.rejects(mergeReports(promoted, supplemental), /already-scored|duplicate promotion/);
});

for (const kind of ['contract', 'candidate', 'source', 'duplicateSource'])
  test('rejects primary bundled ' + kind + ' mismatch', async t => {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'Task14Clock-manifest-'));
    t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
    const p = clone(primary), manifest = JSON.parse(fs.readFileSync(p.nativeEvidence.manifest));
    const matches = item => item.taskId === p.taskId && item.role === p.role;
    if (kind === 'contract') manifest.contracts.find(item => item.taskId === p.taskId).sha256 = '0'.repeat(64);
    if (kind === 'candidate') manifest.candidates.find(matches).original = ROOT;
    if (kind === 'source') manifest.production.find(matches).sha256 = '0'.repeat(64);
    if (kind === 'duplicateSource') manifest.production.push(clone(manifest.production.find(matches)));
    p.nativeEvidence.manifest = path.join(directory, 'manifest.json');
    fs.writeFileSync(p.nativeEvidence.manifest, JSON.stringify(manifest));
    await assert.rejects(mergeReports(p, supplemental));
  });

test('output is independent, never overwrites files, and binds both unchanged input artifacts', async t => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'Task14Clock-merge-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const p = path.join(directory, 'primary.json'), s = path.join(directory, 'supplemental.json'), out = path.join(directory, 'validated.json');
  fs.writeFileSync(p, JSON.stringify(primary)); fs.writeFileSync(s, JSON.stringify(supplemental));
  const pBefore = fs.readFileSync(p), sBefore = fs.readFileSync(s);
  await assert.rejects(mergeFiles(p, s, p), /overwrite/);
  await assert.rejects(mergeFiles(p, s, s), /overwrite/);
  const report = await mergeFiles(p, s, out);
  assert.deepEqual(fs.readFileSync(p), pBefore);
  assert.deepEqual(fs.readFileSync(s), sBefore);
  assert.deepEqual(JSON.parse(fs.readFileSync(out)), report);
  assert.equal(report.diagnostics.hostClockSupplemental[0].primaryReport.path, fs.realpathSync(p));
  assert.equal(report.diagnostics.hostClockSupplemental[0].supplementalReport.path, fs.realpathSync(s));
  await assert.rejects(mergeFiles(p, s, out), /overwrite/);
});
