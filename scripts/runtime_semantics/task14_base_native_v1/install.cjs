'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
const finalInstaller = require('../task14_full_native_v18/install.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const root = path.resolve(__dirname, '../../..');
const native = path.join(root, 'state_tests/runtime/arkts/native');
const contract = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks/14_join_room_by_address/transitions.json')));
const read = file => fs.readFileSync(file, 'utf8');

function replaceOnce(source, before, after) {
  if (source.split(before).length !== 2) throw Error('Task14 base V1 derivation changed: ' + before);
  return source.replace(before, after);
}

function adapterSource() { return read(path.join(__dirname, 'Task14Base.adapter.js')); }
function e2eSource() { return finalInstaller.e2eSource(); }

function bridgeSource() {
  let source = read(path.join(native, 'Task14DeviceUi.js'));
  source = source
    .replace("import { evaluateTask14UI } from './Task14DeviceUi.adapter';\n", '')
    .replace("import { evaluateTask14RealFlowV2 } from './Task14RealFlowV2.adapter';\n", '')
    .replace("import { TASK14_CASES } from './Task14DeviceUi.suite';",
      `import fs from '@ohos.file.fs';
import fileUri from '@ohos.file.fileuri';
import certificateManager from '@ohos.security.certManager';
import wantConstant from '@ohos.app.ability.wantConstant';
import http from '@ohos.net.http';
import { task14NativeE2EConfig, createTask14NativeE2E } from './Task14NativeE2E';
import { evaluateTask14BaseV1 } from './Task14Base.adapter';
const TASK14_CASES = ${JSON.stringify(Object.fromEntries(contract.cases.map(item => [item.caseId, item.key])))};`);
  source = replaceOnce(source,
    `    return config.realFlowV2 === true && caseSpec.caseId === 'jr_state_001_entry_opens_address_flow' ?
      evaluateTask14RealFlowV2(args, config, ports, record) : evaluateTask14UI(args, config, ports, record);`,
    `    const appContext = abilityDelegatorRegistry.getAbilityDelegator().getAppContext();
    const e2e = createTask14NativeE2E(task14NativeE2EConfig(abilityDelegatorRegistry.getArguments().parameters),
      appContext.getApplicationContext(), appContext.createModuleContext('entry_test'), ports.createDriver(), ON,
      { fs, fileUri, certificateManager, wantConstant, http,
        abilityDelegator: abilityDelegatorRegistry.getAbilityDelegator() });
    await e2e.prepare(config.bundleName);
    bridge.task14E2E = e2e;
    return evaluateTask14BaseV1(args, config, ports, record);`);
  source = replaceOnce(source, `  bridge.dispose = async function() {`, `  bridge.dispose = async function() {
    if (bridge.task14E2E) { await bridge.task14E2E.cleanup(); delete bridge.task14E2E; }`);
  return source;
}

function expectedFixtures() {
  const values = {
    'Task14DeviceUi.js': bridgeSource(),
    'Task14DeviceUi.core.js': read(path.join(native, 'Task14DeviceUi.core.js')),
    'Task14AncestorObserver.js': read(path.join(native, 'Task14AncestorObserver.js')),
    'Task14NativeE2E.js': e2eSource(),
    'Task14Base.adapter.js': adapterSource()
  };
  return Object.entries(values).map(([name, source]) => ({ name, sha256: hash(source) }));
}

function install(work, options = {}) {
  const deadline = Number(options.deadlineEpochMs || process.env.LTB_TASK14_ROUTE_DEADLINE_EPOCH_MS);
  if (!Number.isFinite(deadline) || deadline <= Date.now()) throw Error('Whole task deadline unavailable');
  const app = json5.parse(read(path.join(work, 'AppScope/app.json5'))).app;
  const main = json5.parse(read(path.join(work, 'entry/src/main/module.json5'))).module;
  const profile = /^\$profile:([\w]+)$/.exec(main.pages);
  if (!profile || !main.abilities.some(ability => ability.name === main.mainElement))
    throw Error('Original base app entry metadata unavailable');
  const routes = json5.parse(read(path.join(work, 'entry/src/main/resources/base/profile/' + profile[1] + '.json'))).src;
  for (const route of ['pages/Index', 'pages/StartChat', 'pages/CreateRoom'])
    if (!routes.includes(route)) throw Error('Base positive-control route missing: ' + route);
  const basePage = read(path.join(work, 'entry/src/main/ets/pages/StartChat.ets'));
  const menu = read(path.join(work, 'entry/src/main/ets/components/ConfiguredStartChatMenu.ets'));
  if (!basePage.includes('ConfiguredStartChatMenu({ confirmNewDM: false })') ||
      !menu.includes('showJoinAddress: boolean = false') ||
      !menu.includes("if (this.showJoinAddress)")) throw Error('Base join-address boundary changed');

  const production = [];
  function visit(directory) {
    for (const entry of fs.readdirSync(path.join(work, directory), { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const relative = directory + '/' + entry.name;
      if (entry.isSymbolicLink()) throw Error('Candidate symlinks unsupported');
      if (entry.isDirectory()) visit(relative);
      else production.push({ path: relative, sha256: hash(fs.readFileSync(path.join(work, relative))) });
    }
  }
  visit('entry/src/main');
  const config = { bundleName: app.bundleName, moduleName: main.name, abilityName: main.mainElement,
    entryRoute: 'pages/StartChat', allowedRoutes: routes, deadlineEpochMs: deadline,
    productionSourcePath: 'entry/src/main/ets/features/ConfiguredStartChatOwner.ets',
    fullNativeProtocol: 'task14.base-entry-absence.v1', productionSources: production.filter(item => /\.(ets|ts)$/.test(item.path)) };

  const caFile = process.env.TASK14_NATIVE_E2E_CA_DER;
  if (!caFile) throw Error('Task14 external Matrix TLS CA missing');
  const resolvedCA = fs.realpathSync(caFile);
  const rawRoot = path.join(work, 'entry/src/ohosTest/resources/rawfile');
  fs.mkdirSync(rawRoot, { recursive: true });
  const installedCA = path.join(rawRoot, 'task14-ca.der'); fs.copyFileSync(resolvedCA, installedCA);
  const moduleFile = path.join(work, 'entry/src/ohosTest/module.json5');
  const moduleConfig = json5.parse(read(moduleFile));
  const permissions = moduleConfig.module.requestPermissions || [];
  if (!permissions.some(item => item.name === 'ohos.permission.ACCESS_CERT_MANAGER'))
    permissions.push({ name: 'ohos.permission.ACCESS_CERT_MANAGER' });
  moduleConfig.module.requestPermissions = permissions;
  fs.writeFileSync(moduleFile, JSON.stringify(moduleConfig, null, 2) + '\n');

  const testRoot = path.join(work, 'entry/src/test');
  const bundleFile = path.join(testRoot, 'native-bundle.js');
  const suiteFile = path.join(testRoot, 'NativeBundle.test.ets');
  const originalBundle = read(bundleFile), originalSuite = read(suiteFile);
  const navigate = 'if (candidateUI) await bridge.ui.navigate(candidateUI.route);';
  const run = 'const adapter = { runCase: context => module.exports.runCase({ ...context, native: bridge,';
  const suiteEntry = 'export default function nativeBundleTests(): void {';
  for (const [source, token] of [[originalBundle, navigate], [originalBundle, run], [originalSuite, suiteEntry]])
    if (source.split(token).length !== 2) throw Error('Generated base device hook changed: ' + token);
  let bundle = "import { attachTask14DeviceUI } from './Task14DeviceUi';\n" + originalBundle
    .replace(navigate, 'const task14DeviceUI = attachTask14DeviceUI(bridge, taskId, caseSpec);\n    ' +
      'if (!task14DeviceUI && candidateUI) await bridge.ui.navigate(candidateUI.route);')
    .replace(run, 'const adapter = { runCase: context => (bridge.evaluateTask14UI || module.exports.runCase)({ ...context, native: bridge,');
  bundle = replaceOnce(bundle,
    `    else if (comparison.missing.length || missingInvariants.length) row.reason = 'Adapter did not observe every canonical expectation and invariant';`,
    `    else if (result.semanticFailure === 'semantic_missing_feature_entry' && productionSources.length &&
        calls.length && checkpoints.length >= 2) {
      row.status = 'fail'; row.failureKind = result.semanticFailure;
      row.reason = result.semanticFailureReason || 'Final feature entry is absent from the reachable base UI';
    }
    else if (comparison.missing.length || missingInvariants.length) row.reason = 'Adapter did not observe every canonical expectation and invariant';`);
  const suite = "import { configureTask14DeviceUI } from './Task14DeviceUi';\n" + originalSuite.replace(suiteEntry,
    suiteEntry + '\nconfigureTask14DeviceUI(' + JSON.stringify(JSON.stringify(config)) + ');\n');
  fs.writeFileSync(bundleFile, bundle); fs.writeFileSync(suiteFile, suite);

  const fixtureSources = {
    'Task14DeviceUi.js': bridgeSource(),
    'Task14DeviceUi.core.js': read(path.join(native, 'Task14DeviceUi.core.js')),
    'Task14AncestorObserver.js': read(path.join(native, 'Task14AncestorObserver.js')),
    'Task14NativeE2E.js': e2eSource(),
    'Task14Base.adapter.js': adapterSource()
  };
  const fixtures = [];
  for (const [name, source] of Object.entries(fixtureSources)) {
    if (fs.existsSync(path.join(testRoot, name))) throw Error('Refusing existing evaluator file ' + name);
    fs.writeFileSync(path.join(testRoot, name), source);
    fixtures.push({ path: 'entry/src/test/' + name, sha256: hash(source), source: __filename });
  }
  for (const item of production)
    if (hash(fs.readFileSync(path.join(work, item.path))) !== item.sha256) throw Error('Production changed');
  return { config, productionUnchanged: true, production, fixtures, bundleFile, suiteFile,
    bundleSha256: hash(bundle), suiteSha256: hash(suite), protocol: config.fullNativeProtocol,
    e2e: { enabled: true, caSource: resolvedCA, caSha256: hash(fs.readFileSync(resolvedCA)),
      installedPath: path.relative(work, installedCA), testPermission: 'ohos.permission.ACCESS_CERT_MANAGER' },
    controlledBoundary: { commonEntry: 'pages/StartChat', positiveControl: 'pages/CreateRoom round trip',
      absentEntry: 'join_room_by_address', applicationMethodsReplaced: false,
      semanticFailureClassification: 'explicit missing feature entry after two stable native frames' },
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) },
    scope: 'Configured base login and StartChat/CreateRoom runtime with strict final-entry absence' };
}

module.exports = { install, adapterSource, bridgeSource, e2eSource, expectedFixtures };
