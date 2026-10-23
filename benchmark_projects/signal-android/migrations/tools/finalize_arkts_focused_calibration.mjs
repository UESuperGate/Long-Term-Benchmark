import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const migration = path.resolve(process.argv[2] ?? '');
const taskId = path.basename(migration);
const read = relative => JSON.parse(fs.readFileSync(path.join(migration, relative), 'utf8'));
const base = read('results/arkts-base.json');
const final = read('results/arkts-final.json');
const controls = read('provenance/arkts-control-audit.json');
const parity = read('provenance/arkts-transition-parity.json');
const summary = report => ({ passed: report.semantic.passed, failed: report.semantic.failed, notScored: report.semantic.notScored, total: report.semantic.total });
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const expected = JSON.stringify({ passed: 0, failed: 10, notScored: 0, total: 10 });
if (JSON.stringify(summary(base)) !== expected) throw new Error('ArkTS base polarity mismatch');
if (JSON.stringify(summary(final)) !== JSON.stringify({ passed: 10, failed: 0, notScored: 0, total: 10 })) throw new Error('ArkTS final polarity mismatch');
if (!parity.valid || controls.status !== 'passed') throw new Error('ArkTS parity or controls failed');
const summaryPath = path.join(migration, 'provenance', 'arkts-calibration-summary.json');
const payload = {
  schemaVersion: 1, taskId, status: 'passed', observationMode: 'api23_arkvm_index_page_owner_runtime_state_transition',
  matrix: { 'arkts-base': summary(base), 'arkts-final': summary(final), ...Object.fromEntries(Object.entries(controls.matrix).map(([key, value]) => [key, { passed: value.passed, failed: value.failed, notScored: value.notScored, total: value.total }])) },
  publicationEligible: true, sourceObserver: false, roleUsedForScoring: false, hostRunnerCounted: false,
  device: { target: controls.target, apiVersion: 23 }, locks: controls.locks,
  reports: { base: '../results/arkts-base.json', final: '../results/arkts-final.json', controls: 'arkts-control-audit.json', parity: 'arkts-transition-parity.json' },
  rawObservations: { base: 'runtime-logs/arkts-base.jsonl', final: 'runtime-logs/arkts-final.jsonl' },
  runtimeArtifactSha256: { base: base.runtimeArtifact.sha256, final: final.runtimeArtifact.sha256 },
  reportSha256: { base: crypto.createHash('sha256').update(fs.readFileSync(path.join(migration, 'results/arkts-base.json'))).digest('hex'), final: crypto.createHash('sha256').update(fs.readFileSync(path.join(migration, 'results/arkts-final.json'))).digest('hex') }
};
fs.writeFileSync(summaryPath, `${JSON.stringify(payload, null, 2)}\n`);
const androidTask = read('android/task.json');
const candidateProvenance = role => {
  const manifestFile = path.join(migration, 'arkts', role, 'SOURCE_MANIFEST.json');
  const manifest = JSON.parse(fs.readFileSync(manifestFile, 'utf8'));
  return {
    bundleName: manifest.bundleName,
    apiVersion: manifest.apiVersion,
    sourceObserver: manifest.sourceObserver,
    sourceManifest: path.relative(migration, manifestFile),
    sourceManifestSha256: sha256(manifestFile),
    productionFiles: manifest.files
  };
};
const sourceProvenance = {
  schemaVersion: 1,
  taskId,
  sourceObserver: false,
  androidBoundary: {
    repository: androidTask.android.repository,
    baseRef: androidTask.android.baseRef,
    baseCommit: androidTask.android.baseCommit,
    finalRef: androidTask.android.finalRef,
    finalCommit: androidTask.android.finalCommit
  },
  arktsCandidates: { base: candidateProvenance('base'), final: candidateProvenance('final') },
  canonicalContract: {
    androidPath: 'canonical/transitions.json',
    androidSha256: sha256(path.join(migration, 'canonical', 'transitions.json')),
    arktsPath: 'arkts/transitions.json',
    arktsSha256: sha256(path.join(migration, 'arkts', 'transitions.json')),
    parityReport: 'provenance/arkts-transition-parity.json'
  },
  evaluator: {
    observerPath: 'arkts/evaluator/RuntimeObserver.ets',
    observerSha256: sha256(path.join(migration, 'arkts', 'evaluator', 'RuntimeObserver.ets')),
    bindingsPath: 'arkts/bindings.json',
    bindingsSha256: sha256(path.join(migration, 'arkts', 'bindings.json')),
    scorerPath: 'benchmark_projects/signal-android/migrations/tools/score_arkts_focused_candidate.mjs',
    roleUsedForScoring: false
  },
  buildEvidence: {
    baseLog: { path: 'provenance/build-logs/arkts-base.log', sha256: sha256(path.join(migration, 'provenance', 'build-logs', 'arkts-base.log')), bytes: fs.statSync(path.join(migration, 'provenance', 'build-logs', 'arkts-base.log')).size },
    finalLog: { path: 'provenance/build-logs/arkts-final.log', sha256: sha256(path.join(migration, 'provenance', 'build-logs', 'arkts-final.log')), bytes: fs.statSync(path.join(migration, 'provenance', 'build-logs', 'arkts-final.log')).size },
    target: controls.target,
    apiVersion: 23,
    node: process.version,
    hvigor: '/Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw',
    sdk: '$HOME/Library/OpenHarmony/Sdk/23'
  }
};
fs.writeFileSync(path.join(migration, 'provenance', 'arkts-source-provenance.json'), `${JSON.stringify(sourceProvenance, null, 2)}\n`);
process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
