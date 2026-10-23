import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const arg = name => process.argv[process.argv.indexOf(name) + 1];
const optionalArg = name => process.argv.includes(name) ? arg(name) : null;
const project = path.resolve(arg('--project'));
const role = arg('--role');
const output = path.resolve(arg('--output'));
const observationsPath = optionalArg('--observations');
const nativeDevice = optionalArg('--native-device');
const apkPath = optionalArg('--apk');
const migration = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..', '..');
const contract = JSON.parse(fs.readFileSync(path.join(migration, 'canonical', 'transitions.json'), 'utf8'));
const sourceManifest = JSON.parse(fs.readFileSync(path.join(project, 'IMMUTABLE_SOURCES.json'), 'utf8'));
const productionSources = role === 'agent' ? (() => {
  const files = [];
  const visit = directory => { for (const entry of fs.readdirSync(directory, { withFileTypes: true })) { const target = path.join(directory, entry.name); if (entry.isDirectory()) visit(target); else if (/\.(?:kt|java)$/.test(entry.name)) { const bytes = fs.readFileSync(target); files.push({ path: path.relative(project, target), sha256: crypto.createHash('sha256').update(bytes).digest('hex'), bytes: bytes.length }); } } };
  visit(path.join(project, 'immutable-src'));
  return files;
})() : sourceManifest.files.map(file => ({ path: file.path, gitBlob: file.gitBlob, sha256: file.sha256 }));
const runtimeJar = path.join(project, 'build', 'runtime.jar');
const runtimeClasspathFile = path.join(project, 'build', 'runtime.classpath');

const subset = (actual, expected) => {
  if (expected === null || typeof expected !== 'object') return Object.is(actual, expected);
  if (Array.isArray(expected)) return Array.isArray(actual) && actual.length === expected.length && expected.every((item, index) => subset(actual[index], item));
  return actual !== null && typeof actual === 'object' && Object.entries(expected).every(([key, value]) => subset(actual[key], value));
};

const sameMembers = (left = [], right = []) => JSON.stringify([...left].sort()) === JSON.stringify([...right].sort());

const givenPassed = (caseId, observed) => {
  const before = observed.before ?? {};
  const setup = observed.setup ?? {};
  switch (caseId) {
    case 'mk_state_001_initialize_tabs':
      return observed.givenEstablished === true && before.initialized === false && before.availableTabs?.length === 0 && sameMembers(setup.repositoryTabs, ['GIF', 'EMOJI', 'STICKER']) && setup.initialTab === null;
    case 'mk_state_002_restrict_fallback':
      return observed.givenEstablished === true && JSON.stringify(before.availableTabs) === JSON.stringify(['EMOJI', 'STICKER', 'GIF']) && before.selectedTab === 'GIF' && before.preferredTab === 'GIF' && before.restrictedTo === null;
    case 'mk_state_003_lift_restriction':
      return observed.givenEstablished === true && JSON.stringify(before.availableTabs) === JSON.stringify(['EMOJI']) && before.selectedTab === 'EMOJI' && before.preferredTab === 'GIF' && JSON.stringify(before.restrictedTo) === JSON.stringify(['EMOJI']);
    case 'mk_state_004_tab_clears_query':
      return observed.givenEstablished === true && JSON.stringify(before.availableTabs) === JSON.stringify(['EMOJI', 'STICKER', 'GIF']) && before.selectedTab === 'EMOJI' && before.searchActive === true && before.searchQuery === 'cats' && setup.queryEstablishedBy === 'MediaKeyboardViewModel.onEvent(SearchQueryChanged)';
    case 'mk_state_005_gif_initial_failure':
      return observed.givenEstablished === true && before.gifs?.length === 0 && before.hasMore === true && setup.repositoryFirstPage?.result === 'network_failure';
    case 'mk_state_006_gif_retry_recovery':
      return observed.givenEstablished === true && before.gifs?.length === 0 && before.loadFailed === true && before.hasMore === false && setup.failedStateEstablishedBy === 'GifPageViewModel.init/onEvent(Initialize)' && setup.repositoryFirstPage?.result === 'success';
    case 'mk_state_007_gif_pagination':
      return observed.givenEstablished === true && JSON.stringify(before.gifs) === JSON.stringify(['g1', 'g2']) && before.hasMore === true && before.loadFailed === false && setup.firstPageEstablishedBy === 'GifPageViewModel.init/onEvent(Initialize)' && setup.repositoryNextPage?.result === 'success';
    case 'mk_state_008_sticker_tap_defers_send':
      return observed.givenEstablished === true && before.confirmation === null && setup.sticker?.packId === 'pack-1' && setup.sticker?.stickerId === 7;
    case 'mk_state_009_confirmation_cancel':
    case 'mk_state_010_confirmation_send_once':
      return observed.givenEstablished === true && before.confirmation?.packId === 'pack-1' && before.confirmation?.stickerId === 7 && setup.confirmationEstablishedBy === 'ChatStickerConfirmationController.show';
    default:
      return false;
  }
};

const terminalPrefixPassed = observed => {
  const terminal = observed.terminalFailure;
  return terminal?.kind === 'missing_canonical_transition_after_reachable_prefix' &&
    terminal.prefixReached === true &&
    observed.after?.isShowing === true &&
    observed.after?.current === 'media';
};

const invariantFacts = (caseId, observed) => {
  const before = observed.before ?? {};
  const after = observed.after ?? {};
  const effects = observed.effects ?? [];
  const named = name => effects.filter(effect => effect.name === name);
  switch (caseId) {
    case 'mk_state_001_initialize_tabs': return [JSON.stringify(after.availableTabs) === JSON.stringify(['EMOJI', 'STICKER', 'GIF'])];
    case 'mk_state_002_restrict_fallback': return [after.preferredTab === before.preferredTab, Array.isArray(after.availableTabs) && after.availableTabs.every(tab => tab === 'EMOJI')];
    case 'mk_state_003_lift_restriction': return [after.selectedTab === before.preferredTab && after.availableTabs?.includes(before.preferredTab) === true];
    case 'mk_state_004_tab_clears_query': return [after.searchActive === before.searchActive];
    case 'mk_state_005_gif_initial_failure': return [after.isLoading === false && after.isLoadingMore === false];
    case 'mk_state_006_gif_retry_recovery': return [Array.isArray(before.gifs) && before.gifs.length === 0 && JSON.stringify(after.gifs) === JSON.stringify(['g1', 'g2'])];
    case 'mk_state_007_gif_pagination': return [JSON.stringify(after.gifs?.slice(0, before.gifs?.length)) === JSON.stringify(before.gifs), named('getGifs')[0]?.offset === before.gifs?.length];
    case 'mk_state_008_sticker_tap_defers_send': return [named('onSend').length === 0];
    case 'mk_state_009_confirmation_cancel': return [after.confirmation === null && named('onSend').length === 0];
    case 'mk_state_010_confirmation_send_once': return [after.confirmation === null && effects.findIndex(effect => effect.name === 'confirmationVisibility') < effects.findIndex(effect => effect.name === 'onSend'), named('onSend').length === 1];
    default: return [];
  }
};

const unavailable = reason => contract.cases.map(item => ({
  caseId: item.caseId,
  traceDigest: item.traceDigest,
  status: 'not_scored',
  checkpoints: [],
  observed: null,
  invariantChecks: [],
  reason
}));

let rows;
let runtime;
if (!observationsPath && (!fs.existsSync(runtimeJar) || !fs.existsSync(runtimeClasspathFile))) {
  rows = unavailable('immutable_runtime_not_built');
  runtime = { status: null, stderr: 'Build the selected project with execution.json buildCommand first.' };
} else {
  if (observationsPath) {
    runtime = { status: 0, stdout: fs.readFileSync(observationsPath, 'utf8'), stderr: '' };
  } else {
    const dependencies = fs.readFileSync(runtimeClasspathFile, 'utf8').trim();
    runtime = spawnSync('java', ['-cp', `${runtimeJar}:${dependencies}`, 'benchmark.evaluator.ImmutableMediaProbeKt'], { encoding: 'utf8' });
  }
  if (runtime.status !== 0) {
    rows = unavailable('immutable_runtime_probe_failed');
  } else {
    const parsedObservations = runtime.stdout.trim().split(/\r?\n/).filter(Boolean).map(line => JSON.parse(line));
    const expectedCaseIds = new Set(contract.cases.map(item => item.caseId));
    const observedCaseIds = parsedObservations.map(value => value.caseId);
    const observationSetValid = parsedObservations.length === contract.cases.length &&
      new Set(observedCaseIds).size === observedCaseIds.length &&
      observedCaseIds.every(caseId => expectedCaseIds.has(caseId));
    const observations = new Map(parsedObservations.map(value => [value.caseId, value]));
    rows = observationSetValid ? contract.cases.map(item => {
      const observed = observations.get(item.caseId);
      if (!observed) return unavailable('missing_runtime_observation').find(row => row.caseId === item.caseId);
      if (observed.terminalFailure) {
        const prefixPassed = terminalPrefixPassed(observed);
        return {
          caseId: item.caseId,
          traceDigest: item.traceDigest,
          status: prefixPassed ? 'fail' : 'not_scored',
          productionSources,
          invokedProductionMethods: [observed.productionEntrypoint],
          checkpoints: [{ label: 'common_prefix_before', state: observed.before }, { label: 'common_prefix_after', state: observed.after }],
          observed: prefixPassed ? null : { state: observed.after, effects: observed.effects ?? [] },
          invariantChecks: item.invariants.map(text => ({ text, passed: null, evidence: 'unobserved_after_terminal_missing_transition' })),
          reason: prefixPassed ? 'canonical_transition_missing_after_reachable_production_prefix' : 'production_prefix_not_established',
          diagnostics: { availability: observed.availability, givenPassed: false, prefixPassed, terminalFailure: observed.terminalFailure }
        };
      }
      const setupPassed = givenPassed(item.caseId, observed);
      if (!setupPassed) {
        return {
          caseId: item.caseId,
          traceDigest: item.traceDigest,
          status: 'not_scored',
          productionSources,
          invokedProductionMethods: [observed.productionEntrypoint],
          checkpoints: [{ label: 'before', state: observed.before }, { label: 'after', state: observed.after }],
          observed: { state: observed.after, effects: observed.effects ?? [] },
          invariantChecks: [],
          reason: 'canonical_given_not_established',
          diagnostics: { availability: observed.availability, givenPassed: false }
        };
      }
      const expectedEffects = item.expected.effects ?? [];
      const absentEffects = item.expected.absentEffects ?? [];
      const facts = invariantFacts(item.caseId, observed);
      const invariantChecks = item.invariants.map((text, index) => ({
        text,
        passed: facts[index] === true,
        evidence: 'derived_from_runtime_before_after_or_ordered_effects'
      }));
      const statePassed = subset(observed.after, item.expected.state);
      const effectsPassed = expectedEffects.every(expected => observed.effects.some(actual => subset(actual, expected)));
      const absentPassed = absentEffects.every(name => observed.effects.every(actual => actual.name !== name));
      const passed = statePassed && effectsPassed && absentPassed && invariantChecks.every(check => check.passed);
      return {
        caseId: item.caseId,
        traceDigest: item.traceDigest,
        status: passed ? 'pass' : 'fail',
        productionSources,
        invokedProductionMethods: [observed.productionEntrypoint],
        checkpoints: [{ label: 'before', state: observed.before }, { label: 'after', state: observed.after }],
        observed: { state: observed.after, effects: observed.effects },
        invariantChecks,
        diagnostics: { availability: observed.availability, givenPassed: setupPassed, statePassed, effectsPassed, absentEffectsPassed: absentPassed }
      };
    }) : unavailable('invalid_runtime_observation_set');
  }
}

const count = status => rows.filter(row => row.status === status).length;
const polarityEligible = role === 'base'
  ? rows.every(item => item.status === 'fail')
  : role === 'final'
    ? rows.every(item => item.status === 'pass')
    : rows.every(item => item.status !== 'not_scored');
const report = {
  schemaVersion: 1,
  taskId: contract.taskId,
  platform: 'android',
  role,
  observationMode: 'runtime_state_transition',
  runtime: observationsPath ? 'android_app_runtime_over_immutable_official_kotlin_source_slice' : 'debug_immutable_official_kotlin_source_slice',
  productionSourceCommit: role === 'agent' ? null : sourceManifest.sourceCommit,
  productionSourceHashes: productionSources,
  runtimeArtifact: fs.existsSync(apkPath ?? runtimeJar) ? {
    kind: apkPath ? 'installable_android_harness_apk' : 'debug_runtime_jar',
    sha256: crypto.createHash('sha256').update(fs.readFileSync(apkPath ?? runtimeJar)).digest('hex'),
    bytes: fs.statSync(apkPath ?? runtimeJar).size
  } : null,
  codeGeneration: { passed: false, changedProductionFiles: [] },
  compile: { passed: runtime.status === 0, scope: observationsPath ? 'installable_api37_android_harness' : 'debug_focused_immutable_source_slice', command: null },
  semantic: { passed: count('pass'), failed: count('fail'), notScored: count('not_scored'), total: rows.length, cases: rows },
  diagnostics: {
    adapter: runtime.status === 0 ? 'executed' : 'unavailable',
    runtimeCompile: runtime.status === 0,
    stderr: runtime.stderr?.trim() || null,
    nativeAndroidUiEvidence: observationsPath ? 'app_runtime_observer_collected' : 'not_collected',
    nativeDevice: nativeDevice ?? null,
    rawObservationLog: observationsPath ? path.relative(migration, observationsPath) : null,
    publicationEligible: Boolean(observationsPath) && runtime.status === 0 && polarityEligible
  }
};

fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`);
process.exit(runtime.status === 0 ? 0 : 2);
