'use strict';
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const previous = require('../task14_full_native_v9/install.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const replace = (text, old, next) => {
  if (text.split(old).length !== 2) throw Error('Task14 V10 derivation changed: ' + old);
  return text.replace(old, next);
};

function e2eSource() {
  return replace(previous.e2eSource(),
    `      checkpoint('login_fields_entered', { homeserver: config.homeserver, username: loginUsername,
        passwordDerivedFromNonce: true, passwordRedacted: true });
      const submit = await control('login_submit');`,
    `      checkpoint('login_fields_entered', { homeserver: config.homeserver, username: loginUsername,
        passwordDerivedFromNonce: true, passwordRedacted: true });
      const passwordNode = await control('login_password');
      const passwordFocused = await passwordNode.isFocused();
      if (passwordFocused) {
        await driver.pressBack();
        await driver.delayMs(300);
      }
      checkpoint('login_keyboard_dismissed', { passwordFocusedBeforeBack: passwordFocused,
        systemBackExecuted: passwordFocused });
      const submit = await control('login_submit');`);
}

function adapterSource() {
  return previous.adapterSource()
    .replace('evaluateTask14FullNativeV9', 'evaluateTask14FullNativeV10')
    .replaceAll('task14.full-nine-configured-sdk.v9', 'task14.full-nine-configured-sdk.v10')
    .replaceAll('fullNativeEpisodeV9', 'fullNativeEpisodeV10');
}

function bridgeSource() {
  return previous.bridgeSource()
    .replace("import { evaluateTask14FullNativeV9 } from './Task14FullNativeV9.adapter';",
      "import { evaluateTask14FullNativeV10 } from './Task14FullNativeV10.adapter';")
    .replace('return evaluateTask14FullNativeV9(args, config, ports, record);',
      'return evaluateTask14FullNativeV10(args, config, ports, record);');
}

function expectedFixtures() {
  return previous.expectedFixtures()
    .filter(item => !['Task14NativeE2E.js', 'Task14FullNativeV9.adapter.js',
      'Task14DeviceUi.js'].includes(item.name))
    .concat([
      { name: 'Task14NativeE2E.js', sha256: hash(e2eSource()) },
      { name: 'Task14FullNativeV10.adapter.js', sha256: hash(adapterSource()) },
      { name: 'Task14DeviceUi.js', sha256: hash(bridgeSource()) }
    ]);
}

function install(work, options = {}) {
  const report = previous.install(work, options);
  const testRoot = path.join(work, 'entry/src/test');
  const oldConfig = report.config;
  const config = { ...oldConfig, fullNativeProtocol: 'task14.full-nine-configured-sdk.v10' };
  const e2e = e2eSource(), adapter = adapterSource(), bridge = bridgeSource();
  fs.writeFileSync(path.join(testRoot, 'Task14NativeE2E.js'), e2e);
  fs.rmSync(path.join(testRoot, 'Task14FullNativeV9.adapter.js'));
  fs.writeFileSync(path.join(testRoot, 'Task14FullNativeV10.adapter.js'), adapter);
  fs.writeFileSync(path.join(testRoot, 'Task14DeviceUi.js'), bridge);
  const suite = replace(fs.readFileSync(report.suiteFile, 'utf8'), JSON.stringify(JSON.stringify(oldConfig)),
    JSON.stringify(JSON.stringify(config)));
  fs.writeFileSync(report.suiteFile, suite);
  const replacements = new Map(expectedFixtures().map(item => [item.name, item]));
  const fixtures = report.fixtures
    .filter(item => path.basename(item.path) !== 'Task14FullNativeV9.adapter.js')
    .map(item => replacements.has(path.basename(item.path)) ?
      { ...item, sha256: replacements.get(path.basename(item.path)).sha256, derivedBy: __filename } : item);
  fixtures.push({ path: 'entry/src/test/Task14FullNativeV10.adapter.js', source: __filename,
    sha256: hash(adapter), derivedBy: __filename });
  for (const item of report.production) {
    if (hash(fs.readFileSync(path.join(work, item.path))) !== item.sha256) throw Error('Production changed');
  }
  return { ...report, config, fixtures, suiteSha256: hash(suite), protocol: config.fullNativeProtocol,
    e2e: { ...report.e2e, imeAction: 'focus-bound UiDriver.pressBack after password input' },
    predecessor: { protocol: report.protocol, installer: report.installer },
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) } };
}

module.exports = { install, e2eSource, adapterSource, bridgeSource, expectedFixtures,
  pageObserverAlias: previous.pageObserverAlias };
