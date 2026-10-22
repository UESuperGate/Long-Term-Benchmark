#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const { removeCopiedHaps } = require('./task09_hap_cleanup.cjs');

const root = path.resolve(__dirname, '../..');
const buildScript = path.join(__dirname, 'task09_arkts_strict_build.cjs');
const executeScript = path.join(__dirname, 'arkts_device_execute.cjs');
const contractFile = path.join(root, 'benchmark_tasks/09_spaces_lifecycle/transitions.json');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const fileRecord = file => { const bytes = fs.readFileSync(file); return {
  path: path.resolve(file), bytes: bytes.length, sha256: sha(bytes) }; };
const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

function executionEnvironment(ownsDeviceLock, environment = process.env) {
  const result = { ...environment };
  // Never inherit a different scorer's ownership claim.
  delete result.LTB_DEVICE_LOCK_PREACQUIRED;
  if (ownsDeviceLock) result.LTB_DEVICE_LOCK_PREACQUIRED = '1';
  return result;
}

function value(args, flag, fallback) {
  const index = args.indexOf(flag);
  if (index < 0) return fallback;
  if (!args[index + 1] || args[index + 1].startsWith('--')) throw new Error(flag + ' requires a value');
  return args[index + 1];
}

async function main() {
  const args = process.argv.slice(2);
  const source = path.resolve(value(args, '--source'));
  const role = value(args, '--role');
  const output = path.resolve(value(args, '--output'));
  const serial = value(args, '--serial', '127.0.0.1:5555');
  const timeoutSeconds = Number(value(args, '--timeout', '3600'));
  if (!['base', 'final', 'agent'].includes(role) || !Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0)
    throw new Error('Invalid role or timeout');
  if (!/^[A-Za-z0-9.:_-]+$/.test(serial) || !fs.statSync(source).isDirectory())
    throw new Error('Invalid serial or source');
  const evidenceDirectory = output.replace(/\.json$/, '') + '.evidence';
  if (fs.existsSync(output) || fs.existsSync(evidenceDirectory)) throw new Error('Refusing existing Task09 runtime evidence');
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.mkdirSync(evidenceDirectory, { recursive: true });
  const started = process.hrtime.bigint();
  const elapsed = () => Number(process.hrtime.bigint() - started) / 1e9;
  const remainingMs = () => {
    const remaining = Math.floor((timeoutSeconds - elapsed()) * 1000);
    if (remaining <= 0) throw new Error('Task09 runtime score exhausted its total monotonic budget');
    return remaining;
  };
  const contract = JSON.parse(fs.readFileSync(contractFile));
  const contractRecord = fileRecord(contractFile);
  const lockName = 'ltb-arkts-device-' + sha(Buffer.from(serial)).slice(0, 16);
  const requiredLock = path.join('/tmp', lockName);
  const transportLock = path.join(os.tmpdir(), lockName);
  const leaseToken = crypto.randomBytes(16).toString('hex');
  const ownerFile = path.join(requiredLock, 'owner.json');
  const rows = [], commands = [];
  const report = { schemaVersion: 2, taskId: '09_spaces_lifecycle', platform: 'arkts', role,
    source, target: source, observationMode: 'runtime_state_transition',
    runtime: 'openharmony_api23_device_uitest_and_original_production_runtime', timeoutSeconds,
    budgetClock: 'process.hrtime.bigint monotonic remaining across packaging and all nine device cases',
    contract: contractRecord, runtimeCompile: { passed: false, status: 'not_run',
      scope: 'evaluator_test_packaging_and_runtime_build' }, compile: { passed: null,
      status: 'not_provided', scope: 'standalone application build supplied by caller' }, rows,
    commands, hapCleanup: [], status: 'incomplete', publication: { eligible: false }, startedAt: new Date().toISOString() };
  report.deviceLease = { path: requiredLock, token: leaseToken, acquisitions: [], releases: [] };
  const run = (name, command, commandArgs, limitMs) => {
    const budget = Math.min(remainingMs(), limitMs);
    const result = spawnSync(command, commandArgs, { cwd: root, encoding: 'utf8', timeout: budget,
      env: executionEnvironment(ownsRequiredLock), maxBuffer: 20 * 1024 * 1024 });
    const log = path.join(evidenceDirectory, name + '.log');
    fs.writeFileSync(log, (result.stdout || '') + (result.stderr || ''));
    commands.push({ name, command: [command, ...commandArgs], budgetMs: budget,
      exitCode: result.status, error: result.error && String(result.error), log: fileRecord(log) });
    if (result.error || result.status !== 0) throw new Error(name + ' failed: ' + (result.error || result.status));
  };
  const waitForLocks = async () => {
    // The mkdir is the acquisition, not the preceding existence check.
    // Another task may win between those operations; retry under the same budget.
    while (true) {
      remainingMs();
      if (transportLock !== requiredLock && fs.existsSync(transportLock)) { await sleep(2000); continue; }
      try {
        fs.mkdirSync(requiredLock); ownsRequiredLock = true;
        fs.writeFileSync(ownerFile, JSON.stringify({ taskId: contract.taskId, serial, pid: process.pid, token: leaseToken }), { flag: 'wx' });
        report.deviceLease.acquisitions.push({ at: new Date().toISOString(), inode: fs.statSync(requiredLock).ino });
        return;
      }
      catch (error) { if (error.code !== 'EEXIST') throw error; await sleep(2000); }
    }
  };
  let ownsRequiredLock = false;
  const releaseLock = () => {
    if (!ownsRequiredLock) return;
    if (!fs.existsSync(ownerFile) || JSON.parse(fs.readFileSync(ownerFile)).token !== leaseToken)
      throw new Error('Task09 device lease ownership changed; refusing to remove a foreign lock');
    fs.unlinkSync(ownerFile);
    fs.rmdirSync(requiredLock);
    ownsRequiredLock = false;
    report.deviceLease.releases.push({ at: new Date().toISOString() });
  };
  try {
    if (contract.taskId !== '09_spaces_lifecycle' || contract.cases.length !== 9)
      throw new Error('Expected nine canonical Task09 cases');
    for (const spec of contract.cases) {
      const disk = fs.statfsSync(root);
      if (Number(disk.bavail) * Number(disk.bsize) < 8 * 1024 ** 3)
        throw new Error('Task09 8 GiB disk guard rejected runtime packaging');
      const slug = role + '-' + spec.caseId;
      const directory = path.join(evidenceDirectory, slug);
      report.runtimeCompile = { passed: false, status: 'building',
        scope: 'evaluator_test_packaging_and_runtime_build', builds: rows.length };
      run('build-' + slug, process.execPath, [buildScript, '--source', source, '--role', role,
        '--case', spec.caseId, '--output-dir', directory, '--timeout', String(Math.max(1, Math.floor(remainingMs() / 1000)))], 600000);
      const buildReport = path.join(directory, 'device-build-report.json');
      report.runtimeCompile = { passed: true, status: 'passed',
        scope: 'evaluator_test_packaging_and_runtime_build', builds: rows.length + 1 };
      await waitForLocks();
      let rowEntry, executionError;
      try {
        const attempts = [];
        for (let attempt = 1; attempt <= 3 && !rowEntry; attempt++) {
          const executionDirectory = path.join(directory, 'execution-attempt-' + attempt);
          let commandError;
          try {
            run('execute-' + slug + '-attempt-' + attempt, process.execPath,
              [executeScript, buildReport, serial, executionDirectory], 240000);
          } catch (error) {
            commandError = error;
          }
          const executionFile = path.join(executionDirectory, 'device-execution.json');
          if (!fs.existsSync(executionFile)) {
            if (attempt === 3) throw commandError || new Error('Task09 execution produced no report: ' + slug);
            await sleep(2000);
            continue;
          }
          const execution = JSON.parse(fs.readFileSync(executionFile));
          attempts.push(fileRecord(executionFile));
          const row = execution.rows.find(item => item.caseId === spec.caseId);
          if (execution.transportCompleted && execution.status === 'transport_completed' &&
              execution.cleanup?.ownedAppUninstalled && execution.candidateAbsentBeforeInstall === true &&
              row && row.traceDigest === spec.traceDigest && ['pass', 'fail'].includes(row.status)) {
            rowEntry = { ...row, key: spec.key, role, freshInstall: true, build: fileRecord(buildReport),
              execution: fileRecord(executionFile), nativeResult: fileRecord(path.join(executionDirectory, 'native-result.json')),
              transportAttempts: attempts };
            break;
          }
          const transportReason = [execution.error, row?.reason].filter(Boolean).join('; ');
          const retryableTransportFailure = (!row || row.status === 'not_scored') &&
            (execution.rows.length === 0 || execution.rows.length === 1) &&
            execution.cleanup?.ownedAppUninstalled === true &&
            /Unexpected end of JSON|preflight|dumpLayout|transport|offline|timeout|canonical device row missing|App died|THREAD_BLOCK|connect to AAMS|RET_ERR_CONNECTION_EXIST/i
              .test(transportReason);
          if (!retryableTransportFailure || attempt === 3)
            if (row && row.traceDigest === spec.traceDigest) {
              rowEntry = { ...row, key: spec.key, role, freshInstall: true, build: fileRecord(buildReport),
                execution: fileRecord(executionFile), nativeResult: fileRecord(path.join(executionDirectory, 'native-result.json')),
                transportAttempts: attempts };
              break;
            } else throw commandError || new Error('Incomplete fresh Task09 execution: ' + slug);
          await sleep(5000);
        }
      } catch (error) {
        executionError = error;
      } finally {
        releaseLock();
      }
      const cleanup = removeCopiedHaps(buildReport);
      report.hapCleanup.push({ caseId: spec.caseId, ...cleanup });
      if (rowEntry) rowEntry.hapCleanup = cleanup;
      if (executionError) throw executionError;
      rows.push(rowEntry);
      await sleep(2000);
    }
    if (rows.some(row => row.evidence?.some(item => item.label === 'Task09.missingFeatureEntry'))) {
      const input = path.join(evidenceDirectory, 'entry-normalization.input.json');
      const normalized = path.join(evidenceDirectory, 'entry-normalized.json');
      const verifier = path.join(__dirname, 'task09_arkts_entry_evidence.py');
      fs.writeFileSync(input, JSON.stringify(report, null, 2) + '\n');
      run('verify-source-bound-spaces-entry', '/usr/bin/python3',
        [verifier, '--report', input, '--output', normalized], 120000);
      const verified = JSON.parse(fs.readFileSync(normalized));
      rows.splice(0, rows.length, ...verified.rows);
      report.entryVerification = { evaluator: fileRecord(verifier), input: fileRecord(input),
        output: fileRecord(normalized) };
    }
    const semantic = { total: 9, passed: 0, failed: 0, notScored: 0, cases: rows };
    for (const row of rows) semantic[row.status === 'pass' ? 'passed' : row.status === 'fail' ? 'failed' : 'notScored']++;
    report.semantic = semantic;
    report.runtimeCompile = { passed: true, status: 'passed',
      scope: 'evaluator_test_packaging_and_runtime_build', builds: 9 };
    report.status = semantic.notScored === 0 ? 'scored' : 'not_publishable';
    report.publication = { eligible: semantic.notScored === 0,
      reason: semantic.notScored === 0 ? 'All nine fresh runtime verdicts are available' : 'At least one runtime case is not scored' };
  } catch (error) {
    report.error = `${error.name || 'Error'}: ${error.message || error}`;
    report.semantic = { total: 9, passed: 0, failed: 0, notScored: 9,
      cases: contract.cases.map(spec => ({ caseId: spec.caseId, key: spec.key, traceDigest: spec.traceDigest,
        status: 'not_scored', reason: report.error, checkpoints: [], observed: {}, invariantChecks: [] })) };
    // Transport errors do not turn successful evaluator packaging into a build failure.
    if (report.runtimeCompile.passed !== true) report.runtimeCompile.status = rows.length ? 'partial' : 'failed';
    report.status = 'not_publishable';
    report.publication = { eligible: false, reason: report.error };
    process.exitCode = 1;
  } finally {
    try { releaseLock(); }
    catch (error) { report.cleanupError = String(error); report.publication.eligible = false; }
    const visit = directory => {
      for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
        const file = path.join(directory, item.name);
        if (item.isDirectory()) visit(file);
        else if (item.name === 'device-build-report.json') {
          const build = JSON.parse(fs.readFileSync(file));
          if (build.haps?.some(hap => fs.existsSync(hap.path))) {
            try { report.hapCleanup.push({ interruptedCase: build.caseId, ...removeCopiedHaps(file) }); }
            catch (error) { report.cleanupError = String(error); report.publication.eligible = false; }
          }
        }
      }
    };
    visit(evidenceDirectory);
    const observedLocks = [requiredLock, transportLock].filter(file => fs.existsSync(file));
    report.deviceLocksPresentAfter = ownsRequiredLock ? [requiredLock] : [];
    report.deviceLocksPresentAfterScope = 'only leases acquired by this scorer';
    report.foreignDeviceLocksPresentAfter = observedLocks.filter(file => !report.deviceLocksPresentAfter.includes(file));
    report.elapsedSeconds = Number(elapsed().toFixed(3));
    report.finishedAt = new Date().toISOString();
    fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
    fs.writeFileSync(path.join(evidenceDirectory, 'matrix.json'), JSON.stringify(report, null, 2) + '\n');
  }
  console.log(JSON.stringify({ output, status: report.status, semantic: report.semantic && {
    passed: report.semantic.passed, failed: report.semantic.failed, notScored: report.semantic.notScored },
    elapsedSeconds: report.elapsedSeconds }));
}

if (require.main === module) main().catch(error => { console.error(error.stack || String(error)); process.exitCode = 1; });

module.exports = { executionEnvironment };
