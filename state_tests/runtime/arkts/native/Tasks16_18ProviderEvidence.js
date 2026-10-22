// Read-only evaluator evidence. Provider identity comes from same-run records
// and the installed declaration, never a vendor package allowlist.
const dumpSource = 'https://github.com/openharmony/ability_ability_runtime/blob/master/services/abilitymgr/src/extension_record/base_extension_record.cpp';

function shellOK(sample, command) {
  return sample?.command === command && sample.completed === true && !sample.error && sample.exitCode === 0 &&
    typeof sample.stdResult === 'string' && Number.isFinite(sample.startedAtMs) &&
    Number.isFinite(sample.finishedAtMs) && sample.finishedAtMs >= sample.startedAtMs;
}

export function parseTasks16To18ExtensionDump(raw) {
  const records = [], errors = [];
  if (typeof raw !== 'string' || raw.length > 1024 * 1024) return { records, errors: ['Missing/oversized dump'], recognized: false };
  const lines = raw.split(/\r?\n/);
  let record, serviceUri, section = false, recognized = false;
  const finish = () => {
    if (!record) return;
    const required = ['recordId', 'state', 'startTimeRaw', 'providerAbility', 'providerBundle', 'abilityType'];
    if (record.abilityType === 'UIEXTENSION') required.push('providerModule', 'rootHostBundle', 'rootHostModule', 'rootHostAbility', 'pid');
    if (record.uriBundle !== undefined && record.uriBundle !== record.providerBundle) record.errors.push('Service URI bundle mismatch');
    record.missing = required.filter(key => record[key] === undefined || record[key] === '');
    record.complete = record.missing.length === 0 && record.errors.length === 0;
    records.push(record);
    record = undefined;
  };
  const fields = { 'main name': 'providerAbility', 'bundle name': 'providerBundle', 'ability type': 'abilityType',
    'root host bundle name': 'rootHostBundle', 'root host module name': 'rootHostModule', 'root host ability name': 'rootHostAbility' };
  lines.forEach((line, index) => {
    if (/^\s*ExtensionRecords:\s*$/.test(line)) { finish(); serviceUri = undefined; section = true; recognized = true; return; }
    if (!section) return;
    const uri = /^\s*uri \[([^\]]+)\]\s*$/.exec(line);
    if (uri) { finish(); serviceUri = uri[1].trim(); return; }
    if (/^\s*uri \[/.test(line)) { finish(); serviceUri = undefined; errors.push('Unrecognized service URI at line ' + (index + 1)); return; }
    const header = /^\s*AbilityRecord ID #(\d+)\s+state #([A-Z_]+)\s+start time \[(\d+)\]\s*$/.exec(line);
    if (header) {
      finish();
      record = { recordId: header[1], state: header[2], startTimeRaw: header[3], startLine: index + 1,
        endLine: index + 1, serviceUri, errors: [] };
      const element = /^\/([^/]+)\/([^/]+)\/[^/]+$/.exec(serviceUri || '');
      if (element) { record.uriBundle = element[1]; record.providerModule = element[2]; }
      return;
    }
    if (/^\s*AbilityRecord ID\b/.test(line)) { finish(); errors.push('Unrecognized record header at line ' + (index + 1)); return; }
    if (!record) return;
    record.endLine = index + 1;
    // Source emits identity fields at this indentation. Never borrow identity
    // from nested client dumps or from the following ability record.
    const field = /^ {6}(main name|bundle name|ability type|root host bundle name|root host module name|root host ability name) \[([^\]\r\n]*)\]\s*$/.exec(line);
    const pid = /^ {6}pid: (\d+)\s*$/.exec(line);
    const key = field ? fields[field[1]] : pid ? 'pid' : undefined;
    if (key) {
      if (record[key] !== undefined) record.errors.push('Duplicate field ' + key);
      else record[key] = field ? field[2] : Number(pid[1]);
    }
  });
  finish();
  return { records, errors, recognized, source: dumpSource,
    clockNote: 'startTimeRaw is retained in the service clock; no conversion to wall clock is assumed.' };
}

function json(value) { try { return JSON.parse(value); } catch (_) { return undefined; } }
function pending(snapshot) {
  const data = json(snapshot);
  return data?.observer?.available === true && data.calls?.length === 1 &&
    data.calls[0].status === 'pending' && data.calls[0].api === '@ohos.file.picker.AudioViewPicker.select' ? data.calls[0] : undefined;
}

function safeBundle(bundle) {
  return typeof bundle === 'string' && bundle.length <= 255 && /^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$/.test(bundle);
}

function deviceUser(result) {
  const user = result.deviceUserId;
  return typeof user === 'string' && /^(0|[1-9][0-9]{0,9})$/.test(user) && Number(user) <= 2147483647 &&
    result.deviceUserParameter === user && !result.deviceUserError &&
    result.deviceUserSource === 'AbilityDelegatorRegistry.getArguments().parameters["-s ltbDeviceUser"]' ? user : undefined;
}

function metadata(sample, record, user) {
  if (user === undefined) return { available: false, reason: 'Installed device user parameter is missing/invalid; no default user is assumed.' };
  if (!record || !safeBundle(record.providerBundle) || !shellOK(sample, 'bm dump -n ' + record.providerBundle + ' -u ' + user)) {
    return { available: false, reason: 'Exact observed provider metadata command unavailable/nonzero' };
  }
  const raw = sample.stdResult.trim(), start = raw.indexOf('{');
  if (start < 0 || !['', record.providerBundle + ':'].includes(raw.slice(0, start).trim())) {
    return { available: false, reason: 'Unrecognized bm JSON envelope' };
  }
  const data = json(raw.slice(start));
  if (!data || typeof data !== 'object' || Array.isArray(data)) return { available: false, reason: 'Invalid bm JSON payload' };
  const declarations = [];
  if (Array.isArray(data.hapModuleInfos)) data.hapModuleInfos.forEach((module, moduleIndex) => {
    if (!Array.isArray(module?.extensionInfos)) return;
    module.extensionInfos.forEach((item, extensionIndex) => {
      if (item && typeof item === 'object') declarations.push({ path: ['hapModuleInfos', moduleIndex, 'extensionInfos', extensionIndex],
        name: item.name, bundleName: item.bundleName, moduleName: item.moduleName, enabled: item.enabled, visible: item.visible,
        extensionTypeName: item.extensionTypeName, type: item.type, hapPath: item.hapPath });
    });
  });
  const app = data.applicationInfo;
  const systemApp = data.name === record.providerBundle && app?.bundleName === record.providerBundle &&
    app.name === record.providerBundle && app.isSystemApp === true;
  const matching = declarations.filter(item => item.name === record.providerAbility &&
    item.bundleName === record.providerBundle && item.moduleName === record.providerModule);
  const declaration = matching.length === 1 ? matching[0] : undefined;
  return { available: true, bundleName: data.name, applicationInfo: app ? { name: app.name, bundleName: app.bundleName,
    isSystemApp: app.isSystemApp, versionName: app.versionName } : undefined,
    declarations, declaration, verifiedSystemAudioProvider: !!(systemApp && declaration?.enabled === true &&
      declaration.visible === true && declaration.extensionTypeName === 'sysPicker/audioPicker'),
    scope: 'Exact installed system app and extension declaration; numeric extension type is diagnostic only.' };
}

export function summarizeTasks16To18ProviderEvidence(resultJson) {
  const result = JSON.parse(resultJson), samples = result.providerCommands || [];
  const beforeSamples = samples.filter(sample => sample.phase === 'before_picker' && sample.command === 'aa dump -e');
  const afterSamples = samples.filter(sample => sample.phase === 'pending_after' && sample.command === 'aa dump -e');
  const before = beforeSamples[0], after = afterSamples[0];
  const parsedBefore = parseTasks16To18ExtensionDump(before?.stdResult);
  const parsedAfter = parseTasks16To18ExtensionDump(after?.stdResult);
  const binding = json(result.originalModuleBindingJson), host = binding?.monitoredContext?.scope;
  const pickerStart = pending(after?.pickerStateBeforeJson), pickerEnd = pending(after?.pickerStateAfterJson);
  const beforePickerStart = json(before?.pickerStateBeforeJson), beforePickerEnd = json(before?.pickerStateAfterJson);
  const frame = result.checkpoints?.find(item => item.label === 'after_event');
  const frameStart = pending(frame?.pickerStateBeforeJson), frameEnd = pending(frame?.pickerStateJson);
  const validDump = parsed => parsed.recognized && parsed.errors.length === 0 && parsed.records.every(record => record.complete);
  const intervalCorrelated = !!(beforeSamples.length === 1 && afterSamples.length === 1 &&
    shellOK(before, 'aa dump -e') && shellOK(after, 'aa dump -e') && validDump(parsedBefore) && validDump(parsedAfter) &&
    beforePickerStart?.observer?.available && beforePickerEnd?.observer?.available &&
    beforePickerStart.calls?.length === 0 && beforePickerEnd.calls?.length === 0 && pickerStart && pickerEnd &&
    pickerStart.id === pickerEnd.id && pickerStart.startedAtMs === pickerEnd.startedAtMs &&
    pickerStart.samePageContext === true && pickerEnd.samePageContext === true &&
    before.finishedAtMs <= pickerStart.startedAtMs && pickerStart.startedAtMs <= after.startedAtMs &&
    frame?.completed === true && !frame.error && frameStart?.id === pickerStart.id && frameEnd?.id === pickerStart.id &&
    frameStart.startedAtMs === pickerStart.startedAtMs && frameEnd.startedAtMs === pickerStart.startedAtMs &&
    frame.startedAtMs <= after.startedAtMs && after.finishedAtMs <= frame.finishedAtMs &&
    frame.focusedBundle === result.bundleName);
  const exactHost = record => host && host.bundleName === result.bundleName &&
    [host.bundleName, host.moduleName, host.abilityName].every(value => typeof value === 'string' && value.length > 0) &&
    record.rootHostBundle === host.bundleName && record.rootHostModule === host.moduleName && record.rootHostAbility === host.abilityName;
  const key = record => [record.providerBundle, record.providerAbility, record.recordId, record.pid, record.startTimeRaw].join('|');
  const prior = new Set(parsedBefore.records.map(key));
  const priorRecordIds = new Set(parsedBefore.records.map(record => record.recordId));
  const matched = parsedAfter.records.filter(record => record.complete && record.abilityType === 'UIEXTENSION' &&
    ['ACTIVE', 'FOREGROUND'].includes(record.state) && Number.isSafeInteger(record.pid) && record.pid > 0 && exactHost(record));
  const isNew = record => !prior.has(key(record)) && !priorRecordIds.has(record.recordId);
  const matches = matched.map(record => ({ ...record, newRecord: isNew(record),
    correlatedNewHostExtension: intervalCorrelated && isNew(record) }));
  const candidates = matches.filter(record => record.correlatedNewHostExtension);
  const candidate = candidates.length === 1 ? candidates[0] : undefined;
  const hostSamples = samples.filter(sample => sample.phase === 'pending_metadata_host');
  const metadataSamples = hostSamples.length ? hostSamples : samples.filter(sample => sample.phase === 'pending_metadata');
  const metadataSample = metadataSamples.length === 1 ? metadataSamples[0] : undefined;
  const user = deviceUser(result);
  let hostTransportVerified = false, hostTransportError;
  if (metadataSample?.phase === 'pending_metadata_host') {
    try {
      const expected = tasks16To18ProviderHostRequest(resultJson, metadataSample.startedAtMs);
      if (expected !== metadataSample.hostRequestJson) throw new Error('Host request is not bound to this runtime record');
      validateTasks16To18ProviderHostResponse(expected, metadataSample.hostResponseJson,
        metadataSample.responseStdoutSha256, metadataSample.responseStdoutBytes);
      const response = JSON.parse(metadataSample.hostResponseJson);
      if (response.stdResult !== metadataSample.stdResult || response.exitCode !== metadataSample.exitCode) {
        throw new Error('Host raw metadata differs from the received response');
      }
      if (metadataSample.responseReadPath !== response.request.nativeResponsePath + '.tmp' ||
        metadataSample.responseFinalPath !== response.request.nativeResponsePath ||
        metadataSample.responseRenameApi !== '@ohos.file.fs.renameSync' || metadataSample.responseRenamed !== true ||
        metadataSample.responseFinalBytes !== metadataSample.responseFileBytes ||
        metadataSample.responseReadApi !== '@ohos.file.fs.readTextSync' || !Number.isSafeInteger(metadataSample.responseFileBytes) ||
        metadataSample.responseFileBytes < 1 || metadataSample.responseFileBytes > 3 * 1024 * 1024) {
        throw new Error('Host response was not read from the bound application cache');
      }
      hostTransportVerified = true;
    } catch (error) { hostTransportError = String(error); }
  }
  const installedProvider = metadataSample?.phase === 'pending_metadata_host' && !hostTransportVerified ?
    { available: false, reason: hostTransportError } : metadata(metadataSample, candidate, user);
  const metadataStart = pending(metadataSample?.pickerStateBeforeJson), metadataEnd = pending(metadataSample?.pickerStateAfterJson);
  const metadataIntervalCorrelated = !!(candidate && metadataSample && pickerEnd && metadataStart && metadataEnd &&
    metadataStart.id === pickerEnd.id && metadataEnd.id === pickerEnd.id &&
    metadataStart.startedAtMs === pickerEnd.startedAtMs && metadataEnd.startedAtMs === pickerEnd.startedAtMs &&
    metadataStart.samePageContext === true && metadataEnd.samePageContext === true &&
    after.finishedAtMs <= metadataSample.startedAtMs && frame.finishedAtMs <= metadataSample.startedAtMs &&
    user !== undefined && shellOK(metadataSample, 'bm dump -n ' + candidate.providerBundle + ' -u ' + user));
  return JSON.stringify({ schemaVersion: 1, observationLevel: 'native_shell_evidence',
    before: parsedBefore, after: parsedAfter, installedProvider, host,
    deviceUserId: user, deviceUserParameter: result.deviceUserParameter, deviceUserSource: result.deviceUserSource,
    metadataTransport: hostSamples.length ? 'nonce_bound_hdc' : 'delegator_shell',
    hostTransportVerified, hostTransportError, executionNonce: result.executionNonce,
    sdkCallId: pickerStart?.id, sdkStartedAtMs: pickerStart?.startedAtMs, intervalCorrelated, metadataIntervalCorrelated, matches,
    providerIdentityVerified: !!(candidate && metadataIntervalCorrelated && installedProvider.verifiedSystemAudioProvider),
    matchedRecord: candidate,
    limitation: 'Provider identity alone is insufficient. Scoring also requires original-page GIVEN, native pending call, unchanged preferences and real extension anchors.' });
}

export function tasks16To18ProviderMetadataCommand(resultJson) {
  const summary = JSON.parse(summarizeTasks16To18ProviderEvidence(resultJson));
  const bundle = summary.matchedRecord?.providerBundle;
  return summary.intervalCorrelated && safeBundle(bundle) && summary.deviceUserId !== undefined ?
    'bm dump -n ' + bundle + ' -u ' + summary.deviceUserId : '';
}

export function tasks16To18ProviderHostRequest(resultJson, requestedAtMs) {
  const result = JSON.parse(resultJson);
  if (!/^[a-f0-9]{32}$/.test(result.executionNonce || '') || result.hostProviderTransportEnabled !== true ||
    result.taskId !== '18_custom_notification_sounds' || result.key !== 'message_picker_launch' ||
    !Number.isFinite(requestedAtMs)) throw new Error('Host provider request requires this execution nonce and explicit transport capability');
  // Exclude the response being validated so request derivation never trusts its
  // own claimed provider identity, and recursion cannot accept a forged summary.
  result.providerCommands = (result.providerCommands || []).filter(sample => sample.phase !== 'pending_metadata_host');
  const proof = JSON.parse(summarizeTasks16To18ProviderEvidence(JSON.stringify(result)));
  const record = proof.matchedRecord, user = deviceUser(result);
  if (!proof.intervalCorrelated || !record || !safeBundle(record.providerBundle) || user === undefined) {
    throw new Error('No unique same-run pending provider record for the host request');
  }
  const context = result.providerTransportContext;
  if (context?.origin !== 'AbilityDelegator.getAppContext().getApplicationContext()' ||
    context.applicationName !== result.bundleName || context.cacheDir !== '/data/storage/el2/base/cache') {
    throw new Error('Actual application cache context is unavailable or cannot be mapped to this candidate');
  }
  const responseName = 'Tasks16_18_provider_' + result.executionNonce + '.json';
  return JSON.stringify({ version: 2, nonce: result.executionNonce, requestId: 'provider1',
    taskId: result.taskId, caseId: result.caseId, bundleName: result.bundleName, userId: user,
    providerBundle: record.providerBundle, providerModule: record.providerModule, providerAbility: record.providerAbility,
    recordId: record.recordId, pid: record.pid, hostModule: record.rootHostModule, hostAbility: record.rootHostAbility,
    sdkCallId: proof.sdkCallId, sdkStartedAtMs: proof.sdkStartedAtMs, requestedAtMs,
    responseName, cacheContext: context, nativeResponsePath: context.cacheDir + '/' + responseName,
    debugResponsePath: context.cacheDir.slice(1) + '/' + responseName,
    hostResponsePath: '/data/app/el2/' + user + '/base/' + result.bundleName + '/cache/' + responseName });
}

export function validateTasks16To18ProviderHostResponse(requestJson, responseJson, stdoutSha256, stdoutBytes) {
  const request = JSON.parse(requestJson), response = JSON.parse(responseJson);
  if (request.version !== 2 || response.version !== 2 || response.transport !== 'hdc_provider_metadata_app_cache_v2' ||
    JSON.stringify(response.request) !== JSON.stringify(request) || !/^[a-f0-9]{32}$/.test(request.nonce) ||
    response.command !== 'bm dump -n ' + request.providerBundle + ' -u ' + request.userId ||
    !Number.isInteger(response.exitCode) || typeof response.stdResult !== 'string' ||
    response.stdResult.length > 2 * 1024 * 1024 || response.stderr !== '' ||
    !/^[a-f0-9]{64}$/.test(stdoutSha256 || '') || stdoutSha256 !== response.stdoutSha256 ||
    !Number.isSafeInteger(stdoutBytes) || stdoutBytes !== response.stdoutBytes ||
    response.stdoutCharacters !== response.stdResult.length ||
    typeof response.host?.serial !== 'string' || !response.host.serial ||
    typeof response.host.role !== 'string' || !response.host.role ||
    !/^[1-9][0-9]*$/.test(response.host.requestLogPid || '') ||
    ![response.host.receivedAtMs, response.host.startedAtMs, response.host.finishedAtMs].every(Number.isFinite) ||
    response.host.receivedAtMs > response.host.startedAtMs || response.host.startedAtMs > response.host.finishedAtMs) {
    throw new Error('Host metadata response identity, raw digest or command provenance mismatch');
  }
}
