#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const providerHostFile = path.resolve(__dirname, '../../state_tests/runtime/arkts/native/Tasks16_18ProviderHost.cjs');
const providerHost = require(providerHostFile);
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const sleepSync = milliseconds => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, milliseconds);
const deviceLockPath = serial => path.join('/tmp', 'ltb-arkts-device-' +
  crypto.createHash('sha256').update(serial).digest('hex').slice(0, 16));

function decodeRows(log) {
  const groups = new Map();
  for (const line of log.split('\n')) {
    const marker = 'ARKTS_NATIVE_ROW ';
    const offset = line.indexOf(marker);
    if (offset < 0) continue;
    const item = JSON.parse(line.slice(offset + marker.length));
    if (!Number.isInteger(item.chunks) || item.chunks < 1 || !Number.isInteger(item.index) ||
        item.index < 0 || item.index >= item.chunks || typeof item.text !== 'string') throw new Error('Invalid row fragment');
    const key = JSON.stringify([item.taskId, item.role, item.caseId]);
    if (!groups.has(key)) groups.set(key, { count: item.chunks, parts: new Map() });
    const group = groups.get(key);
    if (group.count !== item.chunks || group.parts.has(item.index)) throw new Error('Duplicate or inconsistent row fragment');
    group.parts.set(item.index, item.text);
  }
  return [...groups].map(([key, group]) => {
    if (group.parts.size !== group.count) throw new Error('Incomplete native row');
    const row = JSON.parse(Array.from({ length: group.count }, (_, i) => group.parts.get(i)).join(''));
    if (JSON.stringify([row.taskId, row.role, row.caseId]) !== key) throw new Error('Row identity differs from fragments');
    return row;
  });
}

function freshPid(before, after) {
  const known = new Set(before.split('\n'));
  const starts = after.split('\n').filter(line => line.includes('ARKTS_DEVICE_HARNESS_START') &&
    !line.includes('START_ERROR') && !known.has(line));
  if (starts.length !== 1) throw new Error('Expected exactly one new harness process');
  const match = starts[0].match(/^\S+\s+\S+\s+(\d+)\s+\d+\s/);
  if (!match) throw new Error('Unrecognized native log PID');
  return match[1];
}

function freshResultPid(before, after, processOutput, expected) {
  const pids = processOutput.trim().split(/\s+/);
  if (pids.length !== 1 || !/^[1-9]\d*$/.test(pids[0])) throw new Error('Candidate process is absent or ambiguous');
  const known = new Set(before.split('\n'));
  const markers = after.split('\n').filter(line => line.includes('ARKTS_NATIVE_ROW_FILE ') && !known.has(line));
  const matching = [];
  for (const line of markers) {
    const marker = JSON.parse(line.slice(line.indexOf('ARKTS_NATIVE_ROW_FILE ') + 'ARKTS_NATIVE_ROW_FILE '.length));
    if (['taskId', 'role', 'caseId'].every(key => marker[key] === expected[key])) matching.push({ line, marker });
  }
  if (matching.length !== 1 || !/^ltb-native-result_\d+\.json$/.test(matching[0].marker.name)) {
    throw new Error('Expected exactly one fresh canonical result marker');
  }
  const match = matching[0].line.match(/^\S+\s+\S+\s+(\d+)\s+\d+\s/);
  if (!match || match[1] !== pids[0]) throw new Error('Result marker does not belong to current candidate process');
  return pids[0];
}

function freshNoncePid(before, after, expected, nonce) {
  if (!/^[a-f0-9]{32}$/.test(nonce)) throw new Error('Invalid expected execution nonce');
  const known = new Set(before.split('\n'));
  const matching = after.split('\n').filter(line => !known.has(line) && line.includes('ARKTS_NATIVE_ROW_FILE '))
    .filter(line => {
      const item = JSON.parse(line.slice(line.indexOf('ARKTS_NATIVE_ROW_FILE ') + 'ARKTS_NATIVE_ROW_FILE '.length));
      return ['taskId', 'role', 'caseId'].every(key => item[key] === expected[key]) &&
        item.executionNonce === nonce && /^ltb-native-result_\d+\.json$/.test(item.name);
    });
  if (matching.length !== 1) throw new Error('Expected exactly one fresh nonce-bound canonical result marker');
  const match = matching[0].match(/^\S+\s+\S+\s+(\d+)\s+\d+\s/);
  if (!match) throw new Error('Nonce marker lacks a process identity');
  return match[1];
}

function screenLocked(layout) {
  if (!layout || !Array.isArray(layout.children) || !layout.children.length) throw new Error('Native UI preflight has no window tree');
  const visit = node => ['ScreenLockRootComponent', 'MainPageView_Screen_Lock_Home'].includes(node.attributes?.id) ||
    (node.children || []).some(visit);
  return visit(layout);
}

function inputSetupBlocked(layout) {
  const windows = [];
  const walk = node => {
    if (node.attributes?.bundleName === 'com.huawei.hmos.inputmethod') windows.push(node);
    for (const child of node.children || []) walk(child);
  };
  walk(layout || {});
  return windows.some(window => {
    const ids = new Set();
    const collect = node => {
      if (node.attributes?.visible !== 'false') ids.add(node.attributes?.id);
      for (const child of node.children || []) collect(child);
    };
    collect(window);
    return ids.has('Paf.Permission.button_cancel') && ids.has('Paf.Permission.button_confirm');
  });
}

async function main() {
  const [buildFile, serial, outputDirectory] = process.argv.slice(2);
  if (!buildFile || !serial || !/^[A-Za-z0-9.:_-]+$/.test(serial)) throw new Error('Usage: arkts_device_execute.cjs BUILD_REPORT SERIAL [FRESH_OUTPUT_DIRECTORY]');
  const build = JSON.parse(fs.readFileSync(buildFile));
  const output = outputDirectory ? path.resolve(outputDirectory) : path.dirname(path.resolve(buildFile));
  if (outputDirectory && fs.existsSync(output)) throw new Error('Refusing existing replay directory');
  fs.mkdirSync(output, { recursive: true });
  const reportFile = path.join(output, 'device-execution.json');
  if (fs.existsSync(reportFile)) throw new Error('Refusing to overwrite execution evidence');
  const report = { startedAt: new Date().toISOString(), taskId: build.taskId, role: build.role, caseId: build.caseId,
    buildReport: { path: path.resolve(buildFile), sha256: hash(buildFile) }, serial,
    status: 'incomplete', productionUnchanged: build.productionUnchanged, commands: [], rows: [],
    benchmarkSemanticMetric: null, cleanup: { ownedAppUninstalled: false } };
  if (build.supportsExecutionNonce) report.executionNonce = crypto.randomBytes(16).toString('hex');
  const hdc = path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/toolchains/hdc');
  const lock = deviceLockPath(serial);
  const lockPreacquired = process.env.LTB_DEVICE_LOCK_PREACQUIRED === '1';
  let locked = false;
  let owned = false;
  let uiPreflightFile;
  let uiPostflightFile;
  let providerWorker;
  let providerConfig;
  const run = (name, args, timeout = 30000) => {
    for (let attempt = 1; attempt <= 5; attempt++) {
      const result = spawnSync(hdc, ['-t', serial, ...args], { encoding: 'utf8', timeout, maxBuffer: 16 * 1024 * 1024 });
      const log = (result.stdout || '') + (result.stderr || '');
      const disconnected = /\[Fail\]\[E001005\]\s*Device not found or connected/.test(log);
      const file = path.join(output, name + (disconnected ? '-device-retry-' + attempt : '') + '.log');
      fs.writeFileSync(file, log);
      report.commands.push({ args, attempt, transientDeviceOffline: disconnected, exitCode: result.status,
        signal: result.signal, error: result.error && String(result.error), log: path.basename(file), sha256: hash(file) });
      if (disconnected && attempt < 5) { sleepSync(2000); continue; }
      if (result.error || result.status !== 0 || disconnected) throw new Error(name + ' command failed');
      return log;
    }
    throw new Error(name + ' exhausted device retries');
  };
  try {
    if (!lockPreacquired) {
      fs.mkdirSync(lock);
      locked = true;
    }
    if (!build.runtimeCompile.passed || !build.productionUnchanged || !build.copiedProductionUnchanged) throw new Error('Unverified build');
    if (!/^com\.[a-zA-Z0-9_.]+$/.test(build.bundleName)) throw new Error('Invalid candidate bundle');
    const apps = run('installed-before', ['shell', 'bm', 'dump', '-a']);
    if (!apps.includes('ID:')) throw new Error('Unable to inventory installed apps');
    const users = [...apps.matchAll(/^ID: (\d+):/gm)].map(match => match[1]);
    if (users.length !== 1) throw new Error('Ambiguous device user for sandbox evidence retrieval');
    report.deviceUserId = users[0];
    if (apps.split('\n').some(line => line.trim() === build.bundleName)) throw new Error('Candidate already installed; refusing to touch existing app data');
    report.candidateAbsentBeforeInstall = true;
    const haps = build.haps.filter(hap => hap.signed === build.haps.some(item => item.signed));
    if (haps.length !== 2) throw new Error('Expected app and test HAP');
    for (const hap of haps) if (hash(hap.path) !== hap.sha256) throw new Error('HAP digest mismatch');
    owned = true;
    for (const [index, hap] of haps.entries()) {
      if (!run('install-' + index, ['install', hap.path]).includes('install bundle successfully')) throw new Error('Install rejected');
    }
    if (build.nativeUIObserver) {
      run('screen-wakeup', ['shell', 'power-shell', 'wakeup']);
      uiPreflightFile = '/data/local/tmp/ltb-ui-preflight-' + Date.now() + '.json';
      run('ui-preflight-dump', ['shell', 'uitest', 'dumpLayout', '-p', uiPreflightFile], 120000);
      const layout = JSON.parse(run('ui-preflight-tree', ['shell', 'cat', uiPreflightFile]));
      report.uiPreflight = { locked: screenLocked(layout), inputSetupBlocked: inputSetupBlocked(layout),
        scope: 'Device state only, not candidate semantics' };
      if (report.uiPreflight.locked) throw new Error('Emulator is locked; unlock it before testing candidate UI');
      if (report.uiPreflight.inputSetupBlocked) throw new Error('System keyboard onboarding blocks candidate input; configure the emulator input method before testing');
    }
    const before = run('harness-before', ['shell', 'hilog', '-x', '-e', 'ARKTS_DEVICE_HARNESS_START']);
    const resultBefore = run('result-markers-before', ['shell', 'hilog', '-x', '-e', 'ARKTS_NATIVE_ROW_FILE']);
    const command = build.deviceTestCommand.slice(3);
    command.push('-s', 'ltbDeviceUser', report.deviceUserId);
    if (report.executionNonce) command.push('-s', 'ltbExecutionNonce', report.executionNonce);
    if (build.supportsTasks16To18ProviderHost === true) {
      if (!build.providerHostSource || build.providerHostSource.sha256 !== hash(providerHostFile)) {
        throw new Error('Provider worker source changed since build; rebuild to bind evaluator provenance');
      }
      const original = build.nativeUIObserver?.originalModule;
      if (original?.bundleName !== build.bundleName) throw new Error('Provider host requires exact original app scope');
      providerConfig = { nonce: report.executionNonce, taskId: build.taskId, caseId: build.caseId,
        bundleName: build.bundleName, role: build.role, userId: report.deviceUserId, serial,
        hostModule: original.moduleName, hostAbility: original.abilityName, hdc, output };
      providerWorker = await providerHost.startWorker(providerConfig);
      report.providerHostSource = { path: providerHostFile, sha256: hash(providerHostFile) };
      command.push('-s', 'ltbProviderHostBridge', '1');
    }
    if (command.some(arg => /<.*>/.test(arg))) throw new Error('Unresolved device command placeholder');
    const transcript = run('aa-test', command, 150000);
    if (providerWorker) {
      report.providerHost = await providerWorker.stop();
      providerWorker = undefined;
    }
    const after = run('harness-after', ['shell', 'hilog', '-x', '-e', 'ARKTS_DEVICE_HARNESS_START']);
    try {
      report.pid = freshPid(before, after);
      report.pidSource = 'fresh_harness_start';
    } catch (error) {
      // A busy device can rotate the start marker before the case finishes.
      // Fresh installation, a new case-bound marker, the live app PID and the
      // subsequent cache-file identity/hash checks must all agree instead.
      const resultAfter = run('result-markers-after', ['shell', 'hilog', '-x', '-e', 'ARKTS_NATIVE_ROW_FILE']);
      if (report.executionNonce) {
        report.pid = freshNoncePid(resultBefore, resultAfter, build, report.executionNonce);
        report.pidSource = 'fresh_nonce_bound_result_marker';
      } else {
        const current = run('candidate-process-after', ['shell', 'pidof', build.bundleName]);
        report.pid = freshResultPid(resultBefore, resultAfter, current, build);
        report.pidSource = 'fresh_result_marker_and_live_candidate_process';
      }
      report.startMarkerDiagnostic = String(error);
    }
    const log = run('native-process', ['shell', 'hilog', '-x', '-P', report.pid]);
    const files = log.split('\n').filter(line => line.includes('ARKTS_NATIVE_ROW_FILE ')).map(line =>
      JSON.parse(line.slice(line.indexOf('ARKTS_NATIVE_ROW_FILE ') + 'ARKTS_NATIVE_ROW_FILE '.length)));
    if (files.length) {
      if (files.length !== 1 || !/^ltb-native-result_\d+\.json$/.test(files[0].name)) throw new Error('Invalid native result file marker');
      const artifact = files[0];
      const remote = `/data/app/el2/${users[0]}/base/${build.bundleName}/cache/${artifact.name}`;
      const local = path.join(output, 'native-result.json');
      if (fs.existsSync(local)) throw new Error('Refusing old result file');
      run('pull-result', ['file', 'recv', remote, local]);
      const bytes = fs.readFileSync(local);
      const json = bytes.toString('utf8');
      if (bytes.length !== artifact.bytes || json.length !== artifact.characters) throw new Error('Native result length mismatch');
      const row = JSON.parse(json);
      if (['taskId', 'role', 'caseId'].some(key => row[key] !== artifact[key])) throw new Error('Native result file identity mismatch');
      if (report.executionNonce && (artifact.executionNonce !== report.executionNonce ||
          row.nativeBridge?.capabilities?.execution?.nonce !== report.executionNonce)) throw new Error('Native result execution nonce mismatch');
      report.rowArtifact = { remote, local, bytes: bytes.length, sha256: hash(local), processLogMarker: artifact };
      report.rows = [row];
    } else report.rows = decodeRows(log);
    if (providerConfig) report.providerHostVerification = report.rows.map(row =>
      providerHost.verifyRowTransport(row, { ...providerConfig, candidatePid: report.pid }, report.providerHost));
    report.transportCompleted = /TestFinished-ResultCode: 0\b/.test(transcript) &&
      /Tests run: [1-9]\d*, Failure: 0, Error: 0, Pass: [1-9]\d*, Ignore: 0/.test(transcript);
    if (build.caseId && (report.rows.length !== 1 || report.rows[0].caseId !== build.caseId || report.rows[0].taskId !== build.taskId ||
        (build.role && report.rows[0].role !== build.role))) throw new Error('Expected canonical device row missing');
    report.status = report.transportCompleted ? 'transport_completed' : 'transport_failed';
    if (build.nativeUIObserver && report.rows.some(row => row.status === 'not_scored')) {
      try {
        uiPostflightFile = '/data/local/tmp/ltb-ui-postflight-' + Date.now() + '.json';
        run('ui-postflight-dump', ['shell', 'uitest', 'dumpLayout', '-p', uiPostflightFile], 120000);
        const layout = JSON.parse(run('ui-postflight-tree', ['shell', 'cat', uiPostflightFile]));
        report.uiPostflight = { inputSetupBlocked: inputSetupBlocked(layout),
          scope: 'Read-only infrastructure diagnostic. Does not change canonical rows or transport status.' };
      } catch (error) { report.uiPostflight = { error: String(error) }; }
    }
  } catch (error) {
    report.error = String(error);
    process.exitCode = 1;
  } finally {
    if (providerWorker) {
      try { report.providerHost = await providerWorker.stop(); }
      catch (error) { report.providerHost = { error: String(error) }; }
    }
    if (providerConfig) {
      try {
        const remote = providerHost.responsePaths(providerConfig).debugResponsePath;
        const cleanupOutput = run('cleanup-provider-transport', ['shell', '-b', providerConfig.bundleName, 'rm', '-f', remote, remote + '.tmp']);
        if (cleanupOutput.trim()) throw new Error('Debug sandbox cleanup returned nonempty diagnostic; see raw command log');
        report.cleanup.providerTransportRemoved = true;
      }
      catch (error) { report.cleanup.providerTransportError = String(error); }
    }
    if (uiPreflightFile) {
      try { run('cleanup-ui-preflight', ['shell', 'rm', uiPreflightFile]); }
      catch (error) { report.cleanup.uiPreflightError = String(error); }
    }
    if (uiPostflightFile) {
      try { run('cleanup-ui-postflight', ['shell', 'rm', uiPostflightFile]); }
      catch (error) { report.cleanup.uiPostflightError = String(error); }
    }
    if (owned) {
      try { report.cleanup.ownedAppUninstalled = run('cleanup-uninstall', ['uninstall', build.bundleName]).includes('uninstall bundle successfully'); }
      catch (error) { report.cleanup.error = String(error); }
    }
    if (providerConfig && report.cleanup.ownedAppUninstalled && !report.cleanup.providerTransportRemoved) {
      report.cleanup.providerTransportRemovedByOwnedUninstall = true;
    }
    if (locked && fs.existsSync(lock)) fs.rmdirSync(lock);
    report.finishedAt = new Date().toISOString();
    fs.writeFileSync(reportFile, JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify({ reportFile, status: report.status, error: report.error,
      cases: report.rows.map(row => ({ caseId: row.caseId, status: row.status, reason: row.reason })), cleanup: report.cleanup }, null, 2));
  }
}

module.exports = { decodeRows, freshPid, freshResultPid, freshNoncePid, screenLocked, inputSetupBlocked,
  deviceLockPath };
if (require.main === module) main().catch(error => { console.error(String(error)); process.exitCode = 1; });
