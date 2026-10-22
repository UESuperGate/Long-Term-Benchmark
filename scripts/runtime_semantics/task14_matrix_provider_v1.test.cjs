'use strict';

const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const https = require('node:https');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { generateCertificates, createProvider } = require('./task14_matrix_provider_v1.cjs');

function request(baseUrl, pathname, options = {}) {
  const url = new URL(pathname, baseUrl);
  const bytes = options.body === undefined ? null : Buffer.from(JSON.stringify(options.body));
  return new Promise((resolve, reject) => {
    const req = https.request(url, {
      method: options.method || 'GET',
      rejectUnauthorized: false,
      headers: {
        ...(bytes ? { 'content-type': 'application/json', 'content-length': bytes.length } : {}),
        ...(options.headers || {})
      }
    }, response => {
      const chunks = [];
      response.on('data', chunk => chunks.push(chunk));
      response.on('end', () => {
        const raw = Buffer.concat(chunks).toString('utf8');
        resolve({
          status: response.statusCode,
          body: raw ? JSON.parse(raw) : null,
          peerCertificate: response.socket.getPeerCertificate()
        });
      });
    });
    req.once('error', reject);
    if (bytes) req.end(bytes);
    else req.end();
  });
}

function bearer(provider) {
  return { authorization: `Bearer ${provider.expected.accessToken}` };
}

async function fixture(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'task14-provider-v1-'));
  const nonce = `task14-test-${crypto.randomBytes(12).toString('hex')}`;
  const commands = [];
  const certificates = await generateCertificates(directory, nonce, commands);
  const provider = createProvider(certificates, nonce, {
    credentials: { username: 'alice', password: 'correct horse battery staple' },
    cases: [
      { caseId: 'success', alias: '#success:task14.test', behavior: 'success',
        roomId: '!success:task14.test', servers: ['via-b.test:8448', 'via-a.test', 'via-b.test:8448'],
        preview: { name: 'Success room', joinedMembers: 7 } },
      { caseId: 'missing', alias: '#missing:task14.test', behavior: 'not_found' },
      { caseId: 'held', alias: '#held:task14.test', behavior: 'held', releaseBehavior: 'success',
        roomId: '!held:task14.test', servers: ['held-via.test'] }
    ]
  });
  await provider.listen();
  t.after(async () => {
    await provider.close();
    fs.rmSync(directory, { recursive: true, force: true });
  });
  return { directory, nonce, commands, certificates, provider };
}

test('generates a nonce-bound short-lived CA and localhost server certificate with both SANs', async t => {
  const { nonce, commands, certificates } = await fixture(t);
  assert.equal(commands.length, 7);
  assert.ok(commands.every(command => command.exitCode === 0 && command.executable === '/usr/bin/openssl'));
  const parsed = new crypto.X509Certificate(fs.readFileSync(certificates.serverPem));
  const parsedCA = new crypto.X509Certificate(fs.readFileSync(certificates.caPem));
  assert.equal(parsedCA.subject, 'CN=LTB Task14 ' + nonce);
  assert.equal(parsed.checkIP('127.0.0.1'), '127.0.0.1');
  assert.equal(parsed.checkHost('localhost'), 'localhost');
  assert.match(parsed.subjectAltName, /IP Address:127\.0\.0\.1/);
  assert.match(parsed.subjectAltName, /DNS:localhost/);
  const lifetime = new Date(parsed.validTo).getTime() - new Date(parsed.validFrom).getTime();
  assert.ok(lifetime > 0 && lifetime <= 3 * 24 * 60 * 60 * 1000, `unexpected certificate lifetime ${lifetime}`);
});

test('serves strict Matrix login, success/not-found/held cases, preview/sync, and a nonce-bound transcript', async t => {
  const { nonce, provider } = await fixture(t);
  const wellKnown = await request(provider.baseUrl, '/.well-known/matrix/client');
  assert.equal(wellKnown.status, 200);
  assert.equal(wellKnown.body['m.homeserver'].base_url, provider.baseUrl);
  assert.match(wellKnown.peerCertificate.subjectaltname, /IP Address:127\.0\.0\.1/);

  const versions = await request(provider.baseUrl, '/_matrix/client/versions');
  assert.equal(versions.status, 200);
  assert.ok(versions.body.versions.includes('v1.11'));

  const wrongUser = await request(provider.baseUrl, '/_matrix/client/v3/login', {
    method: 'POST',
    body: { type: 'm.login.password', identifier: { type: 'm.id.user', user: 'mallory' },
      password: provider.expected.password }
  });
  assert.equal(wrongUser.status, 403);
  const wrongPassword = await request(provider.baseUrl, '/_matrix/client/v3/login', {
    method: 'POST',
    body: { type: 'm.login.password', identifier: { type: 'm.id.user', user: provider.expected.username },
      password: 'wrong password' }
  });
  assert.equal(wrongPassword.status, 403);
  const login = await request(provider.baseUrl, '/_matrix/client/v3/login', {
    method: 'POST',
    body: { type: 'm.login.password', identifier: { type: 'm.id.user', user: provider.expected.username },
      password: provider.expected.password }
  });
  assert.equal(login.status, 200);
  assert.equal(login.body.access_token, provider.expected.accessToken);

  const successPath = '/_matrix/client/v3/directory/room/' + encodeURIComponent('#success:task14.test');
  const unauthorized = await request(provider.baseUrl, successPath);
  assert.equal(unauthorized.status, 401);
  assert.equal(unauthorized.body.errcode, 'M_UNKNOWN_TOKEN');
  const success = await request(provider.baseUrl, successPath, { headers: bearer(provider) });
  assert.equal(success.status, 200);
  assert.deepEqual(success.body, {
    room_id: '!success:task14.test',
    servers: ['via-b.test:8448', 'via-a.test', 'via-b.test:8448']
  });
  const missing = await request(provider.baseUrl,
    '/_matrix/client/v3/directory/room/' + encodeURIComponent('#missing:task14.test'), { headers: bearer(provider) });
  assert.equal(missing.status, 404);
  assert.equal(missing.body.errcode, 'M_NOT_FOUND');

  const heldPromise = request(provider.baseUrl,
    '/_matrix/client/v3/directory/room/' + encodeURIComponent('#held:task14.test'), { headers: bearer(provider) });
  await new Promise(resolve => setTimeout(resolve, 40));
  const rejectedStatus = await request(provider.baseUrl, `/__task14/status?nonce=${encodeURIComponent(nonce)}`, {
    headers: { 'x-task14-nonce': 'wrong' }
  });
  assert.equal(rejectedStatus.status, 403);
  const status = await request(provider.baseUrl, `/__task14/status?nonce=${encodeURIComponent(nonce)}`, {
    headers: { 'x-task14-nonce': nonce }
  });
  assert.equal(status.status, 200);
  assert.equal(status.body.held.length, 1);
  assert.equal(status.body.held[0].caseId, 'held');
  assert.equal(status.body.held[0].alias, '#held:task14.test');
  let heldCompleted = false;
  heldPromise.then(() => { heldCompleted = true; });
  await new Promise(resolve => setTimeout(resolve, 20));
  assert.equal(heldCompleted, false);

  const rejectedRelease = await request(provider.baseUrl, '/__task14/release', {
    method: 'POST', headers: { 'x-task14-nonce': 'wrong' },
    body: { nonce: 'wrong', caseId: 'held', requestSequence: status.body.held[0].requestSequence }
  });
  assert.equal(rejectedRelease.status, 403);
  const release = await request(provider.baseUrl, '/__task14/release', {
    method: 'POST', headers: { 'x-task14-nonce': nonce },
    body: { nonce, caseId: 'held', requestSequence: status.body.held[0].requestSequence }
  });
  assert.equal(release.status, 200);
  const heldResult = await heldPromise;
  assert.equal(heldResult.status, 200);
  assert.deepEqual(heldResult.body, { room_id: '!held:task14.test', servers: ['held-via.test'] });

  const sync = await request(provider.baseUrl, '/_matrix/client/v3/sync?timeout=0', { headers: bearer(provider) });
  assert.equal(sync.status, 200);
  assert.equal(typeof sync.body.next_batch, 'string');
  assert.deepEqual(sync.body.rooms, { join: {}, invite: {}, leave: {} });
  const preview = await request(provider.baseUrl,
    '/_matrix/client/v1/room_summary/' + encodeURIComponent('!success:task14.test'), { headers: bearer(provider) });
  assert.equal(preview.status, 200);
  assert.equal(preview.body.room_id, '!success:task14.test');
  assert.equal(preview.body.name, 'Success room');
  assert.equal(preview.body.num_joined_members, 7);

  const production = provider.state.requests.filter(item => item.kind === 'resolve_room_alias');
  assert.equal(production.length, 4);
  assert.deepEqual(production.map(item => item.outcome), ['unauthorized', 'success', 'not_found', 'success']);
  assert.ok(production.every(item => item.providerNonce === nonce));
  assert.ok(production.every(item => item.bindingSha256.length === 64));
  assert.ok(production.every(item => item.tls.encrypted && item.tls.protocol && item.tls.cipher?.name));
  assert.ok(production.every(item => item.method === 'GET' && item.path.includes('/directory/room/')));
  assert.equal(production[0].auth.valid, false);
  assert.ok(production.slice(1).every(item => item.auth.valid && item.auth.tokenSha256.length === 64));
  assert.ok(production.every(item => item.body === null && item.bodySha256.length === 64));
  assert.ok(production.every(item => item.timestamps.receivedAt && item.timestamps.responseStartedAt));
  assert.ok(production.every(item => item.timestamps.responseFinishedAt));
  const heldRecord = production.find(item => item.caseId === 'held');
  assert.equal(typeof heldRecord.releasedBySequence, 'number');
  assert.ok(heldRecord.timestamps.releasedAt);
  const loginRecords = provider.state.requests.filter(item => item.path === '/_matrix/client/v3/login');
  assert.equal(loginRecords.length, 3);
  assert.deepEqual(loginRecords.map(item => item.login.valid), [false, false, true]);
  assert.ok(loginRecords.every(item => item.body.identifier.user));
  assert.ok(loginRecords.every(item => item.body.password.redacted && item.body.password.sha256.length === 64));
  assert.deepEqual(provider.state.controls.filter(item => item.kind === 'status').map(item => item.validNonce), [false, true]);
  assert.deepEqual(provider.state.controls.filter(item => item.kind === 'release').map(item => item.validNonce), [false, true]);
});
