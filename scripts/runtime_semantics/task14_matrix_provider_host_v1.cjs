#!/usr/bin/env node
'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { generateCertificates, createProvider } = require('./task14_matrix_provider_v1.cjs');

const sha256 = value => crypto.createHash('sha256').update(value).digest('hex');
const json = value => JSON.stringify(value, null, 2) + '\n';

function parseArguments(argv) {
  const result = {};
  for (let index = 0; index < argv.length; index++) {
    const argument = argv[index];
    if (argument !== '--control-dir' && argument !== '--case-config') {
      throw new Error(`Unknown argument: ${argument}`);
    }
    const value = argv[++index];
    if (!value || value.startsWith('--')) throw new Error(`Missing value for ${argument}`);
    const key = argument === '--control-dir' ? 'controlDir' : 'caseConfig';
    if (result[key]) throw new Error(`Duplicate argument: ${argument}`);
    result[key] = path.resolve(value);
  }
  if (!result.controlDir || !result.caseConfig) {
    throw new Error('Usage: task14_matrix_provider_host_v1.cjs --control-dir PATH --case-config PATH');
  }
  return result;
}

function loadConfiguration(file) {
  const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new TypeError('Task14 case configuration must be a JSON object');
  }
  if (!parsed.cases || (typeof parsed.cases !== 'object' && !Array.isArray(parsed.cases))) {
    throw new TypeError('Task14 case configuration requires cases');
  }
  const nonce = parsed.nonce === undefined ? crypto.randomBytes(16).toString('hex') : String(parsed.nonce).toLowerCase();
  if (!/^[0-9a-f]{32}$/.test(nonce)) throw new TypeError('Task14 nonce must be exactly 32 hexadecimal characters');
  return { nonce, cases: parsed.cases };
}

function writeAtomic(file, contents) {
  const temporary = path.join(path.dirname(file), `.${path.basename(file)}.${process.pid}.${crypto.randomBytes(6).toString('hex')}.tmp`);
  fs.writeFileSync(temporary, contents, { flag: 'wx', mode: 0o600 });
  try {
    fs.renameSync(temporary, file);
  } catch (error) {
    fs.rmSync(temporary, { force: true });
    throw error;
  }
}

function writeJsonAtomic(file, value) {
  writeAtomic(file, json(value));
}

function removeSensitiveCertificateArtifacts(directory) {
  const retained = new Set(['ca.der', 'ca.pem', 'server.pem']);
  for (const entry of fs.readdirSync(directory)) {
    if (!retained.has(entry)) fs.rmSync(path.join(directory, entry), { recursive: true, force: true });
  }
  const remaining = fs.readdirSync(directory).sort();
  if (remaining.join('\n') !== [...retained].sort().join('\n')) {
    throw new Error(`Unexpected Task14 certificate artifacts remain: ${remaining.join(', ')}`);
  }
  return remaining;
}

function redactTranscript(state, secrets) {
  let serialized = json(state);
  for (const [name, value] of Object.entries(secrets)) {
    if (!value) continue;
    serialized = serialized.split(value).join(`[REDACTED_${name.toUpperCase()}]`);
  }
  for (const value of Object.values(secrets)) {
    if (value && serialized.includes(value)) throw new Error('Task14 transcript secret redaction failed');
  }
  return serialized;
}

async function runHost(arguments_) {
  const { controlDir, caseConfig } = arguments_;
  const configuration = loadConfiguration(caseConfig);
  if (fs.existsSync(controlDir)) throw new Error(`Refusing to overwrite existing Task14 control directory: ${controlDir}`);
  fs.mkdirSync(path.dirname(controlDir), { recursive: true });
  fs.mkdirSync(controlDir, { mode: 0o700 });

  const certificateDirectory = path.join(controlDir, 'certificates');
  const commands = [];
  let provider;
  let stopping;
  try {
    const certificates = await generateCertificates(certificateDirectory, configuration.nonce, commands);
    const prefix = configuration.nonce.slice(0, 12);
    const credentials = {
      username: `task14_${prefix}`,
      password: `task14-login-${configuration.nonce}`,
      userId: `@task14_${prefix}:task14.test`,
      accessToken: `task14-token-${configuration.nonce}`
    };
    provider = createProvider(certificates, configuration.nonce, { credentials, cases: configuration.cases });
    const port = await provider.listen(0, '127.0.0.1');
    const retainedCertificates = removeSensitiveCertificateArtifacts(certificateDirectory);
    const certificateAudit = {
      schemaVersion: 1,
      provider: 'task14_matrix_provider_host_v1',
      generatedAt: new Date().toISOString(),
      caSha256: certificates.caSha256,
      serverSha256: certificates.serverSha256,
      subject: certificates.subject,
      issuer: certificates.issuer,
      subjectAltName: certificates.subjectAltName,
      validFrom: certificates.validFrom,
      validTo: certificates.validTo,
      retainedCertificates,
      commands
    };
    writeJsonAtomic(path.join(controlDir, 'certificate-audit.json'), certificateAudit);
    const ready = {
      schemaVersion: 1,
      provider: 'task14_matrix_provider_host_v1',
      pid: process.pid,
      readyAt: new Date().toISOString(),
      port,
      baseUrl: provider.baseUrl,
      nonce: configuration.nonce,
      caDer: path.join(certificateDirectory, 'ca.der'),
      caSha256: certificates.caSha256
    };
    writeJsonAtomic(path.join(controlDir, 'ready.json'), ready);
    process.stdout.write(json({ status: 'ready', controlDir, port, baseUrl: provider.baseUrl }));

    const stop = signal => {
      if (stopping) return stopping;
      stopping = (async () => {
        const stopStartedAt = new Date().toISOString();
        await provider.close();
        const transcriptPath = path.join(controlDir, 'transcript.json');
        const transcript = redactTranscript(provider.state, {
          password: credentials.password,
          token: credentials.accessToken
        });
        writeAtomic(transcriptPath, transcript);
        const stopped = {
          schemaVersion: 1,
          provider: 'task14_matrix_provider_host_v1',
          signal,
          stopStartedAt,
          stoppedAt: new Date().toISOString(),
          transcript: path.basename(transcriptPath),
          transcriptSha256: sha256(Buffer.from(transcript)),
          retainedCertificates: fs.readdirSync(certificateDirectory).sort()
        };
        writeJsonAtomic(path.join(controlDir, 'stopped.json'), stopped);
        process.stdout.write(json({ status: 'stopped', signal, controlDir }));
      })();
      return stopping;
    };

    await new Promise((resolve, reject) => {
      const handle = signal => {
        stop(signal).then(resolve, reject);
      };
      process.once('SIGTERM', () => handle('SIGTERM'));
      process.once('SIGINT', () => handle('SIGINT'));
    });
  } catch (error) {
    if (provider) await provider.close().catch(() => {});
    throw error;
  }
}

async function main(argv = process.argv.slice(2)) {
  await runHost(parseArguments(argv));
}

module.exports = { parseArguments, loadConfiguration, runHost };

if (require.main === module) {
  main().catch(error => {
    process.stderr.write(`Task14 provider host failed: ${error.message}\n`);
    process.exitCode = 1;
  });
}
