#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const { removeCopiedHaps } = require('./task09_hap_cleanup.cjs');
const { retainTree } = require('./task11_arkts_evidence_retention.cjs');

const root = path.resolve(__dirname, '../..');
const buildScript = path.join(__dirname, 'task11_arkts_strict_build.cjs');
const executeScript = path.join(__dirname, 'arkts_device_execute.cjs');
const contractFile = path.join(root, 'benchmark_tasks/11_room_upgrade_navigation/transitions.json');
const hdc = path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/toolchains/hdc');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const fileRecord = file => { const bytes = fs.readFileSync(file); return {
  path: path.resolve(file), bytes: bytes.length, sha256: sha(bytes) }; };
const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

function value(args, flag, fallback) {
  const index = args.indexOf(flag);
  if (index < 0) return fallback;
  if (!args[index + 1] || args[index + 1].startsWith('--')) throw new Error(flag + ' requires a value');
  return args[index + 1];
}

function files(directory) {
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const file = path.join(directory, entry.name);
    return entry.isDirectory() ? files(file) : entry.isFile() ? [file] : [];
  });
}

function sourceInventory(source) {
  const digest = crypto.createHash('sha256');
  const ignored = new Set(['.git', '.hvigor', 'build', 'oh_modules', 'node_modules']);
  let count = 0;
  for (const file of files(source).sort()) {
    const relative = path.relative(source, file);
    if (relative.split(path.sep).some(part => ignored.has(part))) continue;
    const name = Buffer.from(relative.split(path.sep).join('/'));
    const bytes = fs.readFileSync(file);
    digest.update(Buffer.from(String(name.length) + ':')); digest.update(name);
    digest.update(Buffer.from(String(bytes.length) + ':')); digest.update(bytes); count++;
  }
  return { root: path.resolve(source), files: count, sha256: digest.digest('hex') };
}

function exact(expected, observed) {
  if (expected && typeof expected === 'object' && !Array.isArray(expected))
    return observed && typeof observed === 'object' && !Array.isArray(observed) &&
      Object.entries(expected).every(([key, item]) => key in observed && exact(item, observed[key]));
  if (Array.isArray(expected)) return Array.isArray(observed) && expected.length === observed.length &&
    expected.every((item, index) => exact(item, observed[index]));
  return typeof expected === typeof observed && expected === observed;
}

function lockRace(log) {
  return /EEXIST: file already exists, mkdir ['\"][^'\"]*ltb-arkts-device-/.test(log);
}

function retryablePreflight(directory) {
  try {
    const execution = JSON.parse(fs.readFileSync(path.join(directory, 'device-execution.json')));
    return execution.status === 'incomplete' &&
      execution.error === 'SyntaxError: Unexpected end of JSON input' &&
      (!execution.rows || execution.rows.length === 0) && execution.cleanup?.ownedAppUninstalled === true &&
      fs.existsSync(path.join(directory, 'ui-preflight-tree.log')) &&
      fs.readFileSync(path.join(directory, 'ui-preflight-tree.log'), 'utf8').trim() === '' &&
      !fs.existsSync(path.join(directory, 'aa-test.log'));
  } catch (_) { return false; }
}

function normalizeRow(row, spec, role, snapshotDirectory) {
  if (row.caseId !== spec.caseId || row.traceDigest !== spec.traceDigest || row.role !== role ||
      !['pass', 'fail'].includes(row.status)) throw new Error('Task11 native row identity/verdict mismatch');
  const raw = row.checkpoints || [];
  if (raw.length < 2) throw new Error(spec.caseId + ' lacks real before/after runtime checkpoints');
  const checkpoints = ['before:event', 'after:event'].map(label => {
    const point = raw.find(point => (point.label || point.name) === label);
    const production = point?.state?.state && typeof point.state.state === 'object' ?
      point.state.state : point?.state?.stateAfter;
    if (!production || typeof production !== 'object' || !point.state.controls || production.executed === false)
      throw new Error(spec.caseId + ' lacks actual canonical snapshot: ' + label);
    const state = { production, controls: point.state.controls,
      routeName: point.state.routeName, windowId: point.state.windowId, viewport: point.state.viewport };
    const result = { name: label, sourceLabel: label, state,
      evidenceSha256: sha(Buffer.from(JSON.stringify(point))) };
    if (snapshotDirectory) {
      fs.mkdirSync(snapshotDirectory, { recursive: true });
      const target = path.join(snapshotDirectory, label.replace(':', '-') + '.snapshot.json');
      fs.writeFileSync(target, JSON.stringify(point, null, 2) + '\n', { flag: 'wx' });
      result.actualSnapshot = fileRecord(target);
    }
    return result;
  });
  const bound = new Map((row.invariantChecks || []).map(check => [check.description || check.invariant,
    check.passed === undefined ? check.status === 'pass' : check.passed]));
  for (const invariant of spec.invariants || []) if (typeof bound.get(invariant) !== 'boolean')
    throw new Error(spec.caseId + ' missing executable canonical invariant: ' + invariant);
  const matches = exact(spec.expected, row.observed || {});
  const invariantsPass = (spec.invariants || []).every(item => bound.get(item) === true);
  if (row.status === 'pass' && (!matches || !invariantsPass))
    throw new Error(spec.caseId + ' native PASS does not satisfy exact canonical state');
  if (row.status === 'fail' && matches && invariantsPass)
    throw new Error(spec.caseId + ' native FAIL has no semantic mismatch');
  const { calls, evidence, ...retained } = row;
  const removedPayloads = {};
  for (const [name, value] of Object.entries({ calls, evidence })) if (value !== undefined) {
    const bytes = Buffer.from(JSON.stringify(value));
    removedPayloads[name] = { bytes: bytes.length, sha256: sha(bytes),
      removedAsDuplicatePayload: true, actualCheckpointsRetained: true };
  }
  return { ...retained, key: spec.key, transitionExecuted: true, checkpoints, removedPayloads };
}

function cleanupArtifacts(directory) {
  const suffixes = new Set(['.apk', '.hap', '.aab', '.apks', '.abc', '.dex', '.so', '.jar', '.class', '.har']);
  const binaryHashes = [];
  for (const file of files(directory)) if (suffixes.has(path.extname(file).toLowerCase())) {
    binaryHashes.push(fileRecord(file)); fs.unlinkSync(file);
  }
  const disposable = new Set(['build', '.hvigor', 'oh_modules', 'node_modules']);
  const directories = [];
  const visit = current => {
    if (!fs.existsSync(current)) return;
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) if (entry.isDirectory()) {
      const child = path.join(current, entry.name);
      if (disposable.has(entry.name)) directories.push(child); else visit(child);
    }
  };
  visit(directory);
  directories.sort((a, b) => b.split(path.sep).length - a.split(path.sep).length)
    .forEach(item => fs.rmSync(item, { recursive: true, force: true }));
  const remaining = files(directory).filter(file => suffixes.has(path.extname(file).toLowerCase()));
  return { performed: true, binaryHashes, binaryArtifactsRetained: remaining.length > 0,
    retainedEvidenceExcludesBinaries: remaining.length === 0, temporaryBuildRemoved: true,
    temporaryArtifactRootRemoved: true, remainingBinaries: remaining };
}

async function main() {
  const args = process.argv.slice(2);
  const source = path.resolve(value(args, '--source'));
  const role = value(args, '--role');
  const output = path.resolve(value(args, '--output'));
  const artifactRoot = path.resolve(value(args, '--artifact-root'));
  const platform = value(args, '--platform');
  const timeoutSeconds = Number(value(args, '--timeout', '3600'));
  const selectedCase = value(args, '--case', null);
  if (platform !== 'arkts' || !['base', 'final', 'agent'].includes(role) ||
      !Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0 || timeoutSeconds > 3600)
    throw new Error('Invalid Task11 ArkTS strict arguments');
  if (!fs.statSync(source).isDirectory() || fs.existsSync(output)) throw new Error('Invalid source or existing output');
  fs.mkdirSync(artifactRoot, { recursive: true });
  const started = process.hrtime.bigint();
  const elapsed = () => Number(process.hrtime.bigint() - started) / 1e9;
  const remainingMs = () => {
    const budget = Math.floor((timeoutSeconds - elapsed()) * 1000);
    if (budget <= 0) throw new Error('Task11 ArkTS strict runner exhausted its unified deadline');
    return budget;
  };
  const contract = JSON.parse(fs.readFileSync(contractFile));
  if (contract.taskId !== '11_room_upgrade_navigation' || contract.cases.length !== 6)
    throw new Error('Task11 canonical contract identity/count changed');
  if (selectedCase && !contract.cases.some(spec => spec.caseId === selectedCase)) throw new Error('Unknown diagnostic case');
  const selected = contract.cases.filter(spec => !selectedCase || spec.caseId === selectedCase);
  const retainedRoot = output.replace(/\.json$/, '') + '.raw-evidence';
  const retain = () => retainTree(artifactRoot, retainedRoot);
  const sourceBefore = sourceInventory(source);
  const executedImplementations = { runner: fileRecord(__filename),
    retention: fileRecord(require.resolve('./task11_arkts_evidence_retention.cjs')) };
  const targetText = spawnSync(hdc, ['list', 'targets'], { encoding: 'utf8', timeout: 30000 }).stdout || '';
  const targets = targetText.trim().split(/\s+/).filter(Boolean);
  if (targets.length !== 1) throw new Error('Expected exactly one OpenHarmony target');
  const serial = targets[0];
  const taskExecuteScript = path.join(artifactRoot, 'task11-device-execute.generated.cjs');
  let executor = fs.readFileSync(executeScript, 'utf8').replace(
    "const providerHostFile = path.resolve(__dirname, '../../state_tests/runtime/arkts/native/Tasks16_18ProviderHost.cjs');",
    'const providerHostFile = ' + JSON.stringify(path.join(root, 'state_tests/runtime/arkts/native/Tasks16_18ProviderHost.cjs')) + ';');
  if (!/const os = require\(/.test(executor)) executor = executor.replace("'use strict';", "'use strict';\nconst os = require('node:os');");
  fs.writeFileSync(taskExecuteScript, executor, { flag: 'wx' });
  const lockName = 'ltb-arkts-device-' + sha(Buffer.from(serial)).slice(0, 16);
  const lockCandidates = [path.join('/tmp', lockName), path.join(os.tmpdir(), lockName)];
  const commands = [], rows = [], hapCleanup = [];
  const run = (name, command, commandArgs, capMs) => {
    const budget = Math.min(remainingMs(), capMs);
    const result = spawnSync(command, commandArgs, { cwd: root, encoding: 'utf8', timeout: budget,
      maxBuffer: 24 * 1024 * 1024 });
    const log = path.join(artifactRoot, name + '.log');
    fs.writeFileSync(log, (result.stdout || '') + (result.stderr || ''));
    commands.push({ name, command: [command, ...commandArgs], budgetMs: budget, exitCode: result.status,
      error: result.error && String(result.error), log: fileRecord(log) });
    if (result.error || result.status !== 0) throw new Error(name + ' failed: ' + (result.error || result.status));
  };
  const waitForDeviceLock = async () => {
    while (lockCandidates.some(file => fs.existsSync(file))) { remainingMs(); await sleep(2000); }
  };

  let failure, retainedEvidence;
  try { for (const spec of selected) {
    const storage = fs.statfsSync(artifactRoot);
    if (storage.bavail * storage.bsize < 8 * 1024 ** 3) throw new Error('Task11 storage guard requires at least 8 GiB free');
    const slug = role + '-' + spec.caseId;
    const directory = path.join(artifactRoot, slug);
    run('build-' + slug, process.execPath, [buildScript, '--source', source, '--role', role,
      '--case', spec.caseId, '--output-dir', directory], 600000);
    retainedEvidence = retain();
    const buildReport = path.join(directory, 'device-build-report.json');
    let executionDirectory;
    let executionFile;
    let execution;
    let executionError;
    try {
      for (let attempt = 1; attempt <= 3; attempt += 1) {
        await waitForDeviceLock();
        executionDirectory = path.join(directory, 'execution-attempt-' + attempt);
        try {
          run('execute-' + slug + '-attempt-' + attempt, process.execPath,
            [taskExecuteScript, buildReport, serial, executionDirectory], 300000);
          break;
        } catch (error) {
          const log = path.join(artifactRoot, 'execute-' + slug + '-attempt-' + attempt + '.log');
          if (attempt < 3 && ((fs.existsSync(log) && lockRace(fs.readFileSync(log, 'utf8'))) ||
              retryablePreflight(executionDirectory))) continue;
          throw error;
        }
      }
      executionFile = path.join(executionDirectory, 'device-execution.json');
      execution = JSON.parse(fs.readFileSync(executionFile));
      const native = execution.rows.find(item => item.caseId === spec.caseId);
      // Preserve original bytes before transport checks or strict normalization
      // can throw. The shared scorer may remove this whole temporary tree.
      retainedEvidence = retain();
      if (!execution.transportCompleted || execution.status !== 'transport_completed' ||
          !execution.cleanup?.ownedAppUninstalled || execution.candidateAbsentBeforeInstall !== true || !native)
        throw new Error('Incomplete fresh Task11 device execution: ' + slug);
      if (native.status === 'not_scored') throw new Error('Task11 actual native not_scored: ' +
        String(native.reason || 'No native reason supplied; see preserved raw bytes'));
      rows.push({ ...normalizeRow(native, spec, role, path.join(directory, 'snapshots')), freshInstall: true,
        build: fileRecord(buildReport), execution: fileRecord(executionFile),
        nativeResult: fileRecord(path.join(executionDirectory, 'native-result.json')) });
      const rawFiles = [executionFile, path.join(executionDirectory, 'native-result.json')];
      const retainedManifest = JSON.parse(fs.readFileSync(retainedEvidence.path));
      const rawCleanup = rawFiles.map(file => {
        const original = fileRecord(file);
        const retained = retainedManifest.files.find(item => item.original.path === original.path &&
          item.original.sha256 === original.sha256);
        if (!retained) throw new Error('Task11 raw payload lacks lossless retention');
        return { ...original, losslessGzip: retained.gzip, originalBytesRestorable: true };
      });
      fs.writeFileSync(path.join(executionDirectory, 'raw-payload-cleanup.json'), JSON.stringify({
        actualSnapshotsRetained: rows[rows.length - 1].checkpoints.map(point => point.actualSnapshot),
        transportCompleted: execution.transportCompleted, status: execution.status,
        cleanup: execution.cleanup, files: rawCleanup }, null, 2) + '\n');
      rawFiles.forEach(file => fs.unlinkSync(file));
    } catch (error) { executionError = error; }
    finally {
      retainedEvidence = retain();
      if (fs.existsSync(buildReport)) hapCleanup.push({ caseId: spec.caseId, ...removeCopiedHaps(buildReport) });
    }
    if (executionError) throw executionError;
  }
  if (sourceInventory(source).sha256 !== sourceBefore.sha256) throw new Error('Task11 evaluator mutated candidate source');
  } catch (error) { failure = error; }
  // Also retain build failures that happened before an execution directory
  // existed. No unsupported row is converted into a semantic failure.
  retainedEvidence = retain();
  const cases = selected.map(spec => rows.find(row => row.caseId === spec.caseId) || {
    caseId: spec.caseId, key: spec.key, traceDigest: spec.traceDigest, role, status: 'not_scored',
    observed: null, checkpoints: [], invariantChecks: [],
    reason: String(failure?.message || 'Canonical runtime row unavailable') });
  const semantic = { total: cases.length, passed: cases.filter(row => row.status === 'pass').length,
    failed: cases.filter(row => row.status === 'fail').length,
    notScored: cases.filter(row => row.status === 'not_scored').length, cases };
  const cleanup = cleanupArtifacts(artifactRoot);
  if (cleanup.binaryArtifactsRetained || !cleanup.temporaryBuildRemoved) throw new Error('Task11 binary cleanup incomplete');
  const report = { schemaVersion: 2, taskId: '11_room_upgrade_navigation', platform: 'arkts', role,
    target: source, source, observationMode: 'runtime_state_transition',
    compile: { passed: null, status: 'not_run', scope: 'standalone_candidate_application_build' },
    runtimeCompile: { passed: commands.filter(item => item.name.startsWith('build-') && item.exitCode === 0).length === selected.length,
      status: commands.filter(item => item.name.startsWith('build-') && item.exitCode === 0).length === selected.length ? 'passed' : 'incomplete',
      scope: 'source_parameterized_application_and_ohosTest_runtime_builds',
      builds: commands.filter(item => item.name.startsWith('build-') && item.exitCode === 0).length,
      diagnosticCaseSelection: selectedCase || null },
    semantic, provenance: { productionSourceRoot: source, sourceInventory: sourceBefore,
      contract: fileRecord(contractFile), runner: executedImplementations.runner, commands, hapCleanup,
      executedImplementations,
      retainedNativeEvidence: retainedEvidence, caseSelection: selectedCase || 'all' },
    diagnostics: { adapter: failure ? 'failed' : 'ready', transport: failure ? 'unverified' : 'ready', serial,
      reason: failure ? String(failure.message || failure) : null, strictRuntime: {
      sourceParameterized: true, entryEvaluator: true, runtimeOrDeviceEvaluator: true,
      sourceObserverUsed: false, fallbackUsed: false, candidateSmoke: { passed: true, source }, cleanup } },
    elapsedSeconds: Number(elapsed().toFixed(3)) };
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ output, semantic: { passed: semantic.passed, failed: semantic.failed,
    notScored: semantic.notScored }, elapsedSeconds: report.elapsedSeconds }));
  if (failure) throw failure;
}

module.exports = { exact, normalizeRow, cleanupArtifacts, sourceInventory, lockRace, retryablePreflight };

if (require.main === module) main().catch(error => {
  console.error(error.stack || String(error)); process.exitCode = 1;
});
