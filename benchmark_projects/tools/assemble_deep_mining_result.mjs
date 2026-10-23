import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const benchmarkRoot = path.resolve(here, '..');
const repositoryRoot = path.resolve(benchmarkRoot, '..');
const runId = 'deep_mining_minimax_m3_runtime_20261023';
const outputRoot = path.join(benchmarkRoot, 'results', runId);

const taskSpecs = [
  ['signal-android', '03_media_editor'],
  ['signal-android', '06_numberless_registration'],
  ['wordpress-android', '03_site_picker'],
  ['wordpress-android', '04_new_stats'],
  ['wikipedia-android', '03_explore_feed'],
  ['wikipedia-android', '04_reading_lists']
];

const projectMetadata = {
  'signal-android': {
    displayName: 'Signal Android',
    source: 'https://github.com/signalapp/Signal-Android.git'
  },
  'wordpress-android': {
    displayName: 'WordPress Android',
    source: 'https://github.com/wordpress-mobile/WordPress-Android.git'
  },
  'wikipedia-android': {
    displayName: 'Wikipedia Android',
    source: 'https://github.com/wikimedia/apps-android-wikipedia.git'
  }
};

const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const stable = value => JSON.stringify(value);
const relative = file => path.relative(repositoryRoot, file).split(path.sep).join('/');
const hashFile = file => {
  const contents = fs.readFileSync(file);
  return {
    path: relative(file),
    bytes: contents.length,
    sha256: crypto.createHash('sha256').update(contents).digest('hex')
  };
};
const roundRate = (passed, total) => total === 0 ? null : Number((passed / total).toFixed(6));
const metric = (passed, total) => ({ passed, total, rate: roundRate(passed, total) });

function semanticCounts(report) {
  const semantic = report.semanticTestcase ?? report.semantic ?? {};
  const summary = semantic.summary ?? semantic;
  if ([summary.passed, summary.failed, summary.notScored, summary.total].every(Number.isInteger)) {
    return {
      passed: summary.passed,
      failed: summary.failed,
      notScored: summary.notScored,
      total: summary.total
    };
  }
  const cases = Array.isArray(semantic.cases) ? semantic.cases : [];
  const passed = cases.filter(item => item.status === 'pass').length;
  const failed = cases.filter(item => item.status === 'fail').length;
  const notScored = cases.filter(item => ['not_scored', 'notScored'].includes(item.status)).length;
  return { passed, failed, notScored, total: cases.length };
}

function pushError(errors, condition, message) {
  if (!condition) errors.push(message);
}

const tasks = [];
const rows = [];
const artifacts = [];
const calibrationRows = [];
const validationRows = [];
const globalCaseIds = new Set();
const globalDigests = new Set();
const isolationWarnings = [];
const startedAtValues = [];
const finishedAtValues = [];

for (const [projectId, taskId] of taskSpecs) {
  const projectRoot = path.join(benchmarkRoot, projectId);
  const taskRoot = path.join(projectRoot, 'tasks', taskId);
  const migrationRoot = path.join(projectRoot, 'migrations', taskId);
  const resultsRoot = path.join(migrationRoot, 'results');
  const task = readJson(path.join(taskRoot, 'task.json'));
  const canonical = readJson(path.join(taskRoot, 'transitions.json'));
  const migrationCanonical = readJson(path.join(migrationRoot, 'canonical', 'transitions.json'));
  const summaryFile = path.join(resultsRoot, 'agent-evaluation-summary.json');
  const summary = readJson(summaryFile);
  const taskErrors = [];

  pushError(taskErrors, task.status === 'accepted', 'task status is not accepted');
  pushError(taskErrors, Array.isArray(canonical.cases) && canonical.cases.length === 10, 'canonical case count is not 10');
  pushError(taskErrors, stable(canonical) === stable(migrationCanonical), 'task and migration canonical contracts differ');
  for (const item of canonical.cases ?? []) {
    pushError(taskErrors, typeof item.caseId === 'string' && !globalCaseIds.has(item.caseId), `duplicate global caseId: ${item.caseId}`);
    pushError(taskErrors, typeof item.traceDigest === 'string' && !globalDigests.has(item.traceDigest), `duplicate global traceDigest: ${item.traceDigest}`);
    globalCaseIds.add(item.caseId);
    globalDigests.add(item.traceDigest);
  }

  tasks.push({
    projectId,
    taskId,
    title: task.title,
    status: task.status,
    android: task.android,
    releaseNotes: task.releaseNotes,
    functionalAreas: task.functionalAreas,
    caseCount: canonical.cases.length
  });

  for (const platform of ['android', 'arkts']) {
    for (const role of ['base', 'final']) {
      const reportFile = path.join(resultsRoot, `${platform}-${role}.json`);
      const report = readJson(reportFile);
      const counts = semanticCounts(report);
      const expectedPassed = role === 'base' ? 0 : 10;
      const expectedFailed = role === 'base' ? 10 : 0;
      const errors = [];
      pushError(errors, report.compile?.passed === true, 'production compile did not pass');
      pushError(errors, counts.passed === expectedPassed && counts.failed === expectedFailed, `wrong polarity ${counts.passed}/${counts.total}`);
      pushError(errors, counts.notScored === 0 && counts.total === 10, 'calibration has unscored or missing cases');
      pushError(errors, typeof report.observationMode === 'string' && report.observationMode.includes('runtime'), 'not a runtime observation report');
      pushError(errors, report.sourceObserver !== true && report.diagnostics?.sourceObserver !== true, 'source observer used for verdict');
      pushError(errors, report.diagnostics?.roleAffectsVerdict !== true, 'role affects verdict');
      calibrationRows.push({
        projectId,
        taskId,
        platform,
        role,
        valid: errors.length === 0,
        compile: report.compile?.passed === true,
        semanticTestcase: counts,
        observationMode: report.observationMode,
        report: relative(reportFile),
        errors
      });
      taskErrors.push(...errors.map(error => `${platform}/${role}: ${error}`));
    }

    const run = summary.runs?.find(item => item.platform === platform);
    const errors = [];
    pushError(errors, Boolean(run), 'agent run missing from summary');
    const semantic = run ? semanticCounts(run) : { passed: 0, failed: 0, notScored: 10, total: 10 };
    if (run) {
      pushError(errors, typeof run.codeGeneration?.passed === 'boolean', 'code generation metric missing');
      pushError(errors, run.compile?.passed === true, 'application compile did not pass');
      pushError(errors, semantic.notScored === 0 && semantic.total === 10, 'agent semantic score is incomplete');
      pushError(errors, run.semanticFeedbackDuringGeneration === false, 'semantic feedback was exposed during generation');
      pushError(errors, run.candidatePatch?.reconstructionVerified === true, 'candidate patch reconstruction is unverified');
      pushError(errors, run.credentialAudit?.apiKeyRecorded !== true, 'API key was recorded');
      if (run.startedAt) startedAtValues.push(new Date(run.startedAt));
      if (run.finishedAt) finishedAtValues.push(new Date(run.finishedAt));
      if (run.availability === 'isolation_unverified' || run.runIntegrity?.isolation === 'isolation_unverified') {
        isolationWarnings.push({ projectId, taskId, platform, diagnostic: 'isolation_unverified' });
      }
    }

    const reportFile = path.join(resultsRoot, `${platform}-agent.json`);
    const patchFile = path.join(resultsRoot, 'agent-patches', `${platform}-agent.patch`);
    const generatedFile = path.join(resultsRoot, 'agent-patches', `${platform}-agent-generated-files.json`);
    for (const file of [reportFile, patchFile, generatedFile]) {
      pushError(errors, fs.existsSync(file), `missing artifact: ${relative(file)}`);
    }

    const row = {
      projectId,
      taskId,
      platform,
      codeGeneration: run?.codeGeneration?.passed ?? false,
      compile: run?.compile?.passed ?? false,
      semanticTestcase: semantic,
      report: relative(reportFile),
      summary: relative(summaryFile)
    };
    rows.push(row);
    validationRows.push({ projectId, taskId, platform, valid: errors.length === 0, errors });
    taskErrors.push(...errors.map(error => `${platform}/agent: ${error}`));

    if ([reportFile, patchFile, generatedFile].every(fs.existsSync)) {
      artifacts.push({
        projectId,
        taskId,
        platform,
        report: hashFile(reportFile),
        summary: hashFile(summaryFile),
        patch: hashFile(patchFile),
        generatedFiles: hashFile(generatedFile)
      });
    }
  }

  pushError(taskErrors, summary.benchmarkMetrics?.semanticTestcase?.notScored === 0, 'task summary contains notScored cases');
}

const summarizeRows = selected => ({
  taskRuns: selected.length,
  codeGeneration: metric(selected.filter(row => row.codeGeneration).length, selected.length),
  compile: metric(selected.filter(row => row.compile).length, selected.length),
  semanticTestcase: metric(
    selected.reduce((total, row) => total + row.semanticTestcase.passed, 0),
    selected.reduce((total, row) => total + row.semanticTestcase.total, 0)
  )
});

const platforms = Object.fromEntries(['android', 'arkts'].map(platform => [
  platform,
  summarizeRows(rows.filter(row => row.platform === platform))
]));
const projects = Object.fromEntries(Object.keys(projectMetadata).map(projectId => [
  projectId,
  Object.fromEntries(['android', 'arkts'].map(platform => [
    platform,
    summarizeRows(rows.filter(row => row.projectId === projectId && row.platform === platform))
  ]))
]));
const metrics = summarizeRows(rows);
const allValid = validationRows.every(row => row.valid)
  && calibrationRows.every(row => row.valid)
  && globalCaseIds.size === 60
  && globalDigests.size === 60;

const startedAt = new Date(Math.min(...startedAtValues.map(value => value.getTime())));
const completedAt = new Date(Math.max(...finishedAtValues.map(value => value.getTime())));
const formalEvaluation = {
  startedAt: startedAt.toISOString(),
  completedAt: completedAt.toISOString(),
  elapsedSeconds: Math.round((completedAt - startedAt) / 1000),
  timingPolicy: 'overall wall clock from first top-level model task start to last top-level model task finish; subagent time is not added separately'
};

const manifest = {
  schemaVersion: 1,
  runId,
  status: allValid ? 'complete' : 'invalid',
  scope: 'Six newly mined Signal, WordPress, and Wikipedia Android long-horizon tasks with matched ArkTS migrations',
  projects: Object.entries(projectMetadata).map(([projectId, metadata]) => ({
    projectId,
    ...metadata,
    catalog: `${projectId}/catalog.json`
  })),
  tasks,
  agent: {
    runner: 'OpenCode',
    runnerVersion: '2.0.20',
    provider: 'MiniMax token plan',
    model: 'MiniMax-M3',
    modelId: 'minimax-token-plan/MiniMax-M3',
    endpoint: 'https://api.minimaxi.com/v1',
    timeoutSecondsPerTask: 3600,
    subagentsAllowed: true,
    semanticFeedbackDuringGeneration: false,
    apiKeyRecorded: false
  },
  formalAgentEvaluation: formalEvaluation,
  environment: {
    android: {
      compileSdk: 37,
      targetSdk: 37,
      minSdk: 23,
      emulator: { serial: 'emulator-5554', apiLevel: 37, androidRelease: '17' },
      runtime: 'ADB instrumentation against installed production application owners'
    },
    arkts: {
      apiLevel: 23,
      openHarmonySdkComponentVersion: '6.1.0.32',
      emulatorSystemBuild: '6.1.0.115(SP11DEVC00E115R4P11)',
      target: '127.0.0.1:10178',
      devecoStudio: '6.1.1',
      jdk: 'JBR 21.0.8',
      runtime: 'HDC EntryAbility/ArkUI page-owner execution'
    }
  },
  calibrationRuns: {
    signal: 'deep_mining_runtime_calibration_20261023',
    wordpress: 'deep_mining_runtime_calibration_20261023',
    wikipedia: 'deep_mining_runtime_calibration_20261023'
  },
  noChangeControls: {
    signal: 'deep_mining_no_change_runtime_20261023',
    wordpress: 'deep_mining_no_change_runtime_20261023',
    wikipedia: 'deep_mining_no_change_runtime_20261023'
  },
  qualityGates: {
    baseAllFail: calibrationRows.filter(row => row.role === 'base').every(row => row.semanticTestcase.passed === 0 && row.semanticTestcase.failed === 10),
    finalAllPass: calibrationRows.filter(row => row.role === 'final').every(row => row.semanticTestcase.passed === 10 && row.semanticTestcase.failed === 0),
    noUnscoredCalibration: calibrationRows.every(row => row.semanticTestcase.notScored === 0),
    noUnscoredAgentResults: rows.every(row => row.semanticTestcase.notScored === 0),
    canonicalCasesUnique: globalCaseIds.size === 60 && globalDigests.size === 60,
    sourceObserversUsedForScoring: false,
    agentPatchesReconstructable: validationRows.every(row => !row.errors.includes('candidate patch reconstruction is unverified'))
  },
  diagnostics: {
    isolationWarnings,
    policy: 'Isolation, adapter, transport, provider, and hidden runtime compile are diagnostics rather than benchmark metrics.'
  },
  benchmarkMetrics: metrics,
  platformMetrics: platforms,
  artifacts,
  metricPolicy: 'Only code generation, production compile, and semantic testcase pass rate are benchmark metrics; adapter, transport, provider, isolation metadata, and hidden runtime compile are diagnostics.'
};

const benchmarkMetrics = {
  schemaVersion: 1,
  runId,
  metrics,
  platforms,
  projects,
  rows
};

const formalValidation = {
  schemaVersion: 1,
  runId,
  valid: allValid,
  canonical: {
    taskCount: tasks.length,
    caseCount: globalCaseIds.size,
    uniqueCaseIds: globalCaseIds.size === 60,
    uniqueTraceDigests: globalDigests.size === 60
  },
  calibrationRows,
  agentRows: validationRows,
  diagnostics: { isolationWarnings }
};

fs.mkdirSync(outputRoot, { recursive: true });
fs.writeFileSync(path.join(outputRoot, 'run-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`);
fs.writeFileSync(path.join(outputRoot, 'benchmark-metrics.json'), `${JSON.stringify(benchmarkMetrics, null, 2)}\n`);
fs.writeFileSync(path.join(outputRoot, 'formal-validation.json'), `${JSON.stringify(formalValidation, null, 2)}\n`);

if (!allValid) {
  console.error(JSON.stringify(formalValidation, null, 2));
  process.exit(1);
}

console.log(JSON.stringify({ runId, valid: true, metrics, platforms, isolationWarnings }, null, 2));
