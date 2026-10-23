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
    case 'sm_state_001_exit_multiselect':
      return observed.givenEstablished === true && JSON.stringify(before.installedPackIds) === JSON.stringify(['a', 'b']) && JSON.stringify(before.selectedPackIds) === JSON.stringify(['a']) && before.multiSelectEnabled === true && setup.selectionEstablishedBy === 'StickerManagementViewModel.toggleSelection';
    case 'sm_state_002_install_lifecycle':
      return observed.givenEstablished === true && before.availablePackIds?.includes('p1') === true && setup.availablePackLoadedFrom === 'StickerManagementRepository.getStickerPacks' && setup.linkedDevices === false;
    case 'sm_state_003_install_status_settles':
      return observed.givenEstablished === true && before.downloadStatus === 'DOWNLOADED' && before.availablePackIds?.includes('p1') === true && before.installedPackIds?.includes('p1') === true && setup.downloadedStateEstablishedBy === 'StickerManagementViewModel.installStickerPack';
    case 'sm_state_004_drag_reorder':
    case 'sm_state_005_drop_persists_order':
      return observed.givenEstablished === true && JSON.stringify(before.installedPackIds) === JSON.stringify(['a', 'b', 'c']) && setup.installedPacksLoadedFrom === 'StickerManagementRepository.getStickerPacks';
    case 'sm_state_006_select_enters_multiselect':
      return observed.givenEstablished === true && JSON.stringify(before.installedPackIds) === JSON.stringify(['a', 'b']) && before.selectedPackIds?.length === 0 && before.multiSelectEnabled === false && setup.installedPacksLoadedFrom === 'StickerManagementRepository.getStickerPacks';
    case 'sm_state_007_select_all_toggle':
      return observed.givenEstablished === true && JSON.stringify(before.installedPackIds) === JSON.stringify(['a', 'b', 'c']) && JSON.stringify(before.selectedPackIds) === JSON.stringify(['a']) && before.multiSelectEnabled === true && setup.selectionEstablishedBy === 'StickerManagementViewModel.toggleSelection';
    case 'sm_state_008_request_multi_delete':
      return observed.givenEstablished === true && JSON.stringify(before.installedPackIds) === JSON.stringify(['a', 'b', 'c']) && sameMembers(before.selectedPackIds, ['a', 'c']) && before.multiSelectEnabled === true && before.prompt === null && setup.selectionEstablishedBy === 'StickerManagementViewModel.toggleSelection';
    case 'sm_state_009_cancel_multi_delete':
    case 'sm_state_010_confirm_multi_delete':
      return observed.givenEstablished === true && JSON.stringify(before.installedPackIds) === JSON.stringify(['a', 'b', 'c']) && sameMembers(before.selectedPackIds, ['a', 'c']) && before.prompt?.numItemsToDelete === 2 && setup.promptEstablishedBy === 'StickerManagementViewModel.onUninstallStickerPacksRequested' && (caseId !== 'sm_state_010_confirm_multi_delete' || setup.linkedDevices === true);
    default:
      return false;
  }
};

const terminalPrefixPassed = observed => {
  const terminal = observed.terminalFailure;
  return terminal?.kind === 'missing_canonical_transition_after_reachable_prefix' &&
    terminal.prefixReached === true &&
    Array.isArray(observed.after?.installedPackIds) &&
    Array.isArray(observed.after?.availablePackIds);
};

const terminalCapabilityFailurePassed = observed => {
  const terminal = observed.terminalFailure;
  return terminal?.kind === 'mandatory_public_integration_contract_unavailable_after_app_launch' &&
    terminal.appRuntimeReached === true &&
    Array.isArray(terminal.missingDeclarations) &&
    terminal.missingDeclarations.length > 0 &&
    observed.availability === 'executed_android_application_runtime_capability_gate';
};

const terminalReachableGivenFailurePassed = observed => {
  const terminal = observed.terminalFailure;
  return terminal?.kind === 'canonical_given_unreachable_after_executed_production_prefix' &&
    terminal.prefixReached === true &&
    observed.availability === 'executed_production_owner' &&
    Array.isArray(observed.after?.installedPackIds) &&
    Array.isArray(observed.after?.availablePackIds);
};

const invariantFacts = (caseId, observed) => {
  const before = observed.before ?? {};
  const after = observed.after ?? {};
  const effects = observed.effects ?? [];
  const named = name => effects.filter(effect => effect.name === name);
  switch (caseId) {
    case 'sm_state_001_exit_multiselect': return [after.multiSelectEnabled === false && after.selectedPackIds?.length === 0 && JSON.stringify(after.installedPackIds) === JSON.stringify(before.installedPackIds)];
    case 'sm_state_002_install_lifecycle': {
      const timeline = observed.orderedTimeline ?? [];
      return [timeline.indexOf('STATE:IN_PROGRESS') < timeline.indexOf('EFFECT:installStickerPack') && timeline.indexOf('EFFECT:installStickerPack') < timeline.indexOf('STATE:DOWNLOADED'), JSON.stringify(after.installedPackIds?.filter(id => id !== 'p1')) === JSON.stringify(before.installedPackIds?.filter(id => id !== 'p1'))];
    }
    case 'sm_state_003_install_status_settles': return [named('uninstallStickerPacks').length === 0, after.installedPackIds?.includes('p1') === true];
    case 'sm_state_004_drag_reorder': return [sameMembers(after.installedPackIds, before.installedPackIds)];
    case 'sm_state_005_drop_persists_order': return [JSON.stringify(named('setStickerPacksOrder')[0]?.packIds) === JSON.stringify(after.installedPackIds) && JSON.stringify(after.reopenedInstalledPackIds) === JSON.stringify(after.installedPackIds)];
    case 'sm_state_006_select_enters_multiselect': return [after.selectedPackIds?.every(id => after.installedPackIds?.includes(id)) === true];
    case 'sm_state_007_select_all_toggle': return [JSON.stringify(after.installedPackIds) === JSON.stringify(before.installedPackIds)];
    case 'sm_state_008_request_multi_delete': return [named('uninstallStickerPacks').length === 0 && JSON.stringify(after.installedPackIds) === JSON.stringify(before.installedPackIds)];
    case 'sm_state_009_cancel_multi_delete': return [JSON.stringify(after.installedPackIds) === JSON.stringify(before.installedPackIds) && JSON.stringify(after.selectedPackIds) === JSON.stringify(before.selectedPackIds) && named('uninstallStickerPacks').length === 0 && named('enqueueLinkedOperation').length === 0];
    case 'sm_state_010_confirm_multi_delete': return [after.selectedPackIds?.every(id => !['a', 'c'].includes(id)) === true, named('enqueueLinkedOperation').filter(effect => ['a', 'c'].includes(effect.packId) && effect.operation === 'REMOVE').length === 2];
    default: return [];
  }
};

const unavailable = reason => contract.cases.map(item => ({ caseId: item.caseId, traceDigest: item.traceDigest, status: 'not_scored', checkpoints: [], observed: null, invariantChecks: [], reason }));

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
    const mainClass = role === 'base' ? 'org.thoughtcrime.securesms.stickers.ImmutableStickerBaseProbeKt' : 'benchmark.evaluator.ImmutableStickerProbeKt';
    runtime = spawnSync('java', ['-cp', `${runtimeJar}:${dependencies}`, mainClass], { encoding: 'utf8' });
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
        const capabilityFailurePassed = terminalCapabilityFailurePassed(observed);
        const reachableGivenFailurePassed = terminalReachableGivenFailurePassed(observed);
        const scoredFailure = prefixPassed || capabilityFailurePassed || reachableGivenFailurePassed;
        return {
          caseId: item.caseId,
          traceDigest: item.traceDigest,
          status: scoredFailure ? 'fail' : 'not_scored',
          productionSources,
          invokedProductionMethods: [observed.productionEntrypoint],
          checkpoints: [{ label: 'common_prefix_before', state: observed.before }, { label: 'common_prefix_after', state: observed.after }],
          observed: scoredFailure ? null : { state: observed.after, effects: observed.effects ?? [] },
          invariantChecks: item.invariants.map(text => ({ text, passed: null, evidence: 'unobserved_after_terminal_missing_transition' })),
          reason: prefixPassed
            ? 'canonical_transition_missing_after_reachable_production_prefix'
            : capabilityFailurePassed
              ? 'mandatory_public_integration_contract_unavailable_in_android_app_runtime'
              : reachableGivenFailurePassed
                ? 'canonical_given_unreachable_after_executed_production_prefix'
                : 'production_prefix_not_established',
          diagnostics: { availability: observed.availability, givenPassed: false, prefixPassed, capabilityFailurePassed, reachableGivenFailurePassed, terminalFailure: observed.terminalFailure }
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
          observed: { state: observed.after, effects: observed.effects ?? [], orderedStates: observed.orderedStates ?? [] },
          invariantChecks: [],
          reason: 'canonical_given_not_established',
          diagnostics: { availability: observed.availability, givenPassed: false }
        };
      }
      const expectedEffects = item.expected.effects ?? [];
      const absentEffects = item.expected.absentEffects ?? [];
      const facts = invariantFacts(item.caseId, observed);
      const invariantChecks = item.invariants.map((text, index) => ({ text, passed: facts[index] === true, evidence: 'derived_from_runtime_before_after_or_ordered_effects' }));
      const statePassed = subset(observed.after, item.expected.state);
      const effectsPassed = expectedEffects.every(expected => observed.effects.some(actual => subset(actual, expected)));
      const absentPassed = absentEffects.every(name => observed.effects.every(actual => actual.name !== name));
      const orderedPassed = item.expected.orderedStates ? subset(observed.orderedStates, item.expected.orderedStates) : true;
      const passed = statePassed && effectsPassed && absentPassed && orderedPassed && invariantChecks.every(check => check.passed);
      return {
        caseId: item.caseId,
        traceDigest: item.traceDigest,
        status: passed ? 'pass' : 'fail',
        productionSources,
        invokedProductionMethods: [observed.productionEntrypoint],
        checkpoints: [{ label: 'before', state: observed.before }, { label: 'after', state: observed.after }],
        observed: { state: observed.after, effects: observed.effects, orderedStates: observed.orderedStates, orderedTimeline: observed.orderedTimeline ?? [] },
        invariantChecks,
        diagnostics: { availability: observed.availability, givenPassed: setupPassed, statePassed, effectsPassed, absentEffectsPassed: absentPassed, orderedStatesPassed: orderedPassed }
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
  runtime: observationsPath ? 'android_app_runtime_over_immutable_official_kotlin_java_source_slice' : 'debug_immutable_official_kotlin_java_source_slice',
  productionSourceCommit: role === 'agent' ? null : sourceManifest.sourceCommit,
  productionSourceHashes: productionSources,
  runtimeArtifact: fs.existsSync(apkPath ?? runtimeJar) ? { kind: apkPath ? 'installable_android_harness_apk' : 'debug_runtime_jar', sha256: crypto.createHash('sha256').update(fs.readFileSync(apkPath ?? runtimeJar)).digest('hex'), bytes: fs.statSync(apkPath ?? runtimeJar).size } : null,
  codeGeneration: { passed: false, changedProductionFiles: [] },
  compile: { passed: runtime.status === 0, scope: observationsPath ? 'installable_api37_android_harness' : 'debug_focused_immutable_source_slice', command: null },
  semantic: { passed: count('pass'), failed: count('fail'), notScored: count('not_scored'), total: rows.length, cases: rows },
  diagnostics: { adapter: runtime.status === 0 ? 'executed' : 'unavailable', runtimeCompile: runtime.status === 0, stderr: runtime.stderr?.trim() || null, nativeAndroidUiEvidence: observationsPath ? 'app_runtime_observer_collected' : 'not_collected', nativeDevice: nativeDevice ?? null, rawObservationLog: observationsPath ? path.relative(migration, observationsPath) : null, publicationEligible: Boolean(observationsPath) && runtime.status === 0 && polarityEligible }
};

fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`);
process.exit(runtime.status === 0 ? 0 : 2);
