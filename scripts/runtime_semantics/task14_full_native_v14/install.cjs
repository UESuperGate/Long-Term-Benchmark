'use strict';
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const previous = require('../task14_full_native_v13/install.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const replace = (text, old, next) => {
  if (text.split(old).length !== 2) throw Error('Task14 V14 derivation changed: ' + old);
  return text.replace(old, next);
};

function e2eSource() {
  let source = previous.e2eSource();
  source = replace(source,
    `  const http = platform.http;`,
    `  const http = platform.http;
  const matrixNativeAddon = platform.matrixNativeAddon;
  if (!matrixNativeAddon || typeof matrixNativeAddon.configureAdditionalRootCertificate !== 'function') {
    throw new Error('Task14 native additional-root configuration unavailable');
  }`);
  source = replace(source,
    `    certificateBytes = await resourceContext.resourceManager.getRawFileContent('task14-ca.der');
    candidateAbility = await abilityDelegator.getCurrentTopAbility();`,
    `    certificateBytes = await resourceContext.resourceManager.getRawFileContent('task14-ca.der');
    const rootConfigurationCode = matrixNativeAddon.configureAdditionalRootCertificate(certificateBytes);
    if (rootConfigurationCode !== 0) {
      throw new Error('Task14 native additional-root configuration failed: ' + rootConfigurationCode);
    }
    result.certificate.nativeRootConfigured = true;
    result.certificate.nativeRootConfigurationCode = rootConfigurationCode;
    checkpoint('native_additional_root_configured', { configured: true,
      errorCode: rootConfigurationCode, byteLength: certificateBytes.length,
      expectedSha256: config.caSha256 });
    candidateAbility = await abilityDelegator.getCurrentTopAbility();`);
  return source;
}

function adapterSource() {
  return previous.adapterSource()
    .replace('evaluateTask14FullNativeV13', 'evaluateTask14FullNativeV14')
    .replaceAll('task14.full-nine-configured-sdk.v13', 'task14.full-nine-configured-sdk.v14')
    .replaceAll('fullNativeEpisodeV13', 'fullNativeEpisodeV14');
}

function bridgeSource() {
  let source = previous.bridgeSource();
  source = replace(source,
    `import http from '@ohos.net.http';`,
    `import http from '@ohos.net.http';
import matrixNativeAddon from 'libmatrix_native.so';`);
  source = replace(source,
    `import { evaluateTask14FullNativeV13 } from './Task14FullNativeV13.adapter';`,
    `import { evaluateTask14FullNativeV14 } from './Task14FullNativeV14.adapter';`);
  source = replace(source,
    `      { fs, fileUri, certificateManager, wantConstant, http,
        abilityDelegator: abilityDelegatorRegistry.getAbilityDelegator() });`,
    `      { fs, fileUri, certificateManager, wantConstant, http, matrixNativeAddon,
        abilityDelegator: abilityDelegatorRegistry.getAbilityDelegator() });`);
  return source.replace('return evaluateTask14FullNativeV13(args, config, ports, record);',
    'return evaluateTask14FullNativeV14(args, config, ports, record);');
}

function expectedFixtures() {
  return previous.expectedFixtures()
    .filter(item => !['Task14NativeE2E.js', 'Task14FullNativeV13.adapter.js',
      'Task14DeviceUi.js'].includes(item.name))
    .concat([
      { name: 'Task14NativeE2E.js', sha256: hash(e2eSource()) },
      { name: 'Task14FullNativeV14.adapter.js', sha256: hash(adapterSource()) },
      { name: 'Task14DeviceUi.js', sha256: hash(bridgeSource()) }
    ]);
}

function install(work, options = {}) {
  const report = previous.install(work, options);
  const testRoot = path.join(work, 'entry/src/test');
  const oldConfig = report.config;
  const config = { ...oldConfig, fullNativeProtocol: 'task14.full-nine-configured-sdk.v14' };
  const e2e = e2eSource(), adapter = adapterSource(), bridge = bridgeSource();
  fs.writeFileSync(path.join(testRoot, 'Task14NativeE2E.js'), e2e);
  fs.rmSync(path.join(testRoot, 'Task14FullNativeV13.adapter.js'));
  fs.writeFileSync(path.join(testRoot, 'Task14FullNativeV14.adapter.js'), adapter);
  fs.writeFileSync(path.join(testRoot, 'Task14DeviceUi.js'), bridge);
  const suite = replace(fs.readFileSync(report.suiteFile, 'utf8'), JSON.stringify(JSON.stringify(oldConfig)),
    JSON.stringify(JSON.stringify(config)));
  fs.writeFileSync(report.suiteFile, suite);
  const replacements = new Map(expectedFixtures().map(item => [item.name, item]));
  const fixtures = report.fixtures
    .filter(item => path.basename(item.path) !== 'Task14FullNativeV13.adapter.js')
    .map(item => replacements.has(path.basename(item.path)) ?
      { ...item, sha256: replacements.get(path.basename(item.path)).sha256, derivedBy: __filename } : item);
  fixtures.push({ path: 'entry/src/test/Task14FullNativeV14.adapter.js', source: __filename,
    sha256: hash(adapter), derivedBy: __filename });
  for (const item of report.production) {
    if (hash(fs.readFileSync(path.join(work, item.path))) !== item.sha256) throw Error('Production changed');
  }
  return { ...report, config, fixtures, suiteSha256: hash(suite), protocol: config.fullNativeProtocol,
    e2e: { ...report.e2e,
      nativeTrust: 'the exact evaluator CA is added to rustls before the first Matrix Client build' },
    controlledBoundary: { ...report.controlledBoundary,
      tlsCertificateVerificationDisabled: false, hostnameVerificationDisabled: false },
    predecessor: { protocol: report.protocol, installer: report.installer },
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) } };
}

module.exports = { install, e2eSource, coreSource: previous.coreSource,
  ownerSource: previous.ownerSource, adapterSource, bridgeSource, expectedFixtures,
  pageObserverAlias: previous.pageObserverAlias };
