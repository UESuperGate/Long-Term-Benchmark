const sha256Pattern = /^[a-f0-9]{64}$/;
const noncePattern = /^[a-f0-9]{32}$/;
const hostPattern = /^127\.0\.0\.1:([1-9][0-9]{0,4})$/;
const urlPattern = /^https:\/\/(127\.0\.0\.1:[1-9][0-9]{0,4})$/;

function parameter(parameters, name) {
  return parameters[name] || parameters['-s ' + name] || '';
}

function normalizeHomeserver(value) {
  const text = typeof value === 'string' ? value : '';
  const urlMatch = text.match(urlPattern);
  const host = urlMatch ? urlMatch[1] : text;
  const hostMatch = host.match(hostPattern);
  const port = hostMatch ? Number(hostMatch[1]) : 0;
  if (!hostMatch || port > 65535) throw new Error('Invalid Task14 native E2E homeserver');
  return { homeserver: host, controlHomeserver: 'https://' + host };
}

function validateConfig(value) {
  if (!value || value.enabled !== true || typeof value.nonce !== 'string' ||
      typeof value.caSha256 !== 'string' || !noncePattern.test(value.nonce) ||
      !sha256Pattern.test(value.caSha256)) {
    throw new Error('Invalid Task14 native E2E configuration');
  }
  const normalized = normalizeHomeserver(value.homeserver || value.controlHomeserver);
  if (value.controlHomeserver !== undefined && value.controlHomeserver !== normalized.controlHomeserver) {
    throw new Error('Task14 native E2E homeserver/control URL mismatch');
  }
  return { enabled: true, nonce: value.nonce, homeserver: normalized.homeserver,
    controlHomeserver: normalized.controlHomeserver, caSha256: value.caSha256 };
}

export function task14NativeE2EConfig(parameters) {
  if (parameter(parameters, 'task14E2E') !== '1') return undefined;
  const homeserver = normalizeHomeserver(parameter(parameters, 'task14Homeserver'));
  return validateConfig({ enabled: true, nonce: parameter(parameters, 'task14Nonce'),
    homeserver: homeserver.homeserver, controlHomeserver: homeserver.controlHomeserver,
    caSha256: parameter(parameters, 'task14CaSha256') });
}

export function createTask14NativeE2E(configValue, context, resourceContext, driver, ON, platform) {
  const config = validateConfig(configValue);
  const fs = platform.fs;
  const abilityDelegator = platform.abilityDelegator;
  const certificateManager = platform.certificateManager;
  const fileUri = platform.fileUri;
  const wantConstant = platform.wantConstant;
  const http = platform.http;
  const suffix = config.nonce.slice(0, 12);
  const loginUsername = 'task14_' + suffix;
  const loginPassword = 'task14-login-' + config.nonce;
  const certificateName = 'LTB Task14 ' + config.nonce;
  const result = {
    schemaVersion: 1,
    nonce: config.nonce,
    homeserver: config.homeserver,
    controlHomeserver: config.controlHomeserver,
    caSha256: config.caSha256,
    checkpoints: [],
    certificate: { installed: false, uninstalled: false }
  };
  let certificateBytes;
  let certificateFile = '';
  let candidateAbility;
  let candidateBundleName = '';

  const snapshot = () => JSON.parse(JSON.stringify(result));
  const checkpoint = (label, value) => {
    const item = { label, value, at: Date.now() };
    result.checkpoints.push(item);
    console.info('TASK14_E2E_CHECKPOINT ' + JSON.stringify(item));
    return value;
  };
  const waitFor = async (label, read, accept, attempts = 100) => {
    const observations = [];
    for (let attempt = 0; attempt < attempts; attempt++) {
      try {
        const value = await read();
        observations.push(value);
        if (await accept(value)) return value;
      } catch (error) {
        observations.push({ error: String(error) });
      }
      await driver.delayMs(100);
    }
    throw new Error('Task14 bounded wait exhausted: ' + label + ': ' +
      JSON.stringify(observations.slice(-3)));
  };
  const requestJson = async (method, pathname, body) => {
    if (!http?.createHttp || !http.RequestMethod || !http.HttpDataType) {
      throw new Error('Task14 native HTTP control unavailable');
    }
    const request = http.createHttp();
    try {
      const response = await request.request(config.controlHomeserver + pathname, {
        method,
        header: { 'Content-Type': 'application/json', 'X-Task14-Nonce': config.nonce },
        extraData: body === undefined ? '' : JSON.stringify(body),
        expectDataType: http.HttpDataType.STRING,
        connectTimeout: 5000,
        readTimeout: 5000,
        usingCache: false
      });
      if (response.responseCode < 200 || response.responseCode >= 300) {
        throw new Error('Task14 control response ' + response.responseCode);
      }
      const parsed = typeof response.result === 'string' ? JSON.parse(response.result) : response.result;
      if (!parsed || typeof parsed !== 'object') throw new Error('Task14 control returned invalid JSON');
      return parsed;
    } finally {
      request.destroy();
    }
  };
  const providerStatus = async () => {
    const value = await requestJson(http.RequestMethod.GET,
      '/__task14/status?nonce=' + encodeURIComponent(config.nonce));
    if (value.nonce !== config.nonce || !Array.isArray(value.held)) {
      throw new Error('Task14 provider status is not bound to this run');
    }
    return value;
  };
  const providerControl = async (kind, payload = {}) => {
    if (kind === 'status') return providerStatus();
    if (kind !== 'release' || typeof payload.alias !== 'string') {
      throw new Error('Unsupported Task14 provider control');
    }
    const status = await providerStatus();
    const matches = status.held.filter(item => item.alias === payload.alias);
    if (matches.length !== 1 || typeof matches[0].caseId !== 'string' ||
        !Number.isInteger(matches[0].requestSequence)) {
      throw new Error('Task14 provider held request is missing or ambiguous');
    }
    const held = matches[0];
    const receipt = await requestJson(http.RequestMethod.POST, '/__task14/release', {
      nonce: config.nonce, caseId: held.caseId, requestSequence: held.requestSequence
    });
    if (receipt.released !== held.caseId || receipt.requestSequence !== held.requestSequence) {
      throw new Error('Task14 provider released the wrong request');
    }
    checkpoint('provider_request_released', { alias: payload.alias, caseId: held.caseId,
      requestSequence: held.requestSequence, outcome: receipt.outcome });
    return receipt;
  };
  const globalNodes = async type => await driver.findComponents(ON.type(type)) || [];
  const uniqueControlById = async id => {
    const matches = await driver.findComponents(ON.id(id)) || [];
    if (matches.length > 1) throw new Error('Ambiguous Task14 UI id: ' + id);
    if (matches.length === 1 && await matches[0].getId() !== id) {
      throw new Error('Task14 UiTest returned the wrong control for id: ' + id);
    }
    return matches[0];
  };
  const uniqueById = async (type, id) => {
    const matches = [];
    for (const node of await globalNodes(type)) if (await node.getId() === id) matches.push(node);
    if (matches.length > 1) throw new Error('Ambiguous Task14 UI id: ' + id);
    return matches[0];
  };
  const uniqueByText = async (type, text) => {
    const matches = [];
    for (const node of await globalNodes(type)) if (await node.getText() === text) matches.push(node);
    if (matches.length > 1) throw new Error('Ambiguous Task14 UI text: ' + text);
    return matches[0];
  };
  const control = id => waitFor('control ' + id, () => uniqueControlById(id), value => !!value);
  const clickControl = async id => {
    const node = await control(id);
    if (!await node.isEnabled()) throw new Error('Task14 UI control disabled: ' + id);
    await node.click();
  };
  const inputControl = async (id, value) => {
    const node = await control(id);
    if (!await node.isEnabled()) throw new Error('Task14 UI control disabled: ' + id);
    await node.inputText(value);
  };
  const clickSystemText = async text => {
    const node = await waitFor('system text ' + text, () => uniqueByText('Text', text), value => !!value);
    await node.click();
  };
  const clickSystemButton = async text => {
    const node = await waitFor('system button ' + text, () => uniqueByText('Button', text), value => !!value);
    if (!await node.isEnabled()) throw new Error('System UI button disabled: ' + text);
    await node.click();
  };
  const clickSystemButtonById = async id => {
    const node = await waitFor('system button id ' + id, () => uniqueById('Button', id), value => !!value);
    if (!await node.isEnabled()) throw new Error('System UI button disabled: ' + id);
    await node.click();
  };
  const equalBytes = (left, right) => {
    if (!left || !right || left.length !== right.length) return false;
    for (let index = 0; index < left.length; index++) if (left[index] !== right[index]) return false;
    return true;
  };
  const queryCertificate = async () => {
    const response = await certificateManager.getAllUserTrustedCertificates(certificateManager.CertScope.CURRENT_USER);
    const list = response && Array.isArray(response.certList) ? response.certList : [];
    for (const item of list) {
      const details = await certificateManager.getUserTrustedCertificate(item.uri);
      if (details?.certInfo && equalBytes(details.certInfo.cert, certificateBytes)) {
        return { querySucceeded: true, uri: item.uri, state: item.state, alias: item.certAlias,
          subjectName: item.subjectName, bytesMatch: true };
      }
    }
    return { querySucceeded: true, absent: true, count: list.length };
  };
  const startCertificateManager = async want => {
    if (!candidateAbility?.context) throw new Error('Candidate UIAbility context unavailable');
    await candidateAbility.context.startAbility({ bundleName: 'com.ohos.certmanager', moduleName: 'phone',
      abilityName: 'MainAbility', ...want });
  };
  const openUserCertificates = async () => {
    await startCertificateManager({});
    await clickSystemText('CA certificates');
    await clickSystemText('User');
  };
  const certificateListNode = async () => {
    const matches = [];
    for (const node of await globalNodes('Text')) {
      if (await node.getText() === certificateName) matches.push(node);
    }
    if (matches.length !== 2) throw new Error('Expected one Task14 self-signed certificate list item');
    return matches[0];
  };
  const openCertificateDetails = async () => {
    const node = await waitFor('Task14 certificate list item', certificateListNode, value => !!value);
    await node.click();
  };
  const enableCertificate = async installed => {
    if (installed.state === true) return installed;
    await openUserCertificates();
    await openCertificateDetails();
    const toggles = [...await globalNodes('Toggle'), ...await globalNodes('Switch')];
    if (toggles.length !== 1) throw new Error('Expected one Task14 user certificate enable toggle');
    await toggles[0].click();
    await clickSystemButton('Continue');
    return waitFor('Task14 user CA enabled', queryCertificate,
      value => value.bytesMatch === true && value.state === true);
  };
  const returnToCandidate = async () => {
    await abilityDelegator.startAbility({ bundleName: candidateBundleName, abilityName: 'EntryAbility', moduleName: 'entry' });
    await control('login_homeserver');
    checkpoint('candidate_returned_after_certificate_ui', { bundleName: candidateBundleName,
      loginFormVisible: true });
  };
  const installCertificate = async () => {
    certificateBytes = await resourceContext.resourceManager.getRawFileContent('task14-ca.der');
    candidateAbility = await abilityDelegator.getCurrentTopAbility();
    if (candidateAbility?.context?.abilityInfo?.bundleName !== candidateBundleName) {
      throw new Error('Certificate setup did not capture the Task14 candidate ability');
    }
    certificateFile = context.cacheDir + '/task14-ca-' + config.nonce + '.der';
    const file = fs.openSync(certificateFile, fs.OpenMode.CREATE | fs.OpenMode.WRITE_ONLY | fs.OpenMode.TRUNC);
    try {
      const written = fs.writeSync(file.fd, certificateBytes.buffer);
      if (written !== certificateBytes.length) throw new Error('Incomplete Task14 evaluator CA file write');
    } finally {
      fs.closeSync(file.fd);
    }
    const uri = fileUri.getUriFromPath(certificateFile);
    await startCertificateManager({ action: wantConstant.Action.ACTION_VIEW_DATA, uri,
      type: 'com.ohos.certmanager.der', flags: wantConstant.Flags.FLAG_AUTH_READ_URI_PERMISSION });
    await clickSystemButton('Install');
    await waitFor('Task14 certificate install confirmation', () => uniqueByText('Text', 'Install certificate'),
      value => !!value);
    await clickSystemButtonById('advanced_dialog_button_1');
    const installed = await waitFor('Task14 user CA installed', queryCertificate, value => value.bytesMatch === true);
    const enabled = await enableCertificate(installed);
    result.certificate = { installed: true, uninstalled: false, uriPresent: !!enabled.uri,
      bytesMatch: enabled.bytesMatch === true, trustEnabled: enabled.state === true,
      method: 'system_file_open_ui_with_read_uri_grant',
      subjectMatched: String(enabled.subjectName).includes(certificateName) };
    checkpoint('certificate_installed_and_enabled', { bytesMatch: result.certificate.bytesMatch,
      trustEnabled: result.certificate.trustEnabled, subjectMatched: result.certificate.subjectMatched });
    await returnToCandidate();
  };
  const removeCertificateFile = () => {
    if (!certificateFile) return;
    try { fs.unlinkSync(certificateFile); } catch (error) {
      console.info('TASK14_E2E_CA_FILE_CLEANUP ' + JSON.stringify({ removed: false, error: String(error) }));
    }
    certificateFile = '';
  };
  const uninstallCertificate = async () => {
    if (!certificateBytes) {
      result.certificate.cleanupConfirmed = true;
      result.certificate.absenceQuerySucceeded = true;
      removeCertificateFile();
      return;
    }
    const before = await queryCertificate();
    if (before.bytesMatch) {
      await openUserCertificates();
      await openCertificateDetails();
      await clickSystemButton('Delete certificate');
      await waitFor('Task14 certificate delete confirmation', () => uniqueByText('Text', 'Delete certificate'),
        value => !!value);
      await clickSystemButtonById('advanced_dialog_button_1');
    }
    const after = await waitFor('Task14 user CA removed', queryCertificate,
      value => value.querySucceeded === true && value.absent === true);
    result.certificate.uninstalled = before.bytesMatch === true;
    result.certificate.cleanupConfirmed = after.absent === true;
    result.certificate.absenceQuerySucceeded = after.querySucceeded === true;
    checkpoint('certificate_removed', { uninstalled: result.certificate.uninstalled,
      cleanupConfirmed: result.certificate.cleanupConfirmed,
      absenceQuerySucceeded: result.certificate.absenceQuerySucceeded });
    removeCertificateFile();
  };

  return {
    control: providerControl,
    async prepare(bundleName) {
      if (typeof bundleName !== 'string' || !/^[A-Za-z0-9_.]+$/.test(bundleName)) {
        throw new Error('Invalid Task14 candidate bundle name');
      }
      candidateBundleName = bundleName;
      await control('login_homeserver');
      checkpoint('candidate_login_form_ready', { bundleName, loginFormVisible: true });
      await installCertificate();
      await inputControl('login_homeserver', config.homeserver);
      await inputControl('login_username', loginUsername);
      await inputControl('login_password', loginPassword);
      checkpoint('login_fields_entered', { homeserver: config.homeserver, username: loginUsername,
        passwordDerivedFromNonce: true, passwordRedacted: true });
      await clickControl('login_submit');
      const session = await waitFor('Task14 authenticated session', () => uniqueControlById('session_user'),
        async node => !!node && (await node.getText()).startsWith('@' + loginUsername + ':'));
      const sessionUser = await session.getText();
      checkpoint('login_complete', { sessionUser, username: loginUsername, passwordRedacted: true });
      await clickControl('start_chat_action');
      const search = await waitFor('Task14 StartChat people search', () => uniqueControlById('people_search_input'),
        value => !!value);
      checkpoint('start_chat_ready', { peopleSearchId: await search.getId(), reachedByPhysicalControls: true });
      return snapshot();
    },

    async cleanup() {
      try {
        await uninstallCertificate();
      } catch (error) {
        result.certificate.cleanupError = String(error);
        removeCertificateFile();
        throw error;
      }
      return snapshot();
    }
  };
}
