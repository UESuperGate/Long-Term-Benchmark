'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { productionLoader, compareExpected, snapshot } = require('../../../scripts/runtime_semantics/arkts_runtime.cjs');
const ROOT = path.resolve(__dirname, '../../..');
const TASK = '14_join_room_by_address';
const CASE = 'jr_state_002_update_trims_and_debounces';
const DEFAULT_FAKE_TIMERS = '/Users/z1an/Library/OpenHarmony/Sdk/23/ets/build-tools/ets-loader/node_modules/@sinonjs/fake-timers';
const digest = data => crypto.createHash('sha256').update(data).digest('hex');
const copy = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));

function createScheduler() {
  const location = process.env.LTB_FAKE_TIMERS || DEFAULT_FAKE_TIMERS;
  const FakeTimers = require(location);
  const clock = FakeTimers.createClock(0, 1000);
  const packagePath = require.resolve(path.join(location, 'package.json'));
  const entry = require.resolve(location);
  const dependency = { path: entry, sha256: digest(fs.readFileSync(entry)),
    version: JSON.parse(fs.readFileSync(packagePath)).version, packageSha256: digest(fs.readFileSync(packagePath)) };
  const timerEnvironment = { setTimeout: clock.setTimeout.bind(clock), clearTimeout: clock.clearTimeout.bind(clock),
    setInterval: clock.setInterval.bind(clock), clearInterval: clock.clearInterval.bind(clock), Date: clock.Date };
  return { clock, timerEnvironment, dependency };
}

// Executable boundary values come from the approved 299 + 1 test protocol,
// never from caseSpec.expected. All observations come from production execution.
async function execute({ caseSpec, load, clock, trace }) {
  const invariantChecks = [], evidence = [], boundaryChecks = [];
  const observed = {};
  let unsupported;
  const requests = [], updateErrors = [];
  let presenter, navigator;
  const checkpoint = (label, data) => {
    const value = copy({ virtualTimeMs: clock.now, ...data });
    evidence.push({ label, data: value, observationLevel: 'host_transpiled_production' });
    trace(label, value);
  };
  const read = () => copy({ address: presenter.address,
    addressState: presenter.internalAddressState ?? presenter.addressState ?? presenter.state,
    visibleAddressState: typeof presenter.visibleAddressState === 'function' ? presenter.visibleAddressState() :
      presenter.addressState ?? presenter.state,
    resolvedRoom: presenter.resolvedRoom ?? null,
    pendingNavigation: presenter.pendingNavigation ?? null,
    navigationCount: navigator?.openRoomCount,
    requestCount: requests.length });
  const update = value => {
    const result = presenter.updateAddress(value);
    if (result && typeof result.then === 'function') result.catch(error => updateErrors.push(String(error)));
  };
  const lookup = (alias, ...args) => {
    let resolve, reject;
    const promise = new Promise((a, b) => { resolve = a; reject = b; });
    const request = { alias, calledAt: clock.now, resolve, reject, settled: false };
    requests.push(request);
    checkpoint('resolver:requested', { alias, calledAt: request.calledAt, argumentCount: args.length, requestIndex: requests.length - 1 });
    return promise;
  };
  try {
    if (caseSpec.caseId !== CASE || caseSpec.key !== 'update_trims_and_debounces' || caseSpec.event.name !== 'update_address')
      throw new Error('Independent clock fixture supports only canonical Task14 case002');
    let m;
    const paths = ['entry/src/main/ets/features/JoinRoomByAddressFeature.ets',
      'entry/src/main/ets/features/JoinRoomByAddress/JoinRoomByAddressPresenter.ets',
      'entry/src/main/ets/features/ChatFeature.ets'];
    const errors = [];
    for (const file of paths) {
      try { m = load(file); if (typeof m.JoinRoomByAddressPresenter === 'function') break; }
      catch (error) { errors.push(String(error.message || error)); }
    }
    if (typeof m?.JoinRoomByAddressPresenter !== 'function')
      throw new Error('Production presenter cannot be bound: ' + errors.join('; '));
    navigator = typeof m.JoinRoomNavigator === 'function' ? new m.JoinRoomNavigator() : {
      openRoomCount: 0,
      async openRoom() { this.openRoomCount++; },
      async back() {}
    };
    presenter = typeof m.TimerTaskScheduler === 'function' ? new m.JoinRoomByAddressPresenter(
      { resolveRoomAlias: lookup, resolve: lookup }, navigator, new m.TimerTaskScheduler()) :
      new m.JoinRoomByAddressPresenter({ resolveRoomAlias: lookup, resolve: lookup }, navigator);
    if (typeof presenter.updateAddress !== 'function') throw new Error('Original updateAddress API unavailable');
    const before = read();
    const givenChecks = Object.entries(caseSpec.given).map(([key, value]) => ({ key, given: value, actual: before[key],
      established: JSON.stringify(before[key]) === JSON.stringify(value) }));
    checkpoint('before:event', { state: before, givenChecks });
    if (!givenChecks.every(check => check.established)) throw new Error('Canonical empty/unknown given not established');
    if (clock.now !== 0 || requests.length !== 0) throw new Error('Clock fixture did not start at virtual zero with no resolver request');
    const eventStart = clock.now;
    update(caseSpec.event.value);
    checkpoint('event:update-address', { rawInput: caseSpec.event.value, state: read() });
    observed.address = presenter.address;
    await clock.tickAsync(299);
    const at299 = read();
    observed.addressStateBefore300ms = at299.addressState;
    boundaryChecks.push({ description: 'No alias-resolution request by virtual t=299', passed: requests.length === 0,
      observed: { time: clock.now, requests: requests.map(r => ({ alias: r.alias, calledAt: r.calledAt })) } });
    checkpoint('boundary:299', { state: at299 });
    await clock.tickAsync(1);
    const at300 = read();
    const targetAlias = caseSpec.event.value.trim();
    boundaryChecks.push({ description: 'Exactly one target alias request at virtual t=300',
      passed: requests.length === 1 && requests[0].alias === targetAlias && requests[0].calledAt - eventStart === clock.now - eventStart,
      observed: { time: clock.now, requests: requests.map(r => ({ alias: r.alias, calledAt: r.calledAt })) } });
    checkpoint('boundary:300', { state: at300 });
    // Diagnose late/no-request mutants without pretending that advancing time
    // means a request occurred. The canonical t=300 observation is retained.
    if (!requests.some(r => r.alias === targetAlias)) {
      await clock.tickAsync(900);
      checkpoint('diagnostic:late-request-window', { state: read(), horizonMs: clock.now - eventStart });
    }
    const first = requests.find(r => r.alias === targetAlias);
    observed.resolveAfterMs = first ? first.calledAt - eventStart : null;
    checkpoint('after:event', { observed, state: read(), boundaryChecks,
      clockMeaning: 'Actual resolver call timestamp on an isolated virtual scheduler, not requested timeout or wall-clock elapsed' });
    if (!first) throw new Error('No pending canonical resolution exists to exercise the stale-response invariant');
    // Invariant probe starts AFTER canonical measurement, as on Android.
    const nextAddress = '#other:example.org';
    update(nextAddress);
    const afterEdit = read();
    checkpoint('invariant:second-edit', { state: afterEdit });
    first.settled = true;
    first.resolve({ roomId: '!old:example.org', servers: ['example.org'] });
    await clock.tickAsync(0);
    const afterStale = read();
    invariantChecks.push({ description: 'each address change invalidates the previous resolution',
      passed: afterStale.address === nextAddress && afterStale.addressState === afterEdit.addressState &&
        afterStale.resolvedRoom === null && afterStale.pendingNavigation === null &&
        (navigator ? afterStale.navigationCount === afterEdit.navigationCount && afterStale.navigationCount === 0 : true),
      observed: { afterEdit, afterStale, completedAlias: first.alias, response: { roomId: '!old:example.org', servers: ['example.org'] } } });
    checkpoint('invariant:stale-response', { state: afterStale, invariantChecks });
    if (updateErrors.length) throw new Error('Production asynchronous update rejected: ' + updateErrors.join('; '));
  } catch (error) { unsupported = String(error.message || error); }
  finally {
    try {
      if (presenter && typeof presenter.dismiss === 'function') presenter.dismiss();
      for (const request of requests) if (!request.settled) { request.settled = true; request.resolve(undefined); }
      await clock.tickAsync(0);
      checkpoint('fixture:cleanup', { remainingVirtualTimers: clock.countTimers(), updateErrors,
        operation: 'Original dismiss when available, release external responses, discard isolated virtual timers' });
    } catch (error) {
      unsupported = [unsupported, 'Fixture cleanup failed: ' + String(error.message || error)].filter(Boolean).join('; ');
    } finally { clock.reset(); }
  }
  if (!evidence.some(item => item.label === 'before:event')) checkpoint('before:event', { executed: false, unsupported });
  if (!evidence.some(item => item.label === 'after:event')) checkpoint('after:event', { executed: false, unsupported });
  return { observed, invariantChecks, boundaryChecks, evidence, unsupported,
    observationLevel: 'host_transpiled_production',
    unsupportedInvariants: (caseSpec.invariants || []).filter(description => !invariantChecks.some(check => check.description === description))
      .map(description => ({ description, reason: unsupported || 'Invariant not observed' })) };
}

async function evaluateClockCase(project, caseSpec) {
  const productionSources = [], calls = [], checkpoints = [];
  const row = { caseId: caseSpec.caseId, traceDigest: caseSpec.traceDigest, status: 'not_scored', productionSources, calls, checkpoints };
  try {
    const { clock, timerEnvironment, dependency } = createScheduler();
    const load = productionLoader(project, productionSources, calls, timerEnvironment);
    const result = await execute({ caseSpec, load, clock, trace: (label, state) => checkpoints.push({ label, state: snapshot(state) }) });
    Object.assign(row, result);
    const comparison = compareExpected(caseSpec.expected, result.observed);
    row.assertionFailures = comparison.failures;
    row.missingObservations = comparison.missing;
    row.missingInvariants = (caseSpec.invariants || []).filter(description =>
      !row.invariantChecks.some(check => check.description === description && typeof check.passed === 'boolean'));
    row.clock = { dependency, implementation: 'fake-timers.createClock + tickAsync; only production VM timer environment injected',
      timeDomain: 'isolated_virtual_milliseconds', globalTimersModified: false, nativeRuntimeExecuted: false };
    if (calls.some(call => call.unavailableNativeService)) row.reason = 'Unbound native service invoked';
    else if (result.unsupported) row.reason = result.unsupported;
    else if (!productionSources.length || !calls.length || checkpoints.length < 2) row.reason = 'Incomplete production execution evidence';
    else if (comparison.missing.length || row.missingInvariants.length) row.reason = 'Incomplete canonical observations/invariants';
    else {
      for (const check of row.boundaryChecks.filter(check => !check.passed)) row.assertionFailures.push({
        path: 'schedulerBoundary', description: check.description, observed: check.observed });
      row.status = row.assertionFailures.length || row.invariantChecks.some(check => !check.passed) ? 'fail' : 'pass';
    }
  } catch (error) {
    Object.assign(row, { reason: String(error.stack || error), observed: {}, invariantChecks: [],
      observationLevel: 'not_executed', assertionFailures: [],
      missingObservations: compareExpected(caseSpec.expected, {}).missing,
      missingInvariants: (caseSpec.invariants || []).slice() });
  }
  return row;
}

async function runReport(project, role) {
  const contractFile = path.join(ROOT, 'benchmark_tasks', TASK, 'transitions.json');
  const bytes = fs.readFileSync(contractFile);
  const contract = JSON.parse(bytes);
  const cases = [];
  for (const spec of contract.cases) {
    if (spec.caseId === CASE) cases.push(await evaluateClockCase(project, spec));
    else cases.push({ caseId: spec.caseId, traceDigest: spec.traceDigest, status: 'not_scored',
      reason: 'Outside this independent case002 scheduler report; existing primary/native results are not copied or overridden',
      observed: {}, invariantChecks: [], productionSources: [], calls: [], checkpoints: [],
      observationLevel: 'not_executed', missingObservations: Object.keys(spec.expected), missingInvariants: spec.invariants.slice() });
  }
  const counts = { passed: 0, failed: 0, notScored: 0, total: cases.length };
  for (const row of cases) counts[row.status === 'pass' ? 'passed' : row.status === 'fail' ? 'failed' : 'notScored']++;
  return { schemaVersion: 2, taskId: TASK, platform: 'arkts', role, target: fs.realpathSync(project),
    observationMode: 'runtime_state_transition', runtime: 'host_transpiled_production',
    observationScope: 'Original production methods under isolated virtual timers; no ArkVM, ArkUI, device or network execution',
    generatedAt: new Date().toISOString(), contractSha256: digest(bytes),
    compile: { passed: null, scope: 'TypeScript transpilation only; no native build' },
    provenance: { canonicalContract: { path: contractFile, sha256: digest(bytes) },
      fixture: { path: __filename, sha256: digest(fs.readFileSync(__filename)) },
      loader: { path: require.resolve('../../../scripts/runtime_semantics/arkts_runtime.cjs'),
        sha256: digest(fs.readFileSync(require.resolve('../../../scripts/runtime_semantics/arkts_runtime.cjs'))) } },
    semantic: { ...counts, cases }, diagnostics: { nativeRuntimeExecuted: false, reviewStatus: 'parent_review_required',
      promotion: 'not_promoted', selectedCaseIds: [CASE], otherCaseRows: 'explicitly unexecuted, not regressions of primary results' } };
}

module.exports = { createScheduler, execute, evaluateClockCase, runReport, CASE };
if (require.main === module) {
  const args = process.argv.slice(2);
  const value = name => args[args.indexOf(name) + 1];
  if (!['--source', '--role', '--output'].every(name => args.includes(name))) throw new Error('--source --role --output required');
  runReport(path.resolve(value('--source')), value('--role')).then(report => {
    const output = path.resolve(value('--output'));
    fs.mkdirSync(path.dirname(output), { recursive: true });
    fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify({ output, ...report.semantic, cases: undefined }));
  }).catch(error => { console.error(error); process.exitCode = 1; });
}
