'use strict';

// Synthetic command transport cases exercise parsing only, never device evidence.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const compiled = ts.transpileModule(fs.readFileSync(path.join(__dirname, 'Tasks16_18ProviderEvidence.js'), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
const m = { exports: {} };
new vm.Script(`(function(exports,module){${compiled}\n})`).runInNewContext()(m.exports, m);
const { parseTasks16To18ExtensionDump: parse, summarizeTasks16To18ProviderEvidence: summarize,
  tasks16To18ProviderMetadataCommand: metadataCommand } = m.exports;
const empty = '  ExtensionRecords:\n';
const record = [
  '    uri [/com.ohos.filepicker/audiopicker/audiopicker]',
  '      AbilityRecord ID #42   state #FOREGROUND   start time [123456]',
  '      main name [audiopicker]', '      bundle name [com.ohos.filepicker]', '      ability type [UIEXTENSION]',
  '      root host bundle name [test]', '      root host module name [entry]',
  '      root host ability name [EntryAbility]', '      pid: 313'
].join('\n');

function observation() {
  const call = { id: 1, startedAtMs: 20, status: 'pending', api: '@ohos.file.picker.AudioViewPicker.select', samePageContext: true };
  const noPicker = JSON.stringify({ observer: { available: true }, calls: [] });
  const picker = JSON.stringify({ observer: { available: true }, calls: [call] });
  return { bundleName: 'test', deviceUserId: '100', deviceUserParameter: '100',
    deviceUserSource: 'AbilityDelegatorRegistry.getArguments().parameters["-s ltbDeviceUser"]',
    originalModuleBindingJson: JSON.stringify({ monitoredContext: { scope: {
    bundleName: 'test', moduleName: 'entry', abilityName: 'EntryAbility' } } }),
    providerCommands: [
      { phase: 'before_picker', command: 'aa dump -e', completed: true, exitCode: 0, stdResult: empty,
        startedAtMs: 10, finishedAtMs: 15, pickerStateBeforeJson: noPicker, pickerStateAfterJson: noPicker },
      { phase: 'pending_after', command: 'aa dump -e', completed: true, exitCode: 0, stdResult: empty + record,
        startedAtMs: 30, finishedAtMs: 35, pickerStateBeforeJson: picker, pickerStateAfterJson: picker }
    ], checkpoints: [{ label: 'after_event', completed: true, focusedBundle: 'test', startedAtMs: 25, finishedAtMs: 40,
      pickerStateBeforeJson: picker, pickerStateJson: picker }] };
}

test('parser retains exact service identity and missing fields without filling from neighbors', () => {
  const parsed = parse(empty + record);
  assert.equal(parsed.recognized, true);
  assert.equal(parsed.records[0].recordId, '42');
  assert.equal(parsed.records[0].pid, 313);
  assert.equal(parsed.records[0].startTimeRaw, '123456');
  assert.equal(parsed.records[0].rootHostModule, 'entry');
  const split = parse(empty + record.replace('      root host module name [entry]\n', '') + '\n' + record);
  assert.equal(split.records[0].complete, false);
  assert.equal(split.records[0].rootHostModule, undefined);
  assert.equal(split.records[1].complete, true);
  assert.equal(parse('permission denied').recognized, false);
  assert.equal(parse(empty).records.length, 0);
});

for (const variant of ['complete', 'preexisting', 'wrong_host', 'wrong_module', 'wrong_ability', 'dead_pid', 'inactive',
  'missing_module', 'duplicate_field', 'bad_header', 'exit_failure', 'command_error', 'truncated', 'resolved_during_dump',
  'wrong_call', 'stale_dump', 'late_dump', 'bad_clock', 'no_baseline', 'duplicate_sample']) {
  test('provider interval correlation: ' + variant, () => {
    const result = observation(), before = result.providerCommands[0], after = result.providerCommands[1];
    if (variant === 'preexisting') before.stdResult = after.stdResult;
    if (variant === 'wrong_host') after.stdResult = after.stdResult.replace('root host bundle name [test]', 'root host bundle name [other]');
    if (variant === 'wrong_module') after.stdResult = after.stdResult.replace('root host module name [entry]', 'root host module name [other]');
    if (variant === 'wrong_ability') after.stdResult = after.stdResult.replace('root host ability name [EntryAbility]', 'root host ability name [Other]');
    if (variant === 'dead_pid') after.stdResult = after.stdResult.replace('pid: 313', 'pid: 0');
    if (variant === 'inactive') after.stdResult = after.stdResult.replace('#FOREGROUND', '#BACKGROUND');
    if (variant === 'missing_module') after.stdResult = after.stdResult.replace('      root host module name [entry]\n', '');
    if (variant === 'duplicate_field') after.stdResult += '\n      bundle name [other]';
    if (variant === 'bad_header') after.stdResult = after.stdResult.replace('ID #42', 'ID ???');
    if (variant === 'exit_failure') after.exitCode = 1;
    if (variant === 'command_error') after.error = 'SDK timeout';
    if (variant === 'truncated') after.completed = false;
    if (variant === 'resolved_during_dump') after.pickerStateAfterJson = after.pickerStateAfterJson.replace('pending', 'resolved');
    if (variant === 'wrong_call') after.pickerStateAfterJson = after.pickerStateAfterJson.replace('"id":1', '"id":2');
    if (variant === 'stale_dump') after.startedAtMs = 19;
    if (variant === 'late_dump') after.finishedAtMs = 41;
    if (variant === 'bad_clock') after.finishedAtMs = 29;
    if (variant === 'no_baseline') result.providerCommands.shift();
    if (variant === 'duplicate_sample') result.providerCommands.push({ ...after });
    const rawResult = JSON.stringify(result);
    const diagnostics = JSON.parse(summarize(rawResult));
    assert.equal(diagnostics.providerIdentityVerified, false);
    assert.equal(diagnostics.matches.some(item => item.correlatedNewHostExtension), variant === 'complete');
    if (variant === 'preexisting') assert.equal(diagnostics.matches[0].newRecord, false);
    assert.equal(JSON.stringify(result), rawResult, 'Raw command evidence was not overwritten');
  });
}

test('installed metadata never guesses numeric extension types', () => {
  const result = observation();
  result.providerCommands.push({ phase: 'pending_metadata', command: 'bm dump -n com.ohos.filepicker -u 100',
    completed: true, exitCode: 0, startedAtMs: 45, finishedAtMs: 50,
    stdResult: 'com.ohos.filepicker:\n' + JSON.stringify({ name: 'com.ohos.filepicker', hapModuleInfos: [
      { name: 'audiopicker', extensionInfos: [{ name: 'audiopicker', type: 123456 }] }] }) });
  const parsed = JSON.parse(summarize(JSON.stringify(result)));
  assert.equal(parsed.installedProvider.available, true);
  assert.equal(parsed.installedProvider.declarations[0].type, 123456);
  assert.equal(parsed.providerIdentityVerified, false);
});

function withMetadata() {
  const result = observation(), bundleName = 'com.vendor.audio';
  for (const sample of result.providerCommands) sample.stdResult = sample.stdResult.replaceAll('com.ohos.filepicker', bundleName);
  const data = { name: bundleName, applicationInfo: { name: bundleName, bundleName, isSystemApp: true, versionName: 'test' },
    hapModuleInfos: [{ extensionInfos: [{ name: 'audiopicker', bundleName, moduleName: 'audiopicker',
      enabled: true, visible: true, extensionTypeName: 'sysPicker/audioPicker', type: 409,
      hapPath: '/system/app/Audio/audio.hap' }] }] };
  const after = result.providerCommands[1];
  result.providerCommands.push({ phase: 'pending_metadata', command: 'bm dump -n ' + bundleName + ' -u 100', completed: true,
    exitCode: 0, startedAtMs: 45, finishedAtMs: 50, pickerStateBeforeJson: after.pickerStateBeforeJson,
    pickerStateAfterJson: after.pickerStateAfterJson, stdResult: JSON.stringify(data) });
  return { result, data, sample: result.providerCommands[2] };
}

for (const variant of ['complete', 'wrong_provider', 'wrong_app', 'nonsystem', 'wrong_ability', 'wrong_module',
  'wrong_type', 'numeric_only', 'disabled', 'hidden', 'duplicate_declaration', 'resolved', 'wrong_sdk', 'old_metadata',
  'exit_failure', 'missing_dump', 'old_record', 'wrong_host', 'duplicate_metadata']) {
  test('installed system audio provider identity: ' + variant, () => {
    const { result, data, sample } = withMetadata(), extension = data.hapModuleInfos[0].extensionInfos[0];
    if (variant === 'wrong_provider') data.name = 'com.other.app';
    if (variant === 'wrong_app') data.applicationInfo.bundleName = 'com.other.app';
    if (variant === 'nonsystem') data.applicationInfo.isSystemApp = false;
    if (variant === 'wrong_ability') extension.name = 'other';
    if (variant === 'wrong_module') extension.moduleName = 'other';
    if (variant === 'wrong_type') extension.extensionTypeName = 'sysPicker/photoPicker';
    if (variant === 'numeric_only') delete extension.extensionTypeName;
    if (variant === 'disabled') extension.enabled = false;
    if (variant === 'hidden') extension.visible = false;
    if (variant === 'duplicate_declaration') data.hapModuleInfos[0].extensionInfos.push({ ...extension });
    if (variant === 'resolved') sample.pickerStateAfterJson = sample.pickerStateAfterJson.replace('pending', 'resolved');
    if (variant === 'wrong_sdk') sample.pickerStateAfterJson = sample.pickerStateAfterJson.replace('"id":1', '"id":2');
    if (variant === 'old_metadata') sample.startedAtMs = 5;
    if (variant === 'exit_failure') sample.exitCode = 1;
    if (variant === 'missing_dump') result.providerCommands.shift();
    if (variant === 'old_record') result.providerCommands[0].stdResult = result.providerCommands[1].stdResult;
    if (variant === 'wrong_host') result.providerCommands[1].stdResult = result.providerCommands[1].stdResult.replace('[EntryAbility]', '[Wrong]');
    if (variant === 'duplicate_metadata') result.providerCommands.push({ ...sample });
    sample.stdResult = JSON.stringify(data);
    const proof = JSON.parse(summarize(JSON.stringify(result)));
    assert.equal(proof.providerIdentityVerified, variant === 'complete');
    if (variant === 'complete') {
      assert.equal(metadataCommand(JSON.stringify(result)), 'bm dump -n com.vendor.audio -u 100');
      assert.equal(proof.matchedRecord.providerModule, 'audiopicker');
    }
  });
}

test('dynamic provider query rejects unsafe package text and ambiguous new extensions', () => {
  const { result } = withMetadata();
  result.providerCommands[1].stdResult = result.providerCommands[1].stdResult.replaceAll('com.vendor.audio', 'com.vendor.audio;id');
  assert.equal(metadataCommand(JSON.stringify(result)), '');
  const ambiguous = withMetadata().result;
  ambiguous.providerCommands[1].stdResult += '\n' + record;
  assert.equal(metadataCommand(JSON.stringify(ambiguous)), '');
});

for (const user of [undefined, '-1', '0100', '100;id', '1.0', '2147483648', '0', '107']) {
  test('provider query binds the explicit validated inventory user: ' + String(user), () => {
    const { result, sample } = withMetadata();
    result.deviceUserId = user; result.deviceUserParameter = user;
    const valid = ['0', '107'].includes(user);
    sample.command = 'bm dump -n com.vendor.audio -u ' + user;
    const raw = JSON.stringify(result);
    assert.equal(metadataCommand(raw), valid ? sample.command : '');
    assert.equal(JSON.parse(summarize(raw)).providerIdentityVerified, valid);
  });
}

test('metadata for a different/default user and the real 66-byte bm error cannot verify identity', () => {
  const { result, sample } = withMetadata();
  sample.command = 'bm dump -n com.vendor.audio';
  assert.equal(JSON.parse(summarize(JSON.stringify(result))).providerIdentityVerified, false);
  sample.command = 'bm dump -n com.vendor.audio -u 0';
  assert.equal(JSON.parse(summarize(JSON.stringify(result))).providerIdentityVerified, false);
  sample.command = 'bm dump -n com.vendor.audio -u 100';
  sample.stdResult = 'error: failed to get information and the parameters may be wrong.\n';
  const parsed = JSON.parse(summarize(JSON.stringify(result)));
  assert.equal(sample.exitCode, 0);
  assert.equal(Buffer.byteLength(sample.stdResult), 66);
  assert.equal(parsed.providerIdentityVerified, false);
  assert.match(parsed.installedProvider.reason, /Unrecognized bm JSON envelope/);
  result.deviceUserParameter = '101';
  assert.equal(metadataCommand(JSON.stringify(result)), '');
});

for (const variant of ['valid', 'wrong_nonce', 'wrong_request', 'wrong_raw', 'wrong_digest', 'wrong_bytes',
  'stderr', 'host_time', 'settled', 'wrong_sdk', 'old_metadata', 'duplicate', 'nonsystem', 'wrong_type', 'old_record']) {
  test('host metadata remains bound to raw same-pending interval: ' + variant, () => {
    const { result, sample, data } = withMetadata();
    Object.assign(result, { taskId: '18_custom_notification_sounds', caseId: 'ns_state_003_message_picker_launch',
      key: 'message_picker_launch', executionNonce: 'a'.repeat(32), hostProviderTransportEnabled: true,
      providerTransportContext: { origin: 'AbilityDelegator.getAppContext().getApplicationContext()',
        applicationName: result.bundleName, cacheDir: '/data/storage/el2/base/cache' } });
    const requestJson = m.exports.tasks16To18ProviderHostRequest(JSON.stringify(result), 55);
    sample.stdResult = 'error: failed to get information and the parameters may be wrong.\n';
    if (variant === 'nonsystem') data.applicationInfo.isSystemApp = false;
    if (variant === 'wrong_type') data.hapModuleInfos[0].extensionInfos[0].extensionTypeName = 'sysPicker/photoPicker';
    const raw = JSON.stringify(data), digest = require('node:crypto').createHash('sha256').update(raw).digest('hex');
    const response = { version: 2, transport: 'hdc_provider_metadata_app_cache_v2', request: JSON.parse(requestJson),
      command: sample.command, exitCode: 0, stdResult: raw, stderr: '', stdoutSha256: digest,
      stdoutBytes: Buffer.byteLength(raw), stdoutCharacters: raw.length,
      host: { serial: 'test', role: 'final', requestLogPid: '1234', receivedAtMs: 100, startedAtMs: 101, finishedAtMs: 102 } };
    const hostSample = { ...sample, phase: 'pending_metadata_host', startedAtMs: 55, finishedAtMs: 60,
      stdResult: raw, hostRequestJson: requestJson, responseStdoutSha256: digest, responseStdoutBytes: Buffer.byteLength(raw),
      responseReadPath: response.request.nativeResponsePath + '.tmp', responseReadApi: '@ohos.file.fs.readTextSync',
      responseFinalPath: response.request.nativeResponsePath, responseRenameApi: '@ohos.file.fs.renameSync', responseRenamed: true };
    result.providerCommands.push(hostSample);
    if (variant === 'wrong_nonce') response.request.nonce = 'b'.repeat(32);
    if (variant === 'wrong_request') hostSample.hostRequestJson = requestJson.replace('"recordId":"42"', '"recordId":"43"');
    if (variant === 'wrong_raw') hostSample.stdResult = '{}';
    if (variant === 'wrong_digest') hostSample.responseStdoutSha256 = 'b'.repeat(64);
    if (variant === 'wrong_bytes') response.stdoutBytes++;
    if (variant === 'stderr') response.stderr = 'permission denied';
    if (variant === 'host_time') response.host.startedAtMs = 103;
    if (variant === 'settled') hostSample.pickerStateAfterJson = hostSample.pickerStateAfterJson.replace('pending', 'resolved');
    if (variant === 'wrong_sdk') hostSample.pickerStateAfterJson = hostSample.pickerStateAfterJson.replace('"id":1', '"id":2');
    if (variant === 'old_metadata') hostSample.startedAtMs = 5;
    if (variant === 'duplicate') result.providerCommands.push({ ...hostSample });
    if (variant === 'old_record') result.providerCommands[0].stdResult = result.providerCommands[1].stdResult;
    hostSample.hostResponseJson = JSON.stringify(response);
    hostSample.responseFileBytes = Buffer.byteLength(hostSample.hostResponseJson);
    hostSample.responseFinalBytes = hostSample.responseFileBytes;
    const proof = JSON.parse(summarize(JSON.stringify(result)));
    assert.equal(proof.metadataTransport, 'nonce_bound_hdc');
    assert.equal(proof.providerIdentityVerified, variant === 'valid');
    if (variant === 'valid') {
      assert.equal(proof.hostTransportVerified, true);
      assert.equal(proof.metadataIntervalCorrelated, true);
      assert.equal(result.providerCommands[2].stdResult.length, 66, 'Original native failure retained');
    }
  });
}
