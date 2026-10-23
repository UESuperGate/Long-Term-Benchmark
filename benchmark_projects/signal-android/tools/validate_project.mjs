import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(process.argv[2] ?? path.join(path.dirname(new URL(import.meta.url).pathname), '..'));
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const requireValue = (condition, message) => { if (!condition) throw new Error(message); };
const stable = value => JSON.stringify(value);
const walk = directory => fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
  const target = path.join(directory, entry.name);
  return entry.isDirectory() ? [target, ...walk(target)] : [target];
});
const hasArgv = (argv, value) => Array.isArray(argv) && argv.includes(value);

const catalog = read(path.join(root, 'catalog.json'));
requireValue(catalog.status === 'ready', 'catalog must be ready after the formal model run');
requireValue(catalog.latestAgentResult === '../results/deep_mining_minimax_m3_runtime_20261023/run-manifest.json', 'catalog formal result pointer');
requireValue(stable(catalog.acceptedTaskIds) === stable(['01_media_keyboard', '02_sticker_management', '03_media_editor', '06_numberless_registration']), 'unexpected acceptedTaskIds');
requireValue(stable(catalog.reviewTaskIds) === stable(['04_group_termination']), 'unexpected reviewTaskIds');
requireValue(stable(catalog.excludedTaskIds) === stable(['05_member_labels']), 'unexpected excludedTaskIds');

const legacyTaskIds = ['01_media_keyboard', '02_sticker_management'];
const focusedTaskIds = ['03_media_editor', '06_numberless_registration'];

const runnerSmoke = read(path.join(root, 'provenance', 'runner-calibration-smoke.json'));
requireValue(runnerSmoke.valid === true, 'unified runner calibration smoke is not valid');
requireValue(runnerSmoke.lockImplementation === 'python_fcntl.flock', 'device lock implementation must be Python fcntl.flock');

const noChange = read(path.join(root, 'provenance', 'no-change-agent-control.json'));
requireValue(noChange.valid === true && noChange.openCodeRun === false, 'no-change control must be valid and must not claim a model run');
requireValue(noChange.patchArchivedBeforePrepare === true && noChange.rows.length === 4, 'no-change control coverage is incomplete');

for (const taskId of legacyTaskIds) {
  const taskRoot = path.join(root, 'tasks', taskId);
  const migration = path.join(root, 'migrations', taskId);
  for (const name of ['task.json', 'requirement.md', 'evidence.json', 'raw_release_evidence.json', 'transitions.draft.json', 'transitions.json', 'observer_rules.json', 'arkts_bindings.json', 'migration_validation.json']) {
    requireValue(fs.existsSync(path.join(taskRoot, name)), `${taskId}: missing ${name}`);
  }
  for (const name of ['manifest.json', 'execution.json', 'canonical/transitions.json', 'arkts/transitions.json', 'arkts/bindings.json', 'android/task.json', 'results/manifest.json']) {
    requireValue(fs.existsSync(path.join(migration, name)), `${taskId}: missing migration ${name}`);
  }

  const canonical = read(path.join(taskRoot, 'transitions.json'));
  const migrationCanonical = read(path.join(migration, 'canonical/transitions.json'));
  const arktsContract = read(path.join(migration, 'arkts/transitions.json'));
  requireValue(canonical.cases.length === 10, `${taskId}: expected ten canonical cases`);
  requireValue(stable(canonical) === stable(migrationCanonical) && stable(canonical) === stable(arktsContract), `${taskId}: canonical copies differ`);
  const ids = canonical.cases.map(item => item.caseId);
  const digests = canonical.cases.map(item => item.traceDigest);
  requireValue(new Set(ids).size === 10 && new Set(digests).size === 10, `${taskId}: duplicate case identity`);

  const bindings = read(path.join(taskRoot, 'arkts_bindings.json'));
  requireValue(bindings.cases.length === 10, `${taskId}: binding count`);
  for (const item of canonical.cases) {
    const binding = bindings.cases.find(row => row.caseId === item.caseId);
    requireValue(binding?.traceDigest === item.traceDigest, `${taskId}: binding mismatch ${item.caseId}`);
  }
  requireValue(stable(bindings) === stable(read(path.join(migration, 'arkts/bindings.json'))), `${taskId}: migration binding copy differs`);

  const execution = read(path.join(migration, 'execution.json'));
  for (const platform of ['android', 'arkts']) {
    const spec = execution[platform];
    const lock = `/tmp/long-term-benchmark-${platform}-device.lock`;
    for (const key of ['buildCommand', 'semanticCommand', 'agentPrepareCommand', 'agentVisibleBuildCommand', 'agentBuildCommand', 'agentSemanticCommand']) {
      requireValue(Array.isArray(spec[key]) && spec[key].length > 0, `${taskId}/${platform}: ${key} argv required`);
    }
    requireValue(spec.buildCommand.some(value => value.includes('{migration}/../tools/')), `${taskId}/${platform}: build command must resolve from {migration}`);
    requireValue(['{project}', '{role}', '{output}'].every(token => hasArgv(spec.semanticCommand, token)), `${taskId}/${platform}: semantic placeholders required`);
    requireValue(['{project}', '{role}', '{output}'].every(token => hasArgv(spec.agentSemanticCommand, token)), `${taskId}/${platform}: agent semantic placeholders required`);
    for (const command of [spec.semanticCommand, spec.agentSemanticCommand]) {
      requireValue(hasArgv(command, '{migration}/../tools/with_device_lock.py') && hasArgv(command, lock), `${taskId}/${platform}: full device sequence is not locked`);
    }
    requireValue(spec.reportRelativePath.includes('{role}'), `${taskId}/${platform}: report role placeholder required`);
    for (const key of ['baseProject', 'finalProject']) {
      const project = path.join(migration, spec[key]);
      requireValue(fs.statSync(project).isDirectory(), `${taskId}/${platform}: ${key} is not a directory`);
      requireValue(fs.existsSync(path.join(project, platform === 'android' ? 'settings.gradle.kts' : 'build-profile.json5')), `${taskId}/${platform}: ${key} is not a build root`);
    }
  }

  for (const platform of ['android', 'arkts']) {
    for (const role of ['base', 'final']) {
      const report = read(path.join(migration, 'results', `${platform}-${role}.json`));
      const expected = role === 'base' ? { passed: 0, failed: 10 } : { passed: 10, failed: 0 };
      requireValue(report.observationMode === 'runtime_state_transition' && report.compile.passed === true, `${taskId}/${platform}/${role}: native runtime did not compile`);
      requireValue(report.semantic.total === 10 && report.semantic.notScored === 0, `${taskId}/${platform}/${role}: incomplete native score`);
      requireValue(report.semantic.passed === expected.passed && report.semantic.failed === expected.failed, `${taskId}/${platform}/${role}: wrong calibration polarity`);
      requireValue(report.diagnostics?.publicationEligible === true, `${taskId}/${platform}/${role}: native report is not publication eligible`);
      if (platform === 'android') requireValue(report.diagnostics.nativeAndroidUiEvidence === 'app_runtime_observer_collected', `${taskId}/${role}: Android app observer evidence missing`);
      if (platform === 'arkts') requireValue(report.diagnostics.nativeArkvmUiEvidence === 'entryability_page_owner_runtime_observer_collected' && report.diagnostics.hostRunnerUsedForScoring === false, `${taskId}/${role}: ArkVM page-owner evidence missing`);
      for (const item of report.semantic.cases) {
        requireValue(item.checkpoints?.some(row => row.label === 'before') && item.checkpoints?.some(row => row.label === 'after'), `${taskId}/${platform}/${role}/${item.caseId}: before/after missing`);
        requireValue(Array.isArray(item.observed?.effects), `${taskId}/${platform}/${role}/${item.caseId}: effects missing`);
        requireValue(Array.isArray(item.invariantChecks) && item.invariantChecks.length > 0, `${taskId}/${platform}/${role}/${item.caseId}: invariants missing`);
        requireValue(Array.isArray(item.productionSources) && item.productionSources.length > 0, `${taskId}/${platform}/${role}/${item.caseId}: production hashes missing`);
      }
    }

    const agent = read(path.join(migration, 'results', `${platform}-agent.json`));
    requireValue(typeof agent.codeGeneration.passed === 'boolean' && agent.compile.passed === true, `${taskId}/${platform}: formal model metrics missing`);
    requireValue(agent.observationMode === 'runtime_state_transition', `${taskId}/${platform}: formal runtime mode missing`);
    requireValue(agent.semantic.cases.length === 10 && agent.semantic.cases.every(row => ['pass', 'fail'].includes(row.status)), `${taskId}/${platform}: formal agent cases must all be scored`);
    requireValue(agent.semantic.notScored === 0 && agent.semantic.total === 10, `${taskId}/${platform}: formal agent score is incomplete`);
    requireValue(agent.diagnostics?.publicationEligible === true, `${taskId}/${platform}: formal agent report is not publication eligible`);
    for (const item of agent.semantic.cases) {
      const expected = canonical.cases.find(row => row.caseId === item.caseId);
      requireValue(expected?.traceDigest === item.traceDigest, `${taskId}/${platform}/${item.caseId}: formal agent contract mismatch`);
      requireValue(Array.isArray(item.checkpoints) && item.checkpoints.length >= 2, `${taskId}/${platform}/${item.caseId}: formal agent checkpoints missing`);
      requireValue(Array.isArray(item.productionSources) && item.productionSources.length > 0, `${taskId}/${platform}/${item.caseId}: formal agent production provenance missing`);
    }
  }

  const validation = read(path.join(taskRoot, 'migration_validation.json'));
  requireValue(validation.status === 'ready' && validation.contractParity.status === 'passed' && validation.fourWayNativeCalibration.status === 'passed' && validation.agentEvaluation.status === 'complete', `${taskId}: migration validation status`);
  for (const role of ['base', 'final']) {
    const profile = read(path.join(migration, 'arkts', role, 'build-profile.json5'));
    requireValue(profile.app.products[0].compileSdkVersion === 23 && profile.app.products[0].targetSdkVersion === 23, `${taskId}/${role}: API23 required`);
  }

  for (const platform of ['android', 'arkts']) {
    const row = noChange.rows.find(item => item.taskId === taskId && item.platform === platform);
    requireValue(row?.valid === true && row.score.passed === 0 && row.score.failed === 10 && row.score.notScored === 0, `${taskId}/${platform}: no-change agent must fail 0/10`);
    requireValue(row.candidateEvaluatorFilesBeforePrepare.length === 0, `${taskId}/${platform}: candidate contained evaluator files before prepare`);
    requireValue(row.patch.bytes === 0 && row.patch.sha256 === 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', `${taskId}/${platform}: no-change patch archive is invalid`);
    requireValue(row.hiddenAudit.forbiddenTokens.length === 0 && row.hiddenAudit.exactFinalProductionFileHashMatches.length === 0 && row.hiddenAudit.productionLogicInjected === false, `${taskId}/${platform}: hidden probe audit failed`);
    requireValue(row.hiddenAudit.injectedFileRecords.length > 0, `${taskId}/${platform}: injected files were not audited`);
    if (platform === 'arkts') requireValue(row.hiddenAudit.injectedRoots.includes('entry/src/main/ets/.benchmark-evaluator'), `${taskId}/arkts: actual injected root was not audited`);
  }

  for (const platform of ['android', 'arkts']) for (const role of ['base', 'final']) {
    const project = path.join(migration, platform, role);
    const entries = walk(project);
    requireValue(!entries.some(item => ['.benchmark-evaluator', 'evaluator-src'].includes(path.basename(item))), `${taskId}/${platform}/${role}: hidden evaluator leaked into candidate root`);
    for (const item of entries.filter(file => fs.statSync(file).isFile() && /\.(?:java|kt|ts|ets)$/.test(file))) {
      requireValue(!/(?:traceDigest|mk_state_|sm_state_|source_transition_conformance)/.test(fs.readFileSync(item, 'utf8')), `${item}: production contains evaluator identity`);
    }
  }
}

for (const taskId of focusedTaskIds) {
  const taskRoot = path.join(root, 'tasks', taskId);
  const migration = path.join(root, 'migrations', taskId);
  for (const name of ['task.json', 'requirement.md', 'evidence.json', 'raw_release_evidence.json', 'transitions.draft.json', 'transitions.json']) {
    requireValue(fs.existsSync(path.join(taskRoot, name)), `${taskId}: missing ${name}`);
  }
  for (const name of ['manifest.json', 'execution.json', 'canonical/transitions.json', 'arkts/transitions.json', 'arkts/bindings.json', 'android/task.json', 'results/manifest.json', 'results/agent-evaluation-summary.json', 'results/agent-bundle-audit.json']) {
    requireValue(fs.existsSync(path.join(migration, name)), `${taskId}: missing migration ${name}`);
  }

  const canonical = read(path.join(taskRoot, 'transitions.json'));
  const migrationCanonical = read(path.join(migration, 'canonical/transitions.json'));
  const arktsContract = read(path.join(migration, 'arkts/transitions.json'));
  requireValue(canonical.cases.length === 10, `${taskId}: expected ten canonical cases`);
  requireValue(stable(canonical) === stable(migrationCanonical) && stable(canonical) === stable(arktsContract), `${taskId}: canonical copies differ`);
  requireValue(new Set(canonical.cases.map(item => item.caseId)).size === 10, `${taskId}: duplicate case identity`);
  requireValue(new Set(canonical.cases.map(item => item.traceDigest)).size === 10, `${taskId}: duplicate transition digest`);

  const bindings = read(path.join(migration, 'arkts/bindings.json'));
  requireValue(Object.keys(bindings.cases).length === 10, `${taskId}: binding count`);
  requireValue(bindings.sourceObserver === false, `${taskId}: ArkTS binding must not use a source observer`);
  for (const item of canonical.cases) {
    requireValue(typeof bindings.cases[item.caseId] === 'string', `${taskId}: binding mismatch ${item.caseId}`);
  }

  for (const platform of ['android', 'arkts']) {
    for (const role of ['base', 'final']) {
      const report = read(path.join(migration, 'results', `${platform}-${role}.json`));
      const expected = role === 'base' ? { passed: 0, failed: 10 } : { passed: 10, failed: 0 };
      requireValue(report.compile.passed === true, `${taskId}/${platform}/${role}: production compile failed`);
      requireValue(report.semantic.total === 10 && report.semantic.notScored === 0, `${taskId}/${platform}/${role}: incomplete native score`);
      requireValue(report.semantic.passed === expected.passed && report.semantic.failed === expected.failed, `${taskId}/${platform}/${role}: wrong calibration polarity`);
      requireValue(typeof report.observationMode === 'string' && report.observationMode.includes('runtime'), `${taskId}/${platform}/${role}: runtime observation missing`);
      requireValue(report.sourceObserver !== true && report.diagnostics?.sourceObserver !== true, `${taskId}/${platform}/${role}: source observer used for scoring`);
      requireValue(report.diagnostics?.roleAffectsVerdict !== true, `${taskId}/${platform}/${role}: role affects verdict`);
      for (const item of report.semantic.cases) {
        const expectedCase = canonical.cases.find(row => row.caseId === item.caseId);
        requireValue(expectedCase?.traceDigest === item.traceDigest, `${taskId}/${platform}/${role}/${item.caseId}: contract mismatch`);
        requireValue(Array.isArray(item.checkpoints) && item.checkpoints.length >= 2, `${taskId}/${platform}/${role}/${item.caseId}: checkpoints missing`);
        requireValue(Array.isArray(item.productionSources) && item.productionSources.length > 0, `${taskId}/${platform}/${role}/${item.caseId}: production provenance missing`);
      }
    }

    const controlDirectory = platform === 'android' ? 'android-controls' : 'arkts-controls';
    for (const [name, expectedPassed] of [['no-change-agent.json', 0], ['known-final-agent.json', 10]]) {
      const report = read(path.join(migration, 'results', controlDirectory, name));
      requireValue(report.compile.passed === true, `${taskId}/${platform}/${name}: control compile failed`);
      requireValue(report.semantic.passed === expectedPassed && report.semantic.notScored === 0 && report.semantic.total === 10, `${taskId}/${platform}/${name}: control polarity failed`);
    }
  }

  const summary = read(path.join(migration, 'results', 'agent-evaluation-summary.json'));
  requireValue(summary.runs.length === 2, `${taskId}: expected two platform agent runs`);
  requireValue(summary.benchmarkMetrics.codeGeneration.total === 2 && summary.benchmarkMetrics.compile.passed === 2, `${taskId}: formal model metrics missing`);
  requireValue(summary.benchmarkMetrics.semanticTestcase.scored === 20 && summary.benchmarkMetrics.semanticTestcase.notScored === 0, `${taskId}: formal model semantic score incomplete`);
  for (const run of summary.runs) {
    requireValue(typeof run.codeGeneration.passed === 'boolean' && run.compile.passed === true, `${taskId}/${run.platform}: independent metrics missing`);
    requireValue(run.semanticTestcase.total === 10 && run.semanticTestcase.notScored === 0, `${taskId}/${run.platform}: agent cases are incomplete`);
    requireValue(run.candidatePatch.reconstructionVerified === true, `${taskId}/${run.platform}: candidate reconstruction failed`);
    requireValue(run.semanticFeedbackDuringGeneration === false && run.credentialAudit.apiKeyRecorded === false, `${taskId}/${run.platform}: generation integrity failed`);
    for (const item of ['agent.patch', 'generated-files.json']) {
      requireValue(fs.existsSync(path.join(migration, 'results', 'agent-runs', summary.runId, run.platform, item)), `${taskId}/${run.platform}: missing archived ${item}`);
    }
  }
  requireValue(read(path.join(migration, 'results', 'agent-bundle-audit.json')).status === 'passed', `${taskId}: agent bundle audit failed`);
}

const lockSource = fs.readFileSync(path.join(root, 'migrations', 'tools', 'with_device_lock.py'), 'utf8');
requireValue(lockSource.includes('fcntl.flock'), 'device lock wrapper must call fcntl.flock');

const residueNames = new Set(['.no-change-agent-control', '.build-home', '.npm', '.arkts-tool-home', 'build', '.gradle', '.hvigor', 'oh_modules', '__pycache__']);
const binaryExtensions = /\.(?:apk|hap|aab|class|dex)$/i;
const allEntries = walk(root);
const cacheResidue = allEntries.filter(item => fs.statSync(item).isDirectory() && residueNames.has(path.basename(item)));
const binaryResidue = allEntries.filter(item => fs.statSync(item).isFile() && binaryExtensions.test(item));
requireValue(cacheResidue.length === 0, `cache residue: ${cacheResidue.join(', ')}`);
requireValue(binaryResidue.length === 0, `binary residue: ${binaryResidue.join(', ')}`);

console.log(JSON.stringify({
  valid: true,
  projectId: catalog.projectId,
  tasks: catalog.acceptedTaskIds,
  casesPerTask: 10,
  nativeCalibration: 'android+arkts base 0/10 final 10/10 for all accepted tasks',
  noChangeAgentControl: 'android+arkts 0/10 for all accepted tasks',
  modelAgentStatus: 'complete',
  cacheResidue: [],
  binaryResidue: []
}, null, 2));
