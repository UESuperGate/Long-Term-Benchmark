'use strict';

const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const https = require('node:https');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const test = require('node:test');

const hostScript = path.join(__dirname, 'task14_matrix_provider_host_v1.cjs');

function startHost(controlDir, caseConfig) {
  const child = spawn(process.execPath, [hostScript, '--control-dir', controlDir, '--case-config', caseConfig], {
    cwd: path.resolve(__dirname, '../..'),
    stdio: ['ignore', 'pipe', 'pipe']
  });
  const stdout = [];
  const stderr = [];
  child.stdout.on('data', chunk => stdout.push(chunk));
  child.stderr.on('data', chunk => stderr.push(chunk));
  const exited = new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('exit', (code, signal) => resolve({
      code,
      signal,
      stdout: Buffer.concat(stdout).toString('utf8'),
      stderr: Buffer.concat(stderr).toString('utf8')
    }));
  });
  return { child, exited };
}

async function waitForFile(file, processHandle, timeout = 10000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (fs.existsSync(file)) return JSON.parse(fs.readFileSync(file, 'utf8'));
    if (processHandle.child.exitCode !== null) {
      const result = await processHandle.exited;
      throw new Error(`Host exited before ${path.basename(file)}: ${JSON.stringify(result)}`);
    }
    await new Promise(resolve => setTimeout(resolve, 20));
  }
  throw new Error(`Timed out waiting for ${file}`);
}

function request(baseUrl, pathname, options = {}) {
  const bytes = options.body === undefined ? null : Buffer.from(JSON.stringify(options.body));
  return new Promise((resolve, reject) => {
    const req = https.request(new URL(pathname, baseUrl), {
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
        resolve({ status: response.statusCode, body: raw ? JSON.parse(raw) : null });
      });
    });
    req.once('error', reject);
    req.end(bytes || undefined);
  });
}

function allFileContents(directory) {
  const contents = [];
  const visit = current => {
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const absolute = path.join(current, entry.name);
      if (entry.isDirectory()) visit(absolute);
      else contents.push({ file: absolute, bytes: fs.readFileSync(absolute) });
    }
  };
  visit(directory);
  return contents;
}

test('child host logs in, holds/releases a case, terminates cleanly, redacts secrets, and removes certificate debris', async t => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'task14-provider-host-v1-'));
  const controlDir = path.join(temporary, 'control');
  const caseConfig = path.join(temporary, 'cases.json');
  const nonce = '0123456789abcdef0123456789abcdef';
  fs.writeFileSync(caseConfig, JSON.stringify({
    nonce,
    cases: [{
      caseId: 'held-case',
      alias: '#held:task14.test',
      behavior: 'held',
      releaseBehavior: 'success',
      roomId: '!held:task14.test',
      servers: ['via.task14.test']
    }]
  }));
  const host = startHost(controlDir, caseConfig);
  t.after(async () => {
    if (host.child.exitCode === null) host.child.kill('SIGKILL');
    await host.exited.catch(() => {});
    fs.rmSync(temporary, { recursive: true, force: true });
  });

  const ready = await waitForFile(path.join(controlDir, 'ready.json'), host);
  assert.equal(ready.nonce, nonce);
  assert.match(ready.baseUrl, /^https:\/\/127\.0\.0\.1:\d+$/);
  assert.equal(ready.port, Number(new URL(ready.baseUrl).port));
  assert.equal(ready.caDer, path.join(controlDir, 'certificates', 'ca.der'));
  assert.equal(crypto.createHash('sha256').update(fs.readFileSync(ready.caDer)).digest('hex'), ready.caSha256);
  assert.deepEqual(fs.readdirSync(path.join(controlDir, 'certificates')).sort(), ['ca.der', 'ca.pem', 'server.pem']);
  assert.deepEqual(fs.readdirSync(controlDir).sort(), ['certificate-audit.json', 'certificates', 'ready.json']);

  const username = `task14_${nonce.slice(0, 12)}`;
  const password = `task14-login-${nonce}`;
  const token = `task14-token-${nonce}`;
  const login = await request(ready.baseUrl, '/_matrix/client/v3/login', {
    method: 'POST',
    body: { type: 'm.login.password', identifier: { type: 'm.id.user', user: username }, password }
  });
  assert.equal(login.status, 200);
  assert.equal(login.body.user_id, `@task14_${nonce.slice(0, 12)}:task14.test`);
  assert.equal(login.body.access_token, token);

  const heldRequest = request(ready.baseUrl,
    '/_matrix/client/v3/directory/room/' + encodeURIComponent('#held:task14.test'), {
      headers: { authorization: `Bearer ${token}` }
    });
  await new Promise(resolve => setTimeout(resolve, 40));
  const status = await request(ready.baseUrl, `/__task14/status?nonce=${nonce}`, {
    headers: { 'x-task14-nonce': nonce }
  });
  assert.equal(status.status, 200);
  assert.deepEqual(status.body.held.map(item => item.caseId), ['held-case']);
  let completed = false;
  heldRequest.then(() => { completed = true; });
  await new Promise(resolve => setTimeout(resolve, 20));
  assert.equal(completed, false);
  const release = await request(ready.baseUrl, '/__task14/release', {
    method: 'POST',
    headers: { 'x-task14-nonce': nonce },
    body: { nonce, caseId: 'held-case', requestSequence: status.body.held[0].requestSequence }
  });
  assert.equal(release.status, 200);
  const resolved = await heldRequest;
  assert.equal(resolved.status, 200);
  assert.deepEqual(resolved.body, { room_id: '!held:task14.test', servers: ['via.task14.test'] });

  assert.equal(host.child.kill('SIGTERM'), true);
  const exit = await host.exited;
  assert.equal(exit.code, 0, exit.stderr);
  assert.equal(exit.signal, null);
  const transcript = JSON.parse(fs.readFileSync(path.join(controlDir, 'transcript.json'), 'utf8'));
  const stopped = JSON.parse(fs.readFileSync(path.join(controlDir, 'stopped.json'), 'utf8'));
  assert.equal(stopped.signal, 'SIGTERM');
  assert.equal(stopped.transcriptSha256,
    crypto.createHash('sha256').update(fs.readFileSync(path.join(controlDir, 'transcript.json'))).digest('hex'));
  assert.deepEqual(stopped.retainedCertificates, ['ca.der', 'ca.pem', 'server.pem']);
  assert.ok(transcript.requests.some(item => item.outcome === 'login'));
  assert.ok(transcript.requests.some(item => item.caseId === 'held-case' && item.outcome === 'success'));
  assert.ok(transcript.controls.some(item => item.kind === 'release' && item.accepted));
  assert.equal(transcript.requests.find(item => item.outcome === 'login').body.password.redacted, true);

  const files = allFileContents(controlDir);
  for (const secret of [password, token]) {
    assert.equal(files.some(item => item.bytes.includes(Buffer.from(secret))), false,
      `${secret.slice(0, 12)} leaked into ${files.find(item => item.bytes.includes(Buffer.from(secret)))?.file}`);
  }
  const forbidden = /(?:\.key|\.csr|\.srl|openssl-\d+\.log|\.ext)$/;
  assert.deepEqual(files.filter(item => forbidden.test(item.file)).map(item => item.file), []);
});

test('generates a 32-hex nonce and refuses to overwrite an existing control directory', async t => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'task14-provider-host-nonce-v1-'));
  const controlDir = path.join(temporary, 'control');
  const caseConfig = path.join(temporary, 'cases.json');
  fs.writeFileSync(caseConfig, JSON.stringify({
    cases: [{ caseId: 'success', alias: '#success:task14.test', behavior: 'success' }]
  }));
  const first = startHost(controlDir, caseConfig);
  t.after(async () => {
    if (first.child.exitCode === null) first.child.kill('SIGKILL');
    await first.exited.catch(() => {});
    fs.rmSync(temporary, { recursive: true, force: true });
  });
  const ready = await waitForFile(path.join(controlDir, 'ready.json'), first);
  assert.match(ready.nonce, /^[0-9a-f]{32}$/);
  const readyBefore = fs.readFileSync(path.join(controlDir, 'ready.json'));

  const second = startHost(controlDir, caseConfig);
  const rejected = await second.exited;
  assert.notEqual(rejected.code, 0);
  assert.match(rejected.stderr, /Refusing to overwrite existing Task14 control directory/);
  assert.deepEqual(fs.readFileSync(path.join(controlDir, 'ready.json')), readyBefore);

  first.child.kill('SIGINT');
  const stopped = await first.exited;
  assert.equal(stopped.code, 0, stopped.stderr);
  assert.equal(JSON.parse(fs.readFileSync(path.join(controlDir, 'stopped.json'), 'utf8')).signal, 'SIGINT');
});
