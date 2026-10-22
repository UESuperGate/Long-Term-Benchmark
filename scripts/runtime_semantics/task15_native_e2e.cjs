#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const https = require('node:https');
const crypto = require('node:crypto');
const { spawn } = require('node:child_process');
const { verifyTask15NativeE2E } = require('../../state_tests/runtime/arkts/native/Task15NativeE2E.verifier.cjs');

const root = path.resolve(__dirname, '../..');
const hdc = path.join(os.homedir(), 'Library/OpenHarmony/Sdk/23/toolchains/hdc');
const source = path.join(root, 'final_dev_nodes/15_account_deactivation_final_0_6_3');
const builder = path.join(root, 'scripts/runtime_semantics/arkts_native_device.cjs');
const hashBytes = value => crypto.createHash('sha256').update(value).digest('hex');
const hashFile = file => hashBytes(fs.readFileSync(file));
const write = (file, value) => fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n');
const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

function commandHash(file, args) {
  return hashBytes(JSON.stringify([file, args]));
}

function runCommand(file, args, options = {}) {
  const timeout = options.timeout || 30000;
  return new Promise((resolve, reject) => {
    const child = spawn(file, args, { cwd: options.cwd || root, env: options.env || process.env });
    const chunks = [];
    child.stdout.on('data', chunk => chunks.push(chunk));
    child.stderr.on('data', chunk => chunks.push(chunk));
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; child.kill('SIGKILL'); }, timeout);
    child.on('error', error => { clearTimeout(timer); reject(error); });
    child.on('close', code => {
      clearTimeout(timer);
      const output = Buffer.concat(chunks).toString('utf8');
      if (options.log) fs.writeFileSync(options.log, output);
      const item = { file, args, exitCode: code, timedOut, sha256: commandHash(file, args),
        log: options.log && path.basename(options.log), logSha256: options.log && hashFile(options.log) };
      if (timedOut || code !== 0) reject(Object.assign(new Error('Command failed: ' + file + ' ' + args.join(' ')), { item, output }));
      else resolve({ item, output });
    });
  });
}

async function generateCertificates(directory, nonce, commands) {
  fs.mkdirSync(directory, { recursive: true });
  const caKey = path.join(directory, 'ca.key');
  const caPem = path.join(directory, 'ca.pem');
  const caDer = path.join(directory, 'ca.der');
  const serverKey = path.join(directory, 'server.key');
  const serverCsr = path.join(directory, 'server.csr');
  const serverPem = path.join(directory, 'server.pem');
  const caExtensions = path.join(directory, 'ca.ext');
  const extensions = path.join(directory, 'server.ext');
  fs.writeFileSync(caExtensions, '[v3_ca]\nbasicConstraints=critical,CA:true,pathlen:0\n' +
    'keyUsage=critical,keyCertSign,cRLSign\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid:always\n');
  fs.writeFileSync(extensions, 'subjectAltName=IP:127.0.0.1,DNS:localhost\nextendedKeyUsage=serverAuth\nkeyUsage=digitalSignature,keyEncipherment\n');
  const specs = [
    ['genrsa', '-out', caKey, '2048'],
    ['req', '-new', '-key', caKey, '-subj', '/CN=LTB Task15 ' + nonce, '-out', path.join(directory, 'ca.csr')],
    ['x509', '-req', '-in', path.join(directory, 'ca.csr'), '-signkey', caKey, '-days', '2', '-sha256',
      '-extfile', caExtensions, '-extensions', 'v3_ca', '-out', caPem],
    ['genrsa', '-out', serverKey, '2048'],
    ['req', '-new', '-key', serverKey, '-subj', '/CN=127.0.0.1', '-out', serverCsr],
    ['x509', '-req', '-in', serverCsr, '-CA', caPem, '-CAkey', caKey, '-CAcreateserial',
      '-out', serverPem, '-days', '2', '-sha256', '-extfile', extensions],
    ['x509', '-in', caPem, '-outform', 'der', '-out', caDer]
  ];
  for (let index = 0; index < specs.length; index++) {
    const result = await runCommand('/usr/bin/openssl', specs[index], { log: path.join(directory, 'openssl-' + index + '.log') });
    commands.push(result.item);
  }
  const certificate = new crypto.X509Certificate(fs.readFileSync(serverPem));
  return { caKey, caPem, caDer, caCsr: path.join(directory, 'ca.csr'), serverKey, serverCsr, serverPem,
    caSha256: hashFile(caDer), serverSha256: hashFile(serverPem),
    subject: certificate.subject, issuer: certificate.issuer, validFrom: certificate.validFrom, validTo: certificate.validTo };
}

function createProvider(certificates, nonce) {
  const suffix = nonce.slice(0, 8);
  const expected = {
    user: 'alice_' + suffix,
    loginPassword: 'login-' + nonce.slice(0, 12),
    userId: '@alice_' + suffix + ':task15.test',
    deviceId: 'DEVICE_' + suffix.toUpperCase(),
    accessToken: 'token-' + nonce
  };
  const state = { schemaVersion: 1, nonce, protocol: 'https', loginCount: 0, deactivationCount: 0,
    held: null, requests: [], controls: [], tls: { caSha256: certificates.caSha256,
      serverSha256: certificates.serverSha256, subject: certificates.subject, issuer: certificates.issuer,
      authorized: false, meaning: 'A native production login request completed a TLS handshake using the installed user CA' } };
  let heldResponse;
  const reply = (response, status, body) => {
    response.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    response.end(JSON.stringify(body));
  };
  const readBody = request => new Promise((resolve, reject) => {
    const chunks = [];
    request.on('data', chunk => {
      chunks.push(chunk);
      if (Buffer.concat(chunks).length > 65536) reject(new Error('Task15 provider request too large'));
    });
    request.on('end', () => {
      try { resolve(chunks.length ? JSON.parse(Buffer.concat(chunks).toString('utf8')) : {}); }
      catch (error) { reject(error); }
    });
    request.on('error', reject);
  });
  const server = https.createServer({ key: fs.readFileSync(certificates.serverKey), cert: fs.readFileSync(certificates.serverPem) },
    async (request, response) => {
      try {
        const url = new URL(request.url, 'https://127.0.0.1');
        const secure = request.socket.encrypted === true;
        if (url.pathname === '/__task15/status') {
          if (url.searchParams.get('nonce') !== nonce || request.headers['x-task15-nonce'] !== nonce) return reply(response, 403, { error: 'nonce' });
          state.controls.push({ kind: 'status', at: new Date().toISOString(), secure });
          return reply(response, 200, { nonce, loginCount: state.loginCount, deactivationCount: state.deactivationCount,
            held: state.held && { deactivationNumber: state.held.deactivationNumber, requestSequence: state.held.requestSequence } });
        }
        if (url.pathname === '/__task15/release') {
          const body = await readBody(request);
          if (request.headers['x-task15-nonce'] !== nonce || body.nonce !== nonce) return reply(response, 403, { error: 'nonce' });
          const allowed = { 1: 401, 2: 503, 3: 401, 4: 200 };
          if (!state.held || body.deactivationNumber !== state.held.deactivationNumber || body.status !== allowed[body.deactivationNumber]) {
            return reply(response, 409, { error: 'unexpected release', held: state.held && state.held.deactivationNumber });
          }
          const current = state.held;
          const productionResponse = heldResponse;
          state.held = null;
          heldResponse = undefined;
          const requestRecord = state.requests.find(item => item.sequence === current.requestSequence);
          if (!requestRecord || requestRecord.kind !== 'deactivation') {
            return reply(response, 500, { error: 'held request record missing' });
          }
          requestRecord.responseStatus = body.status;
          const responseBody = body.status === 401 ? {
            errcode: 'M_UNAUTHORIZED', error: 'Additional authentication required',
            session: (body.deactivationNumber === 1 ? 'uia-initial-' : 'uia-retry-') + suffix
          } : body.status === 503 ? { errcode: 'M_UNKNOWN', error: 'Evaluator-owned upstream failure' } : {};
          reply(productionResponse, body.status, responseBody);
          state.controls.push({ kind: 'release', deactivationNumber: body.deactivationNumber, status: body.status,
            at: new Date().toISOString(), secure });
          return reply(response, 200, { released: body.deactivationNumber, status: body.status });
        }
        const body = await readBody(request);
        if (url.pathname === '/_matrix/client/v3/login') {
          state.loginCount++;
          const record = { sequence: state.requests.length + 1, kind: 'login', method: request.method, path: url.pathname,
            secure, body: { type: body.type, user: body.identifier?.user,
              passwordSha256: hashBytes(String(body.password || '')) }, responseStatus: 200 };
          state.requests.push(record);
          if (!secure || request.method !== 'POST' || state.loginCount !== 1 || body.type !== 'm.login.password' ||
            body.identifier?.user !== expected.user || body.password !== expected.loginPassword) {
            record.responseStatus = 400;
            return reply(response, 400, { errcode: 'M_BAD_JSON', error: 'Unexpected evaluator login payload' });
          }
          state.tls.authorized = true;
          return reply(response, 200, { user_id: expected.userId, device_id: expected.deviceId, access_token: expected.accessToken });
        }
        if (url.pathname === '/_matrix/client/v3/account/deactivate') {
          state.deactivationCount++;
          const auth = body.auth;
          const record = { sequence: state.requests.length + 1, kind: 'deactivation', number: state.deactivationCount,
            method: request.method, path: url.pathname, secure,
            authorizationSha256: hashBytes(String(request.headers.authorization || '')),
            body: { erase: body.erase, hasAuth: !!auth, ...(auth ? { authType: auth.type, user: auth.identifier?.user,
              passwordSha256: hashBytes(String(auth.password || '')), session: auth.session } : {}) } };
          state.requests.push(record);
          if (!secure || request.method !== 'POST' || request.headers.authorization !== 'Bearer ' + expected.accessToken ||
            state.deactivationCount > 4 || heldResponse) {
            record.responseStatus = 409;
            return reply(response, 409, { errcode: 'M_UNKNOWN', error: 'Unexpected evaluator request ordering' });
          }
          state.held = { deactivationNumber: state.deactivationCount, requestSequence: record.sequence };
          heldResponse = response;
          request.on('close', () => {
            if (!response.writableEnded && heldResponse === response) record.clientClosedBeforeRelease = true;
          });
          return;
        }
        reply(response, 404, { error: 'not found' });
      } catch (error) {
        reply(response, 500, { error: 'provider error', detailHash: hashBytes(String(error)) });
      }
    });
  return {
    state,
    listen: () => new Promise((resolve, reject) => {
      server.once('error', reject);
      server.listen(0, '127.0.0.1', () => resolve(server.address().port));
    }),
    close: () => new Promise(resolve => {
      if (heldResponse && !heldResponse.writableEnded) heldResponse.destroy();
      server.close(resolve);
      server.closeAllConnections?.();
    })
  };
}

function freshMarker(before, after) {
  const known = new Set(before.split('\n'));
  const lines = after.split('\n').filter(line => line.includes('ARKTS_NATIVE_ROW_FILE ') && !known.has(line));
  const parsed = lines.map(line => ({ line, marker: JSON.parse(line.slice(line.indexOf('ARKTS_NATIVE_ROW_FILE ') + 22)) }))
    .filter(item => item.marker.taskId === '15_account_deactivation' && item.marker.caseId === 'ad_state_005_first_submit_confirms');
  if (parsed.length !== 1 || !/^ltb-native-result_\d+\.json$/.test(parsed[0].marker.name)) {
    throw new Error('Expected exactly one fresh Task15 native result marker');
  }
  return parsed[0];
}

async function main() {
  const args = process.argv.slice(2);
  const value = flag => {
    const index = args.indexOf(flag);
    if (index < 0 || !args[index + 1] || args[index + 1].startsWith('--')) throw new Error(flag + ' is required');
    return args[index + 1];
  };
  if (args.includes('--help')) {
    console.log('task15_native_e2e.cjs --output-dir NEW_DIRECTORY --serial DEVICE');
    return;
  }
  const output = path.resolve(value('--output-dir'));
  const serial = value('--serial');
  const prepareOnly = args.includes('--prepare-only');
  const debugPreserveWork = args.includes('--debug-preserve-work');
  const taskTimeoutMs = 3600 * 1000;
  if (fs.existsSync(output)) throw new Error('Refusing existing Task15 evidence directory');
  if (!/^[A-Za-z0-9.:_-]+$/.test(serial)) throw new Error('Invalid device serial');
  fs.mkdirSync(output, { recursive: true });
  const buildDirectory = path.join(output, 'build');
  const executionDirectory = path.join(output, 'execution');
  const certificateDirectory = path.join(output, 'certificates');
  fs.mkdirSync(executionDirectory);
  const nonce = crypto.randomBytes(16).toString('hex');
  const run = { schemaVersion: 1, startedAt: new Date().toISOString(), status: 'incomplete', nonce, serial,
    source, taskTimeoutSeconds: taskTimeoutMs / 1000, commands: [], sourceHashes: [], haps: [], security: { productionTransportUnchanged: true,
      testOnlyPermission: 'ohos.permission.ACCESS_CERT_MANAGER', httpDowngradeAllowed: false },
    cleanup: { appUninstalled: false, reverseRemoved: false, serverClosed: false, privateKeysRemoved: false } };
  let provider;
  let certificates;
  let build;
  let bundleName;
  let reverse;
  let owned = false;
  const lock = path.join('/tmp', 'ltb-arkts-device-' + hashBytes(serial).slice(0, 16));
  let locked = false;
  const device = async (name, commandArgs, timeout = 30000) => {
    const result = await runCommand(hdc, ['-t', serial, ...commandArgs], {
      timeout, log: path.join(executionDirectory, name + '.log')
    });
    run.commands.push(result.item);
    return result.output;
  };
  try {
    certificates = await generateCertificates(certificateDirectory, nonce, run.commands);
    const sharedBuilderSource = fs.readFileSync(builder, 'utf8');
    const generatedBuilder = path.join(output, 'task15-builder-expanded-log.cjs');
    const smoke = path.join(root, 'scripts/runtime_semantics/arkts_native_smoke.cjs');
    const bundleBuilder = path.join(root, 'scripts/runtime_semantics/arkts_native_bundle.cjs');
    let generatedBuilderSource = sharedBuilderSource
      .replace("require('./arkts_native_smoke.cjs')", 'require(' + JSON.stringify(smoke) + ')')
      .replace("require('./arkts_native_bundle.cjs')", 'require(' + JSON.stringify(bundleBuilder) + ')')
      .replace("const root = path.resolve(__dirname, '../..');", 'const root = ' + JSON.stringify(root) + ';')
      .replace("log.split('\\n').map(line => line.length > 4000 ? '[omitted SDK source dump]' : line).join('\\n')", 'log');
    if (debugPreserveWork) {
      generatedBuilderSource = generatedBuilderSource.replace(
        'const { withTemporaryWorkspace } = require(' + JSON.stringify(smoke) + ');',
        "const withTemporaryWorkspace = async callback => { const work = process.env.TASK15_DEBUG_WORK; fs.mkdirSync(work, { recursive: true }); return callback(work); };");
    }
    if (generatedBuilderSource === sharedBuilderSource || generatedBuilderSource.includes('[omitted SDK source dump]')) {
      throw new Error('Unable to derive Task15 expanded-log builder');
    }
    fs.writeFileSync(generatedBuilder, generatedBuilderSource);
    run.builder = { sharedPath: builder, sharedSha256: hashFile(builder), generatedPath: generatedBuilder,
      generatedSha256: hashFile(generatedBuilder), semanticChange: debugPreserveWork ?
        'diagnostic logging plus preserved temporary workspace; shared packager source remains untouched' :
        'logging only; shared packager source remains untouched' };
    const buildResult = await runCommand(process.execPath, [generatedBuilder, '--source', source, '--task', '15_account_deactivation',
      '--fixture', 'bundle', '--role', 'final', '--case', 'ad_state_005_first_submit_confirms', '--native-ui',
      '--output-dir', buildDirectory], { timeout: 600000, log: path.join(output, 'build-command.log'),
      env: { ...process.env, NODE_OPTIONS: [process.env.NODE_OPTIONS, '--enable-source-maps'].filter(Boolean).join(' '),
        TASK15_NATIVE_E2E_CA_DER: certificates.caDer,
        ...(debugPreserveWork ? { TASK15_DEBUG_WORK: path.join(output, 'preserved-work') } : {}) } });
    run.commands.push(buildResult.item);
    const buildFile = path.join(buildDirectory, 'device-build-report.json');
    build = JSON.parse(fs.readFileSync(buildFile));
    if (build.runtimeCompile?.passed !== true || build.productionUnchanged !== true ||
      build.copiedProductionUnchanged !== true || build.nativeUIObserver?.e2e?.caSha256 !== certificates.caSha256) {
      throw new Error('Task15 E2E build provenance is incomplete');
    }
    run.buildReport = { path: buildFile, sha256: hashFile(buildFile) };
    run.productionUnchanged = build.productionUnchanged;
    run.copiedProductionUnchanged = build.copiedProductionUnchanged;
    run.sourceHashes = build.production;
    run.haps = build.haps.map(item => ({ path: item.path, sha256: item.sha256, bytes: item.bytes }));
    bundleName = build.bundleName;
    if (prepareOnly) {
      run.status = 'built_not_executed';
      return;
    }

    const lockWaitStartedAt = Date.now();
    const lockDeadline = lockWaitStartedAt + taskTimeoutMs;
    while (true) {
      try {
        fs.mkdirSync(lock);
        break;
      } catch (error) {
        if (error.code !== 'EEXIST' || Date.now() >= lockDeadline) throw error;
        await sleep(1000);
      }
    }
    locked = true;
    run.deviceLockWaitSeconds = Number(((Date.now() - lockWaitStartedAt) / 1000).toFixed(3));
    const installed = await device('installed-before', ['shell', 'bm', 'dump', '-a']);
    if (installed.split('\n').some(line => line.trim() === bundleName)) throw new Error('Task15 candidate already installed');
    const users = [...installed.matchAll(/^ID: (\d+):/gm)].map(match => match[1]);
    if (users.length !== 1) throw new Error('Ambiguous device user');
    run.deviceUserId = users[0];
    provider = createProvider(certificates, nonce);
    const hostPort = await provider.listen();
    const devicePort = hostPort;
    reverse = ['tcp:' + devicePort, 'tcp:' + hostPort];
    const reverseResult = await device('reverse-create', ['rport', ...reverse]);
    if (!reverseResult.includes('Forwardport result:OK')) throw new Error('HDC reverse rejected');
    const reverseList = await device('reverse-list', ['fport', 'ls']);
    if (!reverseList.includes(reverse[0] + ' ' + reverse[1]) || !reverseList.includes('[Reverse]')) {
      throw new Error('HDC reverse absent from inventory');
    }
    run.reverse = { hostPort, devicePort, createOutput: reverseResult.trim(), inventorySha256: hashBytes(reverseList) };

    owned = true;
    for (const [index, hap] of build.haps.entries()) {
      if (hashFile(hap.path) !== hap.sha256) throw new Error('HAP changed after build');
      const install = await device('install-' + index, ['install', hap.path], 120000);
      if (!install.includes('install bundle successfully')) throw new Error('HAP install rejected');
    }
    await device('screen-wakeup', ['shell', 'power-shell', 'wakeup']);
    const before = await device('result-markers-before', ['shell', 'hilog', '-x', '-e', 'ARKTS_NATIVE_ROW_FILE']);
    const command = build.deviceTestCommand.slice(3).filter(item => !/<.*>/.test(item));
    const timeoutValue = command.findIndex((item, index) => item === 'timeout' && command[index - 1] === '-s');
    if (timeoutValue < 0) command.push('-s', 'timeout', String(taskTimeoutMs));
    else command[timeoutValue + 1] = String(taskTimeoutMs);
    const waitValue = command.indexOf('-w');
    if (waitValue >= 0) command[waitValue + 1] = String(taskTimeoutMs + 120000);
    command.push('-s', 'ltbExecutionNonce', nonce,
      '-s', 'task15E2E', '1',
      '-s', 'task15Nonce', nonce,
      '-s', 'task15Homeserver', 'https://127.0.0.1:' + devicePort,
      '-s', 'task15CaSha256', certificates.caSha256);
    const aa = await device('aa-test', command, taskTimeoutMs + 120000);
    if (!/TestFinished-ResultCode: 0\b/.test(aa) || !/Failure: 0, Error: 0/.test(aa)) {
      throw new Error('Task15 Hypium transport did not complete');
    }
    const after = await device('result-markers-after', ['shell', 'hilog', '-x', '-e', 'ARKTS_NATIVE_ROW_FILE']);
    const fresh = freshMarker(before, after);
    run.resultMarker = fresh.marker;
    const remote = '/data/app/el2/' + users[0] + '/base/' + bundleName + '/cache/' + fresh.marker.name;
    const nativeResultFile = path.join(executionDirectory, 'native-result.json');
    await device('pull-result', ['file', 'recv', remote, nativeResultFile]);
    const nativeRow = JSON.parse(fs.readFileSync(nativeResultFile));
    const raw = nativeRow.evidence?.find(item => item.nativePageTransition)?.nativePageTransition;
    if (!raw?.integration || raw.integration.nonce !== nonce) throw new Error('Nonce-bound Task15 integration evidence missing');
    run.deviceCertificateCleanupConfirmed = raw.integration.certificate?.cleanupConfirmed === true;
    write(path.join(executionDirectory, 'native-e2e-evidence.json'), raw.integration);
    write(path.join(executionDirectory, 'native-row-summary.json'), {
      taskId: nativeRow.taskId, role: nativeRow.role, caseId: nativeRow.caseId, status: nativeRow.status,
      reason: nativeRow.reason, traceDigest: nativeRow.traceDigest, nativeResultSha256: hashFile(nativeResultFile),
      integrationCleanup: raw.integrationCleanup, failure: raw.failure
    });
    write(path.join(executionDirectory, 'provider-transcript.json'), provider.state);
    run.nativeResult = { path: nativeResultFile, sha256: hashFile(nativeResultFile),
      rowStatus: nativeRow.status, canonicalScope: 'case005 only; E2E continuation verified separately' };
    run.providerTranscript = { path: path.join(executionDirectory, 'provider-transcript.json'),
      sha256: hashFile(path.join(executionDirectory, 'provider-transcript.json')) };
    run.scriptHashes = [__filename,
      path.join(root, 'state_tests/runtime/arkts/native/Task15NativeE2E.js'),
      path.join(root, 'state_tests/runtime/arkts/native/Task15NativeE2E.verifier.cjs'),
      path.join(root, 'state_tests/runtime/arkts/native/Task15NativeUi.js'),
      path.join(root, 'state_tests/runtime/arkts/native/Task15NativeUi.install.cjs')]
      .map(file => ({ path: path.relative(root, file), sha256: hashFile(file) }));
    run.status = 'executed_pending_cleanup';
  } catch (error) {
    run.error = String(error);
    if (error.item) run.commands.push(error.item);
    process.exitCode = 1;
  } finally {
    if (owned && bundleName && run.nativeResult && run.deviceCertificateCleanupConfirmed === true) {
      try {
        run.cleanup.appUninstalled = (await device('cleanup-uninstall', ['uninstall', bundleName], 120000))
          .includes('uninstall bundle successfully');
      } catch (error) { run.cleanup.appUninstallError = String(error); }
    } else if (owned && bundleName) {
      run.cleanup.appUninstallDeferred = true;
      run.cleanup.appUninstallReason = 'Device certificate cleanup was not positively confirmed';
    }
    if (reverse) {
      try {
        await device('cleanup-reverse', ['fport', 'rm', ...reverse]);
        const after = await device('cleanup-reverse-list', ['fport', 'ls']);
        run.cleanup.reverseRemoved = !after.includes(reverse[0] + ' ' + reverse[1]);
      } catch (error) { run.cleanup.reverseError = String(error); }
    }
    if (provider) {
      try { await provider.close(); run.cleanup.serverClosed = true; }
      catch (error) { run.cleanup.serverError = String(error); }
    }
    if (certificates) {
      for (const file of [certificates.caKey, certificates.caCsr, certificates.serverKey, certificates.serverCsr,
        path.join(certificateDirectory, 'ca.srl')]) fs.rmSync(file, { force: true });
      run.cleanup.privateKeysRemoved = [certificates.caKey, certificates.serverKey].every(file => !fs.existsSync(file));
    }
    if (locked) fs.rmdirSync(lock);
    run.finishedAt = new Date().toISOString();
    if (prepareOnly && run.status === 'built_not_executed') {
      // Compile-only preflight deliberately has no device verdict.
    } else if (run.nativeResult && fs.existsSync(path.join(executionDirectory, 'native-e2e-evidence.json')) &&
      fs.existsSync(path.join(executionDirectory, 'provider-transcript.json'))) {
      const evidence = JSON.parse(fs.readFileSync(path.join(executionDirectory, 'native-e2e-evidence.json')));
      const transcript = JSON.parse(fs.readFileSync(path.join(executionDirectory, 'provider-transcript.json')));
      const verification = verifyTask15NativeE2E({ evidence, provider: transcript, run });
      write(path.join(executionDirectory, 'verification.json'), verification);
      run.verification = { path: path.join(executionDirectory, 'verification.json'),
        sha256: hashFile(path.join(executionDirectory, 'verification.json')), status: verification.status,
        passed: verification.passed, total: verification.total };
      run.status = verification.status === 'passed' ? 'passed' : 'failed';
      if (verification.status !== 'passed') process.exitCode = 1;
    } else if (!run.error) {
      run.error = 'Task15 native evidence was not produced';
      run.status = 'incomplete';
      process.exitCode = 1;
    }
    write(path.join(output, 'run.json'), run);
    console.log(JSON.stringify({ output, status: run.status, error: run.error, verification: run.verification,
      cleanup: run.cleanup }, null, 2));
  }
}

module.exports = { createProvider, freshMarker };
if (require.main === module) main().catch(error => { console.error(String(error)); process.exitCode = 1; });
