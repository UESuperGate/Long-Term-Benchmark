'use strict';

const crypto = require('node:crypto');
const equal = (left, right) => JSON.stringify(left) === JSON.stringify(right);
const sha256 = value => crypto.createHash('sha256').update(value).digest('hex');

function verifyTask15NativeE2E({ evidence, provider, run }) {
  const checks = [];
  const check = (name, passed, observed) => checks.push({ name, passed: Boolean(passed), observed });
  const nonce = evidence?.nonce;
  check('identity_nonce', /^[a-f0-9]{32}$/.test(nonce || '') && provider?.nonce === nonce && run?.nonce === nonce,
    { evidence: nonce, provider: provider?.nonce, run: run?.nonce });
  check('https_no_downgrade', /^https:\/\/127\.0\.0\.1:[1-9][0-9]{1,4}$/.test(evidence?.homeserver || '') &&
    provider?.protocol === 'https' && provider?.tls?.authorized === true && run?.security?.productionTransportUnchanged === true,
    { homeserver: evidence?.homeserver, protocol: provider?.protocol, tls: provider?.tls, security: run?.security });
  check('certificate_lifecycle', evidence?.certificate?.installed === true && evidence?.certificate?.uninstalled === true &&
    evidence.certificate.cleanupConfirmed === true && evidence.certificate.absenceQuerySucceeded === true &&
    evidence.certificate.bytesMatch === true && evidence.certificate.trustEnabled === true &&
    evidence.certificate.subjectMatched === true &&
    evidence.certificate.method === 'system_file_open_ui_with_read_uri_grant' &&
    /^[a-f0-9]{64}$/.test(evidence?.caSha256 || '') && evidence.caSha256 === provider?.tls?.caSha256,
    { certificate: evidence?.certificate, evidenceCA: evidence?.caSha256, providerCA: provider?.tls?.caSha256 });

  const requests = provider?.requests || [];
  const login = requests.filter(item => item.kind === 'login');
  const deactivation = requests.filter(item => item.kind === 'deactivation');
  check('request_sequence', login.length === 1 && deactivation.length === 4 &&
    equal(deactivation.map(item => item.number), [1, 2, 3, 4]) &&
    equal(deactivation.map(item => item.responseStatus), [401, 503, 401, 200]),
    requests.map(item => ({ kind: item.kind, number: item.number, responseStatus: item.responseStatus })));
  check('login_boundary', login.length === 1 && login[0].method === 'POST' &&
    login[0].path === '/_matrix/client/v3/login' && login[0].body?.type === 'm.login.password' &&
    login[0].body?.passwordSha256 === sha256('login-' + nonce?.slice(0, 12)) && login[0].responseStatus === 200,
    login[0]);
  const expectedAuth = [false, true, false, true];
  check('uia_payloads', deactivation.length === 4 && deactivation.every((item, index) =>
    item.method === 'POST' && item.path === '/_matrix/client/v3/account/deactivate' &&
    item.body?.erase === true && item.body?.hasAuth === expectedAuth[index] &&
    (!expectedAuth[index] || (item.body.authType === 'm.login.password' &&
      item.body.passwordSha256 === sha256('secret') && item.body.user === '@alice_' + nonce.slice(0, 8) + ':task15.test' &&
      item.body.session === (index === 1 ? 'uia-initial-' : 'uia-retry-') + nonce.slice(0, 8)))),
    deactivation.map(item => item.body));
  check('authorization_preserved', deactivation.length === 4 &&
    deactivation.every(item => /^[a-f0-9]{64}$/.test(item.authorizationSha256 || '')) &&
    new Set(deactivation.map(item => item.authorizationSha256)).size === 1,
    deactivation.map(item => item.authorizationSha256));

  check('first_submit_zero_io', evidence?.firstSubmit?.action === 'confirming' &&
    evidence.firstSubmit.logicalServiceCalls === 0 && evidence.firstSubmit.confirmationVisible === true &&
    evidence.firstSubmit.accountSessionActive === true, evidence?.firstSubmit);
  check('pending_modal_blocks_input', evidence?.pending?.action === 'loading' && evidence.pending.modalVisible === true &&
    evidence.pending.logicalServiceCalls === 1 && evidence.pending.inputAttempted === true &&
    evidence.pending.passwordAfterInputAttempt === 'secret' && evidence.pending.eraseDataAfterInputAttempt === true &&
    evidence.pending.accountSessionActive === true && evidence.pending.providerHeld?.deactivationNumber === 1,
    evidence?.pending);
  check('failure_preserves_form_session', evidence?.failure?.action === 'failure' &&
    evidence.failure.password === 'secret' && evidence.failure.eraseData === true &&
    evidence.failure.accountSessionActive === true && evidence.failure.logicalServiceCalls === 1 &&
    evidence.failure.retryVisible === true && evidence.failure.loadingModalVisible === false,
    evidence?.failure);
  check('retry_is_real_second_logical_call', evidence?.retry?.action === 'loading' &&
    evidence.retry.logicalServiceCalls === 2 && evidence.retry.modalVisible === true &&
    evidence.retry.confirmationVisible === false && evidence.retry.password === 'secret' &&
    evidence.retry.eraseData === true && evidence.retry.providerHeld?.deactivationNumber === 3,
    evidence?.retry);
  check('success_cleans_native_state', evidence?.success?.action === 'success' &&
    evidence.success.logicalServiceCalls === 2 && evidence.success.accountSessionActive === false &&
    evidence.success.loadingModalVisible === false && evidence.success.assetAbsent === true &&
    evidence.success.assetErrorCode === 24000002 && evidence.success.filesAbsent === true &&
    evidence.success.cacheAbsent === true && evidence.success.freshRestoreSignedOut === true,
    evidence?.success);
  check('signed_out_ui_restored', evidence?.restoration?.signedOutFormVisible === true &&
    evidence.restoration.sessionControlAbsent === true && evidence.restoration.loginCount === 1 &&
    evidence.restoration.deactivationCount === 4 && !evidence.restoration.held,
    evidence?.restoration);

  check('source_hap_command_provenance', run?.productionUnchanged === true && run?.copiedProductionUnchanged === true &&
    Array.isArray(run?.sourceHashes) && run.sourceHashes.length >= 5 &&
    run.sourceHashes.every(item => /^[a-f0-9]{64}$/.test(item.sha256 || '')) &&
    Array.isArray(run?.haps) && run.haps.length === 2 && run.haps.every(item => /^[a-f0-9]{64}$/.test(item.sha256 || '')) &&
    Array.isArray(run?.commands) && run.commands.length > 0 && run.commands.every(item => /^[a-f0-9]{64}$/.test(item.sha256 || '')),
    { sources: run?.sourceHashes?.length, haps: run?.haps, commands: run?.commands });
  check('cleanup_complete', run?.cleanup?.appUninstalled === true && run?.cleanup?.reverseRemoved === true &&
    run?.cleanup?.serverClosed === true && run?.cleanup?.privateKeysRemoved === true &&
    run?.deviceCertificateCleanupConfirmed === true,
    run?.cleanup);

  return {
    schemaVersion: 1,
    status: checks.every(item => item.passed) ? 'passed' : 'failed',
    passed: checks.filter(item => item.passed).length,
    total: checks.length,
    checks
  };
}

module.exports = { verifyTask15NativeE2E };
