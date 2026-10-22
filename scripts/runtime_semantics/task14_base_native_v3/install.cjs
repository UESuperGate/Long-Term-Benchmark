'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const previous = require('../task14_base_native_v2/install.cjs');
const finalV11 = require('../task14_full_native_v11/install.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');

function replaceOnce(source, before, after) {
  if (source.split(before).length !== 2) throw Error('Task14 base V3 derivation changed: ' + before);
  return source.replace(before, after);
}

function coreSource() { return finalV11.coreSource(); }

function expectedFixtures() {
  return previous.expectedFixtures().map(item => item.name === 'Task14DeviceUi.core.js' ?
    { name: item.name, sha256: hash(coreSource()) } : item);
}

function install(work, options = {}) {
  const report = previous.install(work, options);
  const oldConfig = report.config;
  const config = { ...oldConfig, fullNativeProtocol: 'task14.base-entry-absence.v3',
    preparedForegroundEntry: true };
  const core = coreSource();
  fs.writeFileSync(path.join(work, 'entry/src/test/Task14DeviceUi.core.js'), core);
  const suite = replaceOnce(fs.readFileSync(report.suiteFile, 'utf8'),
    JSON.stringify(JSON.stringify(oldConfig)), JSON.stringify(JSON.stringify(config)));
  fs.writeFileSync(report.suiteFile, suite);
  const fixtures = report.fixtures.map(item => path.basename(item.path) === 'Task14DeviceUi.core.js' ?
    { ...item, sha256: hash(core), derivedBy: __filename } : item);
  for (const item of report.production) {
    if (hash(fs.readFileSync(path.join(work, item.path))) !== item.sha256) throw Error('Production changed');
  }
  return { ...report, config, fixtures, suiteSha256: hash(suite), protocol: config.fullNativeProtocol,
    controlledBoundary: { ...report.controlledBoundary,
      pageAcquisition: 'adopt prepared foreground with unchanged final V11 identity/window/router/tree checks' },
    predecessor: { protocol: report.protocol, installer: report.installer,
      defect: 'base evaluator registered cold-create observers after shared E2E preparation had already foregrounded the app' },
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) } };
}

module.exports = { install, coreSource, expectedFixtures,
  bridgeSource: previous.bridgeSource, adapterSource: previous.adapterSource,
  e2eSource: previous.e2eSource };
