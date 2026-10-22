'use strict';

// Evaluator-only metadata transport. No application or picker operations live here.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn, spawnSync } = require('node:child_process');
const MARKER = 'ARKTS_16_18_PROVIDER_REQUEST ';
const sha = data => crypto.createHash('sha256').update(data).digest('hex');
const safeBundle = value => typeof value === 'string' && /^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$/.test(value);
const positive = value => typeof value === 'string' && /^[1-9][0-9]*$/.test(value);
function transferOK(result, expectedBytes) {
  const stdout = result.stdout || '';
  const confirmations = [...stdout.matchAll(/FileTransfer finish, Size:(\d+), File count\s*=\s*(\d+),/g)];
  return !result.error && result.status === 0 && !(result.stderr || '').trim() &&
    !/(?:\[fail\]|\berror\b|permission denied|no such file|failed)/i.test(stdout) &&
    confirmations.length === 1 && Number(confirmations[0][1]) === expectedBytes && confirmations[0][2] === '1';
}

function validateConfig(config) {
  if (!/^[a-f0-9]{32}$/.test(config.nonce || '') || !safeBundle(config.bundleName) ||
      config.taskId !== '18_custom_notification_sounds' || config.caseId !== 'ns_state_003_message_picker_launch' ||
      !/^(0|[1-9][0-9]*)$/.test(config.userId || '') || Number(config.userId) > 2147483647 ||
      !['hostModule', 'hostAbility'].every(key => typeof config[key] === 'string' && /^[A-Za-z][A-Za-z0-9_.]*$/.test(config[key])) ||
      typeof config.role !== 'string' || !config.role || !/^[A-Za-z0-9.:_-]+$/.test(config.serial || '')) {
    throw new Error('Invalid host provider execution identity');
  }
}

function validateRequest(request, config) {
  validateConfig(config);
  const paths = responsePaths(config);
  if (request.version !== 2 || request.requestId !== 'provider1' ||
      !['nonce', 'taskId', 'caseId', 'bundleName', 'userId', 'hostModule', 'hostAbility'].every(key => request[key] === config[key]) ||
      !safeBundle(request.providerBundle) ||
      !['providerModule', 'providerAbility'].every(key => typeof request[key] === 'string' && /^[A-Za-z][A-Za-z0-9_.]*$/.test(request[key])) ||
      !/^[0-9]+$/.test(request.recordId || '') || !Number.isSafeInteger(request.pid) || request.pid <= 0 ||
      !Number.isSafeInteger(request.sdkCallId) || request.sdkCallId <= 0 ||
      !Number.isFinite(request.sdkStartedAtMs) || !Number.isFinite(request.requestedAtMs) ||
      request.sdkStartedAtMs > request.requestedAtMs ||
      request.responseName !== paths.responseName || request.nativeResponsePath !== paths.nativeResponsePath ||
      request.debugResponsePath !== paths.debugResponsePath ||
      request.hostResponsePath !== paths.hostResponsePath ||
      request.cacheContext?.origin !== 'AbilityDelegator.getAppContext().getApplicationContext()' ||
      request.cacheContext?.applicationName !== config.bundleName || request.cacheContext?.cacheDir !== paths.nativeCacheDir) {
    throw new Error('Provider request is not bound to the current candidate execution');
  }
  return request;
}

function responsePaths(config) {
  validateConfig(config);
  const responseName = 'Tasks16_18_provider_' + config.nonce + '.json';
  const nativeCacheDir = '/data/storage/el2/base/cache';
  const hostCacheDir = '/data/app/el2/' + config.userId + '/base/' + config.bundleName + '/cache';
  return { responseName, nativeCacheDir, hostCacheDir,
    nativeResponsePath: nativeCacheDir + '/' + responseName, debugResponsePath: nativeCacheDir.slice(1) + '/' + responseName,
    hostResponsePath: hostCacheDir + '/' + responseName };
}

function requestFromLog(log, config, livePid) {
  const matches = [];
  for (const line of log.split('\n')) {
    const offset = line.indexOf(MARKER);
    if (offset < 0 || !line.slice(offset).includes(config.nonce)) continue;
    const parsed = JSON.parse(line.slice(offset + MARKER.length));
    if (parsed.nonce !== config.nonce) continue;
    const request = validateRequest(parsed, config);
    const prefix = line.match(/^\S+\s+\S+\s+(\d+)\s+\d+\s/);
    if (!prefix || !positive(livePid) || prefix[1] !== livePid) throw new Error('Request marker is not from the live candidate PID');
    matches.push({ request, line, requestLogPid: prefix[1] });
  }
  if (matches.length > 1) throw new Error('Multiple nonce-bound provider requests');
  return matches[0];
}

function makeResponse(request, result, config, requestLogPid, times) {
  validateRequest(request, config);
  if (result.error || !Number.isInteger(result.status) || !positive(requestLogPid)) throw new Error('HDC metadata command did not complete');
  const stdResult = result.stdout || '', stderr = result.stderr || '';
  if (Buffer.byteLength(stdResult) > 2 * 1024 * 1024) throw new Error('Provider metadata exceeds transport size limit');
  return { version: 2, transport: 'hdc_provider_metadata_app_cache_v2', request,
    command: 'bm dump -n ' + request.providerBundle + ' -u ' + request.userId,
    exitCode: result.status, stdResult, stderr,
    stdoutSha256: sha(stdResult), stdoutBytes: Buffer.byteLength(stdResult), stdoutCharacters: stdResult.length,
    host: { serial: config.serial, role: config.role, requestLogPid, ...times } };
}

async function serve(config, command, stopped = () => false, sleep = ms => new Promise(resolve => setTimeout(resolve, ms))) {
  validateConfig(config);
  const deadline = Date.now() + 60000;
  const report = { version: 1, nonce: config.nonce, status: 'waiting', pollCount: 0, commands: [], receipts: [],
    debugAccess: { bundleName: config.bundleName, mechanism: 'official hdc file send/recv -b; native SDK rename' } };
  const audited = (args, timeout) => {
    const startedAtMs = Date.now(), result = command(args, timeout);
    report.commands.push({ executable: config.hdc, args: ['-t', config.serial, ...args], timeout,
      startedAtMs, finishedAtMs: Date.now(), exitCode: result.status, error: result.error ? String(result.error) : undefined,
      stdout: result.stdout || '',
      stdoutSha256: sha(result.stdout || ''), stdoutBytes: Buffer.byteLength(result.stdout || ''),
      stderr: result.stderr || '' });
    return result;
  };
  const receipt = (remote, localName, expected, attempt) => {
    const local = path.join(config.output, localName);
    if (fs.existsSync(local)) throw new Error('Refusing preexisting host receipt artifact');
    const result = audited(['file', 'recv', '-b', config.bundleName, remote, local], 2000);
    if (!transferOK(result, expected.length) || !fs.existsSync(local)) {
      report.receipts.push({ remote, local, available: fs.existsSync(local), error: 'HDC receipt unavailable' });
      return undefined;
    }
    const bytes = fs.readFileSync(local);
    const evidence = { remote, local, attempt, bytes: bytes.length, sha256: sha(bytes), matchesExpected: bytes.equals(expected) };
    report.receipts.push(evidence);
    if (!evidence.matchesExpected) throw new Error('HDC receipt bytes differ: ' + localName);
    return evidence;
  };
  try {
    // At most two small command reads per 500 ms; only the matched log is retained.
    for (let attempt = 0; attempt < 120 && Date.now() < deadline && !stopped(); attempt++) {
      report.pollCount++;
      const log = command(['shell', 'hilog', '-x', '-e', MARKER.trim()], 2000);
      if (!log.error && log.status === 0 && (log.stdout || '').includes(config.nonce)) {
        const pid = audited(['shell', 'pidof', config.bundleName], 1000);
        if (pid.error || pid.status !== 0) throw new Error('Unable to verify live candidate PID');
        const match = requestFromLog(log.stdout, config, (pid.stdout || '').trim());
        if (!match) throw new Error('No complete request marker for execution nonce');
        report.liveCandidateProcess = { stdout: pid.stdout, sha256: sha(pid.stdout) };
        const receivedAtMs = Date.now();
        fs.writeFileSync(path.join(config.output, 'provider-host-request.log'), match.line + '\n', { flag: 'wx' });
        report.requestLog = { path: path.join(config.output, 'provider-host-request.log'), sha256: sha(match.line + '\n') };
        report.transportPaths = responsePaths(config);
        const remote = report.transportPaths.debugResponsePath;
        const startedAtMs = Date.now();
        const result = audited(['shell', 'bm', 'dump', '-n', match.request.providerBundle, '-u', config.userId], 3000);
        const response = makeResponse(match.request, result, config, match.requestLogPid,
          { receivedAtMs, startedAtMs, finishedAtMs: Date.now() });
        const file = path.join(config.output, 'provider-host-response.json');
        fs.writeFileSync(file, JSON.stringify(response), { flag: 'wx' });
        report.responseFile = file;
        report.responseSha256 = sha(fs.readFileSync(file));
        report.requestLogPid = match.requestLogPid;
        const expected = fs.readFileSync(file);
        const transfer = audited(['file', 'send', '-b', config.bundleName, file, remote + '.tmp'], 2000);
        if (!transferOK(transfer, expected.length)) throw new Error('HDC send lacks exact file-size completion receipt; see raw stdout');
        report.status = 'send_confirmed';
        // Native validates and atomically renames its own file. HDC never moves
        // or changes permissions on protected files, even through debug shell.
        for (let attempt = 0; attempt < 8; attempt++) {
          report.responseReceipt = receipt(remote, 'provider-host-receipt-' + attempt + '.json', expected, attempt);
          if (report.responseReceipt) break;
          if (stopped()) break;
          await sleep(250);
        }
        if (!report.responseReceipt) throw new Error('No byte-exact final-file receipt after native rename');
        report.status = 'delivered';
        return report;
      }
      await sleep(500);
    }
    report.status = stopped() ? 'stopped_without_request' : 'request_timeout';
  } catch (error) { report.status = 'error'; report.error = String(error); }
  return report;
}

function verifyRowTransport(row, config, workerReport) {
  const samples = (row.evidence || []).flatMap(item =>
    (item.nativePageTransition || item.nativePageTransitionPartial)?.providerCommands || [])
    .filter(sample => sample.phase === 'pending_metadata_host' && sample.completed);
  if (!samples.length) return { used: false };
  if (!workerReport || workerReport.status !== 'delivered') throw new Error('Native host evidence lacks a delivered worker response');
  const file = path.join(config.output, 'provider-host-response.json');
  const bytes = fs.readFileSync(file), response = JSON.parse(bytes);
  validateRequest(response.request, config);
  const paths = responsePaths(config);
  for (const entry of workerReport.commands || []) {
    if (typeof entry.stdout !== 'string' || entry.stdoutSha256 !== sha(entry.stdout) ||
      entry.stdoutBytes !== Buffer.byteLength(entry.stdout)) throw new Error('Worker raw stdout audit mismatch');
    if (entry.args?.slice(2, 4).join(' ') === 'shell -b') throw new Error('Provider worker must not run debug-shell mutations');
  }
  const verifyReceipt = (record, remote, expected) => {
    if (!record || !Number.isInteger(record.attempt) || record.attempt < 0 || record.attempt >= 8) throw new Error('Invalid receipt attempt');
    const name = 'provider-host-receipt-' + record.attempt + '.json';
    const local = path.join(config.output, name);
    const commands = (workerReport.commands || []).filter(item => JSON.stringify(item.args) ===
      JSON.stringify(['-t', config.serial, 'file', 'recv', '-b', config.bundleName, remote, local]));
    if (!record || record.remote !== remote || record.local !== local || commands.length !== 1 ||
      !transferOK({ ...commands[0], status: commands[0].exitCode }, expected.length)) throw new Error('Host receipt command audit mismatch');
    const actual = fs.readFileSync(local);
    if (!actual.equals(expected) || record.bytes !== actual.length || record.sha256 !== sha(actual)) throw new Error('Host receipt artifact mismatch');
  };
  verifyReceipt(workerReport.responseReceipt, paths.debugResponsePath, bytes);
  if (JSON.stringify(workerReport.transportPaths) !== JSON.stringify(paths)) throw new Error('Worker cache path mapping mismatch');
  const transfers = [['file', 'send', '-b', config.bundleName, file, paths.debugResponsePath + '.tmp']];
  for (const args of transfers) {
    const records = (workerReport.commands || []).filter(item => JSON.stringify(item.args) === JSON.stringify(['-t', config.serial, ...args]));
    if (records.length !== 1 || !transferOK({ ...records[0], status: records[0].exitCode }, bytes.length)) throw new Error('Cache transfer command audit mismatch');
  }
  if (workerReport.nonce !== config.nonce || workerReport.responseFile !== file || workerReport.responseSha256 !== sha(bytes) ||
      response.host.serial !== config.serial || response.host.role !== config.role || response.host.requestLogPid !== config.candidatePid ||
      workerReport.requestLogPid !== config.candidatePid || row.nativeBridge?.capabilities?.execution?.nonce !== config.nonce ||
      ['taskId', 'caseId', 'role'].some(key => row[key] !== config[key]) ||
      response.stdoutSha256 !== sha(response.stdResult) || response.stdoutBytes !== Buffer.byteLength(response.stdResult) ||
      response.stdoutCharacters !== response.stdResult.length || response.stderr !== '') throw new Error('Host provider provenance mismatch');
  const requestLog = path.join(config.output, 'provider-host-request.log');
  if (workerReport.requestLog?.path !== requestLog || workerReport.requestLog.sha256 !== sha(fs.readFileSync(requestLog))) {
    throw new Error('Provider request log provenance mismatch');
  }
  const matched = requestFromLog(fs.readFileSync(requestLog, 'utf8'), config, config.candidatePid);
  if (JSON.stringify(matched?.request) !== JSON.stringify(response.request)) throw new Error('Host response differs from actual logged request');
  const livePid = workerReport.liveCandidateProcess;
  const pidCommands = (workerReport.commands || []).filter(item => JSON.stringify(item.args) ===
    JSON.stringify(['-t', config.serial, 'shell', 'pidof', config.bundleName]));
  if (!livePid || livePid.stdout.trim() !== config.candidatePid || livePid.sha256 !== sha(livePid.stdout) ||
      pidCommands.length !== 1 || pidCommands[0].exitCode !== 0 || pidCommands[0].error ||
      pidCommands[0].stdoutSha256 !== livePid.sha256) throw new Error('Live candidate PID audit mismatch');
  const bmArgs = ['-t', config.serial, 'shell', 'bm', 'dump', '-n', response.request.providerBundle, '-u', config.userId];
  const bm = (workerReport.commands || []).filter(item => JSON.stringify(item.args) === JSON.stringify(bmArgs));
  if (bm.length !== 1 || bm[0].executable !== config.hdc || bm[0].exitCode !== response.exitCode || bm[0].error ||
      bm[0].stdoutSha256 !== response.stdoutSha256 || bm[0].stdoutBytes !== response.stdoutBytes || bm[0].stderr !== response.stderr ||
      response.host.receivedAtMs > response.host.startedAtMs || response.host.startedAtMs > bm[0].startedAtMs ||
      bm[0].startedAtMs > bm[0].finishedAtMs || bm[0].finishedAtMs > response.host.finishedAtMs) {
    throw new Error('Host bm command audit mismatch');
  }
  for (const sample of samples) {
    if (sample.hostResponseJson !== bytes.toString('utf8') || sample.hostRequestJson !== JSON.stringify(response.request) ||
        sample.responseReadPath !== paths.nativeResponsePath + '.tmp' || sample.responseReadApi !== '@ohos.file.fs.readTextSync' ||
        sample.responseFinalPath !== paths.nativeResponsePath || sample.responseRenamed !== true ||
        sample.responseRenameApi !== '@ohos.file.fs.renameSync' || sample.responseFinalBytes !== bytes.length ||
        sample.responseFileBytes !== bytes.length ||
        sample.stdResult !== response.stdResult || sample.exitCode !== response.exitCode ||
        sample.responseStdoutSha256 !== response.stdoutSha256 || sample.responseStdoutBytes !== response.stdoutBytes) {
      throw new Error('Native provider evidence differs from this execution host response');
    }
  }
  return { used: true, verified: true, responseSha256: sha(bytes), requestLogPid: config.candidatePid };
}

async function startWorker(config) {
  validateConfig(config);
  const configFile = path.join(config.output, 'provider-host-config.json');
  const stopFile = path.join(config.output, 'provider-host.stop');
  const reportFile = path.join(config.output, 'provider-host-report.json');
  fs.writeFileSync(configFile, JSON.stringify(config), { flag: 'wx' });
  const child = spawn(process.execPath, [__filename, configFile], { stdio: ['ignore', 'ignore', 'ignore', 'ipc'] });
  const exited = new Promise(resolve => { child.once('exit', (code, signal) => resolve({ code, signal })); child.once('error', error => resolve({ error: String(error) })); });
  let timer;
  try {
    await Promise.race([new Promise(resolve => child.once('message', message => { if (message === 'ready') resolve(); })),
      exited.then(() => { throw new Error('Provider worker exited before readiness'); }),
      new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Provider worker readiness timeout')), 3000); })]);
  } catch (error) { child.kill('SIGKILL'); await exited; throw error; }
  finally { clearTimeout(timer); }
  return { async stop() {
    fs.writeFileSync(stopFile, 'stop\n');
    const kill = setTimeout(() => child.kill('SIGKILL'), 4500);
    let exit;
    try { exit = await exited; } finally { clearTimeout(kill); }
    const report = fs.existsSync(reportFile) ? JSON.parse(fs.readFileSync(reportFile)) : { status: 'worker_incomplete', exit };
    if (!fs.existsSync(reportFile)) fs.writeFileSync(reportFile, JSON.stringify(report, null, 2), { flag: 'wx' });
    return report;
  } };
}

async function validateExecutionTransport(execution, build, executionFile) {
  const pages = (execution.rows || []).flatMap(row => (row.evidence || []).flatMap(item =>
    [item.nativePageTransition, item.nativePageTransitionPartial].filter(Boolean)));
  const claimed = pages.some(page => (page.providerCommands || []).some(sample => sample.phase === 'pending_metadata_host') ||
    (page.providerEvidenceJson && JSON.parse(page.providerEvidenceJson).metadataTransport === 'nonce_bound_hdc'));
  if (!build.supportsTasks16To18ProviderHost) {
    if (claimed) throw new Error('Host evidence claimed without supported build');
    return { used: false };
  }
  const output = path.dirname(path.resolve(executionFile));
  const config = JSON.parse(fs.readFileSync(path.join(output, 'provider-host-config.json')));
  validateConfig(config);
  const original = build.nativeUIObserver?.originalModule;
  if (config.output !== output || config.nonce !== execution.executionNonce || config.userId !== execution.deviceUserId ||
      config.serial !== execution.serial || config.bundleName !== build.bundleName ||
      ['taskId', 'caseId', 'role'].some(key => config[key] !== build[key] || config[key] !== execution[key]) ||
      original?.bundleName !== config.bundleName || original?.moduleName !== config.hostModule || original?.abilityName !== config.hostAbility ||
      build.providerHostSource?.sha256 !== sha(fs.readFileSync(__filename)) ||
      execution.providerHostSource?.sha256 !== build.providerHostSource.sha256) throw new Error('Provider build/execution/source identity mismatch');
  const invocations = execution.commands.filter(item => item.args?.slice(0, 3).join(' ') === 'shell aa test');
  if (invocations.length !== 1) throw new Error('Expected one host-enabled test invocation');
  for (const [key, value] of [['ltbExecutionNonce', config.nonce], ['ltbDeviceUser', config.userId], ['ltbProviderHostBridge', '1']]) {
    const args = invocations[0].args, positions = args.flatMap((arg, index) => arg === key ? [index] : []);
    if (positions.length !== 1 || args[positions[0] - 1] !== '-s' || args[positions[0] + 1] !== value) {
      throw new Error('Host invocation parameter mismatch: ' + key);
    }
  }
  const remote = responsePaths(config).debugResponsePath;
  const cleanup = execution.commands.filter(item => JSON.stringify(item.args) === JSON.stringify(['shell', '-b', config.bundleName, 'rm', '-f', remote, remote + '.tmp']));
  let uninstallCleanup = false;
  if (execution.cleanup?.providerTransportRemovedByOwnedUninstall === true && execution.cleanup?.ownedAppUninstalled === true) {
    const uninstall = execution.commands.filter(item => JSON.stringify(item.args) === JSON.stringify(['uninstall', config.bundleName]));
    if (uninstall.length === 1 && uninstall[0].exitCode === 0 && !uninstall[0].error &&
      typeof uninstall[0].log === 'string' && path.basename(uninstall[0].log) === uninstall[0].log) {
      uninstallCleanup = fs.readFileSync(path.join(output, uninstall[0].log), 'utf8').includes('uninstall bundle successfully');
    }
  }
  if (cleanup.length !== 1 || (!uninstallCleanup &&
    (cleanup[0].exitCode !== 0 || cleanup[0].error || execution.cleanup?.providerTransportRemoved !== true))) {
    throw new Error('Exact nonce transport cleanup was not established');
  }
  const stored = JSON.parse(fs.readFileSync(path.join(output, 'provider-host-report.json')));
  if (JSON.stringify(stored) !== JSON.stringify(execution.providerHost)) throw new Error('Worker report differs from execution audit');
  const results = execution.rows.map(row => verifyRowTransport(row, { ...config, candidatePid: execution.pid }, stored));
  if (claimed) {
    const evidenceFile = path.join(__dirname, 'Tasks16_18ProviderEvidence.js');
    const evidenceSource = fs.readFileSync(evidenceFile);
    const fixture = build.nativeUIObserver?.fixtures?.find(item => item.file === evidenceFile);
    if (!fixture || fixture.sha256 !== sha(evidenceSource)) throw new Error('Provider parser source differs from compiled fixture');
    const parser = await import('data:text/javascript;base64,' + evidenceSource.toString('base64'));
    for (const page of pages.filter(item => item.providerCommands?.some(sample => sample.phase === 'pending_metadata_host'))) {
      const complete = page.providerCommands.some(sample => sample.phase === 'pending_metadata_host' && sample.completed);
      const summary = JSON.parse(page.providerEvidenceJson || '{}');
      if (!complete && !summary.providerIdentityVerified && execution.rows.every(row => row.status === 'not_scored')) continue;
      const actual = parser.summarizeTasks16To18ProviderEvidence(JSON.stringify(page));
      if (!page.providerEvidenceJson || JSON.stringify(JSON.parse(actual)) !== JSON.stringify(JSON.parse(page.providerEvidenceJson))) {
        throw new Error('Provider identity summary differs from raw pending records and metadata');
      }
      if (execution.rows.some(row => row.status !== 'not_scored') && !JSON.parse(actual).providerIdentityVerified) {
        throw new Error('Scored host provider evidence has no verified raw identity');
      }
    }
  }
  return { rows: results, sourceVerified: true, rawProviderEvidenceRecomputed: claimed };
}

module.exports = { validateConfig, validateRequest, responsePaths, requestFromLog, makeResponse, serve, verifyRowTransport, startWorker, validateExecutionTransport };
if (require.main === module && process.argv[2] === '--verify-evidence') {
  const file = process.argv[3], execution = JSON.parse(fs.readFileSync(file));
  const build = JSON.parse(fs.readFileSync(execution.buildReport.path));
  validateExecutionTransport(execution, build, file).then(result => console.log(JSON.stringify(result)))
    .catch(error => { console.error(String(error)); process.exitCode = 1; });
} else if (require.main === module) {
  const config = JSON.parse(fs.readFileSync(process.argv[2]));
  validateConfig(config);
  if (process.send) process.send('ready');
  serve(config, (args, timeout) => spawnSync(config.hdc, ['-t', config.serial, ...args],
    { encoding: 'utf8', timeout, maxBuffer: 4 * 1024 * 1024 }),
  () => fs.existsSync(path.join(config.output, 'provider-host.stop'))).then(report => {
    fs.writeFileSync(path.join(config.output, 'provider-host-report.json'), JSON.stringify(report, null, 2));
    if (process.connected) process.disconnect();
  }).catch(error => { process.stderr.write(String(error)); process.exitCode = 1; if (process.connected) process.disconnect(); });
}
