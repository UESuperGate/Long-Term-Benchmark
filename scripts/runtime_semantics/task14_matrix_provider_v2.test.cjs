'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const https = require('node:https');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { generateCertificates, createProvider } = require('./task14_matrix_provider_v2.cjs');

function request(provider, pathname, options = {}) {
  return new Promise((resolve, reject) => {
    const request = https.request(provider.baseUrl + pathname, {
      method: options.method || 'GET', rejectUnauthorized: false,
      headers: { 'content-type': 'application/json', ...(options.headers || {}) }
    }, response => {
      const chunks = [];
      response.on('data', chunk => chunks.push(chunk));
      response.on('end', () => resolve({ status: response.statusCode,
        body: JSON.parse(Buffer.concat(chunks).toString('utf8')) }));
    });
    request.on('error', reject);
    if (options.body) request.write(JSON.stringify(options.body));
    request.end();
  });
}

test('public alias lookup is admitted only after the nonce episode login', async t => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'task14-provider-v2-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const nonce = '1234567890abcdef1234567890abcdef';
  const certificates = await generateCertificates(path.join(directory, 'certificates'), nonce);
  const provider = createProvider(certificates, nonce, { cases: [{
    caseId: 'case', alias: '#team:example.org', behavior: 'success',
    roomId: '!team:example.org', servers: ['example.org']
  }] });
  await provider.listen();
  t.after(() => provider.close());
  const alias = '/_matrix/client/v3/directory/room/' + encodeURIComponent('#team:example.org');
  assert.equal((await request(provider, alias)).status, 401);
  const login = await request(provider, '/_matrix/client/v3/login', { method: 'POST', body: {
    type: 'm.login.password', identifier: { type: 'm.id.user', user: provider.expected.username },
    password: provider.expected.password
  } });
  assert.equal(login.status, 200);
  const resolved = await request(provider, alias);
  assert.equal(resolved.status, 200);
  assert.deepEqual(resolved.body, { room_id: '!team:example.org', servers: ['example.org'] });
  const record = provider.state.requests.find(item => item.kind === 'resolve_room_alias' && item.outcome === 'success');
  assert.deepEqual(record.directoryAdmission, {
    mode: 'tls_after_valid_login', admitted: true, successfulLoginSequence: 2
  });
});
