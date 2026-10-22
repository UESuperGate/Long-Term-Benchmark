'use strict';
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const previous = require('../task14_full_native_v6/install.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const replace = (text, old, next) => {
  if (text.split(old).length !== 2) throw Error('Task14 V7 derivation changed: ' + old);
  return text.replace(old, next);
};

function e2eSource() {
  const prior = previous.sources().find(item => item.name === 'Task14NativeE2E.js')?.source;
  if (!prior) throw Error('Task14 V6 E2E source unavailable');
  return replace(prior, `      candidateBundleName = bundleName;
      await control('login_homeserver');`, `      candidateBundleName = bundleName;
      await abilityDelegator.startAbility({ bundleName: candidateBundleName, abilityName: 'EntryAbility', moduleName: 'entry' });
      checkpoint('candidate_started_for_login', { bundleName: candidateBundleName });
      await control('login_homeserver');`);
}

function adapterSource() {
  const prior = previous.sources().find(item => item.name === 'Task14FullNativeV6.adapter.js')?.source;
  if (!prior) throw Error('Task14 V6 adapter source unavailable');
  return prior
    .replace('evaluateTask14FullNativeV6', 'evaluateTask14FullNativeV7')
    .replaceAll('task14.full-nine-configured-sdk.v6', 'task14.full-nine-configured-sdk.v7')
    .replaceAll('fullNativeEpisodeV6', 'fullNativeEpisodeV7');
}

function bridgeSource() {
  return previous.bridgeSource()
    .replace("import { evaluateTask14FullNativeV6 } from './Task14FullNativeV6.adapter';",
      "import { evaluateTask14FullNativeV7 } from './Task14FullNativeV7.adapter';")
    .replace('return evaluateTask14FullNativeV6(args, config, ports, record);',
      'return evaluateTask14FullNativeV7(args, config, ports, record);');
}

function expectedFixtures() {
  const values = previous.sources().map(item => ({ name: item.name, sha256: hash(item.source) }))
    .filter(item => item.name !== 'Task14NativeE2E.js' && item.name !== 'Task14FullNativeV6.adapter.js');
  values.push({ name: 'Task14NativeE2E.js', sha256: hash(e2eSource()) });
  values.push({ name: 'Task14FullNativeV7.adapter.js', sha256: hash(adapterSource()) });
  values.push({ name: 'Task14DeviceUi.js', sha256: hash(bridgeSource()) });
  values.push({ name: 'Task14PageObserver.js', sha256: hash(previous.pageObserverAlias) });
  return values;
}

function install(work, options = {}) {
  const report = previous.install(work, options);
  const testRoot = path.join(work, 'entry/src/test');
  const oldConfig = report.config;
  const config = { ...oldConfig, fullNativeProtocol: 'task14.full-nine-configured-sdk.v7' };
  const e2e = e2eSource(), adapter = adapterSource(), bridge = bridgeSource();
  fs.writeFileSync(path.join(testRoot, 'Task14NativeE2E.js'), e2e);
  fs.rmSync(path.join(testRoot, 'Task14FullNativeV6.adapter.js'));
  fs.writeFileSync(path.join(testRoot, 'Task14FullNativeV7.adapter.js'), adapter);
  fs.writeFileSync(path.join(testRoot, 'Task14DeviceUi.js'), bridge);
  const suite = replace(fs.readFileSync(report.suiteFile, 'utf8'), JSON.stringify(JSON.stringify(oldConfig)),
    JSON.stringify(JSON.stringify(config)));
  fs.writeFileSync(report.suiteFile, suite);
  const replacements = new Map(expectedFixtures().map(item => [item.name, item]));
  const fixtures = report.fixtures
    .filter(item => path.basename(item.path) !== 'Task14FullNativeV6.adapter.js')
    .map(item => replacements.has(path.basename(item.path)) ?
      { ...item, sha256: replacements.get(path.basename(item.path)).sha256, derivedBy: __filename } : item);
  fixtures.push({ path: 'entry/src/test/Task14FullNativeV7.adapter.js', source: __filename,
    sha256: hash(adapter), derivedBy: __filename });
  for (const item of report.production) {
    if (hash(fs.readFileSync(path.join(work, item.path))) !== item.sha256) throw Error('Production changed');
  }
  return { ...report, config, fixtures, suiteSha256: hash(suite),
    protocol: config.fullNativeProtocol,
    e2e: { ...report.e2e, initialCandidateLaunch: 'AbilityDelegator.startAbility before first UI query' },
    predecessor: { protocol: report.protocol, installer: report.installer },
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) } };
}

module.exports = { install, e2eSource, adapterSource, bridgeSource, expectedFixtures };
