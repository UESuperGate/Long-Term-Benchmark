#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const buildScript = path.join(__dirname, 'task17_arkts_strict_build.cjs');
const executeScript = path.join(__dirname, 'arkts_device_execute.cjs');
const contractFile = path.join(root, 'benchmark_tasks/17_pinned_messages/transitions.json');
const sourceByRole = {
  base: path.join(root, '17_pinned_messages_base_0_5_1'),
  final: path.join(root, 'final_dev_nodes/17_pinned_messages_final_0_5_3')
};
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const fileRecord = file => {
  const bytes = fs.readFileSync(file);
  return { path: path.relative(root, file), bytes: bytes.length, sha256: sha(bytes) };
};
const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

async function main() {
  const args = process.argv.slice(2);
  const value = flag => {
    const index = args.indexOf(flag);
    if (index < 0 || !args[index + 1] || args[index + 1].startsWith('--')) throw new Error(flag + ' is required');
    return args[index + 1];
  };
  const output = path.resolve(value('--output-dir'));
  const serial = value('--serial');
  const roleValue = args.includes('--roles') ? value('--roles') : 'base,final';
  const roles = roleValue.split(',').map(role => role.trim()).filter(Boolean);
  if (roles.length === 0 || roles.some(role => !['base', 'final'].includes(role)) ||
      new Set(roles).size !== roles.length) throw new Error('--roles must be a unique subset of base,final');
  if (fs.existsSync(output)) throw new Error('Refusing existing Task17 strict matrix evidence: ' + output);
  if (!/^[A-Za-z0-9.:_-]+$/.test(serial)) throw new Error('Invalid device serial');
  fs.mkdirSync(output, { recursive: true });
  const started = Date.now();
  const timeoutMs = 3600 * 1000;
  const contract = JSON.parse(fs.readFileSync(contractFile));
  const activeBefore = fileRecord(contractFile);
  const lockName = 'ltb-arkts-device-' + sha(Buffer.from(serial)).slice(0, 16);
  const requiredLock = path.join('/tmp', lockName);
  const transportLock = path.join(os.tmpdir(), lockName);
  const report = { schemaVersion: 1, taskId: '17_pinned_messages', platform: 'arkts',
    runtime: 'openharmony_api23_device_uitest_arkvm_original_module_native_preferences',
    startedAt: new Date(started).toISOString(), taskTimeoutSeconds: timeoutMs / 1000,
    requestedRoles: roles, contract: fileRecord(contractFile), activeCanonicalBefore: activeBefore,
    activeCanonicalModified: false, rows: [], commands: [], semantic: {}, compile: {}, status: 'incomplete' };

  const run = (name, command, commandArgs, timeout) => {
    const remaining = timeoutMs - (Date.now() - started);
    if (remaining <= 0) throw new Error('Task17 strict matrix exceeded 3600 seconds');
    const result = spawnSync(command, commandArgs, { cwd: root, encoding: 'utf8',
      timeout: Math.min(timeout, remaining), maxBuffer: 16 * 1024 * 1024 });
    const log = path.join(output, name + '.log');
    fs.writeFileSync(log, (result.stdout || '') + (result.stderr || ''));
    report.commands.push({ name, command: [command, ...commandArgs], exitCode: result.status,
      error: result.error && String(result.error), log: fileRecord(log) });
    if (result.error || result.status !== 0) throw new Error(name + ' failed: ' + (result.error || result.status));
  };

  try {
    if (contract.taskId !== '17_pinned_messages' || contract.cases.length !== 9) {
      throw new Error('Expected canonical Task17 contract with nine cases');
    }
    for (const role of roles) {
      for (const spec of contract.cases) {
        const slug = role + '-' + spec.caseId;
        const directory = path.join(output, slug);
        run('build-' + slug, process.execPath, [buildScript, '--source', sourceByRole[role], '--role', role,
          '--case', spec.caseId, '--output-dir', directory], 600000);
        let executionDirectory;
        let execution;
        for (let attempt = 1; attempt <= 20; attempt++) {
          while (fs.existsSync(requiredLock) || fs.existsSync(transportLock)) {
            if (Date.now() - started >= timeoutMs) throw new Error('Device lock remained occupied until task timeout');
            await sleep(2000);
          }
          let ownsRequiredLock = false;
          try {
            fs.mkdirSync(requiredLock);
            ownsRequiredLock = true;
            executionDirectory = path.join(directory, 'execution-attempt-' + attempt);
            try {
              run('execute-' + slug + '-attempt-' + attempt, process.execPath,
                [executeScript, path.join(directory, 'device-build-report.json'), serial, executionDirectory], 240000);
            } catch (error) {
              const failedFile = path.join(executionDirectory, 'device-execution.json');
              const failed = fs.existsSync(failedFile) ? JSON.parse(fs.readFileSync(failedFile)) : {};
              if (!String(failed.error || '').includes('EEXIST') || attempt === 20) throw error;
              continue;
            }
            execution = JSON.parse(fs.readFileSync(path.join(executionDirectory, 'device-execution.json')));
            break;
          } finally {
            if (ownsRequiredLock && fs.existsSync(requiredLock)) fs.rmdirSync(requiredLock);
          }
        }
        if (!execution) throw new Error('Task17 execution never acquired the shared device lock: ' + slug);
        const row = execution.rows.find(item => item.caseId === spec.caseId);
        if (!execution.transportCompleted || execution.status !== 'transport_completed' ||
            !execution.cleanup?.ownedAppUninstalled || !row || row.traceDigest !== spec.traceDigest) {
          throw new Error('Incomplete fresh Task17 device execution: ' + slug);
        }
        report.rows.push({ role, caseId: spec.caseId, traceDigest: spec.traceDigest, status: row.status,
          reason: row.reason, build: fileRecord(path.join(directory, 'device-build-report.json')),
          execution: fileRecord(path.join(executionDirectory, 'device-execution.json')),
          nativeResult: fileRecord(path.join(executionDirectory, 'native-result.json')),
          freshInstall: execution.candidateAbsentBeforeInstall === true, cleanup: execution.cleanup });
      }
    }
    for (const role of roles) {
      const rows = report.rows.filter(row => row.role === role);
      const counts = { total: rows.length, passed: 0, failed: 0, notScored: 0 };
      for (const row of rows) counts[row.status === 'pass' ? 'passed' : row.status === 'fail' ? 'failed' : 'notScored'] += 1;
      report.semantic[role] = counts;
      report.compile[role] = { passed: rows.length === 9, scope: 'standalone_application_and_ohosTest_hap_per_case', builds: rows.length };
    }
    const expected = { base: { total: 9, passed: 0, failed: 9, notScored: 0 },
      final: { total: 9, passed: 9, failed: 0, notScored: 0 } };
    if (roles.some(role => JSON.stringify(report.semantic[role]) !== JSON.stringify(expected[role]))) {
      throw new Error('Task17 strict four-pole target not met: ' + JSON.stringify(report.semantic));
    }
    report.status = 'passed';
  } finally {
    report.activeCanonicalAfter = fileRecord(contractFile);
    report.activeCanonicalModified = report.activeCanonicalAfter.sha256 !== activeBefore.sha256;
    report.finishedAt = new Date().toISOString();
    report.elapsedSeconds = Number(((Date.now() - started) / 1000).toFixed(3));
    report.deviceLocksPresentAfter = [requiredLock, transportLock].filter(file => fs.existsSync(file));
    fs.writeFileSync(path.join(output, 'matrix.json'), JSON.stringify(report, null, 2) + '\n');
  }
  console.log(JSON.stringify({ status: report.status, semantic: report.semantic,
    compile: report.compile, elapsedSeconds: report.elapsedSeconds }, null, 2));
}

if (require.main === module) main().catch(error => {
  console.error(error.stack || String(error));
  process.exitCode = 1;
});
