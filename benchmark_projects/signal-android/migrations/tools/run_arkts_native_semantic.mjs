import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const arg = flag => process.argv[process.argv.indexOf(flag) + 1];
const optional = flag => process.argv.includes(flag) ? arg(flag) : null;
const project = path.resolve(arg('--project'));
const role = arg('--role');
const output = path.resolve(arg('--output'));
const migration = path.resolve(optional('--migration') ?? path.resolve(project, '..', '..'));
const contract = JSON.parse(fs.readFileSync(path.join(migration, 'canonical', 'transitions.json'), 'utf8'));
const app = JSON.parse(fs.readFileSync(path.join(project, 'AppScope', 'app.json5'), 'utf8'));
const hap = path.join(project, 'entry', 'build', 'default', 'outputs', 'default', 'entry-default-unsigned.hap');
const hdc = process.env.HDC ?? '/Users/z1an/Library/OpenHarmony/Sdk/23/toolchains/hdc';
const requestedTarget = process.env.HDC_TARGET ?? null;

const command = (args, check = true) => {
  const result = spawnSync(hdc, args, { encoding: 'utf8', timeout: 120000 });
  if (check && result.status !== 0) throw new Error(`hdc ${args.join(' ')} failed: ${result.stderr || result.stdout}`);
  return result;
};
const pause = milliseconds => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, milliseconds);
const subset = (actual, expected) => {
  if (expected === null || typeof expected !== 'object') return Object.is(actual, expected);
  if (Array.isArray(expected)) return Array.isArray(actual) && actual.length === expected.length && expected.every((item, index) => subset(actual[index], item));
  return actual !== null && typeof actual === 'object' && Object.entries(expected).every(([key, value]) => subset(actual[key], value));
};
const sameMembers = (left = [], right = []) => JSON.stringify([...left].sort()) === JSON.stringify([...right].sort());
const named = (observed, name) => (observed.effects ?? []).filter(effect => effect.name === name);

const invariantFacts = (caseId, observed) => {
  const before = observed.before ?? {};
  const after = observed.after ?? {};
  switch (caseId) {
    case 'mk_state_001_initialize_tabs': return [JSON.stringify(after.availableTabs) === JSON.stringify(['EMOJI', 'STICKER', 'GIF'])];
    case 'mk_state_002_restrict_fallback': return [after.preferredTab === before.preferredTab, Array.isArray(after.availableTabs) && after.availableTabs.every(tab => tab === 'EMOJI')];
    case 'mk_state_003_lift_restriction': return [after.selectedTab === before.preferredTab && after.availableTabs?.includes(before.preferredTab) === true];
    case 'mk_state_004_tab_clears_query': return [after.searchActive === before.searchActive];
    case 'mk_state_005_gif_initial_failure': return [after.isLoading === false && after.isLoadingMore === false];
    case 'mk_state_006_gif_retry_recovery': return [Array.isArray(before.gifs) && before.gifs.length === 0 && JSON.stringify(after.gifs) === JSON.stringify(['g1', 'g2'])];
    case 'mk_state_007_gif_pagination': return [JSON.stringify(after.gifs?.slice(0, before.gifs?.length)) === JSON.stringify(before.gifs), named(observed, 'getGifs')[0]?.offset === before.gifs?.length];
    case 'mk_state_008_sticker_tap_defers_send': return [named(observed, 'onSend').length === 0];
    case 'mk_state_009_confirmation_cancel': return [after.confirmation === null && named(observed, 'onSend').length === 0];
    case 'mk_state_010_confirmation_send_once': {
      const visibilityIndex = (observed.effects ?? []).findIndex(effect => effect.name === 'confirmationVisibility' && effect.value === false);
      const sendIndex = (observed.effects ?? []).findIndex(effect => effect.name === 'onSend');
      return [after.confirmation === null && sendIndex > visibilityIndex && named(observed, 'onSend')[0]?.confirmationAtCallback === null, named(observed, 'onSend').length === 1];
    }
    case 'sm_state_001_exit_multiselect': return [after.multiSelectEnabled === false && after.selectedPackIds?.length === 0 && JSON.stringify(after.installedPackIds) === JSON.stringify(before.installedPackIds)];
    case 'sm_state_002_install_lifecycle': return [JSON.stringify(observed.orderedTimeline) === JSON.stringify(['state:IN_PROGRESS', 'effect:installStickerPack', 'state:DOWNLOADED']), JSON.stringify(after.installedPackIds) === JSON.stringify(before.installedPackIds)];
    case 'sm_state_003_install_status_settles': return [named(observed, 'uninstallStickerPacks').length === 0, after.installedPackIds?.includes('p1') === true];
    case 'sm_state_004_drag_reorder': return [sameMembers(after.installedPackIds, before.installedPackIds)];
    case 'sm_state_005_drop_persists_order': return [observed.persistenceReopened === true && JSON.stringify(named(observed, 'setStickerPacksOrder')[0]?.packIds) === JSON.stringify(after.installedPackIds)];
    case 'sm_state_006_select_enters_multiselect': return [after.selectedPackIds?.every(id => after.installedPackIds?.includes(id)) === true];
    case 'sm_state_007_select_all_toggle': return [JSON.stringify(after.installedPackIds) === JSON.stringify(before.installedPackIds)];
    case 'sm_state_008_request_multi_delete': return [named(observed, 'uninstallStickerPacks').length === 0 && JSON.stringify(after.installedPackIds) === JSON.stringify(before.installedPackIds)];
    case 'sm_state_009_cancel_multi_delete': return [JSON.stringify(after.installedPackIds) === JSON.stringify(before.installedPackIds) && JSON.stringify(after.selectedPackIds) === JSON.stringify(before.selectedPackIds) && named(observed, 'uninstallStickerPacks').length === 0 && named(observed, 'enqueueLinkedOperation').length === 0];
    case 'sm_state_010_confirm_multi_delete': return [after.selectedPackIds?.every(id => !['a', 'c'].includes(id)) === true, named(observed, 'enqueueLinkedOperation').filter(effect => ['a', 'c'].includes(effect.packId) && effect.operation === 'REMOVE').length === 2];
    default: return [];
  }
};

const sourceFiles = [];
const collectSources = directory => {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== 'evaluator' && entry.name !== '.benchmark-evaluator') collectSources(target);
    } else if (/\.(?:ets|ts)$/.test(entry.name)) {
      const bytes = fs.readFileSync(target);
      sourceFiles.push({
        path: path.relative(project, target),
        sha256: crypto.createHash('sha256').update(bytes).digest('hex'),
        bytes: bytes.length
      });
    }
  }
};
collectSources(path.join(project, 'entry', 'src', 'main', 'ets'));

const unavailable = reason => {
  const cases = contract.cases.map(item => ({
    caseId: item.caseId,
    traceDigest: item.traceDigest,
    status: 'not_scored',
    reason,
    productionSources: sourceFiles,
    checkpoints: [{ label: 'before', state: null }, { label: 'after', state: null }],
    observed: { state: null, effects: [] },
    invariantChecks: []
  }));
  return {
    schemaVersion: 1,
    taskId: contract.taskId,
    platform: 'arkts',
    role,
    observationMode: 'runtime_state_transition',
    compile: { passed: fs.existsSync(hap) ? true : null, scope: 'api23_hvigor_hap' },
    semantic: { passed: 0, failed: 0, notScored: cases.length, total: cases.length, cases },
    diagnostics: { adapter: 'unavailable', reason, nativeArkvmUiEvidence: 'not_collected', hostRunnerUsedForScoring: false, publicationEligible: false }
  };
};

let report;
try {
  if (!fs.existsSync(hap)) throw new Error('arkts_hap_not_built');
  if (!fs.existsSync(hdc)) throw new Error('api23_hdc_unavailable');
  const targets = command(['list', 'targets']).stdout.split(/\r?\n/).map(value => value.trim()).filter(value => value && value !== '[Empty]');
  const target = requestedTarget ?? targets[0];
  if (!target || !targets.includes(target)) throw new Error('no_connected_api23_arkvm_target');

  const install = command(['-t', target, 'install', '-r', hap]);
  command(['-t', target, 'shell', 'hilog', '-r']);
  command(['-t', target, 'shell', 'aa', 'force-stop', '-b', app.app.bundleName], false);
  const launch = command(['-t', target, 'shell', 'aa', 'start', '-a', 'EntryAbility', '-b', app.app.bundleName]);

  let hilog = '';
  for (let attempt = 0; attempt < 40; attempt += 1) {
    pause(250);
    hilog = command(['-t', target, 'shell', 'hilog', '-x']).stdout;
    if (hilog.includes(`BENCHMARK_COMPLETE:${contract.taskId}`)) break;
  }
  if (!hilog.includes(`BENCHMARK_COMPLETE:${contract.taskId}`)) throw new Error('native_transition_observer_timeout');

  const observations = new Map();
  const rawRows = [];
  for (const line of hilog.split(/\r?\n/)) {
    const marker = 'BENCHMARK_CASE:';
    const index = line.indexOf(marker);
    if (index < 0) continue;
    const json = line.slice(index + marker.length).trim();
    const row = JSON.parse(json);
    if (observations.has(row.caseId)) throw new Error(`duplicate_native_transition_observer_${row.caseId}`);
    observations.set(row.caseId, row);
    rawRows.push(json);
  }
  if (observations.size !== contract.cases.length) throw new Error(`native_transition_observer_count_${observations.size}`);
  const ownerIds = new Set([...observations.values()].map(row => row.ownerId));
  if (ownerIds.size !== 1 || ownerIds.has(undefined) || ownerIds.has(null)) throw new Error('native_page_owner_identity_mismatch');

  const logs = path.join(migration, 'provenance', 'runtime-logs');
  fs.mkdirSync(logs, { recursive: true });
  const rawLog = path.join(logs, `arkts-${role}.jsonl`);
  fs.writeFileSync(rawLog, `${rawRows.join('\n')}\n`);
  fs.writeFileSync(path.join(logs, `arkts-${role}-transport.json`), `${JSON.stringify({
    deviceLock: process.env.BENCHMARK_DEVICE_LOCK_PATH ?? null,
    deviceLockImplementation: process.env.BENCHMARK_DEVICE_LOCK_IMPLEMENTATION ?? null,
    target,
    apiVersion: command(['-t', target, 'shell', 'param', 'get', 'const.ohos.apiversion']).stdout.trim(),
    bundleName: app.app.bundleName,
    entryAbility: 'EntryAbility',
    installStdout: install.stdout.trim(),
    launchStdout: launch.stdout.trim(),
    status: 'completed'
  }, null, 2)}\n`);

  const cases = contract.cases.map(item => {
    const observed = observations.get(item.caseId);
    const expectedEffects = item.expected.effects ?? [];
    const absentEffects = item.expected.absentEffects ?? [];
    const facts = invariantFacts(item.caseId, observed);
    const invariantChecks = item.invariants.map((text, index) => ({
      text,
      passed: facts[index] === true,
      evidence: 'derived_from_native_arkvm_before_after_or_effects'
    }));
    const statePassed = subset(observed.after, item.expected.state);
    const effectsPassed = expectedEffects.every(expected => observed.effects.some(actual => subset(actual, expected)));
    const absentPassed = absentEffects.every(name => observed.effects.every(actual => actual.name !== name));
    const orderedPassed = item.expected.orderedStates ? subset(observed.orderedStates, item.expected.orderedStates) : true;
    const givenPassed = subset(observed.given, item.given);
    const ownerPassed = typeof observed.ownerAction === 'string'
      && observed.ownerAction.length > 0
      && observed.entryLifecycle === 'Index.aboutToAppear'
      && observed.availability === 'executed_arkvm_entryability_arkui_page_owner';
    const passed = givenPassed && ownerPassed && statePassed && effectsPassed && absentPassed && orderedPassed && invariantChecks.every(check => check.passed);
    return {
      caseId: item.caseId,
      traceDigest: item.traceDigest,
      status: passed ? 'pass' : 'fail',
      productionSources: sourceFiles,
      invokedProductionMethods: [observed.productionEntrypoint],
      checkpoints: [{ label: 'before', state: observed.before }, { label: 'after', state: observed.after }],
      observed: { state: observed.after, effects: observed.effects, orderedStates: observed.orderedStates ?? [] },
      invariantChecks,
      diagnostics: { availability: observed.availability, givenPassed, ownerPassed, statePassed, effectsPassed, absentEffectsPassed: absentPassed, orderedStatesPassed: orderedPassed, persistenceReopened: observed.persistenceReopened ?? false }
    };
  });
  const count = status => cases.filter(item => item.status === status).length;
  const polarityEligible = role === 'base'
    ? cases.every(item => item.status === 'fail')
    : role === 'final'
      ? cases.every(item => item.status === 'pass')
      : cases.every(item => item.status !== 'not_scored');
  const hapBytes = fs.readFileSync(hap);
  report = {
    schemaVersion: 1,
    taskId: contract.taskId,
    platform: 'arkts',
    role,
    observationMode: 'runtime_state_transition',
    runtime: 'api23_arkvm_entryability_arkui_page_owned_controller',
    productionSourceHashes: sourceFiles,
    runtimeArtifact: { kind: 'api23_hap', sha256: crypto.createHash('sha256').update(hapBytes).digest('hex'), bytes: hapBytes.length },
    compile: { passed: true, scope: 'api23_hvigor_hap' },
    semantic: { passed: count('pass'), failed: count('fail'), notScored: count('not_scored'), total: cases.length, cases },
    diagnostics: {
      adapter: 'executed',
      target,
      apiVersion: 23,
      entryAbilityStarted: true,
      pageOwnerId: [...ownerIds][0],
      nativeArkvmUiEvidence: 'entryability_page_owner_runtime_observer_collected',
      rawObservationLog: path.relative(migration, rawLog),
      hostRunnerUsedForScoring: false,
      publicationEligible: polarityEligible
    }
  };
} catch (error) {
  report = unavailable(error.message);
}

fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`);
process.stdout.write(`${JSON.stringify({ output, role, passed: report.semantic.passed, failed: report.semantic.failed, notScored: report.semantic.notScored, reason: report.diagnostics.reason ?? null })}\n`);
process.exit(report.semantic.notScored === 0 ? 0 : 2);

