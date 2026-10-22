'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const previous = require('../task14_base_native_v1/install.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');

function replaceOnce(source, before, after) {
  if (source.split(before).length !== 2) throw Error('Task14 base V2 derivation changed: ' + before);
  return source.replace(before, after);
}

function bridgeSource() {
  let source = previous.bridgeSource();
  source = replaceOnce(source,
    `import http from '@ohos.net.http';`,
    `import http from '@ohos.net.http';
import matrixNativeAddon from 'libmatrix_native.so';`);
  source = replaceOnce(source,
    `      { fs, fileUri, certificateManager, wantConstant, http,
        abilityDelegator: abilityDelegatorRegistry.getAbilityDelegator() });`,
    `      { fs, fileUri, certificateManager, wantConstant, http, matrixNativeAddon,
        abilityDelegator: abilityDelegatorRegistry.getAbilityDelegator() });`);
  return source;
}

function expectedFixtures() {
  return previous.expectedFixtures().map(item => item.name === 'Task14DeviceUi.js' ?
    { name: item.name, sha256: hash(bridgeSource()) } : item);
}

function install(work, options = {}) {
  const report = previous.install(work, options);
  const oldConfig = report.config;
  const config = { ...oldConfig, fullNativeProtocol: 'task14.base-entry-absence.v2' };
  const bridge = bridgeSource();
  fs.writeFileSync(path.join(work, 'entry/src/test/Task14DeviceUi.js'), bridge);
  const suite = replaceOnce(fs.readFileSync(report.suiteFile, 'utf8'),
    JSON.stringify(JSON.stringify(oldConfig)), JSON.stringify(JSON.stringify(config)));
  fs.writeFileSync(report.suiteFile, suite);
  const fixtures = report.fixtures.map(item => path.basename(item.path) === 'Task14DeviceUi.js' ?
    { ...item, sha256: hash(bridge), derivedBy: __filename } : item);
  for (const item of report.production) {
    if (hash(fs.readFileSync(path.join(work, item.path))) !== item.sha256) throw Error('Production changed');
  }
  return { ...report, config, fixtures, suiteSha256: hash(suite), protocol: config.fullNativeProtocol,
    controlledBoundary: { ...report.controlledBoundary,
      nativeTrustDependency: 'same libmatrix_native.so additional-root implementation as final V18' },
    predecessor: { protocol: report.protocol, installer: report.installer,
      defect: 'base V1 omitted the native additional-root addon required by the shared E2E factory' },
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) } };
}

module.exports = { install, bridgeSource, expectedFixtures,
  adapterSource: previous.adapterSource, e2eSource: previous.e2eSource };
