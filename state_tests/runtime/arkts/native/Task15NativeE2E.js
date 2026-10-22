const sha256Pattern = /^[a-f0-9]{64}$/;

function parameter(parameters, name) {
  return parameters[name] || parameters['-s ' + name] || '';
}

function validateConfig(config) {
  if (config.enabled !== true || !/^[a-f0-9]{32}$/.test(config.nonce) ||
    !/^https:\/\/127\.0\.0\.1:[1-9][0-9]{1,4}$/.test(config.homeserver) ||
    !sha256Pattern.test(config.caSha256)) {
    throw new Error('Invalid Task15 native E2E configuration');
  }
  return config;
}

export function task15NativeE2EConfig(parameters) {
  if (parameter(parameters, 'task15E2E') !== '1') {
    return undefined;
  }
  return validateConfig({
    enabled: true,
    nonce: parameter(parameters, 'task15Nonce'),
    homeserver: parameter(parameters, 'task15Homeserver'),
    caSha256: parameter(parameters, 'task15CaSha256')
  });
}

export function createTask15NativeE2E(configValue, context, resourceContext, driver, ON, platform) {
  const config = validateConfig(configValue);
  const http = platform.http;
  const asset = platform.asset;
  const fs = platform.fs;
  const util = platform.util;
  const abilityDelegator = platform.abilityDelegator;
  const certificateManager = platform.certificateManager;
  const fileUri = platform.fileUri;
  const wantConstant = platform.wantConstant;
  const suffix = config.nonce.slice(0, 8);
  const loginUser = 'alice_' + suffix;
  const loginPassword = 'login-' + config.nonce.slice(0, 12);
  const expectedUserId = '@' + loginUser + ':task15.test';
  const expectedDeviceId = 'DEVICE_' + suffix.toUpperCase();
  const result = {
    schemaVersion: 1,
    nonce: config.nonce,
    homeserver: config.homeserver,
    caSha256: config.caSha256,
    transport: 'native @ohos.net.http over evaluator-owned HTTPS through HDC reverse',
    checkpoints: [],
    certificate: { installed: false, uninstalled: false }
  };
  const certificateName = 'LTB Task15 ' + config.nonce;
  let certificateBytes, certificateUri = '', certificateFile = '', candidateAbility;

  const checkpoint = (label, value) => {
    const item = { label, value, at: Date.now() };
    result.checkpoints.push(item);
    console.info('TASK15_E2E_CHECKPOINT ' + JSON.stringify(item));
    return value;
  };

  const waitFor = async (label, read, accept, attempts = 80) => {
    const observations = [];
    for (let attempt = 0; attempt < attempts; attempt++) {
      try {
        const value = await read();
        observations.push(value);
        if (accept(value)) return value;
      } catch (error) {
        observations.push({ error: String(error) });
      }
      await driver.delayMs(100);
    }
    throw new Error('Task15 bounded wait exhausted: ' + label + ': ' +
      JSON.stringify(observations.slice(-3)));
  };

  const requestJson = async (method, path, body) => {
    const request = http.createHttp();
    try {
      const response = await request.request(config.homeserver + path, {
        method,
        header: { 'Content-Type': 'application/json', 'X-Task15-Nonce': config.nonce },
        extraData: body === undefined ? '' : JSON.stringify(body),
        expectDataType: http.HttpDataType.STRING,
        connectTimeout: 5000,
        readTimeout: 5000,
        usingCache: false
      });
      if (response.responseCode < 200 || response.responseCode >= 300) {
        throw new Error('Task15 control response ' + response.responseCode);
      }
      return JSON.parse(response.result);
    } finally {
      request.destroy();
    }
  };

  const serverStatus = () => requestJson(http.RequestMethod.GET, '/__task15/status?nonce=' + config.nonce);
  const waitHeld = count => waitFor('held deactivation request ' + count, serverStatus,
    value => value.nonce === config.nonce && value.deactivationCount === count &&
      value.held && value.held.deactivationNumber === count);
  const release = async (count, status) => {
    const response = await requestJson(http.RequestMethod.POST, '/__task15/release', {
      nonce: config.nonce, deactivationNumber: count, status
    });
    if (response.released !== count || response.status !== status) {
      throw new Error('Task15 provider released the wrong request');
    }
    return response;
  };

  const globalNodes = async type => await driver.findComponents(ON.type(type)) || [];
  const globalTextNode = async (text, partial = false) => {
    const matches = [];
    for (const node of await globalNodes('Text')) {
      const value = await node.getText();
      if (partial ? value.includes(text) : value === text) matches.push({ node, text: value });
    }
    if (matches.length > 1) throw new Error('Ambiguous system UI text: ' + text);
    return matches[0];
  };
  const globalCertificateListNode = async () => {
    const matches = [];
    for (const node of await globalNodes('Text')) {
      if (await node.getText() === certificateName) matches.push(node);
    }
    // The certificate manager renders the self-signed subject and issuer in
    // the same list item. The nonce makes this pair evaluator-run-specific.
    if (matches.length !== 2) throw new Error('Expected one self-signed certificate list item');
    return matches[0];
  };
  const globalButton = async text => {
    const matches = [];
    for (const node of await globalNodes('Button')) {
      if (await node.getText() === text) matches.push(node);
    }
    if (matches.length > 1) throw new Error('Ambiguous system UI button: ' + text);
    return matches[0];
  };
  const globalButtonById = async id => {
    const matches = [];
    for (const node of await globalNodes('Button')) {
      if (await node.getId() === id) matches.push(node);
    }
    if (matches.length > 1) throw new Error('Ambiguous system UI button id: ' + id);
    return matches[0];
  };
  const clickSystemText = async (label, partial = false) => {
    const item = await waitFor('system text ' + label, () => globalTextNode(label, partial), value => !!value);
    await item.node.click();
  };
  const clickSystemCertificateListItem = async () => {
    const node = await waitFor('system certificate list item', globalCertificateListNode, value => !!value);
    await node.click();
  };
  const clickSystemButton = async label => {
    const node = await waitFor('system button ' + label, () => globalButton(label), value => !!value);
    if (!await node.isEnabled()) throw new Error('System UI button disabled: ' + label);
    await node.click();
  };
  const clickSystemButtonById = async id => {
    const node = await waitFor('system button id ' + id, () => globalButtonById(id), value => !!value);
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
      if (details && details.certInfo && equalBytes(details.certInfo.cert, certificateBytes)) {
        return { querySucceeded: true, uri: item.uri, state: item.state,
          alias: item.certAlias, subjectName: item.subjectName, bytesMatch: true };
      }
    }
    return { querySucceeded: true, absent: true, count: list.length };
  };
  const startCertificateManager = async want => {
    if (!candidateAbility || !candidateAbility.context) throw new Error('Candidate UIAbility context unavailable');
    await candidateAbility.context.startAbility({ bundleName: 'com.ohos.certmanager', moduleName: 'phone',
      abilityName: 'MainAbility', ...want });
  };
  const openUserCertificates = async () => {
    await startCertificateManager({});
    await clickSystemText('CA certificates');
    await clickSystemText('User');
  };
  const enableCertificate = async installed => {
    if (installed.state === true) return installed;
    await openUserCertificates();
    await clickSystemCertificateListItem();
    const toggles = [...await globalNodes('Toggle'), ...await globalNodes('Switch')];
    if (toggles.length !== 1) throw new Error('Expected one user certificate enable toggle');
    await toggles[0].click();
    await clickSystemButton('Continue');
    return waitFor('user CA enabled', queryCertificate, value => value.bytesMatch === true && value.state === true);
  };
  const returnToCandidate = async tools => {
    await abilityDelegator.startAbility({ bundleName: tools.bundleName, abilityName: 'EntryAbility', moduleName: 'entry' });
    await waitFor('candidate signed-out form after certificate UI',
      () => tools.inspect('account_homeserver', [ON.id('account_homeserver')]),
      value => value.present && value.visible && value.enabled);
  };

  const installCertificate = async tools => {
    certificateBytes = await resourceContext.resourceManager.getRawFileContent('task15-ca.der');
    candidateAbility = await abilityDelegator.getCurrentTopAbility();
    if (candidateAbility.context?.abilityInfo?.bundleName !== tools.bundleName) {
      throw new Error('Certificate setup did not capture the original candidate ability');
    }
    certificateFile = context.cacheDir + '/task15-ca-' + config.nonce + '.der';
    const file = fs.openSync(certificateFile, fs.OpenMode.CREATE | fs.OpenMode.WRITE_ONLY | fs.OpenMode.TRUNC);
    try {
      const written = fs.writeSync(file.fd, certificateBytes.buffer);
      if (written !== certificateBytes.length) throw new Error('Incomplete evaluator CA file write');
    } finally {
      fs.closeSync(file.fd);
    }
    const uri = fileUri.getUriFromPath(certificateFile);
    await startCertificateManager({ action: wantConstant.Action.ACTION_VIEW_DATA, uri,
      type: 'com.ohos.certmanager.der', flags: wantConstant.Flags.FLAG_AUTH_READ_URI_PERMISSION });
    await clickSystemButton('Install');
    await waitFor('certificate install confirmation', () => globalTextNode('Install certificate'), value => !!value);
    await clickSystemButtonById('advanced_dialog_button_1');
    const installed = await waitFor('user CA installed', queryCertificate, value => value.bytesMatch === true);
    const enabled = await enableCertificate(installed);
    certificateUri = enabled.uri;
    result.certificate = { installed: true, uninstalled: false, uriPresent: true,
      bytesMatch: enabled.bytesMatch, trustEnabled: enabled.state === true,
      method: 'system_file_open_ui_with_read_uri_grant', subjectMatched: String(enabled.subjectName).includes(certificateName) };
    checkpoint('certificate_installed_and_enabled', { bytesMatch: result.certificate.bytesMatch,
      trustEnabled: result.certificate.trustEnabled, subjectMatched: result.certificate.subjectMatched });
    await returnToCandidate(tools);
  };

  const uninstallCertificate = async () => {
    if (!certificateBytes) return;
    const before = await queryCertificate();
    if (before.bytesMatch) {
      certificateUri = before.uri;
      await openUserCertificates();
      await clickSystemCertificateListItem();
      await clickSystemButton('Delete certificate');
      await waitFor('certificate delete confirmation', () => globalTextNode('Delete certificate'), value => !!value);
      await clickSystemButtonById('advanced_dialog_button_1');
    }
    const after = await waitFor('user CA removed', queryCertificate,
      value => value.querySucceeded === true && value.absent === true);
    result.certificate.uninstalled = before.bytesMatch === true;
    result.certificate.cleanupConfirmed = after.absent === true;
    result.certificate.absenceQuerySucceeded = after.querySucceeded === true;
    if (certificateFile) fs.unlinkSync(certificateFile);
  };

  const input = async (tools, name, selectors, value, evidence) => {
    const node = await tools.find(selectors);
    const control = await tools.inspect(name, selectors);
    if (!node || !control.visible || !control.enabled) {
      throw new Error('Task15 login control unavailable: ' + name + ': ' + JSON.stringify(control));
    }
    await tools.receipt('input', name, () => node.inputText(value), evidence);
  };
  const ui = tools => ({
    clientCallback: tools.binding?.apiShape === 'clientCallback',
    entryId: tools.binding?.entryId || 'deactivate_account_entry',
    confirmationText: tools.binding?.confirmationText || 'Are you sure you want to deactivate this account?',
    confirmText: tools.binding?.confirmText || 'Confirm deactivation',
    loadingId: tools.binding?.loadingId || 'deactivation_loading_dialog',
    failureId: tools.binding?.failureId
  });

  return {
    async prepare(tools) {
      const homeserver = [ON.id('account_homeserver')];
      const user = [ON.id('account_user')];
      const password = [ON.id('account_password')];
      const signIn = [ON.id('account_sign_in')];
      await waitFor('signed-out login form', () => tools.inspect('account_homeserver', homeserver),
        value => value.present && value.visible && value.enabled);
      const entryBeforeLogin = await tools.inspect('deactivation_entry_before_login',
        [ON.id(ui(tools).entryId)]);
      await installCertificate(tools);
      await input(tools, 'account_homeserver', homeserver, config.homeserver, { value: config.homeserver });
      await input(tools, 'account_user', user, loginUser, { value: loginUser });
      await input(tools, 'account_password', password, loginPassword,
        { valueSha256: 'redacted-in-device-evidence', redacted: true });
      await tools.click('account_sign_in', signIn);
      const signedIn = await waitFor('native signed-in session', async () => {
        const session = await tools.inspect('account_session_user', [ON.id('account_session_user')]);
        const entry = await tools.inspect('deactivation_entry', [ON.id(ui(tools).entryId)]);
        return { session, entry };
      }, value => value.session.visible && value.session.text === expectedUserId &&
        value.entry.visible && value.entry.enabled);
      const provider = await waitFor('provider login transcript', serverStatus,
        value => value.nonce === config.nonce && value.loginCount === 1);
      result.login = checkpoint('login_complete', {
        expectedUserId,
        expectedDeviceId,
        sessionText: signedIn.session.text,
        entryVisible: signedIn.entry.visible,
        entryHiddenBeforeLogin: entryBeforeLogin.present === false,
        entryInspector: tools.inspectRaw(ui(tools).entryId),
        providerLoginCount: provider.loginCount,
        loginPasswordRedacted: true
      });
    },

    async continueSequence(tools) {
      const observer = tools.observer;
      if (!observer || !observer.read().available) throw new Error('Original Task15 observer unavailable');
      const first = observer.read();
      result.firstSubmit = checkpoint('first_submit_confirmation', {
        action: first.action,
        logicalServiceCalls: first.serviceCalls.length,
        accountSessionActive: first.accountSessionActive,
        confirmationVisible: (await tools.inspect('confirmation',
          [ON.text(ui(tools).confirmationText)])).visible
      });

      await tools.click('confirm', [ON.type('Button').text(ui(tools).confirmText)]);
      const heldOne = await waitHeld(1);
      const loadingOne = await waitFor('first loading modal', async () => ({
        modal: await tools.inspect('loadingModal', [ON.id(ui(tools).loadingId)]),
        presenter: observer.read()
      }), value => value.modal.visible && value.presenter.action === 'loading' &&
        value.presenter.serviceCalls.length === 1);
      const passwordNode = await tools.find([ON.id('deactivation_password')]);
      let inputError = '';
      try { await passwordNode.inputText('tampered'); } catch (error) { inputError = String(error); }
      const afterBlockedInput = observer.read();
      result.pending = checkpoint('pending_modal_and_input_routing', {
        providerHeld: heldOne.held,
        action: loadingOne.presenter.action,
        modalVisible: loadingOne.modal.visible,
        logicalServiceCalls: loadingOne.presenter.serviceCalls.length,
        inputAttempted: true,
        inputError,
        passwordAfterInputAttempt: afterBlockedInput.password,
        eraseDataAfterInputAttempt: afterBlockedInput.eraseData,
        accountSessionActive: afterBlockedInput.accountSessionActive
      });

      await release(1, 401);
      const heldTwo = await waitHeld(2);
      result.uiaRetry = checkpoint('uia_password_attempt_held', {
        providerHeld: heldTwo.held,
        action: observer.read().action,
        logicalServiceCalls: observer.read().serviceCalls.length
      });
      await release(2, 503);
      const failure = await waitFor('native failure state', async () => ({
        error: await tools.inspect('failure_message', ui(tools).failureId ? [ON.id(ui(tools).failureId)] :
          [ON.text('Account deactivation failed. Check your password and retry.')]),
        retry: await tools.inspect('retry', [ON.type('Button').text('Retry')]),
        modal: await tools.inspect('loadingModal', [ON.id(ui(tools).loadingId)]),
        presenter: observer.read()
      }), value => value.error.visible && value.retry.visible && value.retry.enabled &&
        !value.modal.visible && value.presenter.action === 'failure');
      result.failure = checkpoint('failure_preserves_session_and_form', {
        action: failure.presenter.action,
        password: failure.presenter.password,
        eraseData: failure.presenter.eraseData,
        accountSessionActive: failure.presenter.accountSessionActive,
        logicalServiceCalls: failure.presenter.serviceCalls.length,
        retryVisible: failure.retry.visible,
        loadingModalVisible: failure.modal.visible
      });

      await tools.click('retry', [ON.type('Button').text('Retry')]);
      const heldThree = await waitHeld(3);
      const retryLoading = await waitFor('retry loading modal', async () => ({
        modal: await tools.inspect('loadingModal', [ON.id(ui(tools).loadingId)]),
        presenter: observer.read()
      }), value => value.modal.visible && value.presenter.action === 'loading' &&
        value.presenter.serviceCalls.length === 2);
      result.retry = checkpoint('retry_bypasses_confirmation', {
        providerHeld: heldThree.held,
        action: retryLoading.presenter.action,
        modalVisible: retryLoading.modal.visible,
        logicalServiceCalls: retryLoading.presenter.serviceCalls.length,
        password: retryLoading.presenter.password,
        eraseData: retryLoading.presenter.eraseData,
        confirmationVisible: (await tools.inspect('confirmation',
          [ON.text(ui(tools).confirmationText)])).visible
      });
      await release(3, 401);
      const heldFour = await waitHeld(4);
      result.retryUia = checkpoint('retry_uia_password_attempt_held', {
        providerHeld: heldFour.held,
        action: observer.read().action,
        logicalServiceCalls: observer.read().serviceCalls.length
      });
      await release(4, 200);

      const success = await waitFor('native deactivation success', async () => ({
        success: await tools.inspect('success', [ON.text('Account deactivated')]),
        back: await tools.inspect('back', [ON.type('Button').text('Back to settings')]),
        signedOutForm: await tools.inspect('signed_out_form', [ON.id('account_homeserver')]),
        session: await tools.inspect('session', [ON.id('account_session_user')]),
        modal: await tools.inspect('loadingModal', [ON.id(ui(tools).loadingId)]),
        presenter: observer.read()
      }), value => !value.modal.visible && value.presenter.action === 'success' &&
        (ui(tools).clientCallback ? value.signedOutForm.visible && !value.session.present :
          value.success.visible && value.back.visible && value.back.enabled));

      const alias = new util.TextEncoder().encode('element.account.session.v1');
      const query = new Map();
      query.set(asset.Tag.ALIAS, alias);
      query.set(asset.Tag.RETURN_TYPE, asset.ReturnType.ALL);
      query.set(asset.Tag.RETURN_LIMIT, 1);
      let assetAbsent = false, assetErrorCode;
      try { await asset.query(query); }
      catch (error) { assetErrorCode = error.code; assetAbsent = error.code === 24000002; }
      const sessionPath = root => root + '/account-sessions/' + encodeURIComponent(expectedUserId) + '/' +
        encodeURIComponent(expectedDeviceId);
      const filesAbsent = !(await fs.access(sessionPath(context.filesDir)));
      const cacheAbsent = !(await fs.access(sessionPath(context.cacheDir)));
      const nativeModule = await import('@bundle:' + tools.bundleName + '/entry/ets/services/NativeAccountClient');
      const reopened = nativeModule.createAccountClient(context);
      await reopened.restore();
      const freshRestoreSignedOut = reopened.userId() === '' && reopened.needsCleanup() === false;
      result.success = checkpoint('success_cleanup_and_fresh_restore', {
        action: success.presenter.action,
        logicalServiceCalls: success.presenter.serviceCalls.length,
        accountSessionActive: success.presenter.accountSessionActive,
        loadingModalVisible: success.modal.visible,
        assetAbsent,
        assetErrorCode,
        filesAbsent,
        cacheAbsent,
        freshRestoreSignedOut
      });

      if (!ui(tools).clientCallback) await tools.click('back_to_settings', [ON.type('Button').text('Back to settings')]);
      const restoredUi = await waitFor('fresh signed-out settings UI', async () => ({
        homeserver: await tools.inspect('account_homeserver', [ON.id('account_homeserver')]),
        session: await tools.inspect('account_session_user', [ON.id('account_session_user')])
      }), value => value.homeserver.visible && !value.session.present);
      const finalProvider = await serverStatus();
      result.restoration = checkpoint('signed_out_ui_and_provider_complete', {
        signedOutFormVisible: restoredUi.homeserver.visible,
        sessionControlAbsent: !restoredUi.session.present,
        loginCount: finalProvider.loginCount,
        deactivationCount: finalProvider.deactivationCount,
        held: finalProvider.held
      });
      return result;
    },

    async cleanup() {
      try {
        await uninstallCertificate();
      } catch (error) {
        result.certificate.cleanupError = String(error);
        throw error;
      }
      return { certificate: result.certificate, checkpoints: result.checkpoints.length };
    },

    evidence() {
      return result;
    }
  };
}
