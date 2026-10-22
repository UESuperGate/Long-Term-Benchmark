'use strict';
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const previous = require('../task14_full_native_v7/install.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const replace = (text, old, next) => {
  if (text.split(old).length !== 2) throw Error('Task14 V8 derivation changed: ' + old);
  return text.replace(old, next);
};

function e2eSource() {
  const prior = previous.e2eSource();
  const withTlsProbe = replace(prior,
    `      await installCertificate();
      await inputControl('login_homeserver', config.homeserver);`,
    `      await installCertificate();
      const providerBeforeLogin = await providerStatus();
      checkpoint('provider_tls_ready_before_login', { requestCount: providerBeforeLogin.requestCount,
        heldCount: providerBeforeLogin.held.length, nonceBound: providerBeforeLogin.nonce === config.nonce });
      await inputControl('login_homeserver', config.homeserver);`);
  return replace(withTlsProbe,
    `      await clickControl('login_submit');
      const session = await waitFor('Task14 authenticated session', () => uniqueControlById('session_user'),
        async node => !!node && (await node.getText()).startsWith('@' + loginUsername + ':'));
      const sessionUser = await session.getText();`,
    `      const submit = await control('login_submit');
      const submitEnabled = await submit.isEnabled();
      checkpoint('login_submit_ready', { enabled: submitEnabled });
      if (!submitEnabled) throw new Error('Task14 UI control disabled: login_submit');
      await submit.click();
      checkpoint('login_submit_clicked', { physicalControl: true });
      let session = null;
      for (let attempt = 0; attempt < 100; attempt++) {
        const candidate = await uniqueControlById('session_user');
        if (candidate && (await candidate.getText()).startsWith('@' + loginUsername + ':')) {
          session = candidate;
          break;
        }
        const errorNode = await uniqueControlById('session_error');
        if (errorNode) {
          const errorText = await errorNode.getText();
          if (errorText.length > 0) {
            const providerAfterError = await providerStatus();
            checkpoint('login_failed', { errorText, providerRequestCount: providerAfterError.requestCount,
              heldCount: providerAfterError.held.length });
            throw new Error('Task14 real login failed: ' + errorText);
          }
        }
        await driver.delayMs(100);
      }
      if (!session) {
        const providerAfterTimeout = await providerStatus();
        checkpoint('login_wait_exhausted', { providerRequestCount: providerAfterTimeout.requestCount,
          heldCount: providerAfterTimeout.held.length });
        throw new Error('Task14 bounded wait exhausted: Task14 authenticated session');
      }
      const sessionUser = await session.getText();`);
}

function adapterSource() {
  return previous.adapterSource()
    .replace('evaluateTask14FullNativeV7', 'evaluateTask14FullNativeV8')
    .replaceAll('task14.full-nine-configured-sdk.v7', 'task14.full-nine-configured-sdk.v8')
    .replaceAll('fullNativeEpisodeV7', 'fullNativeEpisodeV8');
}

function bridgeSource() {
  return previous.bridgeSource()
    .replace("import { evaluateTask14FullNativeV7 } from './Task14FullNativeV7.adapter';",
      "import { evaluateTask14FullNativeV8 } from './Task14FullNativeV8.adapter';")
    .replace('return evaluateTask14FullNativeV7(args, config, ports, record);',
      'return evaluateTask14FullNativeV8(args, config, ports, record);');
}

function expectedFixtures() {
  const values = previous.expectedFixtures()
    .filter(item => !['Task14NativeE2E.js', 'Task14FullNativeV7.adapter.js',
      'Task14DeviceUi.js', 'Task14PageObserver.js'].includes(item.name));
  values.push({ name: 'Task14NativeE2E.js', sha256: hash(e2eSource()) });
  values.push({ name: 'Task14FullNativeV8.adapter.js', sha256: hash(adapterSource()) });
  values.push({ name: 'Task14DeviceUi.js', sha256: hash(bridgeSource()) });
  values.push({ name: 'Task14PageObserver.js', sha256: hash(previous.bridgeSource()
    .replace("import { evaluateTask14FullNativeV7 } from './Task14FullNativeV7.adapter';",
      "import { evaluateTask14FullNativeV8 } from './Task14FullNativeV8.adapter';")
    .replace('return evaluateTask14FullNativeV7(args, config, ports, record);',
      'return evaluateTask14FullNativeV8(args, config, ports, record);')) });
  return values;
}

function install(work, options = {}) {
  const report = previous.install(work, options);
  const testRoot = path.join(work, 'entry/src/test');
  const oldConfig = report.config;
  const config = { ...oldConfig, fullNativeProtocol: 'task14.full-nine-configured-sdk.v8' };
  const e2e = e2eSource(), adapter = adapterSource(), bridge = bridgeSource();
  fs.writeFileSync(path.join(testRoot, 'Task14NativeE2E.js'), e2e);
  fs.rmSync(path.join(testRoot, 'Task14FullNativeV7.adapter.js'));
  fs.writeFileSync(path.join(testRoot, 'Task14FullNativeV8.adapter.js'), adapter);
  fs.writeFileSync(path.join(testRoot, 'Task14DeviceUi.js'), bridge);
  fs.writeFileSync(path.join(testRoot, 'Task14PageObserver.js'), bridge);
  const suite = replace(fs.readFileSync(report.suiteFile, 'utf8'), JSON.stringify(JSON.stringify(oldConfig)),
    JSON.stringify(JSON.stringify(config)));
  fs.writeFileSync(report.suiteFile, suite);
  const replacements = new Map(expectedFixtures().map(item => [item.name, item]));
  const fixtures = report.fixtures
    .filter(item => path.basename(item.path) !== 'Task14FullNativeV7.adapter.js')
    .map(item => replacements.has(path.basename(item.path)) ?
      { ...item, sha256: replacements.get(path.basename(item.path)).sha256, derivedBy: __filename } : item);
  fixtures.push({ path: 'entry/src/test/Task14FullNativeV8.adapter.js', source: __filename,
    sha256: hash(adapter), derivedBy: __filename });
  for (const item of report.production) {
    if (hash(fs.readFileSync(path.join(work, item.path))) !== item.sha256) throw Error('Production changed');
  }
  return { ...report, config, fixtures, suiteSha256: hash(suite), protocol: config.fullNativeProtocol,
    e2e: { ...report.e2e, diagnostics: ['provider TLS before login', 'submit enabled/clicked',
      'rendered login error with provider request count'] },
    predecessor: { protocol: report.protocol, installer: report.installer },
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) } };
}

module.exports = { install, e2eSource, adapterSource, bridgeSource, expectedFixtures };
