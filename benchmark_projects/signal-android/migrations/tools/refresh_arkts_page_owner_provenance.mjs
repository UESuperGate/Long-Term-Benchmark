#!/usr/bin/env node

import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const toolsDir = path.dirname(fileURLToPath(import.meta.url));
const migrationsDir = path.dirname(toolsDir);
const taskIds = ['01_media_keyboard', '02_sticker_management'];

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function writeJson(file, value) {
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`);
}

function fileEvidence(taskDir, relativePath) {
  const bytes = fs.readFileSync(path.join(taskDir, relativePath));
  return {
    path: relativePath,
    bytes: bytes.length,
    sha256: crypto.createHash('sha256').update(bytes).digest('hex'),
  };
}

function semanticScore(report) {
  return {
    passed: report.semantic.passed,
    failed: report.semantic.failed,
    notScored: report.semantic.notScored,
    total: report.semantic.total,
  };
}

function requireCalibration(role, report) {
  const expected = role === 'base'
    ? { passed: 0, failed: 10, notScored: 0, total: 10 }
    : { passed: 10, failed: 0, notScored: 0, total: 10 };
  const actual = semanticScore(report);
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`${report.taskId} ${role} is not calibrated: ${JSON.stringify(actual)}`);
  }
  if (report.runtime !== 'api23_arkvm_entryability_arkui_page_owned_controller') {
    throw new Error(`${report.taskId} ${role} did not use the page-owned runtime`);
  }
  if (report.diagnostics?.apiVersion !== 23 || !report.diagnostics?.entryAbilityStarted) {
    throw new Error(`${report.taskId} ${role} lacks API 23 EntryAbility evidence`);
  }
  if (!report.diagnostics?.pageOwnerId || report.diagnostics?.publicationEligible !== true) {
    throw new Error(`${report.taskId} ${role} lacks page-owner publication evidence`);
  }
}

function runEvidence(taskDir, role, report) {
  const reportPath = `results/arkts-${role}.json`;
  const logPath = `provenance/runtime-logs/arkts-${role}.jsonl`;
  const transportPath = `provenance/runtime-logs/arkts-${role}-transport.json`;
  return {
    build: report.compile?.passed === true ? 'passed' : 'failed',
    semantic: `${report.semantic.passed}/${report.semantic.total}`,
    runtime: report.runtime,
    runtimeArtifact: report.runtimeArtifact,
    artifactBytesRetained: false,
    device: report.diagnostics.target,
    apiVersion: report.diagnostics.apiVersion,
    pageOwnerId: report.diagnostics.pageOwnerId,
    entryAbilityStarted: report.diagnostics.entryAbilityStarted,
    deviceLock: '/tmp/long-term-benchmark-arkts-device.lock',
    deviceLockImplementation: 'python_fcntl.flock',
    report: fileEvidence(taskDir, reportPath),
    rawObservationLog: fileEvidence(taskDir, logPath),
    transport: fileEvidence(taskDir, transportPath),
  };
}

function generatedResidue(taskDir) {
  const residueNames = ['build', '.gradle', '.hvigor', 'oh_modules', '.benchmark-evaluator'];
  const residue = [];
  for (const role of ['base', 'final']) {
    const projectDir = path.join(taskDir, 'arkts', role);
    const candidates = [
      ...residueNames.map((name) => path.join(projectDir, name)),
      ...residueNames.map((name) => path.join(projectDir, 'entry', name)),
      path.join(projectDir, 'entry/src/main/ets/.benchmark-evaluator'),
    ];
    for (const candidate of candidates) {
      if (fs.existsSync(candidate)) {
        residue.push(path.relative(taskDir, candidate));
      }
    }
  }
  return residue;
}

for (const taskId of taskIds) {
  const taskDir = path.join(migrationsDir, taskId);
  const base = readJson(path.join(taskDir, 'results/arkts-base.json'));
  const final = readJson(path.join(taskDir, 'results/arkts-final.json'));
  requireCalibration('base', base);
  requireCalibration('final', final);

  const auditPath = path.join(taskDir, 'provenance/arkts-page-owner-audit.json');
  const parityPath = path.join(taskDir, 'provenance/transition-parity.json');
  const audit = readJson(auditPath);
  const parity = readJson(parityPath);
  if (audit.passed !== true || parity.valid !== true) {
    throw new Error(`${taskId} audit or transition parity failed`);
  }

  const now = new Date().toISOString();
  const manifestPath = path.join(taskDir, 'results/manifest.json');
  const manifest = readJson(manifestPath);
  manifest.generatedAt = now;
  writeJson(manifestPath, manifest);

  const calibrationPath = path.join(taskDir, 'provenance/calibration-summary.json');
  const calibration = readJson(calibrationPath);
  calibration.matrix['arkts-base'] = semanticScore(base);
  calibration.matrix['arkts-final'] = semanticScore(final);
  calibration.observationMode = 'runtime_page_owner_state_transition_and_leaf_effects';
  calibration.arktsCalibration = {
    device: {
      serial: base.diagnostics.target,
      apiLevel: base.diagnostics.apiVersion,
    },
    runtime: base.runtime,
    reports: {
      base: '../results/arkts-base.json',
      final: '../results/arkts-final.json',
    },
    rawObservations: {
      base: 'runtime-logs/arkts-base.jsonl',
      final: 'runtime-logs/arkts-final.jsonl',
    },
    runtimeArtifactSha256: {
      base: base.runtimeArtifact.sha256,
      final: final.runtimeArtifact.sha256,
    },
    pageOwnerIds: {
      base: base.diagnostics.pageOwnerId,
      final: final.diagnostics.pageOwnerId,
    },
    runtimeHarnessAudit: 'arkts-page-owner-audit.json',
    transitionParity: 'transition-parity.json',
  };
  writeJson(calibrationPath, calibration);

  const evalManifestPath = path.join(taskDir, 'provenance/eval-manifest.json');
  const evalManifest = readJson(evalManifestPath);
  for (const run of evalManifest.runs) {
    if (run.id === 'arkts-base') {
      run.score = semanticScore(base);
      run.runtime = base.runtime;
    } else if (run.id === 'arkts-final') {
      run.score = semanticScore(final);
      run.runtime = final.runtime;
    }
  }
  evalManifest.executionEvidence = {
    pageOwnerAudit: 'arkts-page-owner-audit.json',
    transitionParity: 'transition-parity.json',
    ownerLifecycle: 'EntryAbility -> Index.aboutToAppear -> page-owned controller',
    semanticVerdictSource: 'canonical runtime observations; never file presence',
  };
  writeJson(evalManifestPath, evalManifest);

  const buildEvidencePath = path.join(taskDir, 'provenance/build-evidence.json');
  const buildEvidence = readJson(buildEvidencePath);
  buildEvidence.capturedAt = now;
  buildEvidence.arkts.apiVersion = 23;
  buildEvidence.arkts.base = runEvidence(taskDir, 'base', base);
  buildEvidence.arkts.final = runEvidence(taskDir, 'final', final);
  buildEvidence.arkts.pageOwnerAudit = fileEvidence(taskDir, 'provenance/arkts-page-owner-audit.json');
  buildEvidence.arkts.transitionParity = fileEvidence(taskDir, 'provenance/transition-parity.json');
  const residue = generatedResidue(taskDir);
  buildEvidence.cleanup = {
    completed: residue.length === 0,
    artifactBytesRetained: false,
    cacheResidue: residue,
    binaryResidue: residue.filter((entry) => entry.endsWith('/build')),
  };
  writeJson(buildEvidencePath, buildEvidence);

  const evidenceIndexPath = path.join(taskDir, 'provenance/evidence-index.json');
  const evidenceIndex = readJson(evidenceIndexPath);
  const paths = new Set(evidenceIndex.records.map((record) => record.path));
  paths.add('provenance/arkts-page-owner-audit.json');
  paths.add('provenance/transition-parity.json');
  evidenceIndex.generatedAt = now;
  evidenceIndex.records = [...paths]
    .filter((relativePath) => fs.existsSync(path.join(taskDir, relativePath)))
    .sort()
    .map((relativePath) => fileEvidence(taskDir, relativePath));
  writeJson(evidenceIndexPath, evidenceIndex);
}

console.log(JSON.stringify({ refreshed: taskIds }));
