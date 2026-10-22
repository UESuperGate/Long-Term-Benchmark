#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const { withTemporaryWorkspace } = require('./arkts_native_smoke.cjs');

const root = path.resolve(__dirname, '../..');
const taskId = '12_report_room';
const caseId = 'rr_state_005_report_then_leave';
const relativeFile = 'entry/src/main/ets/features/ReportRoomFeature.ets';
const before = 'if (shouldLeave && !this.gateway.leaveRoom())';
const after = 'if (false && !this.gateway.leaveRoom())';
const digest = value => crypto.createHash('sha256').update(value).digest('hex');
const hash = file => digest(fs.readFileSync(file));
const writeJson = (file, value) => fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n');

function files(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))
    .flatMap(entry => entry.isDirectory() ? files(path.join(directory, entry.name)) : [path.join(directory, entry.name)]);
}

function productionDigest(project) {
  return digest(JSON.stringify(files(path.join(project, 'entry/src/main/ets'))
    .map(file => ({ path: path.relative(project, file), sha256: hash(file) }))));
}

function runCandidate(candidate, output, expectedSourceHash) {
  const command = [process.execPath, path.join(__dirname, 'arkts_native_smoke.cjs'),
    '--bundle', taskId, '--role', 'final', '--source', candidate, '--output-dir', output];
  const execution = spawnSync(command[0], command.slice(1), { cwd: root, stdio: 'inherit' });
  if (execution.error || execution.status !== 0) throw execution.error || new Error(`Native runner exited ${execution.status}`);
  const reportFile = path.join(output, 'reports', `arkts_${taskId}_final.json`);
  const report = JSON.parse(fs.readFileSync(reportFile, 'utf8'));
  const target = report.semantic.cases.find(row => row.caseId === caseId);
  const manifest = JSON.parse(fs.readFileSync(report.nativeEvidence.manifest, 'utf8'));
  const bundled = manifest.production.find(item => item.path === relativeFile);
  if (!target || bundled?.sha256 !== expectedSourceHash || !report.diagnostics.nativeRuntimeExecuted ||
      !report.diagnostics.nativeProductionExecuted || !report.runtimeCompile.passed || report.compile.passed !== null ||
      !report.nativeEvidence.nativeProcess?.arkRuntimeLibraries.some(file => file.includes('libark_jsruntime.dylib'))) {
    throw new Error('Native execution, source hash or compile-scope evidence missing');
  }
  if (hash(report.nativeEvidence.bytecode.file) !== report.nativeEvidence.bytecode.sha256) {
    throw new Error('Native bytecode digest mismatch');
  }
  const caseFile = path.join(output, 'target-case.json');
  writeJson(caseFile, target);
  // Retain native logs and provenance, but replace generated code/bytecode and
  // the full ten-case report with hashes and the one mutation target's evidence.
  const artifacts = files(output).map(file => ({ file: path.relative(output, file),
    bytes: fs.statSync(file).size, sha256: hash(file),
    retained: !file.endsWith('.abc') && !file.endsWith('.generated.js') && !file.endsWith('.generated.test.ets') && file !== reportFile }));
  for (const artifact of artifacts.filter(item => !item.retained)) fs.rmSync(path.join(output, artifact.file));
  fs.rmdirSync(path.dirname(reportFile));
  const evidenceFile = path.join(output, 'evidence.json');
  writeJson(evidenceFile, { command, runtime: report.runtime, compile: report.compile,
    runtimeCompile: report.runtimeCompile, diagnostics: report.diagnostics,
    nativeEvidence: report.nativeEvidence, provenance: report.provenance,
    targetCase: caseFile, artifacts,
    retention: 'Raw native log, build log and manifest retained; generated code, bytecode and full case report retained by digest only.' });
  return { status: target.status, traceDigest: target.traceDigest, evidence: evidenceFile,
    targetCase: caseFile, targetCaseSha256: hash(caseFile), sourceSha256: bundled.sha256,
    bytecodeSha256: report.nativeEvidence.bytecode.sha256,
    adapterSha256: manifest.adapters.find(item => item.file.endsWith('tasks12_15.cjs')).sha256,
    evaluator: manifest.evaluator.map(item => ({ name: item.name, sha256: item.sha256 })) };
}

async function main() {
  const index = process.argv.indexOf('--output-dir');
  if (index >= 0 && (!process.argv[index + 1] || process.argv[index + 1].startsWith('--'))) throw new Error('--output-dir requires a directory');
  const output = path.resolve(index >= 0 ? process.argv[index + 1] : path.join(root, 'experiment_results/runtime_transition_20261019'));
  const task = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks', taskId, 'task.json'), 'utf8'));
  const original = path.join(root, task.arkts.finalPath);
  const originalFile = path.join(original, relativeFile);
  const originalText = fs.readFileSync(originalFile, 'utf8');
  if (originalText.split(before).length !== 2) throw new Error('Mutation target is not unique');
  const originalHash = hash(originalFile);
  const originalTreeHash = productionDigest(original);
  const evidenceRoot = path.join(output, 'native-mutation');
  fs.mkdirSync(evidenceRoot, { recursive: true });
  const run = fs.mkdtempSync(path.join(evidenceRoot, 'task12-report-then-leave-'));
  const result = { schemaVersion: 1, taskId, caseId, startedAt: new Date().toISOString(),
    status: 'running', compile: { passed: null, scope: 'candidate application not compiled' },
    mutation: { file: relativeFile, before, after, occurrences: 1 }, evidenceDirectory: run,
    original: { project: original, sourceSha256Before: originalHash, productionTreeSha256Before: originalTreeHash } };
  try {
    result.baseline = runCandidate(original, path.join(run, 'baseline'), originalHash);
    await withTemporaryWorkspace(async work => {
      const candidate = path.join(work, 'candidate');
      fs.cpSync(original, candidate, { recursive: true,
        filter: file => !['.git', '.hvigor', 'build', 'oh_modules', 'node_modules'].includes(path.basename(file)) });
      const mutantFile = path.join(candidate, relativeFile);
      if (hash(mutantFile) !== originalHash) throw new Error('Copied production source differs before mutation');
      fs.writeFileSync(mutantFile, originalText.replace(before, after));
      result.mutant = runCandidate(candidate, path.join(run, 'mutant'), hash(mutantFile));
    });
    result.temporaryCandidateRemoved = true;
    result.sameAdapterAndEvaluator = result.baseline.adapterSha256 === result.mutant.adapterSha256 &&
      JSON.stringify(result.baseline.evaluator) === JSON.stringify(result.mutant.evaluator);
    result.sameCanonicalDigest = result.baseline.traceDigest === result.mutant.traceDigest;
    result.status = result.baseline.status === 'pass' && result.mutant.status === 'fail' &&
      result.sameAdapterAndEvaluator && result.sameCanonicalDigest ? 'pass' : 'fail';
  } catch (error) {
    result.status = 'fail';
    result.error = String(error.stack || error);
  } finally {
    result.original.sourceSha256After = hash(originalFile);
    result.original.productionTreeSha256After = productionDigest(original);
    result.original.unchanged = originalHash === result.original.sourceSha256After &&
      originalTreeHash === result.original.productionTreeSha256After;
    if (!result.original.unchanged) result.status = 'fail';
    result.finishedAt = new Date().toISOString();
    writeJson(path.join(output, 'arkts_mutation.json'), result);
  }
  console.log(JSON.stringify(result, null, 2));
  process.exitCode = result.status === 'pass' ? 0 : 1;
}

main().catch(error => { console.error(error); process.exitCode = 1; });
