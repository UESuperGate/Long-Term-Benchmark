'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const host = require('./Tasks16_18ProviderHost.cjs');
const config = { nonce: 'a'.repeat(32), taskId: '18_custom_notification_sounds', caseId: 'ns_state_003_message_picker_launch',
  bundleName: 'com.example.candidate', userId: '107', hostModule: 'entry', hostAbility: 'EntryAbility',
  serial: 'test-device', role: 'final', hdc: '/fake/hdc' };
const cachePaths = host.responsePaths(config);
const cacheContext = { origin: 'AbilityDelegator.getAppContext().getApplicationContext()',
  applicationName: config.bundleName, cacheDir: cachePaths.nativeCacheDir };
const request = { version: 2, nonce: config.nonce, requestId: 'provider1', taskId: config.taskId, caseId: config.caseId,
  bundleName: config.bundleName, userId: config.userId, providerBundle: 'com.vendor.audio', providerModule: 'audio',
  providerAbility: 'AudioPicker', recordId: '123', pid: 543, hostModule: 'entry', hostAbility: 'EntryAbility',
  sdkCallId: 1, sdkStartedAtMs: 10, requestedAtMs: 20, responseName: cachePaths.responseName,
  cacheContext, nativeResponsePath: cachePaths.nativeResponsePath, debugResponsePath: cachePaths.debugResponsePath,
  hostResponsePath: cachePaths.hostResponsePath };
const marker = value => '10-19 12:34:56.789 1234 1235 I A00000/JSAPP: ARKTS_16_18_PROVIDER_REQUEST ' + JSON.stringify(value);

for (const key of ['nonce', 'taskId', 'caseId', 'bundleName', 'userId', 'hostModule', 'hostAbility',
  'providerBundle', 'providerModule', 'providerAbility', 'responseName', 'sdkCallId', 'pid', 'recordId',
  'nativeResponsePath', 'debugResponsePath', 'hostResponsePath', 'cacheContext']) {
  test('host rejects invalid request field: ' + key, () => {
    const wrong = { ...request, [key]: 'bad; command' };
    assert.throws(() => host.validateRequest(wrong, config));
  });
}
test('request requires the live candidate PID and exactly one nonce marker', () => {
  assert.equal(host.requestFromLog(marker(request), config, '1234').request.providerBundle, request.providerBundle);
  assert.equal(host.requestFromLog(marker({ ...request, nonce: 'b'.repeat(32) }), config, '1234'), undefined);
  for (const pid of ['999', '1234 5678', '']) assert.throws(() => host.requestFromLog(marker(request), config, pid));
  assert.throws(() => host.requestFromLog(marker(request) + '\n' + marker(request), config, '1234'), /Multiple/);
});

for (const variant of ['module_context', 'wrong_app', 'wrong_origin', 'old_tmp', 'wrong_user', 'wrong_nonce', 'traversal', 'v1']) {
  test('cache transport binds actual application context and exact sandbox mapping: ' + variant, () => {
    const wrong = { ...request, cacheContext: { ...cacheContext } };
    if (variant === 'module_context') wrong.cacheContext.cacheDir = '/data/storage/el2/base/haps/entry/cache';
    if (variant === 'wrong_app') wrong.cacheContext.applicationName = 'com.other.app';
    if (variant === 'wrong_origin') wrong.cacheContext.origin = 'getAppContext()';
    if (variant === 'old_tmp') wrong.hostResponsePath = '/data/local/tmp/' + wrong.responseName;
    if (variant === 'wrong_user') wrong.hostResponsePath = wrong.hostResponsePath.replace('/107/', '/100/');
    if (variant === 'wrong_nonce') wrong.nativeResponsePath = wrong.nativeResponsePath.replace(config.nonce, 'b'.repeat(32));
    if (variant === 'traversal') wrong.hostResponsePath = wrong.hostResponsePath.replace('/cache/', '/cache/../');
    if (variant === 'v1') wrong.version = 1;
    assert.throws(() => host.validateRequest(wrong, config));
  });
}

async function delivered(t, result = { status: 0, stdout: '{"realTransportSentinel":"音频"}', stderr: '' }, variant = 'valid') {
  const output = fs.mkdtempSync(path.join(os.tmpdir(), 'Tasks16_18-provider-'));
  t.after(() => fs.rmSync(output, { recursive: true, force: true }));
  const cfg = { ...config, output }, commands = [];
  const report = await host.serve(cfg, args => {
    commands.push(args);
    if (args[1] === 'hilog') return { status: 0, stdout: marker(request) };
    if (args[1] === 'pidof') return { status: 0, stdout: '1234\n' };
    if (args[1] === 'bm') return result;
    if (args[0] === 'file' && args[1] === 'recv') {
      if (variant === 'recv_fail') return { status: 0, stdout: '[Fail]Permission denied' };
      if (variant === 'missing_receipt') return { status: 0, stdout: 'FileTransfer finish, Size:0, File count = 1, time:10ms\n' };
      const bytes = fs.readFileSync(path.join(cfg.output, 'provider-host-response.json'));
      if (variant === 'wrong_receipt') bytes[0] = 33;
      fs.writeFileSync(args[5], bytes);
      return { status: 0, stdout: 'FileTransfer finish, Size:' + bytes.length + ', File count = 1, time:10ms\n' };
    }
    if (args[0] === 'file' && args[1] === 'send') {
      if (variant === 'send_fail') return { status: 0, stdout: '[Fail]Error opening file: permission denied, path:' + args[5] };
      if (variant === 'no_finish') return { status: 0, stdout: '' };
      return { status: 0, stdout: 'FileTransfer finish, Size:' + (fs.statSync(args[4]).size + (variant === 'wrong_size' ? 1 : 0)) +
        ', File count = ' + (variant === 'wrong_count' ? 2 : 1) + ', time:10ms\n' };
    }
    return { status: 0, stdout: '' };
  }, () => false, async () => {});
  return { cfg, commands, report };
}

test('worker executes exact read-only metadata command and only writes its nonce transport files', async t => {
  const { cfg, commands, report } = await delivered(t);
  assert.equal(report.status, 'delivered');
  assert.deepEqual(commands[2], ['shell', 'bm', 'dump', '-n', request.providerBundle, '-u', '107']);
  const remote = cachePaths.debugResponsePath;
  assert.deepEqual(commands.slice(3), [['file', 'send', '-b', cfg.bundleName, path.join(cfg.output, 'provider-host-response.json'), remote + '.tmp'],
    ['file', 'recv', '-b', cfg.bundleName, remote, path.join(cfg.output, 'provider-host-receipt-0.json')]]);
  const response = JSON.parse(fs.readFileSync(report.responseFile));
  assert.equal(response.stdResult, '{"realTransportSentinel":"音频"}');
  assert.equal(response.stdoutBytes, Buffer.byteLength(response.stdResult));
  assert.ok(response.stdoutBytes > response.stdoutCharacters);
  assert.equal(report.commands.length, 4);
  assert.equal(report.responseReceipt.sha256, report.responseSha256);
});

test('worker keeps nonzero and permission-error raw metadata; it never manufactures declarations', async t => {
  const { report } = await delivered(t, { status: 1, stdout: 'permission denied\n', stderr: 'rejected' });
  const response = JSON.parse(fs.readFileSync(report.responseFile));
  assert.equal(response.exitCode, 1); assert.equal(response.stdResult, 'permission denied\n');
  assert.equal(response.stderr, 'rejected');
});

for (const variant of ['send_fail', 'no_finish', 'wrong_size', 'wrong_count', 'recv_fail', 'missing_receipt', 'wrong_receipt']) {
  test('exit zero never substitutes for an actual transfer receipt: ' + variant, async t => {
    const { report } = await delivered(t, undefined, variant);
    assert.equal(report.status, 'error');
    assert.ok(report.commands.every(item => typeof item.stdout === 'string'));
    assert.ok(report.commands.every(item => item.args.slice(2, 4).join(' ') !== 'shell -b'));
    const send = report.commands.find(item => item.args[2] === 'file' && item.args[3] === 'send');
    assert.equal(send.exitCode, 0);
    if (variant === 'send_fail') assert.match(send.stdout, /permission denied/);
    assert.notEqual(report.responseReceipt?.matchesExpected, true);
    if (variant === 'wrong_receipt') assert.equal(report.receipts[0].matchesExpected, false);
  });
}

test('no-request worker is bounded and does not write repeated poll output', async () => {
  let polls = 0, waits = 0;
  const report = await host.serve(config, () => { polls++; return { status: 0, stdout: '' }; }, () => false, async ms => {
    assert.equal(ms, 500); waits++;
  });
  assert.equal(report.status, 'request_timeout'); assert.equal(polls, 120); assert.equal(waits, 120);
  assert.deepEqual(report.commands, []);
});

for (const variant of ['valid', 'nonce', 'pid', 'role', 'serial', 'raw', 'hash', 'request', 'command', 'sample', 'not_delivered',
  'native_read_path', 'native_read_api', 'native_file_size', 'transfer_path', 'missing_rename', 'mapping', 'receipt_bytes', 'stdout']) {
  test('row provenance independently verifies actual worker response: ' + variant, async t => {
    const { cfg, report } = await delivered(t);
    const text = fs.readFileSync(report.responseFile, 'utf8'), response = JSON.parse(text);
    const sample = { phase: 'pending_metadata_host', completed: true, hostResponseJson: text,
      responseReadPath: cachePaths.nativeResponsePath + '.tmp', responseReadApi: '@ohos.file.fs.readTextSync', responseFileBytes: Buffer.byteLength(text),
      responseFinalPath: cachePaths.nativeResponsePath, responseRenameApi: '@ohos.file.fs.renameSync', responseRenamed: true, responseFinalBytes: Buffer.byteLength(text),
      hostRequestJson: JSON.stringify(request), stdResult: response.stdResult, exitCode: response.exitCode,
      responseStdoutSha256: response.stdoutSha256, responseStdoutBytes: response.stdoutBytes };
    const row = { taskId: cfg.taskId, caseId: cfg.caseId, role: cfg.role,
      nativeBridge: { capabilities: { execution: { nonce: cfg.nonce } } }, evidence: [{ nativePageTransition: { providerCommands: [sample] } }] };
    const expected = { ...cfg, candidatePid: '1234' };
    if (variant === 'nonce') expected.nonce = 'b'.repeat(32);
    if (variant === 'pid') expected.candidatePid = '4321';
    if (variant === 'role') expected.role = 'base';
    if (variant === 'serial') expected.serial = 'other';
    if (variant === 'raw') fs.appendFileSync(report.responseFile, ' ');
    if (variant === 'hash') report.responseSha256 = 'a'.repeat(64);
    if (variant === 'request') fs.appendFileSync(report.requestLog.path, 'tamper');
    if (variant === 'command') report.commands[1].args[5] = 'com.wrong.app';
    if (variant === 'sample') sample.stdResult = '{}';
    if (variant === 'not_delivered') report.status = 'waiting';
    if (variant === 'native_read_path') sample.responseReadPath = '/data/local/tmp/' + request.responseName;
    if (variant === 'native_read_api') sample.responseReadApi = 'executeShellCommand';
    if (variant === 'native_file_size') sample.responseFileBytes++;
    if (variant === 'transfer_path') report.commands[2].args[7] = '/wrong/file';
    if (variant === 'missing_rename') sample.responseRenamed = false;
    if (variant === 'receipt_bytes') fs.appendFileSync(report.responseReceipt.local, 'tamper');
    if (variant === 'stdout') report.commands[2].stdout = '[Fail]Error opening file: permission denied';
    if (variant === 'mapping') report.transportPaths.hostCacheDir = '/wrong/cache';
    if (variant === 'valid') assert.equal(host.verifyRowTransport(row, expected, report).verified, true);
    else assert.throws(() => host.verifyRowTransport(row, expected, report));
  });
}

test('missing response remains unused, never a verified provider', () => {
  assert.deepEqual(host.verifyRowTransport({ evidence: [] }, config, undefined), { used: false });
});

test('worker lifecycle joins its child after bounded stop without any device connection', async t => {
  const output = fs.mkdtempSync(path.join(os.tmpdir(), 'Tasks16_18-worker-'));
  t.after(() => fs.rmSync(output, { recursive: true, force: true }));
  const worker = await host.startWorker({ ...config, output, hdc: path.join(output, 'does-not-exist') });
  const report = await worker.stop();
  assert.equal(report.status, 'stopped_without_request');
  assert.ok(report.pollCount <= 1);
});

async function executionFixture(t) {
  const metadata = { name: request.providerBundle,
    applicationInfo: { name: request.providerBundle, bundleName: request.providerBundle, isSystemApp: true },
    hapModuleInfos: [{ extensionInfos: [{ name: request.providerAbility, moduleName: request.providerModule,
      bundleName: request.providerBundle, enabled: true, visible: true, extensionTypeName: 'sysPicker/audioPicker' }] }] };
  const { cfg, report } = await delivered(t, { status: 0, stdout: JSON.stringify(metadata), stderr: '' });
  const responseText = fs.readFileSync(report.responseFile, 'utf8'), response = JSON.parse(responseText);
  const none = JSON.stringify({ observer: { available: true }, calls: [] });
  const pending = JSON.stringify({ observer: { available: true }, calls: [{ id: 1, startedAtMs: 10,
    status: 'pending', samePageContext: true, api: '@ohos.file.picker.AudioViewPicker.select' }] });
  const raw = '  ExtensionRecords:\n    uri [/com.vendor.audio/audio/AudioPicker6]\n' +
    '      AbilityRecord ID #123   state #FOREGROUND   start time [12345]\n' +
    '      main name [AudioPicker]\n      bundle name [com.vendor.audio]\n      ability type [UIEXTENSION]\n' +
    '      root host bundle name [com.example.candidate]\n      root host module name [entry]\n' +
    '      root host ability name [EntryAbility]\n      pid: 543\n';
  const sample = { phase: 'pending_metadata_host', completed: true, command: response.command, exitCode: 0,
    responseReadPath: cachePaths.nativeResponsePath + '.tmp', responseReadApi: '@ohos.file.fs.readTextSync', responseFileBytes: Buffer.byteLength(responseText),
    responseFinalPath: cachePaths.nativeResponsePath, responseRenameApi: '@ohos.file.fs.renameSync', responseRenamed: true, responseFinalBytes: Buffer.byteLength(responseText),
    startedAtMs: 20, finishedAtMs: 25, pickerStateBeforeJson: pending, pickerStateAfterJson: pending,
    hostResponseJson: responseText, hostRequestJson: JSON.stringify(request), stdResult: response.stdResult,
    responseStdoutSha256: response.stdoutSha256, responseStdoutBytes: response.stdoutBytes };
  const originalModule = { bundleName: cfg.bundleName, moduleName: cfg.hostModule, abilityName: cfg.hostAbility };
  const page = { taskId: cfg.taskId, caseId: cfg.caseId, bundleName: cfg.bundleName, key: 'message_picker_launch',
    providerTransportContext: cacheContext,
    executionNonce: cfg.nonce, hostProviderTransportEnabled: true, deviceUserId: cfg.userId, deviceUserParameter: cfg.userId,
    deviceUserSource: 'AbilityDelegatorRegistry.getArguments().parameters["-s ltbDeviceUser"]',
    originalModuleBindingJson: JSON.stringify({ monitoredContext: { scope: originalModule } }),
    checkpoints: [{ label: 'after_event', completed: true, focusedBundle: cfg.bundleName, startedAtMs: 12, finishedAtMs: 18,
      pickerStateBeforeJson: pending, pickerStateJson: pending }],
    providerCommands: [{ phase: 'before_picker', command: 'aa dump -e', completed: true, exitCode: 0,
      stdResult: '  ExtensionRecords:\n', startedAtMs: 1, finishedAtMs: 2, pickerStateBeforeJson: none, pickerStateAfterJson: none },
    { phase: 'pending_after', command: 'aa dump -e', completed: true, exitCode: 0,
      stdResult: raw, startedAtMs: 15, finishedAtMs: 16, pickerStateBeforeJson: pending, pickerStateAfterJson: pending }, sample] };
  const parserFile = path.join(__dirname, 'Tasks16_18ProviderEvidence.js');
  const parser = await import('data:text/javascript;base64,' + fs.readFileSync(parserFile).toString('base64'));
  page.providerEvidenceJson = parser.summarizeTasks16To18ProviderEvidence(JSON.stringify(page));
  assert.equal(JSON.parse(page.providerEvidenceJson).providerIdentityVerified, true);
  const hashFile = file => require('node:crypto').createHash('sha256').update(fs.readFileSync(file)).digest('hex');
  const source = { path: path.join(__dirname, 'Tasks16_18ProviderHost.cjs'), sha256: hashFile(path.join(__dirname, 'Tasks16_18ProviderHost.cjs')) };
  const build = { taskId: cfg.taskId, caseId: cfg.caseId, role: cfg.role, bundleName: cfg.bundleName,
    supportsTasks16To18ProviderHost: true, providerHostSource: source,
    nativeUIObserver: { originalModule, fixtures: [{ file: parserFile, sha256: hashFile(parserFile) }] } };
  const remote = cachePaths.debugResponsePath;
  const row = { taskId: cfg.taskId, caseId: cfg.caseId, role: cfg.role, status: 'pass',
    nativeBridge: { capabilities: { execution: { nonce: cfg.nonce } } }, evidence: [{ nativePageTransition: page }] };
  const execution = { taskId: cfg.taskId, caseId: cfg.caseId, role: cfg.role, serial: cfg.serial, deviceUserId: cfg.userId,
    executionNonce: cfg.nonce, pid: '1234', providerHostSource: source, providerHost: report, rows: [row],
    cleanup: { providerTransportRemoved: true }, commands: [
      { args: ['shell', 'aa', 'test', '-s', 'ltbExecutionNonce', cfg.nonce, '-s', 'ltbDeviceUser', cfg.userId, '-s', 'ltbProviderHostBridge', '1'] },
      { args: ['shell', '-b', cfg.bundleName, 'rm', '-f', remote, remote + '.tmp'], exitCode: 0 }] };
  fs.writeFileSync(path.join(cfg.output, 'provider-host-config.json'), JSON.stringify(cfg));
  fs.writeFileSync(path.join(cfg.output, 'provider-host-report.json'), JSON.stringify(report));
  execution.buildReport = { path: path.join(cfg.output, 'build.json') };
  fs.writeFileSync(execution.buildReport.path, JSON.stringify(build));
  fs.writeFileSync(path.join(cfg.output, 'device-execution.json'), JSON.stringify(execution));
  return { cfg, page, sample, build, execution, file: path.join(cfg.output, 'device-execution.json') };
}

test('offline CLI used by Python imports verifies local artifacts without starting a device worker', async t => {
  const { file } = await executionFixture(t);
  const result = require('node:child_process').spawnSync(process.execPath,
    [path.join(__dirname, 'Tasks16_18ProviderHost.cjs'), '--verify-evidence', file], { encoding: 'utf8', timeout: 3000 });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).rawProviderEvidenceRecomputed, true);
});

for (const actualSuccess of [true, false]) {
  test('owned-app uninstall cleanup fallback requires actual success output: ' + actualSuccess, async t => {
    const { cfg, build, execution, file } = await executionFixture(t);
    execution.cleanup.providerTransportRemoved = false;
    execution.cleanup.ownedAppUninstalled = true;
    execution.cleanup.providerTransportRemovedByOwnedUninstall = true;
    execution.commands.push({ args: ['uninstall', cfg.bundleName], exitCode: 0, log: 'uninstall.log' });
    fs.writeFileSync(path.join(cfg.output, 'uninstall.log'), actualSuccess ? 'uninstall bundle successfully' : 'permission denied');
    if (actualSuccess) await host.validateExecutionTransport(execution, build, file);
    else await assert.rejects(host.validateExecutionTransport(execution, build, file), /cleanup/);
  });
}

for (const variant of ['valid', 'source_hash', 'command', 'cleanup', 'report', 'summary_boolean', 'raw_provider', 'resolved', 'unsupported_build']) {
  test('offline evidence validator recomputes raw identity: ' + variant, async t => {
    const { page, sample, build, execution, file } = await executionFixture(t);
    if (variant === 'source_hash') build.providerHostSource = { sha256: 'b'.repeat(64) };
    if (variant === 'command') execution.commands[0].args.pop();
    if (variant === 'cleanup') execution.commands[1].args.push('/unrelated');
    if (variant === 'report') execution.providerHost = { ...execution.providerHost, status: 'fake' };
    if (variant === 'summary_boolean') page.providerEvidenceJson = '{"providerIdentityVerified":true}';
    if (variant === 'raw_provider') page.providerCommands[1].stdResult = page.providerCommands[1].stdResult.replace('com.vendor.audio', 'com.other.app');
    if (variant === 'resolved') sample.pickerStateAfterJson = sample.pickerStateAfterJson.replace('pending', 'resolved');
    if (variant === 'unsupported_build') build.supportsTasks16To18ProviderHost = false;
    if (variant === 'valid') assert.equal((await host.validateExecutionTransport(execution, build, file)).rawProviderEvidenceRecomputed, true);
    else await assert.rejects(host.validateExecutionTransport(execution, build, file));
  });
}
