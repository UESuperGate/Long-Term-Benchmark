'use strict';
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const previous = require('../task14_full_native_v10/install.cjs');
const root = path.resolve(__dirname, '../../..');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const replace = (text, old, next) => {
  if (text.split(old).length !== 2) throw Error('Task14 V11 derivation changed: ' + old);
  return text.replace(old, next);
};

function coreSource() {
  let source = fs.readFileSync(path.join(root, 'state_tests/runtime/arkts/native/Task14DeviceUi.core.js'), 'utf8');
  source = replace(source,
    `    await delegator.addAbilityMonitor(monitor); monitorAdded = true;
    await delegator.startAbility({ bundleName: config.bundleName, abilityName: config.abilityName, moduleName: config.moduleName });
    const driver = ports.createDriver();`,
    `    await delegator.addAbilityMonitor(monitor); monitorAdded = true;
    if (config.preparedForegroundEntry === true) {
      ability = await delegator.getCurrentTopAbility();
      if (!matches(ability)) throw new Error('Prepared foreground candidate identity unavailable');
      foreground = true;
      record({ method: 'Task14.preparedForegroundAdopted', identity: identity(ability),
        ownershipChecksPending: ['lastWindow', 'UIContext host', 'Driver focus', 'geometry', 'router', 'inspector'] });
    } else {
      await delegator.startAbility({ bundleName: config.bundleName, abilityName: config.abilityName, moduleName: config.moduleName });
    }
    const driver = ports.createDriver();`);
  source = replace(source,
    `      if (lifecycleError || !ability || !stage || !foreground || !matches(await delegator.getCurrentTopAbility()))
        throw new Error(lifecycleError || 'Original cold-created foreground ability/stage unavailable');
      const main = await stage.getMainWindow();
      const win = await ports.getLastWindow(ability.context);`,
    `      if (lifecycleError || !ability || (!stage && config.preparedForegroundEntry !== true) || !foreground ||
          !matches(await delegator.getCurrentTopAbility()))
        throw new Error(lifecycleError || 'Original foreground ability ownership unavailable');
      const win = await ports.getLastWindow(ability.context);
      const main = stage ? await stage.getMainWindow() : win;`);
  return source;
}

function adapterSource() {
  return previous.adapterSource()
    .replace('evaluateTask14FullNativeV10', 'evaluateTask14FullNativeV11')
    .replaceAll('task14.full-nine-configured-sdk.v10', 'task14.full-nine-configured-sdk.v11')
    .replaceAll('fullNativeEpisodeV10', 'fullNativeEpisodeV11');
}

function bridgeSource() {
  return previous.bridgeSource()
    .replace("import { evaluateTask14FullNativeV10 } from './Task14FullNativeV10.adapter';",
      "import { evaluateTask14FullNativeV11 } from './Task14FullNativeV11.adapter';")
    .replace('return evaluateTask14FullNativeV10(args, config, ports, record);',
      'return evaluateTask14FullNativeV11(args, config, ports, record);');
}

function expectedFixtures() {
  return previous.expectedFixtures()
    .filter(item => !['Task14DeviceUi.core.js', 'Task14FullNativeV10.adapter.js',
      'Task14DeviceUi.js'].includes(item.name))
    .concat([
      { name: 'Task14DeviceUi.core.js', sha256: hash(coreSource()) },
      { name: 'Task14FullNativeV11.adapter.js', sha256: hash(adapterSource()) },
      { name: 'Task14DeviceUi.js', sha256: hash(bridgeSource()) }
    ]);
}

function install(work, options = {}) {
  const report = previous.install(work, options);
  const testRoot = path.join(work, 'entry/src/test');
  const oldConfig = report.config;
  const config = { ...oldConfig, fullNativeProtocol: 'task14.full-nine-configured-sdk.v11',
    preparedForegroundEntry: true };
  const core = coreSource(), adapter = adapterSource(), bridge = bridgeSource();
  fs.writeFileSync(path.join(testRoot, 'Task14DeviceUi.core.js'), core);
  fs.rmSync(path.join(testRoot, 'Task14FullNativeV10.adapter.js'));
  fs.writeFileSync(path.join(testRoot, 'Task14FullNativeV11.adapter.js'), adapter);
  fs.writeFileSync(path.join(testRoot, 'Task14DeviceUi.js'), bridge);
  const suite = replace(fs.readFileSync(report.suiteFile, 'utf8'), JSON.stringify(JSON.stringify(oldConfig)),
    JSON.stringify(JSON.stringify(config)));
  fs.writeFileSync(report.suiteFile, suite);
  const replacements = new Map(expectedFixtures().map(item => [item.name, item]));
  const fixtures = report.fixtures
    .filter(item => path.basename(item.path) !== 'Task14FullNativeV10.adapter.js')
    .map(item => replacements.has(path.basename(item.path)) ?
      { ...item, sha256: replacements.get(path.basename(item.path)).sha256, derivedBy: __filename } : item);
  fixtures.push({ path: 'entry/src/test/Task14FullNativeV11.adapter.js', source: __filename,
    sha256: hash(adapter), derivedBy: __filename });
  for (const item of report.production) {
    if (hash(fs.readFileSync(path.join(work, item.path))) !== item.sha256) throw Error('Production changed');
  }
  return { ...report, config, fixtures, suiteSha256: hash(suite), protocol: config.fullNativeProtocol,
    e2e: { ...report.e2e, pageAcquisition: 'prepared foreground with full identity/window/router/tree checks' },
    predecessor: { protocol: report.protocol, installer: report.installer },
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) } };
}

module.exports = { install, e2eSource: previous.e2eSource, coreSource, adapterSource, bridgeSource,
  expectedFixtures, pageObserverAlias: previous.pageObserverAlias };
