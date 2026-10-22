'use strict';
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const root = path.resolve(__dirname, '../../..'), native = path.join(root, 'state_tests/runtime/arkts/native');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const replace = (text, old, next) => {
  if (text.split(old).length !== 2) throw Error('Full-native V6 hook changed: ' + old);
  return text.replace(old, next);
};
const contract = JSON.parse(fs.readFileSync(path.join(root, 'benchmark_tasks/14_join_room_by_address/transitions.json')));
const read = file => fs.readFileSync(file, 'utf8');
const v5 = name => path.join(__dirname, '../task14_full_native_v5', name);

function scalarSource() {
  return read(v5('Task14ScalarCasesV5.js'))
    .replace('runTask14ScalarCasesV5', 'runTask14ScalarCasesV6')
    .replace("protocol:'task14.same-page-scalar.v5'", "protocol:'task14.same-page-scalar.v6'")
    .replace('observer.resolveExternal(first.id,{roomId:', 'await observer.resolveExternal(first.id,{roomId:');
}
function routesSource() {
  return read(path.join(__dirname, '../task14_real_routes_v3/Task14RealRoutesV3.suite.js'))
    .replace('runTask14RealRoutesV3', 'runTask14RealRoutesV6')
    .replaceAll('joinOwner.resolveExternal(', 'await joinOwner.resolveExternal(');
}
function deviceSuiteSource() {
  return read(path.join(native, 'Task14DeviceUi.suite.js'))
    .replace('runTask14Transition(', 'runTask14TransitionV6(')
    .replace('observer.settle(requests[0].id);', 'await observer.settle(requests[0].id);');
}
function bridgeSource() {
  let code = read(path.join(native, 'Task14DeviceUi.js'));
  code = "import fs from '@ohos.file.fs';\nimport fileUri from '@ohos.file.fileuri';\n" +
    "import certificateManager from '@ohos.security.certManager';\nimport wantConstant from '@ohos.app.ability.wantConstant';\n" +
    "import http from '@ohos.net.http';\nimport { task14NativeE2EConfig, createTask14NativeE2E } from './Task14NativeE2E';\n" +
    "import { evaluateTask14FullNativeV6 } from './Task14FullNativeV6.adapter';\n" + code;
  code = replace(code, 'TASK14_CASES[caseSpec.caseId] !== caseSpec.key',
    JSON.stringify(Object.fromEntries(contract.cases.map(item => [item.caseId, item.key]))) + '[caseSpec.caseId] !== caseSpec.key');
  const begin = "    return config.realFlowV2 === true && caseSpec.caseId === 'jr_state_001_entry_opens_address_flow' ?";
  const finish = 'evaluateTask14UI(args, config, ports, record);';
  const start = code.indexOf(begin), end = code.indexOf(finish, start) + finish.length;
  if (start < 0 || end < start) throw Error('Full-native V6 dispatch hook changed');
  code = code.slice(0, start) + '    return evaluateTask14FullNativeV6(args, config, ports, record);' + code.slice(end);
  code = replace(code, 'bridge.evaluateTask14UI = async args => {', `bridge.evaluateTask14UI = async args => {
    const appContext = abilityDelegatorRegistry.getAbilityDelegator().getAppContext();
    const e2e = createTask14NativeE2E(task14NativeE2EConfig(abilityDelegatorRegistry.getArguments().parameters),
      appContext.getApplicationContext(), appContext.createModuleContext('entry_test'), ports.createDriver(), ON,
      { fs, fileUri, certificateManager, wantConstant, http,
        abilityDelegator: abilityDelegatorRegistry.getAbilityDelegator() });
    await e2e.prepare(config.bundleName);
    ports.providerControl = e2e.control;
    bridge.task14E2E = e2e;`);
  code = replace(code, 'bridge.dispose = async function() {', `bridge.dispose = async function() {
    if (bridge.task14E2E) { await bridge.task14E2E.cleanup(); delete bridge.task14E2E; }`);
  return code;
}

const pageObserverAlias = "export { installTask14Observer } from './Task14JoinOwnerV3';\n";
function sources() {
  return [
    { name: 'Task14JoinOwnerV3.js', source: read(path.join(__dirname, 'Task14JoinOwnerV7.js')) },
    { name: 'Task14RealRoutesV6.suite.js', source: routesSource() },
    { name: 'Task14DeviceUiV6.suite.js', source: deviceSuiteSource() },
    { name: 'Task14OwnerClockV5.js', source: read(v5('Task14OwnerClockV5.js')) },
    { name: 'Task14ScalarCasesV6.js', source: scalarSource() },
    { name: 'Task14FullNativeV6.adapter.js', source: read(path.join(__dirname, 'Task14FullNativeV6.adapter.js')) },
    { name: 'Task14NativeE2E.js', source: read(path.join(__dirname, 'Task14NativeE2E.js')) }
  ];
}

function install(work, options = {}) {
  const deadline = Number(options.deadlineEpochMs || process.env.LTB_TASK14_ROUTE_DEADLINE_EPOCH_MS);
  if (!Number.isFinite(deadline) || deadline <= Date.now()) throw Error('Whole task deadline unavailable');
  const report = require(path.join(native, 'Task14DeviceUi.install.cjs')).install(work, { ...options, mode: 'after-page-ready' });
  const production = relative => read(path.join(work, relative));
  const required = { page: 'entry/src/main/ets/pages/StartChat.ets',
    composition: 'entry/src/main/ets/composition/Task14FinalAddressComposition.ets',
    rooms: 'entry/src/main/ets/matrix/production/ConfiguredSessionRooms.ets',
    bridge: 'entry/src/main/ets/nativebridge/AddonNativeMatrixBridge.ets' };
  for (const file of Object.values(required)) if (!fs.existsSync(path.join(work, file)))
    throw Error('Configured Task14 production boundary missing: ' + file);
  if (!production(required.page).includes('Task14FinalAddressComposition.createPresenter(this.runtime.foundation, this.navigator)') ||
      !production(required.composition).includes('new ConfiguredRoomAliasResolver(foundation.rooms)') ||
      !production(required.composition).includes('await this.rooms.resolveRoomAlias(alias)') ||
      !production(required.rooms).includes('await this.bridge.resolveRoomAlias(binding.handle, alias)') ||
      !production(required.bridge).includes('matrixNativeAddon.resolveRoomAlias(handle, alias)'))
    throw Error('Configured Task14 production chain changed; no evaluator substitution permitted');
  const prefix = '@bundle:' + report.config.bundleName + '/' + report.config.moduleName + '/ets/';
  const config = { ...report.config, deadlineEpochMs: deadline, entryRoute: 'pages/StartChat',
    addressRoute: 'pages/StartChat', presenterLoadedByEntry: true,
    fullNativeProtocol: 'task14.full-nine-configured-sdk.v6',
    configuredRoomsModuleUrl: prefix + 'matrix/production/ConfiguredSessionRooms',
    nativeBridgeModuleUrl: prefix + 'nativebridge/AddonNativeMatrixBridge' };
  const caFile = process.env.TASK14_NATIVE_E2E_CA_DER;
  if (!caFile) throw Error('Task14 external Matrix TLS CA missing');
  const resolvedCA = fs.realpathSync(caFile);
  const rawRoot = path.join(work, 'entry/src/ohosTest/resources/rawfile');
  fs.mkdirSync(rawRoot, { recursive: true });
  const installedCA = path.join(rawRoot, 'task14-ca.der'); fs.copyFileSync(resolvedCA, installedCA);
  const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
  const moduleFile = path.join(work, 'entry/src/ohosTest/module.json5');
  const moduleConfig = json5.parse(read(moduleFile));
  const permissions = moduleConfig.module.requestPermissions || [];
  if (!permissions.some(item => item.name === 'ohos.permission.ACCESS_CERT_MANAGER'))
    permissions.push({ name: 'ohos.permission.ACCESS_CERT_MANAGER' });
  moduleConfig.module.requestPermissions = permissions;
  fs.writeFileSync(moduleFile, JSON.stringify(moduleConfig, null, 2) + '\n');
  const testRoot = path.join(work, 'entry/src/test'), bridge = bridgeSource();
  fs.writeFileSync(path.join(testRoot, 'Task14DeviceUi.js'), bridge);
  report.fixtures = report.fixtures.map(item => item.path.endsWith('/Task14DeviceUi.js') ?
    { ...item, sha256: hash(bridge), derivedBy: __filename } : item);
  for (const item of sources()) {
    if (fs.existsSync(path.join(testRoot, item.name))) throw Error('Refuse fixture collision: ' + item.name);
    fs.writeFileSync(path.join(testRoot, item.name), item.source);
    report.fixtures.push({ path: 'entry/src/test/' + item.name, source: __filename, sha256: hash(item.source) });
  }
  const observerPath = 'entry/src/test/Task14PageObserver.js';
  fs.writeFileSync(path.join(work, observerPath), pageObserverAlias);
  report.fixtures = report.fixtures.map(item => item.path === observerPath ?
    { ...item, sha256: hash(pageObserverAlias), derivedBy: __filename } : item);
  const suite = replace(read(report.suiteFile), JSON.stringify(JSON.stringify(report.config)),
    JSON.stringify(JSON.stringify(config)));
  fs.writeFileSync(report.suiteFile, suite);
  for (const item of report.production)
    if (hash(fs.readFileSync(path.join(work, item.path))) !== item.sha256) throw Error('Production changed');
  return { ...report, config, suiteSha256: hash(suite), protocol: config.fullNativeProtocol,
    e2e: { enabled: true, caSource: resolvedCA, caSha256: hash(fs.readFileSync(resolvedCA)),
      installedPath: path.relative(work, installedCA), testPermission: 'ohos.permission.ACCESS_CERT_MANAGER' },
    controlledBoundary: { page: required.page, composition: required.composition, rooms: required.rooms,
      bridge: required.bridge, externalLeaf: 'matrix_sdk::Client.resolve_room_alias',
      provider: 'evaluator-owned nonce-bound Matrix HTTPS server', applicationMethodsReplaced: false },
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) }, upstreamInstaller: report.installer,
    scope: 'Configured owner/UI through N-API/Rust Matrix SDK to external HTTPS provider' };
}

module.exports = { install, bridgeSource, sources, scalarSource, routesSource, deviceSuiteSource, pageObserverAlias };
