#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');

const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const hash = file => sha(fs.readFileSync(file));
const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

function marker(line) {
  const token = 'ARKTS_NATIVE_ROW_FILE ';
  const offset = line.indexOf(token);
  if (offset < 0) return null;
  try { return JSON.parse(line.slice(offset + token.length)); }
  catch (_) { return null; }
}

async function main() {
  const [buildFileArg, serial, outputArg] = process.argv.slice(2);
  if (!buildFileArg || !serial || !outputArg || !/^[A-Za-z0-9.:_-]+$/.test(serial)) {
    throw new Error('Usage: Task16Revision5Device.cjs BUILD_REPORT SERIAL FRESH_OUTPUT_DIR');
  }
  const buildFile = path.resolve(buildFileArg);
  const output = path.resolve(outputArg);
  if (fs.existsSync(output)) throw new Error('Refusing existing execution output');
  fs.mkdirSync(output, { recursive: true });
  const build = JSON.parse(fs.readFileSync(buildFile));
  if (build.taskId !== '16_identity_reset' || build.revision !== 5 || build.status !== 'built' ||
      !build.compile.passed || !build.runtimeCompile.passed || !build.productionCopiedUnchanged ||
      !build.productionSourceUnchanged || build.bundleCaseCount !== 10) throw new Error('Unverified Task16 revision5 build');
  const contract = JSON.parse(fs.readFileSync(build.contract.path));
  if (hash(build.contract.path) !== build.contract.sha256) throw new Error('Staged contract changed after build');
  const expected = new Map(contract.cases.map(item => [item.caseId, item.traceDigest]));
  const hdc = path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/toolchains/hdc');
  const lock = path.join('/tmp', 'ltb-arkts-device-' + sha(Buffer.from(serial)).slice(0, 16));
  const nonce = crypto.randomBytes(16).toString('hex');
  const report = { schemaVersion: 1, taskId: build.taskId, role: build.role, revision: 5,
    startedAt: new Date().toISOString(), serial, executionNonce: nonce,
    buildReport: { path: buildFile, sha256: hash(buildFile) }, contract: build.contract,
    commands: [], rows: [], cleanup: { appUninstalled: false, hapsRemoved: false, lockReleased: false },
    status: 'incomplete' };
  let locked = false;
  let owned = false;
  let userId;
  let originalAppLogBufferBytes;
  const run = (name, args, timeout = 30000, allowed = [0]) => {
    const startedAt = new Date().toISOString();
    const result = spawnSync(hdc, ['-t', serial, ...args], { encoding: 'utf8', timeout,
      maxBuffer: 32 * 1024 * 1024 });
    const text = (result.stdout || '') + (result.stderr || '');
    const logFile = path.join(output, name + '.log');
    fs.writeFileSync(logFile, text);
    report.commands.push({ argv: [hdc, '-t', serial, ...args], startedAt, finishedAt: new Date().toISOString(),
      exitCode: result.status, error: result.error && String(result.error), log: path.basename(logFile), sha256: hash(logFile) });
    if (result.error || !allowed.includes(result.status)) throw new Error(name + ' failed; see ' + logFile);
    return text;
  };
  try {
    const deadline = Date.now() + 3600 * 1000;
    while (!locked) {
      try { fs.mkdirSync(lock); locked = true; }
      catch (error) {
        if (error.code !== 'EEXIST' || Date.now() >= deadline) throw error;
        await sleep(1000);
      }
    }
    const buffer = run('hilog-buffer-before', ['shell', 'hilog', '-g', '-t', 'app']);
    const bufferMatch = buffer.match(/app buffer size is ([0-9.]+)([KMG])\b/);
    if (!bufferMatch) throw new Error('Unable to read original app hilog buffer size');
    const units = { K: 1024, M: 1024 ** 2, G: 1024 ** 3 };
    originalAppLogBufferBytes = Math.round(Number(bufferMatch[1]) * units[bufferMatch[2]]);
    run('hilog-buffer-expanded', ['shell', 'hilog', '-G', '16M', '-t', 'app']);
    run('hilog-cleared', ['shell', 'hilog', '-r', '-t', 'app']);
    const apps = run('installed-before', ['shell', 'bm', 'dump', '-a']);
    const users = [...apps.matchAll(/^ID: (\d+):/gm)].map(match => match[1]);
    if (users.length !== 1) throw new Error('Ambiguous device user inventory');
    userId = users[0];
    if (apps.split('\n').some(line => line.trim() === build.bundleName)) {
      throw new Error('Candidate already installed; refusing to touch unowned app data');
    }
    const haps = build.haps.slice();
    if (haps.length !== 2) throw new Error('Expected exactly application and ohosTest HAPs');
    for (const item of haps) {
      if (!fs.existsSync(item.path) || hash(item.path) !== item.sha256) throw new Error('HAP digest mismatch: ' + item.path);
    }
    owned = true;
    for (const [index, item] of haps.entries()) {
      const install = run('install-' + index, ['install', item.path], 60000);
      if (!install.includes('install bundle successfully')) throw new Error('Device rejected HAP ' + index);
    }
    run('screen-wakeup', ['shell', 'power-shell', 'wakeup']);
    const before = run('markers-before', ['shell', 'hilog', '-x', '-e', 'ARKTS_NATIVE_ROW_FILE']);
    const command = build.deviceTestCommand.slice();
    command.push('-s', 'ltbDeviceUser', userId, '-s', 'ltbExecutionNonce', nonce);
    const transcript = run('aa-test', command, 300000);
    if (!/TestFinished-ResultCode: 0\b/.test(transcript) ||
        !/Tests run: 10, Failure: 0, Error: 0, Pass: 10, Ignore: 0/.test(transcript)) {
      throw new Error('Hypium did not complete all ten cases successfully');
    }
    const after = run('markers-after', ['shell', 'hilog', '-x', '-e', 'ARKTS_NATIVE_ROW_FILE']);
    const known = new Set(before.split('\n'));
    const markers = after.split('\n').filter(line => !known.has(line)).map(marker).filter(item =>
      item && item.taskId === build.taskId && item.role === build.role && item.executionNonce === nonce);
    if (markers.length !== 10 || new Set(markers.map(item => item.caseId)).size !== 10) {
      throw new Error('Expected ten fresh nonce-bound result markers, observed ' + markers.length);
    }
    const rows = [];
    for (const item of markers.sort((a, b) => a.caseId.localeCompare(b.caseId))) {
      if (!/^ltb-native-result_\d+\.json$/.test(item.name) || expected.get(item.caseId) !== item.traceDigest && item.traceDigest !== undefined) {
        throw new Error('Invalid result marker: ' + JSON.stringify(item));
      }
      const remote = `/data/app/el2/${userId}/base/${build.bundleName}/cache/${item.name}`;
      const local = path.join(output, item.caseId + '.json');
      run('pull-' + item.caseId, ['file', 'recv', remote, local]);
      const bytes = fs.readFileSync(local);
      if (bytes.length !== item.bytes || bytes.toString('utf8').length !== item.characters) {
        throw new Error('Result length mismatch: ' + item.caseId);
      }
      const row = JSON.parse(bytes.toString('utf8'));
      if (row.taskId !== build.taskId || row.role !== build.role || row.caseId !== item.caseId ||
          row.traceDigest !== expected.get(item.caseId) || row.nativeBridge?.capabilities?.execution?.nonce !== nonce) {
        throw new Error('Result identity/digest/nonce mismatch: ' + item.caseId);
      }
      rows.push(row);
      report.rows.push({ caseId: row.caseId, traceDigest: row.traceDigest, status: row.status,
        file: path.basename(local), sha256: hash(local), bytes: bytes.length });
    }
    const counts = { passed: rows.filter(row => row.status === 'pass').length,
      failed: rows.filter(row => row.status === 'fail').length,
      notScored: rows.filter(row => row.status === 'not_scored').length,
      total: rows.length };
    report.semantic = { ...counts, cases: rows };
    report.transportCompleted = true;
    report.status = 'completed';
  } catch (error) {
    report.error = String(error.stack || error);
    report.status = 'blocked';
    process.exitCode = 1;
  } finally {
    if (owned) {
      try {
        report.cleanup.appUninstalled = run('cleanup-uninstall', ['uninstall', build.bundleName], 60000)
          .includes('uninstall bundle successfully');
      } catch (error) { report.cleanup.uninstallError = String(error); }
    }
    if (originalAppLogBufferBytes) {
      try {
        run('hilog-buffer-restored', ['shell', 'hilog', '-G', originalAppLogBufferBytes + 'B', '-t', 'app']);
        report.cleanup.hilogBufferRestored = true;
      } catch (error) { report.cleanup.hilogBufferRestoreError = String(error); }
    }
    try {
      for (const item of build.haps) fs.rmSync(item.path, { force: true });
      report.cleanup.hapsRemoved = build.haps.every(item => !fs.existsSync(item.path));
    } catch (error) { report.cleanup.hapCleanupError = String(error); }
    if (locked) {
      try { fs.rmdirSync(lock); report.cleanup.lockReleased = true; }
      catch (error) { report.cleanup.lockError = String(error); }
    }
    report.finishedAt = new Date().toISOString();
    fs.writeFileSync(path.join(output, 'device-execution.json'), JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify({ status: report.status, role: report.role, semantic: report.semantic && {
      passed: report.semantic.passed, failed: report.semantic.failed,
      notScored: report.semantic.notScored, total: report.semantic.total }, cleanup: report.cleanup,
      error: report.error }, null, 2));
  }
}

if (require.main === module) main().catch(error => { console.error(error); process.exitCode = 1; });
