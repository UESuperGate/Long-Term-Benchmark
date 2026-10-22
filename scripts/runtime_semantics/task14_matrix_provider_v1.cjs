#!/usr/bin/env node
'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const https = require('node:https');
const path = require('node:path');
const { spawn } = require('node:child_process');

const sha256 = value => crypto.createHash('sha256').update(value).digest('hex');
const fileSha256 = file => sha256(fs.readFileSync(file));

function runOpenSsl(args, logFile) {
  return new Promise((resolve, reject) => {
    const child = spawn('/usr/bin/openssl', args, { stdio: ['ignore', 'pipe', 'pipe'] });
    const output = [];
    child.stdout.on('data', chunk => output.push(chunk));
    child.stderr.on('data', chunk => output.push(chunk));
    child.once('error', reject);
    child.once('close', code => {
      const bytes = Buffer.concat(output);
      if (logFile) fs.writeFileSync(logFile, bytes);
      const command = {
        executable: '/usr/bin/openssl',
        args: args.slice(),
        exitCode: code,
        outputSha256: sha256(bytes)
      };
      if (code === 0) resolve(command);
      else reject(Object.assign(new Error(`openssl failed with exit code ${code}`), { command }));
    });
  });
}

async function generateCertificates(directory, nonce, commands = []) {
  if (typeof nonce !== 'string' || nonce.length < 8) throw new TypeError('Task14 provider nonce must be at least 8 characters');
  fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
  const files = {
    caKey: path.join(directory, 'ca.key'),
    caCsr: path.join(directory, 'ca.csr'),
    caPem: path.join(directory, 'ca.pem'),
    caDer: path.join(directory, 'ca.der'),
    serverKey: path.join(directory, 'server.key'),
    serverCsr: path.join(directory, 'server.csr'),
    serverPem: path.join(directory, 'server.pem'),
    caExtensions: path.join(directory, 'ca.ext'),
    serverExtensions: path.join(directory, 'server.ext')
  };
  fs.writeFileSync(files.caExtensions,
    '[v3_ca]\n' +
    'basicConstraints=critical,CA:true,pathlen:0\n' +
    'keyUsage=critical,keyCertSign,cRLSign\n' +
    'subjectKeyIdentifier=hash\n' +
    'authorityKeyIdentifier=keyid:always\n');
  fs.writeFileSync(files.serverExtensions,
    '[v3_server]\n' +
    'basicConstraints=critical,CA:false\n' +
    'keyUsage=critical,digitalSignature,keyEncipherment\n' +
    'extendedKeyUsage=serverAuth\n' +
    'subjectAltName=@alt_names\n' +
    '[alt_names]\n' +
    'IP.1=127.0.0.1\n' +
    'DNS.1=localhost\n');

  const specifications = [
    ['genrsa', '-out', files.caKey, '2048'],
    ['req', '-new', '-key', files.caKey, '-subj', `/CN=LTB Task14 ${nonce}`, '-out', files.caCsr],
    ['x509', '-req', '-in', files.caCsr, '-signkey', files.caKey, '-days', '2', '-sha256',
      '-extfile', files.caExtensions, '-extensions', 'v3_ca', '-out', files.caPem],
    ['genrsa', '-out', files.serverKey, '2048'],
    ['req', '-new', '-key', files.serverKey, '-subj', '/CN=localhost', '-out', files.serverCsr],
    ['x509', '-req', '-in', files.serverCsr, '-CA', files.caPem, '-CAkey', files.caKey, '-CAcreateserial',
      '-days', '2', '-sha256', '-extfile', files.serverExtensions, '-extensions', 'v3_server', '-out', files.serverPem],
    ['x509', '-in', files.caPem, '-outform', 'der', '-out', files.caDer]
  ];
  for (let index = 0; index < specifications.length; index++) {
    const command = await runOpenSsl(specifications[index], path.join(directory, `openssl-${index}.log`));
    commands.push(command);
  }
  fs.chmodSync(files.caKey, 0o600);
  fs.chmodSync(files.serverKey, 0o600);

  const certificate = new crypto.X509Certificate(fs.readFileSync(files.serverPem));
  return {
    ...files,
    caSha256: fileSha256(files.caDer),
    serverSha256: fileSha256(files.serverPem),
    subject: certificate.subject,
    issuer: certificate.issuer,
    subjectAltName: certificate.subjectAltName,
    validFrom: certificate.validFrom,
    validTo: certificate.validTo
  };
}

function clone(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

function safeBody(value, key = '') {
  if (Array.isArray(value)) return value.map(item => safeBody(item));
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([name, item]) => [name, safeBody(item, name)]));
  }
  if (/password|access_?token|refresh_?token/i.test(key)) {
    return { redacted: true, sha256: sha256(String(value ?? '')) };
  }
  return value;
}

function normalizeCase(caseId, config) {
  if (!config || typeof config !== 'object') throw new TypeError(`Task14 case ${caseId} requires a configuration object`);
  const alias = config.alias;
  if (typeof alias !== 'string' || !alias.startsWith('#') || !alias.includes(':')) {
    throw new TypeError(`Task14 case ${caseId} requires a Matrix room alias`);
  }
  const behavior = config.behavior || 'success';
  if (!['success', 'not_found', 'held'].includes(behavior)) throw new TypeError(`Unsupported Task14 behavior: ${behavior}`);
  const result = {
    caseId,
    alias,
    behavior,
    roomId: config.roomId || `!${sha256(caseId).slice(0, 12)}:task14.test`,
    servers: config.servers === undefined ? ['task14.test'] : clone(config.servers),
    preview: {
      name: config.preview?.name || `Task14 ${caseId}`,
      topic: config.preview?.topic ?? null,
      avatarUrl: config.preview?.avatarUrl ?? null,
      joinedMembers: config.preview?.joinedMembers ?? 1,
      joinRule: config.preview?.joinRule || 'public'
    }
  };
  if (!Array.isArray(result.servers) || result.servers.some(server => typeof server !== 'string')) {
    throw new TypeError(`Task14 case ${caseId} servers must be strings`);
  }
  if (behavior === 'held') {
    result.releaseBehavior = config.releaseBehavior || 'success';
    if (!['success', 'not_found'].includes(result.releaseBehavior)) {
      throw new TypeError(`Unsupported Task14 release behavior: ${result.releaseBehavior}`);
    }
  }
  return result;
}

function createProvider(certificates, nonce, options = {}) {
  if (typeof nonce !== 'string' || nonce.length < 8) throw new TypeError('Task14 provider nonce must be at least 8 characters');
  const suffix = sha256(nonce).slice(0, 10);
  const expected = {
    username: options.credentials?.username || `alice_${suffix}`,
    password: options.credentials?.password || `login-${nonce.slice(0, 16)}`,
    userId: options.credentials?.userId || `@alice_${suffix}:task14.test`,
    deviceId: options.credentials?.deviceId || `TASK14_${suffix.toUpperCase()}`,
    accessToken: options.credentials?.accessToken || `task14-token-${nonce}`
  };
  const cases = new Map();
  const held = new Map();
  let sequence = 0;
  let baseUrl;

  const state = {
    schemaVersion: 1,
    provider: 'task14_matrix_provider_v1',
    nonce,
    nonceSha256: sha256(nonce),
    protocol: 'https',
    startedAt: null,
    stoppedAt: null,
    baseUrl: null,
    tls: {
      caSha256: certificates.caSha256 || fileSha256(certificates.caDer),
      serverSha256: certificates.serverSha256 || fileSha256(certificates.serverPem),
      subject: certificates.subject || null,
      issuer: certificates.issuer || null,
      subjectAltName: certificates.subjectAltName || null
    },
    cases: [],
    requests: [],
    controls: []
  };

  function configureCase(caseId, config) {
    if (typeof caseId !== 'string' || !caseId) throw new TypeError('Task14 caseId must be a non-empty string');
    if ([...cases.values()].some(item => item.caseId !== caseId && item.alias === config.alias)) {
      throw new Error(`Task14 alias is already configured: ${config.alias}`);
    }
    const normalized = normalizeCase(caseId, config);
    cases.set(caseId, normalized);
    state.cases = [...cases.values()].map(item => clone(item));
    return clone(normalized);
  }

  if (Array.isArray(options.cases)) {
    for (const config of options.cases) configureCase(config.caseId, config);
  } else if (options.cases && typeof options.cases === 'object') {
    for (const [key, config] of Object.entries(options.cases)) {
      configureCase(config.caseId || key, { ...config, alias: config.alias || (key.startsWith('#') ? key : undefined) });
    }
  }

  function describeAuthorization(request) {
    const value = String(request.headers.authorization || '');
    const [scheme, token = ''] = value.split(/\s+/, 2);
    return {
      present: value.length > 0,
      scheme: scheme || null,
      tokenSha256: token ? sha256(token) : null,
      valid: value === `Bearer ${expected.accessToken}`
    };
  }

  function describeTls(request) {
    const cipher = request.socket.getCipher?.();
    return {
      encrypted: request.socket.encrypted === true,
      protocol: request.socket.getProtocol?.() || null,
      cipher: cipher ? { name: cipher.name, version: cipher.version } : null,
      servername: request.socket.servername || null,
      remoteAddress: request.socket.remoteAddress || null
    };
  }

  function beginRecord(request, url, body) {
    const receivedAt = new Date().toISOString();
    const record = {
      sequence: ++sequence,
      providerNonce: nonce,
      bindingSha256: sha256(`${nonce}\n${sequence}\n${request.method}\n${url.pathname}\n${receivedAt}`),
      method: request.method,
      path: url.pathname,
      query: Object.fromEntries([...url.searchParams.entries()].map(([key, value]) =>
        [key, /token|nonce/i.test(key) ? { redacted: true, sha256: sha256(value) } : value])),
      auth: describeAuthorization(request),
      body: body.parsed === undefined ? null : safeBody(body.parsed),
      bodyBytes: body.bytes.length,
      bodySha256: sha256(body.bytes),
      tls: describeTls(request),
      timestamps: { receivedAt, responseStartedAt: null, responseFinishedAt: null }
    };
    state.requests.push(record);
    return record;
  }

  function reply(record, response, status, body, outcome) {
    const bytes = Buffer.from(JSON.stringify(body));
    record.responseStatus = status;
    record.outcome = outcome || record.outcome || null;
    record.responseBodySha256 = sha256(bytes);
    record.timestamps.responseStartedAt = new Date().toISOString();
    response.once('finish', () => { record.timestamps.responseFinishedAt = new Date().toISOString(); });
    response.writeHead(status, {
      'Content-Type': 'application/json',
      'Content-Length': bytes.length,
      'Cache-Control': 'no-store'
    });
    response.end(bytes);
  }

  function readBody(request) {
    return new Promise((resolve, reject) => {
      const chunks = [];
      let length = 0;
      let settled = false;
      request.on('data', chunk => {
        if (settled) return;
        length += chunk.length;
        if (length > 65536) {
          settled = true;
          reject(new Error('Task14 provider request body exceeds 64 KiB'));
          request.destroy();
          return;
        }
        chunks.push(chunk);
      });
      request.once('end', () => {
        if (settled) return;
        settled = true;
        const bytes = Buffer.concat(chunks);
        if (bytes.length === 0) return resolve({ bytes, parsed: undefined });
        try { resolve({ bytes, parsed: JSON.parse(bytes.toString('utf8')) }); }
        catch (error) { reject(new Error(`Task14 provider received invalid JSON: ${error.message}`)); }
      });
      request.once('error', error => {
        if (!settled) {
          settled = true;
          reject(error);
        }
      });
    });
  }

  function hasProductionAuth(record) {
    return record.tls.encrypted && record.auth.valid;
  }

  function successBody(config) {
    return { room_id: config.roomId, servers: clone(config.servers) };
  }

  function finishAlias(record, response, config, behavior) {
    if (behavior === 'not_found') {
      return reply(record, response, 404, { errcode: 'M_NOT_FOUND', error: 'Room alias not found' }, 'not_found');
    }
    return reply(record, response, 200, successBody(config), 'success');
  }

  function findCaseByAlias(alias) {
    return [...cases.values()].find(item => item.alias === alias);
  }

  function previewFor(roomId) {
    const config = [...cases.values()].find(item => item.roomId === roomId);
    if (!config) return null;
    return {
      room_id: config.roomId,
      name: config.preview.name,
      topic: config.preview.topic,
      avatar_url: config.preview.avatarUrl,
      num_joined_members: config.preview.joinedMembers,
      world_readable: true,
      guest_can_join: false,
      join_rule: config.preview.joinRule,
      room_type: null
    };
  }

  const server = https.createServer({
    key: fs.readFileSync(certificates.serverKey),
    cert: fs.readFileSync(certificates.serverPem)
  }, async (request, response) => {
    let record;
    try {
      const url = new URL(request.url, baseUrl || 'https://127.0.0.1');
      const body = await readBody(request);
      record = beginRecord(request, url, body);

      if (url.pathname === '/__task14/status') {
        const validNonce = url.searchParams.get('nonce') === nonce && request.headers['x-task14-nonce'] === nonce;
        state.controls.push({ kind: 'status', sequence: record.sequence, validNonce, at: new Date().toISOString() });
        if (!validNonce) return reply(record, response, 403, { error: 'nonce' }, 'control_rejected');
        return reply(record, response, 200, {
          nonce,
          baseUrl,
          requestCount: state.requests.length,
          held: [...held.values()].map(item => ({ caseId: item.config.caseId, alias: item.config.alias,
            requestSequence: item.record.sequence }))
        }, 'status');
      }

      if (url.pathname === '/__task14/release') {
        const validNonce = request.headers['x-task14-nonce'] === nonce && body.parsed?.nonce === nonce;
        if (!validNonce) {
          state.controls.push({ kind: 'release', sequence: record.sequence, validNonce: false, at: new Date().toISOString() });
          return reply(record, response, 403, { error: 'nonce' }, 'control_rejected');
        }
        const pending = held.get(body.parsed.caseId);
        if (!pending || body.parsed.requestSequence !== pending.record.sequence) {
          state.controls.push({ kind: 'release', sequence: record.sequence, validNonce: true, accepted: false,
            caseId: body.parsed.caseId || null, at: new Date().toISOString() });
          return reply(record, response, 409, { error: 'held request mismatch' }, 'control_rejected');
        }
        held.delete(pending.config.caseId);
        pending.record.releasedBySequence = record.sequence;
        pending.record.timestamps.releasedAt = new Date().toISOString();
        finishAlias(pending.record, pending.response, pending.config, pending.config.releaseBehavior);
        state.controls.push({ kind: 'release', sequence: record.sequence, validNonce: true, accepted: true,
          caseId: pending.config.caseId, requestSequence: pending.record.sequence, at: new Date().toISOString() });
        return reply(record, response, 200, {
          released: pending.config.caseId,
          requestSequence: pending.record.sequence,
          outcome: pending.config.releaseBehavior
        }, 'released');
      }

      if (url.pathname === '/.well-known/matrix/client') {
        if (request.method !== 'GET') return reply(record, response, 405, { error: 'method' }, 'method_not_allowed');
        if (!baseUrl) return reply(record, response, 503, { error: 'provider not listening' }, 'not_ready');
        return reply(record, response, 200, { 'm.homeserver': { base_url: baseUrl } }, 'well_known');
      }

      if (url.pathname === '/_matrix/client/versions') {
        if (request.method !== 'GET') return reply(record, response, 405, { error: 'method' }, 'method_not_allowed');
        return reply(record, response, 200, { versions: ['v1.11'], unstable_features: {} }, 'versions');
      }

      if (url.pathname === '/_matrix/client/v3/login') {
        const login = body.parsed || {};
        const valid = request.method === 'POST' && record.tls.encrypted &&
          login.type === 'm.login.password' && login.identifier?.type === 'm.id.user' &&
          login.identifier?.user === expected.username && login.password === expected.password;
        record.login = { valid, username: login.identifier?.user || null,
          passwordSha256: sha256(String(login.password || '')) };
        if (!valid) return reply(record, response, 403,
          { errcode: 'M_FORBIDDEN', error: 'Invalid Task14 evaluator credentials' }, 'login_rejected');
        return reply(record, response, 200, {
          user_id: expected.userId,
          device_id: expected.deviceId,
          access_token: expected.accessToken,
          well_known: { 'm.homeserver': { base_url: baseUrl } }
        }, 'login');
      }

      const aliasPrefix = '/_matrix/client/v3/directory/room/';
      if (url.pathname.startsWith(aliasPrefix)) {
        let alias;
        try { alias = decodeURIComponent(url.pathname.slice(aliasPrefix.length)); }
        catch { return reply(record, response, 400, { errcode: 'M_INVALID_PARAM', error: 'Invalid room alias' }, 'bad_alias'); }
        const config = findCaseByAlias(alias);
        record.kind = 'resolve_room_alias';
        record.caseId = config?.caseId || null;
        record.alias = alias;
        if (request.method !== 'GET' || !hasProductionAuth(record)) {
          return reply(record, response, 401, { errcode: 'M_UNKNOWN_TOKEN', error: 'Missing evaluator access token' }, 'unauthorized');
        }
        if (!config) return reply(record, response, 404, { errcode: 'M_NOT_FOUND', error: 'Room alias not configured' }, 'not_found');
        if (config.behavior === 'held') {
          if (held.has(config.caseId)) return reply(record, response, 409,
            { errcode: 'M_UNKNOWN', error: 'Case already has a held alias request' }, 'duplicate_held');
          record.outcome = 'held';
          held.set(config.caseId, { config, record, response });
          response.once('close', () => {
            if (!response.writableEnded && held.get(config.caseId)?.response === response) {
              record.clientClosedBeforeRelease = true;
            }
          });
          return;
        }
        return finishAlias(record, response, config, config.behavior);
      }

      if (url.pathname === '/_matrix/client/v3/sync') {
        record.kind = 'sync';
        if (request.method !== 'GET' || !hasProductionAuth(record)) {
          return reply(record, response, 401, { errcode: 'M_UNKNOWN_TOKEN', error: 'Missing evaluator access token' }, 'unauthorized');
        }
        return reply(record, response, 200, {
          next_batch: `task14-empty-${record.sequence}`,
          rooms: { join: {}, invite: {}, leave: {} }
        }, 'empty_sync');
      }

      if (url.pathname === '/_matrix/client/v3/account/whoami') {
        if (request.method !== 'GET' || !hasProductionAuth(record)) {
          return reply(record, response, 401, { errcode: 'M_UNKNOWN_TOKEN', error: 'Missing evaluator access token' }, 'unauthorized');
        }
        return reply(record, response, 200, { user_id: expected.userId, device_id: expected.deviceId }, 'whoami');
      }

      if (url.pathname === '/_matrix/client/v3/joined_rooms') {
        if (request.method !== 'GET' || !hasProductionAuth(record)) {
          return reply(record, response, 401, { errcode: 'M_UNKNOWN_TOKEN', error: 'Missing evaluator access token' }, 'unauthorized');
        }
        return reply(record, response, 200, { joined_rooms: [] }, 'joined_rooms');
      }

      const summaryPatterns = [
        /^\/_matrix\/client\/v1\/room_summary\/([^/]+)$/,
        /^\/_matrix\/client\/unstable\/im\.nheko\.summary\/rooms\/([^/]+)\/summary$/
      ];
      const summaryMatch = summaryPatterns.map(pattern => url.pathname.match(pattern)).find(Boolean);
      if (summaryMatch) {
        let roomId;
        try { roomId = decodeURIComponent(summaryMatch[1]); }
        catch { return reply(record, response, 400, { errcode: 'M_INVALID_PARAM', error: 'Invalid room id' }, 'bad_room_id'); }
        record.kind = 'room_preview';
        record.roomId = roomId;
        const preview = previewFor(roomId);
        if (request.method !== 'GET' || !hasProductionAuth(record)) {
          return reply(record, response, 401, { errcode: 'M_UNKNOWN_TOKEN', error: 'Missing evaluator access token' }, 'unauthorized');
        }
        if (!preview) return reply(record, response, 404, { errcode: 'M_NOT_FOUND', error: 'Room not configured' }, 'not_found');
        return reply(record, response, 200, preview, 'room_preview');
      }

      return reply(record, response, 404, { errcode: 'M_UNRECOGNIZED', error: 'Endpoint not implemented' }, 'unrecognized');
    } catch (error) {
      if (record && !response.headersSent) {
        return reply(record, response, 500,
          { errcode: 'M_UNKNOWN', error: 'Task14 provider failure', detail_sha256: sha256(String(error)) }, 'provider_error');
      }
      if (!response.destroyed) response.destroy(error);
    }
  });

  return {
    state,
    expected: clone(expected),
    configureCase,
    get baseUrl() { return baseUrl; },
    listen(port = 0, host = '127.0.0.1') {
      return new Promise((resolve, reject) => {
        const onError = error => reject(error);
        server.once('error', onError);
        server.listen(port, host, () => {
          server.off('error', onError);
          const address = server.address();
          baseUrl = `https://${host === 'localhost' ? 'localhost' : '127.0.0.1'}:${address.port}`;
          state.baseUrl = baseUrl;
          state.startedAt = new Date().toISOString();
          resolve(address.port);
        });
      });
    },
    close() {
      for (const pending of held.values()) {
        if (!pending.response.writableEnded) pending.response.destroy();
      }
      held.clear();
      state.stoppedAt = new Date().toISOString();
      return new Promise(resolve => {
        if (!server.listening) return resolve();
        server.close(resolve);
        server.closeAllConnections?.();
      });
    }
  };
}

module.exports = { generateCertificates, createProvider };
