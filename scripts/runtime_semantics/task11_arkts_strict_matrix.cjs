#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const buildScript = path.join(__dirname, 'task11_arkts_strict_build.cjs');
const executeScript = path.join(__dirname, 'arkts_device_execute.cjs');
const contractFile = path.join(root, 'benchmark_tasks/11_room_upgrade_navigation/transitions.json');
const sourceByRole = {
  base: path.join(root, '11_room_upgrade_navigation_base_25_06_2'),
  final: path.join(root, 'final_dev_nodes/11_room_upgrade_navigation_final_25_06_3')
};
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const fileRecord = file => {
  const bytes = fs.readFileSync(file);
  return { path: path.relative(root, file), bytes: bytes.length, sha256: sha(bytes) };
};
const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
const hdc = path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/toolchains/hdc');
const sourceFiles = directory => fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
  const file = path.join(directory, entry.name);
  return entry.isDirectory() ? sourceFiles(file) : entry.isFile() ? [file] : [];
});

async function main() {
  const args = process.argv.slice(2);
  const value = flag => {
    const index = args.indexOf(flag);
    if (index < 0 || !args[index + 1] || args[index + 1].startsWith('--')) throw new Error(flag + ' is required');
    return args[index + 1];
  };
  const output = path.resolve(value('--output-dir'));
  const serial = value('--serial');
  const roles = (args.includes('--roles') ? value('--roles') : 'base,final').split(',').map(item => item.trim()).filter(Boolean);
  if (roles.length === 0 || roles.some(role => !['base', 'final'].includes(role)) || new Set(roles).size !== roles.length)
    throw new Error('--roles must be a unique comma-separated subset of base,final');
  if (fs.existsSync(output)) throw new Error('Refusing existing Task11 matrix evidence: ' + output);
  if (!/^[A-Za-z0-9.:_-]+$/.test(serial)) throw new Error('Invalid device serial');
  fs.mkdirSync(output, { recursive: true });
  const sharedExecutorSource = fs.readFileSync(executeScript, 'utf8');
  const providerLine = "const providerHostFile = path.resolve(__dirname, '../../state_tests/runtime/arkts/native/Tasks16_18ProviderHost.cjs');";
  const lockCleanup = '    if (locked) fs.rmdirSync(lock);';
  const idempotentLockCleanup = '    if (locked && fs.existsSync(lock)) fs.rmdirSync(lock);';
  if (sharedExecutorSource.split(providerLine).length !== 2 ||
      ![lockCleanup, idempotentLockCleanup].some(line => sharedExecutorSource.split(line).length === 2))
    throw new Error('Shared device executor shape changed');
  const strictExecutor = path.join(output, 'task11-strict-executor.generated.cjs');
  fs.writeFileSync(strictExecutor, sharedExecutorSource
    .replace(providerLine, 'const providerHostFile = ' + JSON.stringify(path.join(root,
      'state_tests/runtime/arkts/native/Tasks16_18ProviderHost.cjs')) + ';')
    .replace(lockCleanup, idempotentLockCleanup));
  const started = Date.now();
  const timeoutMs = 3600 * 1000;
  const contract = JSON.parse(fs.readFileSync(contractFile));
  const canonicalBefore = fileRecord(contractFile);
  const productionBefore = Object.fromEntries(Object.entries(sourceByRole).map(([role, directory]) => [role,
    sourceFiles(path.join(directory, 'entry/src/main')).map(file => ({ path: path.relative(directory, file), sha256: sha(fs.readFileSync(file)) }))]));
  const lockName = 'ltb-arkts-device-' + sha(Buffer.from(serial)).slice(0, 16);
  const requiredLock = path.join('/tmp', lockName);
  const transportLock = path.join(os.tmpdir(), lockName);
  const report = { schemaVersion: 1, taskId: '11_room_upgrade_navigation', platform: 'arkts',
    runtime: 'openharmony_api23_device_uitest_and_original_production_runtime', startedAt: new Date(started).toISOString(),
    taskTimeoutSeconds: timeoutMs / 1000, requestedRoles: roles, contract: canonicalBefore,
    activeCanonicalBefore: canonicalBefore, activeCanonicalModified: false, productionBefore,
    executor: { shared: fileRecord(executeScript), derived: fileRecord(strictExecutor),
      lockCleanup: 'idempotent release only; no semantic or transport verdict change' },
    rows: [], commands: [], semantic: {}, compile: {}, status: 'incomplete' };
  const run = (name, command, commandArgs, timeout) => {
    const remaining = timeoutMs - (Date.now() - started);
    if (remaining <= 0) throw new Error('Task11 matrix exceeded 3600 seconds');
    const result = spawnSync(command, commandArgs, { cwd: root, encoding: 'utf8', timeout: Math.min(timeout, remaining),
      maxBuffer: 16 * 1024 * 1024 });
    const log = path.join(output, name + '.log');
    fs.writeFileSync(log, (result.stdout || '') + (result.stderr || ''));
    report.commands.push({ name, command: [command, ...commandArgs], exitCode: result.status,
      error: result.error && String(result.error), log: fileRecord(log) });
    if (result.error || result.status !== 0) throw new Error(name + ' failed: ' + (result.error || result.status));
  };
  const waitForLocks = async () => {
    while (fs.existsSync(requiredLock) || fs.existsSync(transportLock)) {
      if (Date.now() - started >= timeoutMs) throw new Error('Shared device lock remained occupied for 3600 seconds');
      await sleep(2000);
    }
  };
  const waitForDevice = async () => {
    while (true) {
      const probe = spawnSync(hdc, ['-t', serial, 'shell', 'bm', 'dump', '-a'], { encoding: 'utf8', timeout: 15000 });
      if (!probe.error && probe.status === 0 && /^ID: \d+:/m.test(probe.stdout)) return;
      if (Date.now() - started >= timeoutMs) throw new Error('OpenHarmony API23 device remained offline for 3600 seconds');
      await sleep(3000);
    }
  };

  try {
    if (contract.taskId !== '11_room_upgrade_navigation' || contract.cases.length !== 6)
      throw new Error('Expected six active Task11 canonical cases');
    for (const role of roles) {
      for (const spec of contract.cases) {
        await waitForLocks();
        const slug = role + '-' + spec.caseId;
        const directory = path.join(output, slug);
        run('build-' + slug, process.execPath, [buildScript, '--source', sourceByRole[role], '--role', role,
          '--case', spec.caseId, '--output-dir', directory], 600000);
        const buildReport = path.join(directory, 'device-build-report.json');
        let executionDirectory, execution;
        for (let attempt = 1; attempt <= 20; attempt++) {
          await waitForDevice();
          await waitForLocks();
          let ownsRequiredLock = false;
          try {
            fs.mkdirSync(requiredLock);
            ownsRequiredLock = true;
            executionDirectory = path.join(directory, 'execution-attempt-' + attempt);
            try {
              run('execute-' + slug + '-attempt-' + attempt, process.execPath,
                [strictExecutor, buildReport, serial, executionDirectory], 240000);
            } catch (error) {
              const failedFile = path.join(executionDirectory, 'device-execution.json');
              const failed = fs.existsSync(failedFile) ? JSON.parse(fs.readFileSync(failedFile)) : {};
              const beforeInstallFailure = failed.candidateAbsentBeforeInstall !== true &&
                failed.cleanup?.ownedAppUninstalled === false && [
                  'installed-before command failed', 'Unable to inventory installed apps'
                ].some(message => String(failed.error || '').includes(message));
              const rejectedBeforeReceipt = failed.candidateAbsentBeforeInstall === true &&
                failed.cleanup?.ownedAppUninstalled === false && String(failed.error || '').includes('Install rejected') &&
                failed.commands?.some(command => command.log === 'install-0.log') &&
                !failed.commands?.some(command => command.log === 'install-1.log');
              const cleanedFailure = failed.cleanup?.ownedAppUninstalled === true;
              const infrastructureOnly = Array.isArray(failed.rows) && failed.rows.length === 0 &&
                (beforeInstallFailure || rejectedBeforeReceipt || cleanedFailure) && [
                  'EEXIST', 'ui-preflight-dump command failed', 'ui-preflight-tree command failed',
                  'screen-wakeup command failed', 'installed-before command failed',
                  'Unable to inventory installed apps', 'Install rejected'
                ].some(message => String(failed.error || '').includes(message));
              if (!infrastructureOnly || attempt === 20) throw error;
              await sleep(5000);
              continue;
            }
            execution = JSON.parse(fs.readFileSync(path.join(executionDirectory, 'device-execution.json')));
            break;
          } finally {
            if (ownsRequiredLock && fs.existsSync(requiredLock)) fs.rmdirSync(requiredLock);
          }
        }
        if (!execution) throw new Error('Task11 execution never acquired the shared lock: ' + slug);
        const row = execution.rows.find(item => item.caseId === spec.caseId);
        if (!execution.transportCompleted || execution.status !== 'transport_completed' ||
            !execution.cleanup?.ownedAppUninstalled || !row || row.traceDigest !== spec.traceDigest ||
            execution.candidateAbsentBeforeInstall !== true) throw new Error('Incomplete fresh device execution: ' + slug);
        report.rows.push({ role, caseId: spec.caseId, traceDigest: spec.traceDigest, status: row.status,
          reason: row.reason, observationLevel: row.observationLevel,
          build: fileRecord(buildReport), execution: fileRecord(path.join(executionDirectory, 'device-execution.json')),
          nativeResult: fileRecord(path.join(executionDirectory, 'native-result.json')),
          freshInstall: true, cleanup: execution.cleanup });
      }
    }
    for (const role of roles) {
      const rows = report.rows.filter(row => row.role === role);
      const counts = { total: rows.length, passed: 0, failed: 0, notScored: 0 };
      for (const row of rows) counts[row.status === 'pass' ? 'passed' : row.status === 'fail' ? 'failed' : 'notScored'] += 1;
      report.semantic[role] = counts;
      report.compile[role] = { passed: rows.length === 6, scope: 'application_and_ohosTest_hap_per_case', builds: rows.length };
    }
    const expected = { base: { total: 6, passed: 0, failed: 6, notScored: 0 },
      final: { total: 6, passed: 6, failed: 0, notScored: 0 } };
    if (roles.some(role => JSON.stringify(report.semantic[role]) !== JSON.stringify(expected[role])))
      throw new Error('Task11 strict four-pole target not met: ' + JSON.stringify(report.semantic));
    report.status = 'passed';
  } finally {
    report.activeCanonicalAfter = fileRecord(contractFile);
    report.activeCanonicalModified = report.activeCanonicalAfter.sha256 !== canonicalBefore.sha256;
    report.productionAfter = Object.fromEntries(Object.entries(sourceByRole).map(([role, directory]) => [role,
      sourceFiles(path.join(directory, 'entry/src/main')).map(file => ({ path: path.relative(directory, file), sha256: sha(fs.readFileSync(file)) }))]));
    report.productionStableDuringRun = JSON.stringify(report.productionBefore) === JSON.stringify(report.productionAfter);
    report.finishedAt = new Date().toISOString();
    report.elapsedSeconds = Number(((Date.now() - started) / 1000).toFixed(3));
    report.deviceLocksPresentAfter = [requiredLock, transportLock].filter(file => fs.existsSync(file));
    fs.writeFileSync(path.join(output, 'matrix.json'), JSON.stringify(report, null, 2) + '\n');
  }
  console.log(JSON.stringify({ status: report.status, semantic: report.semantic, compile: report.compile,
    elapsedSeconds: report.elapsedSeconds }, null, 2));
}

if (require.main === module) main().catch(error => { console.error(error.stack || String(error)); process.exitCode = 1; });
