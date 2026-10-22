#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const fileHash = file => hash(fs.readFileSync(file));
const TASK = '18_custom_notification_sounds';

function inventory(text, bundleName) {
  const users = [...text.matchAll(/^ID: (\d+):/gm)].map(match => match[1]);
  if (users.length !== 1 || !text.includes('ID:')) throw new Error('Installed-user inventory is absent or ambiguous');
  if (text.split('\n').some(line => line.trim() === bundleName)) throw new Error('Candidate already installed; no overwrite or uninstall allowed');
  return users[0];
}

function validateBuild(build) {
  if (build.taskId !== TASK || build.kind !== 'standalone_sdk_capability' || build.canonicalPromotionAllowed !== false ||
      build.status !== 'built_not_executed' || build.runtimeCompile?.passed !== true ||
      build.productionUnchanged !== true || build.copiedCandidateFilesUnchanged !== true) throw new Error('Not a verified task18 diagnostic build');
  if (!/^com\.[A-Za-z0-9_.]+$/.test(build.bundleName)) throw new Error('Invalid bundle name');
  const all = build.haps || [];
  const signed = all.some(item => /-signed\.hap$/.test(item.path));
  const selected = all.filter(item => signed ? /-signed\.hap$/.test(item.path) : /-unsigned\.hap$/.test(item.path));
  if (selected.length !== 2 || !selected.some(item => /entry-default-/.test(path.basename(item.path))) ||
      !selected.some(item => /entry-ohosTest-/.test(path.basename(item.path)))) throw new Error('Expected exactly app and test HAP');
  for (const item of selected) {
    if (fs.statSync(item.path).size !== item.bytes || fileHash(item.path) !== item.sha256) throw new Error('HAP digest/size mismatch');
  }
  if (!Array.isArray(build.installation?.fixtures) || build.installation.fixtures.length !== 2 ||
      !build.installation.fixtures.some(item => path.basename(item.path) === 'Tasks16_18ChannelCapability.test.ets')) throw new Error('Missing fixture provenance');
  for (const item of [...build.installation.fixtures, build.buildScript]) {
    if (!item || fileHash(item.path) !== item.sha256) throw new Error('Fixture or build script changed; rebuild before running');
  }
  return selected;
}

function validateResult(row, { nonce, bundleName, startedAtMs, finishedAtMs }) {
  if (row.schemaVersion !== 1 || row.taskId !== TASK || row.observationLevel !== 'native_sdk_capability_diagnostic_only' ||
      row.canonicalPromotionAllowed !== false || row.nonce !== nonce || row.bundleName !== bundleName) throw new Error('Diagnostic result identity/scope mismatch');
  if (!Number.isFinite(row.startedAtMs) || !Number.isFinite(row.finishedAtMs) ||
      row.startedAtMs < startedAtMs || row.finishedAtMs > finishedAtMs || row.finishedAtMs < row.startedAtMs) throw new Error('Result outside same device-clock run interval');
  if (row.cacheDir !== '/data/storage/el2/base/cache') throw new Error('Unexpected actual ApplicationContext cache directory; mapping not assumed');
  if (!Array.isArray(row.calls) || !row.calls.length || !Array.isArray(row.unsupported) || !Array.isArray(row.cleanupErrors)) throw new Error('Missing raw SDK observations');
  const allowed = new Set(['notificationManager.getSlots', 'notificationManager.addSlot', 'notificationManager.getSlot',
    'reminderAgentManager.addNotificationSlot', 'notificationManager.isNotificationEnabled', 'notificationManager.publish',
    'notificationManager.getActiveNotifications', 'notificationManager.cancel', 'notificationManager.removeSlot']);
  let prior = row.startedAtMs;
  for (const call of row.calls) {
    if (!allowed.has(call.api) || !Number.isFinite(call.startedAtMs) || call.startedAtMs < prior ||
        !Number.isFinite(call.finishedAtMs) || call.finishedAtMs < call.startedAtMs || call.finishedAtMs > row.finishedAtMs) throw new Error('Incomplete or unordered SDK checkpoint');
    JSON.parse(call.inputJson);
    if (typeof call.resultJson === 'string') JSON.parse(call.resultJson);
    else if (typeof call.error !== 'string' || !call.error) throw new Error('SDK result/error missing');
    prior = call.finishedAtMs;
  }
  // Transport validity never opens the canonical gate, including perfect-looking SDK readbacks.
  return { scope: 'SDK diagnostic transport only', canonicalPromotionAllowed: false,
    callCount: row.calls.length, completedWithoutSdkErrors: row.calls.every(call => !call.error),
    effectiveCustomSoundProven: false, productionConsumerObserved: false };
}

function parseDeviceTime(output) {
  const text = output.trim();
  if (!/^\d{13}$/.test(text)) throw new Error('No precise device epoch milliseconds');
  return Number(text);
}

function main() {
  const args = process.argv.slice(2);
  if (args.includes('--help')) {
    console.log('Tasks16_18ChannelExecute.cjs --build capability-build.json --serial SERIAL --output-dir NEW_DIR --reserved-device\nOnly run after the parent explicitly releases/reserves the device. No permission grants or canonical scoring.');
    return;
  }
  if (!args.includes('--reserved-device')) throw new Error('Parent-coordinated --reserved-device required');
  const value = flag => { const i = args.indexOf(flag); if (i < 0 || !args[i + 1] || args[i + 1].startsWith('--')) throw new Error('Missing ' + flag); return args[i + 1]; };
  const serial = value('--serial');
  if (!/^[A-Za-z0-9.:_-]+$/.test(serial)) throw new Error('Invalid serial');
  const buildFile = path.resolve(value('--build')), build = JSON.parse(fs.readFileSync(buildFile, 'utf8'));
  const haps = validateBuild(build);
  const output = path.resolve(value('--output-dir'));
  if (fs.existsSync(output)) throw new Error('Refusing existing output directory');
  fs.mkdirSync(output, { recursive: true });
  const nonce = crypto.randomBytes(16).toString('hex');
  const report = { schemaVersion: 1, taskId: TASK, status: 'incomplete', canonicalPromotionAllowed: false,
    benchmarkSemanticMetric: null, serial, nonce, bundleName: build.bundleName, startedAt: new Date().toISOString(),
    executor: { path: __filename, sha256: fileHash(__filename) },
    build: { path: buildFile, sha256: fileHash(buildFile) }, commands: [], cleanup: { ownedAppUninstalled: false } };
  const hdc = path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/toolchains/hdc');
  const lock = path.join('/tmp', 'ltb-arkts-device-' + hash(serial).slice(0, 16));
  let locked = false, owned = false, attemptedTest = false;
  const run = (name, command, timeout = 20000) => {
    const startedAt = new Date().toISOString();
    const result = spawnSync(hdc, ['-t', serial, ...command], { encoding: 'utf8', timeout, maxBuffer: 8 * 1024 * 1024 });
    const text = (result.stdout || '') + (result.stderr || '');
    const file = path.join(output, name + '.log');
    fs.writeFileSync(file, text);
    report.commands.push({ argv: [hdc, '-t', serial, ...command], startedAt, finishedAt: new Date().toISOString(),
      exitCode: result.status, error: result.error?.message, stdout: result.stdout || '', stderr: result.stderr || '',
      log: file, bytes: Buffer.byteLength(text), sha256: fileHash(file) });
    if (result.error || result.status !== 0) throw new Error(name + ' command failed; raw output retained');
    return text;
  };
  try {
    fs.mkdirSync(lock); locked = true;
    report.deviceUserId = inventory(run('installed-before', ['shell', 'bm', 'dump', '-a']), build.bundleName);
    report.candidateAbsentBeforeInstall = true;
    run('device-api', ['shell', 'param', 'get', 'const.ohos.apiversion']);
    run('device-version', ['shell', 'param', 'get', 'const.ohos.fullname']);
    for (const [index, hap] of haps.entries()) {
      // Inventory proved absence under the shared exclusive device lock. Own
      // any partial install from this attempt too, but never a preexisting app.
      owned = true;
      const text = run('install-' + index, ['install', hap.path], 45000);
      if (!text.includes('install bundle successfully') || /permission denied|\[Fail\]/i.test(text)) throw new Error('Installation rejected');
    }
    const before = run('markers-before', ['shell', 'hilog', '-x', '-e', 'TASK18_CAPABILITY_FILE']);
    const beforeMs = parseDeviceTime(run('device-time-before', ['shell', 'date', '+%s%3N']));
    attemptedTest = true;
    run('aa-test', ['shell', 'aa', 'test', '-b', build.bundleName, '-m', 'entry_test', '-s', 'unittest', 'OpenHarmonyTestRunner',
      '-s', 'ltbExecutionNonce', nonce, '-s', 'timeout', '60000', '-w', '90000'], 100000);
    const afterMs = parseDeviceTime(run('device-time-after', ['shell', 'date', '+%s%3N']));
    const markers = run('markers-after', ['shell', 'hilog', '-x', '-e', 'TASK18_CAPABILITY_FILE']);
    const known = new Set(before.split('\n'));
    const lines = markers.split('\n').filter(line => !known.has(line) && line.includes('TASK18_CAPABILITY_FILE ' + nonce + ' '));
    if (lines.length !== 1) throw new Error('Exactly one fresh nonce-bound diagnostic file marker required');
    const match = lines[0].match(/^\S+\s+\S+\s+(\d+)\s+\d+\s/);
    if (!match) throw new Error('Marker has no native PID');
    report.pid = match[1];
    const filename = 'Tasks16_18ChannelCapability-' + nonce + '.json';
    const expectedPath = '/data/storage/el2/base/cache/' + filename;
    if (!lines[0].trim().endsWith('TASK18_CAPABILITY_FILE ' + nonce + ' ' + expectedPath)) throw new Error('Unrecognized actual cache path');
    run('native-process', ['shell', 'hilog', '-x', '-P', report.pid]);
    const local = path.join(output, 'native-capability.json');
    const remote = 'data/storage/el2/base/cache/' + filename;
    const receipt = run('pull-diagnostic', ['file', 'recv', '-b', build.bundleName, remote, local]);
    const bytes = fs.readFileSync(local);
    const sizes = [...receipt.matchAll(/Size:\s*(\d+)/g)].map(match => Number(match[1]));
    if (!receipt.includes('FileTransfer finish') || !sizes.includes(bytes.length) || bytes.length > 1024 * 1024 ||
        /permission denied|\[Fail\]|no such file/i.test(receipt)) throw new Error('Transfer receipt does not match complete file');
    const row = JSON.parse(bytes.toString('utf8'));
    report.validation = validateResult(row, { nonce, bundleName: build.bundleName, startedAtMs: beforeMs, finishedAtMs: afterMs });
    report.nativeResult = { path: local, remote, actualContextPath: row.cacheDir, sha256: hash(bytes), bytes: bytes.length };
    report.status = 'diagnostic_captured_not_scored';
  } catch (error) { report.error = String(error); process.exitCode = 1; }
  finally {
    if (owned && attemptedTest && !report.nativeResult) {
      // Keep partial checkpoints before removing the owned app. No missing
      // marker, truncated JSON or failed transfer can become verified evidence.
      try {
        const remote = 'data/storage/el2/base/cache/Tasks16_18ChannelCapability-' + nonce + '.json';
        const local = path.join(output, 'partial-native-capability.json');
        const receipt = run('pull-partial-diagnostic', ['file', 'recv', '-b', build.bundleName, remote, local]);
        const bytes = fs.readFileSync(local);
        report.partialDiagnostic = { path: local, remote, bytes: bytes.length, sha256: hash(bytes),
          verified: false, scope: 'Unvalidated partial diagnostic only', receipt };
      } catch (error) { report.partialDiagnosticError = String(error); }
    }
    if (owned) {
      try {
        const result = run('cleanup-uninstall', ['uninstall', build.bundleName]);
        report.cleanup.ownedAppUninstalled = result.includes('uninstall bundle successfully') && !/permission denied|\[Fail\]/i.test(result);
        if (!report.cleanup.ownedAppUninstalled) throw new Error('Owned uninstall not confirmed');
      } catch (error) { report.cleanup.error = String(error); process.exitCode = 1; }
    }
    if (locked) fs.rmdirSync(lock);
    report.finishedAt = new Date().toISOString();
    fs.writeFileSync(path.join(output, 'capability-execution.json'), JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify({ status: report.status, error: report.error, cleanup: report.cleanup, output }, null, 2));
  }
}

module.exports = { inventory, validateBuild, validateResult, parseDeviceTime };
if (require.main === module) { try { main(); } catch (error) { console.error(error); process.exitCode = 1; } }
