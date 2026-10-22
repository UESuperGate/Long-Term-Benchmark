'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const { compareExpected } = require('../../../scripts/runtime_semantics/arkts_runtime.cjs');
const { CASE, createScheduler, evaluateClockCase } = require('./Task14Clock.cjs');
const ROOT = path.resolve(__dirname, '../../..');
const TASK = '14_join_room_by_address';
const SCOPE = 'host_transpiled_production';
const CONTRACT = path.join(ROOT, 'benchmark_tasks', TASK, 'transitions.json');
const TASK_FILE = path.join(ROOT, 'benchmark_tasks', TASK, 'task.json');
const copy = value => JSON.parse(JSON.stringify(value));
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const objectHash = value => hash(JSON.stringify(value));
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const requireThat = (condition, message) => { if (!condition) throw new Error(message); };
const equal = (actual, expected, message) => assert.deepStrictEqual(actual, expected, message);

function record(file) {
  const real = fs.realpathSync(file), bytes = fs.readFileSync(real);
  return { path: real, sha256: hash(bytes), bytes: bytes.length };
}

function verify(item, expectedPath) {
  requireThat(item && typeof item.path === 'string', 'Missing artifact path');
  const actual = record(item.path);
  equal(actual.path, fs.realpathSync(expectedPath), 'Unexpected artifact identity');
  if (item.sha256 !== actual.sha256 && expectedPath === path.join(__dirname, 'Task14Clock.cjs') &&
      item.sha256 === '6f05499ef63ad469bb340df29e1b63b0e11cff593bbeb7e7ca71f4279b653e0a') {
    const archived = record(path.join(ROOT,
      'experiment_results/runtime_transition_20261020/postrun_task14_15_evaluator_repair_v1/before/state_tests/runtime/arkts/Task14Clock.cjs'));
    equal(archived.sha256, item.sha256, 'Historical fixture archive changed');
    if (item.bytes !== undefined) equal(item.bytes, archived.bytes, 'Historical fixture length changed');
    return { ...archived, originalPath: actual.path };
  }
  equal(item.sha256, actual.sha256, 'Artifact hash mismatch: ' + actual.path);
  if (item.bytes !== undefined) equal(item.bytes, actual.bytes, 'Artifact length mismatch');
  return actual;
}

function counts(rows) {
  return { total: rows.length, passed: rows.filter(r => r.status === 'pass').length,
    failed: rows.filter(r => r.status === 'fail').length, notScored: rows.filter(r => r.status === 'not_scored').length };
}

function validateReport(report, contract) {
  equal([report.schemaVersion, report.taskId, report.platform, report.observationMode],
    [2, TASK, 'arkts', 'runtime_state_transition'], 'Report identity/scope mismatch');
  const rows = report.semantic.cases;
  equal(rows.map(r => [r.caseId, r.traceDigest]), contract.cases.map(c => [c.caseId, c.traceDigest]),
    'Complete canonical case IDs/order/trace digests required');
  for (const [key, value] of Object.entries(counts(rows))) equal(report.semantic[key], value, 'Invalid semantic count: ' + key);
  for (const [i, row] of rows.entries()) {
    requireThat(['pass', 'fail', 'not_scored'].includes(row.status), 'Invalid row status');
    if (row.status === 'not_scored') continue;
    const spec = contract.cases[i];
    equal(row.invariantChecks.map(c => c.description), spec.invariants, 'Incomplete/duplicate canonical invariants');
    requireThat(row.invariantChecks.every(c => typeof c.passed === 'boolean' && Object.hasOwn(c, 'observed')),
      'Invariant lacks actual observations');
    const comparison = compareExpected(spec.expected, row.observed);
    equal(comparison.missing, [], 'Missing canonical observations');
    const failed = comparison.failures.length > 0 || row.invariantChecks.some(c => !c.passed);
    equal(row.status, failed ? 'fail' : 'pass', 'Status contradicts exact canonical comparison');
  }
}

function validateExecution(row, spec) {
  equal(row.status, 'pass', 'Only complete passing case002 clock evidence is eligible for this narrow merger');
  equal(row.observationLevel, SCOPE, 'Wrong observation scope');
  requireThat(!row.nativeBridge && !row.deviceEvidence && !row.runtimeCompile, 'Host row claims native evidence');
  requireThat(!row.reason && !row.unsupported, 'Incoming row has unsupported execution');
  for (const field of ['missingObservations', 'missingInvariants', 'unsupportedInvariants', 'assertionFailures'])
    equal(row[field], [], 'Incomplete evidence: ' + field);
  const labels = ['before:event', 'event:update-address', 'boundary:299', 'resolver:requested', 'boundary:300',
    'after:event', 'invariant:second-edit', 'invariant:stale-response', 'fixture:cleanup'];
  equal(row.checkpoints.map(p => p.label), labels, 'Missing/duplicate/out-of-order runtime checkpoints');
  equal(row.evidence, row.checkpoints.map(p => ({ label: p.label, data: p.state, observationLevel: SCOPE })),
    'Checkpoint and evidence disagree');
  const [before, event, at299, request, at300, after, edited, stale, cleanup] = row.checkpoints.map(p => p.state);
  equal(before.virtualTimeMs, 0, 'Initial virtual clock is not zero');
  equal(before.givenChecks, Object.entries(spec.given).map(([key, value]) =>
    ({ key, given: value, actual: before.state[key], established: true })), 'Canonical given proof differs');
  for (const [key, value] of Object.entries(spec.given)) equal(before.state[key], value, 'Canonical given not established: ' + key);
  equal(before.state.requestCount, 0, 'Request preceded canonical event');
  equal([event.virtualTimeMs, event.rawInput], [0, spec.event.value], 'Canonical event/input differs');
  equal([at299.virtualTimeMs, at299.state.requestCount, at299.state.addressState], [299, 0, 'unknown'], 'Invalid t299 boundary');
  const alias = spec.event.value.trim();
  equal([request.virtualTimeMs, request.calledAt, request.alias, request.requestIndex], [300, 300, alias, 0],
    'Missing actual t300 resolver timestamp');
  equal([at300.virtualTimeMs, at300.state.requestCount, at300.state.address], [300, 1, alias], 'Invalid t300 boundary');
  equal(row.observed, { address: event.state.address, addressStateBefore300ms: at299.state.addressState,
    resolveAfterMs: request.calledAt - before.virtualTimeMs }, 'Observed values not derived from actual checkpoints');
  equal(after.observed, row.observed, 'After-event observations differ');
  equal(after.virtualTimeMs, 300, 'Canonical observations were delayed');
  equal(row.boundaryChecks, [
    { description: 'No alias-resolution request by virtual t=299', passed: true, observed: { time: 299, requests: [] } },
    { description: 'Exactly one target alias request at virtual t=300', passed: true,
      observed: { time: 300, requests: [{ alias, calledAt: request.calledAt }] } }
  ], 'Boundary checks are not backed by actual requests');
  equal(after.boundaryChecks, row.boundaryChecks, 'Boundary records disagree');
  equal(row.invariantChecks.map(c => c.description), spec.invariants, 'Incomplete canonical invariants');
  equal(stale.invariantChecks, row.invariantChecks, 'Stale response invariant records disagree');
  equal([edited.virtualTimeMs, stale.virtualTimeMs], [300, 300], 'Stale response probe not after canonical boundary');
  const check = row.invariantChecks[0];
  equal(check.passed, true, 'Stale response invariant failed');
  equal(check.observed.afterEdit, edited.state, 'Second-edit evidence differs');
  equal(check.observed.afterStale, stale.state, 'Stale-response state differs');
  equal(check.observed.completedAlias, alias, 'Wrong response completed');
  equal(check.observed.response, { roomId: '!old:example.org', servers: ['example.org'] }, 'Missing stale external response');
  for (const state of [edited.state, stale.state]) {
    equal([state.address, state.addressState, state.resolvedRoom, state.pendingNavigation, state.navigationCount],
      ['#other:example.org', 'unknown', null, null, 0], 'Old resolution applied or navigation occurred');
  }
  equal(cleanup.updateErrors, [], 'Production asynchronous error');
  requireThat(row.calls.every(c => !c.unavailableNativeService && !c.nativeService), 'Native services used by host fixture');
  equal(row.calls.filter(c => c.method === 'updateAddress').map(c => c.args),
    [[spec.event.value], [edited.state.address]], 'Canonical edit/stale probe missing from production calls');
  requireThat(row.calls.some(c => c.class === 'JoinRoomByAddressPresenter' && c.method === 'constructor'),
    'Original presenter constructor not observed');
}

async function mergeReports(primary, supplemental) {
  const contract = read(CONTRACT), task = read(TASK_FILE);
  validateReport(primary, contract);
  validateReport(supplemental, contract);
  requireThat(['base', 'final'].includes(primary.role), 'Only manifest-bound base/final roles supported');
  equal(supplemental.role, primary.role, 'Candidate role mismatch');
  const target = fs.realpathSync(path.join(ROOT, task.arkts[primary.role + 'Path']));
  equal(fs.realpathSync(supplemental.target), target, 'Supplemental target mismatch');
  equal(fs.realpathSync(primary.provenance.original), target, 'Primary target mismatch');
  equal([primary.provenance.taskId, primary.provenance.role, primary.provenance.sourceOverride],
    [TASK, primary.role, false], 'Primary candidate identity mismatch');
  if (primary.target) equal(fs.realpathSync(primary.target), target, 'Primary target mismatch');
  const index = contract.cases.findIndex(c => c.caseId === CASE), spec = contract.cases[index];
  equal(primary.semantic.cases[index].status, 'not_scored', 'Refusing already-scored case002 or duplicate promotion');
  requireThat(!primary.diagnostics?.hostClockSupplemental?.length && !primary.semantic.cases[index].clockSupplemental,
    'Duplicate clock promotion');
  equal(supplemental.runtime, SCOPE, 'Supplemental runtime must be host_transpiled_production');
  equal(supplemental.observationScope,
    'Original production methods under isolated virtual timers; no ArkVM, ArkUI, device or network execution',
    'Supplemental observation scope differs from reviewed host fixture');
  equal(supplemental.compile, { passed: null, scope: 'TypeScript transpilation only; no native build' }, 'Host evidence claims compilation');
  requireThat(!supplemental.runtimeCompile && !supplemental.nativeEvidence, 'Supplemental claims native runtime/compile');
  equal(supplemental.diagnostics.nativeRuntimeExecuted, false, 'Supplemental claims native execution');
  requireThat(!supplemental.diagnostics.nativeProductionExecuted, 'Supplemental claims native production execution');
  equal(supplemental.diagnostics.promotion, 'not_promoted', 'Supplemental already promoted');
  equal(supplemental.diagnostics.selectedCaseIds, [CASE], 'Only case002 may be selected');
  for (const row of supplemental.semantic.cases.filter(r => r.caseId !== CASE)) {
    equal([row.status, row.observationLevel, row.observed, row.calls, row.productionSources, row.checkpoints],
      ['not_scored', 'not_executed', {}, [], [], []], 'Supplemental attempts to promote another case');
  }
  const artifacts = {
    contract: verify(supplemental.provenance.canonicalContract, CONTRACT),
    fixture: verify(supplemental.provenance.fixture, path.join(__dirname, 'Task14Clock.cjs')),
    loader: verify(supplemental.provenance.loader, path.join(ROOT, 'scripts/runtime_semantics/arkts_runtime.cjs')),
    task: record(TASK_FILE), manifest: record(primary.nativeEvidence.manifest)
  };
  equal(supplemental.contractSha256, artifacts.contract.sha256, 'Full contract hash mismatch');
  const manifest = read(artifacts.manifest.path);
  const manifestContracts = manifest.contracts.filter(c => c.taskId === TASK);
  equal(manifestContracts.length, 1, 'Ambiguous primary bundled contract');
  verify({ path: manifestContracts[0].file, sha256: manifestContracts[0].sha256 }, CONTRACT);
  const candidates = manifest.candidates.filter(c => c.taskId === TASK && c.role === primary.role);
  equal(candidates.length, 1, 'Ambiguous primary candidate');
  equal([fs.realpathSync(candidates[0].original), candidates[0].sourceOverride], [target, false], 'Bundled candidate differs');
  const incoming = supplemental.semantic.cases[index];
  validateExecution(incoming, spec);
  const sources = manifest.production.filter(p => p.taskId === TASK && p.role === primary.role);
  requireThat(sources.length > 0 && new Set(sources.map(p => p.path)).size === sources.length, 'Missing/duplicate primary sources');
  for (const source of sources) {
    requireThat(!path.isAbsolute(source.path) && !source.path.split(/[\\/]/).includes('..'), 'Invalid production path');
    const file = fs.realpathSync(path.join(target, source.path));
    requireThat(file.startsWith(target + path.sep), 'Production source escapes candidate');
    verify({ path: file, sha256: source.sha256 }, file);
  }
  const expectedSources = sources.map(s => ({ path: s.path, sha256: s.sha256 }));
  equal(incoming.productionSources, expectedSources, 'Incoming production differs from primary bundle');
  equal(primary.semantic.cases[index].productionSources, expectedSources, 'Primary case source differs');
  const scheduler = createScheduler();
  equal(incoming.clock.dependency, scheduler.dependency, 'Clock dependency hash/version/path mismatch');
  scheduler.clock.reset();
  equal([incoming.clock.timeDomain, incoming.clock.globalTimersModified, incoming.clock.nativeRuntimeExecuted],
    ['isolated_virtual_milliseconds', false, false], 'Invalid clock execution scope');

  // Replay the reviewed fixture, not a report-supplied module, to reject even
  // internally consistent fabricated call/checkpoint/invariant records.
  const fixtureEvaluator = artifacts.fixture.originalPath ? require(artifacts.fixture.path).evaluateClockCase : evaluateClockCase;
  const replay = copy(await fixtureEvaluator(target, spec));
  equal(incoming, replay, 'Submitted evidence differs from fresh isolated production replay');
  for (const artifact of Object.values(artifacts)) verify(artifact, artifact.path);
  for (const source of sources) verify({ path: path.join(target, source.path), sha256: source.sha256 }, path.join(target, source.path));
  const report = copy(primary), previous = copy(report.semantic.cases[index]);
  report.semantic.cases[index] = copy(incoming);
  report.semantic.cases[index].clockSupplemental = { scope: SCOPE, nativeRuntimeExecuted: false,
    applicationCompiled: false, runtimeCompiled: false, replaySha256: objectHash(replay) };
  report.semantic.cases[index].taskId = TASK;
  report.semantic.cases[index].role = primary.role;
  Object.assign(report.semantic, counts(report.semantic.cases));
  report.runtime = 'mixed_per_case_native_and_host_transpiled_production';
  report.observationScope = 'Original primary native evidence retained; case002 only is host_transpiled_production with isolated virtual timers, not ArkVM, native UI or compilation.';
  const preservedRows = report.semantic.cases.filter(r => r.caseId !== CASE).map(row => {
    equal(row, primary.semantic.cases.find(r => r.caseId === row.caseId), 'Non-target primary row changed');
    return { caseId: row.caseId, status: row.status, sha256: objectHash(row) };
  });
  report.diagnostics.hostClockSupplemental = [{ caseId: CASE, action: 'promoted_original_NS_only',
    validatedAt: new Date().toISOString(), scope: SCOPE, nativeRuntimeExecuted: false, compileCredit: false,
    validator: record(__filename), artifacts, canonicalCase: copy(spec), previous,
    preservedRows, primaryRuntime: primary.runtime, replaySha256: objectHash(replay) }];
  equal(report.compile, primary.compile, 'Primary compile metadata changed');
  equal(report.runtimeCompile, primary.runtimeCompile, 'Primary native runtime compile metadata changed');
  validateReport(report, contract);
  return report;
}

async function mergeFiles(primaryFile, supplementalFile, output) {
  requireThat(!fs.existsSync(output), 'Refusing to overwrite existing evidence/output');
  const primaryArtifact = record(primaryFile), supplementalArtifact = record(supplementalFile);
  const report = await mergeReports(read(primaryFile), read(supplementalFile));
  verify(primaryArtifact, primaryFile);
  verify(supplementalArtifact, supplementalFile);
  const audit = report.diagnostics.hostClockSupplemental[0];
  audit.primaryReport = primaryArtifact;
  audit.supplementalReport = supplementalArtifact;
  fs.mkdirSync(path.dirname(path.resolve(output)), { recursive: true });
  fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
  return report;
}

module.exports = { mergeReports, mergeFiles, validateExecution };
if (require.main === module) {
  const args = process.argv.slice(2), value = flag => args[args.indexOf(flag) + 1];
  if (!['--primary', '--supplemental', '--output'].every(flag => args.includes(flag) && value(flag)))
    throw new Error('--primary --supplemental --output required');
  mergeFiles(value('--primary'), value('--supplemental'), value('--output')).then(report =>
    console.log(JSON.stringify({ output: path.resolve(value('--output')), ...counts(report.semantic.cases), scope: SCOPE })))
    .catch(error => { console.error(error); process.exitCode = 1; });
}
