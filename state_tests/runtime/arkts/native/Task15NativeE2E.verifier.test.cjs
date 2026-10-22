'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const { verifyTask15NativeE2E } = require('./Task15NativeE2E.verifier.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');

function valid() {
  const nonce = '0123456789abcdef0123456789abcdef';
  const user = '@alice_' + nonce.slice(0, 8) + ':task15.test';
  const auth = hash('Bearer token-' + nonce);
  const request = (number, hasAuth, responseStatus) => ({
    kind: 'deactivation', number, method: 'POST', path: '/_matrix/client/v3/account/deactivate',
    authorizationSha256: auth, responseStatus,
    body: { erase: true, hasAuth, ...(hasAuth ? { authType: 'm.login.password', user,
      passwordSha256: hash('secret'), session: (number === 2 ? 'uia-initial-' : 'uia-retry-') + nonce.slice(0, 8) } : {}) }
  });
  const ca = hash('ca');
  const evidence = {
    nonce, homeserver: 'https://127.0.0.1:19443', caSha256: ca,
    certificate: { installed: true, uninstalled: true, cleanupConfirmed: true,
      absenceQuerySucceeded: true, bytesMatch: true, trustEnabled: true, subjectMatched: true,
      method: 'system_file_open_ui_with_read_uri_grant' },
    firstSubmit: { action: 'confirming', logicalServiceCalls: 0, confirmationVisible: true, accountSessionActive: true },
    pending: { action: 'loading', modalVisible: true, logicalServiceCalls: 1, inputAttempted: true,
      passwordAfterInputAttempt: 'secret', eraseDataAfterInputAttempt: true, accountSessionActive: true,
      providerHeld: { deactivationNumber: 1 } },
    failure: { action: 'failure', password: 'secret', eraseData: true, accountSessionActive: true,
      logicalServiceCalls: 1, retryVisible: true, loadingModalVisible: false },
    retry: { action: 'loading', logicalServiceCalls: 2, modalVisible: true, confirmationVisible: false,
      password: 'secret', eraseData: true, providerHeld: { deactivationNumber: 3 } },
    success: { action: 'success', logicalServiceCalls: 2, accountSessionActive: false,
      loadingModalVisible: false, assetAbsent: true, assetErrorCode: 24000002, filesAbsent: true,
      cacheAbsent: true, freshRestoreSignedOut: true },
    restoration: { signedOutFormVisible: true, sessionControlAbsent: true, loginCount: 1,
      deactivationCount: 4, held: null }
  };
  const provider = { nonce, protocol: 'https', tls: { authorized: true, caSha256: ca }, requests: [
    { kind: 'login', method: 'POST', path: '/_matrix/client/v3/login', responseStatus: 200,
      body: { type: 'm.login.password', passwordSha256: hash('login-' + nonce.slice(0, 12)) } },
    request(1, false, 401), request(2, true, 503), request(3, false, 401), request(4, true, 200)
  ] };
  const run = { nonce, security: { productionTransportUnchanged: true }, productionUnchanged: true,
    copiedProductionUnchanged: true, sourceHashes: Array.from({ length: 5 }, (_, index) => ({ path: String(index), sha256: hash('s' + index) })),
    haps: [0, 1].map(index => ({ path: String(index), sha256: hash('h' + index) })),
    commands: [{ sha256: hash('command') }], cleanup: { appUninstalled: true, reverseRemoved: true,
      serverClosed: true, privateKeysRemoved: true }, deviceCertificateCleanupConfirmed: true };
  return { evidence, provider, run };
}

test('independent verifier accepts a complete native HTTPS transition', () => {
  const report = verifyTask15NativeE2E(valid());
  assert.equal(report.status, 'passed');
  assert.equal(report.passed, report.total);
  assert.ok(report.total >= 14);
});

test('verifier rejects HTTP downgrade, settled modal, payload weakening, retained state and incomplete cleanup', () => {
  const mutations = [
    value => { value.evidence.homeserver = 'http://127.0.0.1:19443'; },
    value => { value.evidence.pending.modalVisible = false; },
    value => { value.evidence.pending.passwordAfterInputAttempt = 'tampered'; },
    value => { value.provider.requests[2].body.erase = false; },
    value => { value.provider.requests[2].body.passwordSha256 = hash('wrong'); },
    value => { value.evidence.failure.accountSessionActive = false; },
    value => { value.evidence.retry.logicalServiceCalls = 1; },
    value => { value.evidence.success.assetAbsent = false; },
    value => { value.evidence.success.freshRestoreSignedOut = false; },
    value => { value.evidence.certificate.uninstalled = false; },
    value => { value.evidence.certificate.bytesMatch = false; },
    value => { value.evidence.certificate.trustEnabled = false; },
    value => { value.run.cleanup.reverseRemoved = false; },
    value => { value.run.sourceHashes[0].sha256 = 'source observer'; }
  ];
  for (const mutate of mutations) {
    const value = structuredClone(valid());
    mutate(value);
    assert.equal(verifyTask15NativeE2E(value).status, 'failed');
  }
});

test('verifier rejects reordered or duplicated production requests', () => {
  for (const mutate of [
    value => value.provider.requests.splice(3, 1),
    value => { value.provider.requests[2].number = 1; },
    value => { value.provider.requests[4].responseStatus = 503; },
    value => { value.provider.requests[1].authorizationSha256 = hash('different'); }
  ]) {
    const value = structuredClone(valid());
    mutate(value);
    assert.equal(verifyTask15NativeE2E(value).status, 'failed');
  }
});
