'use strict';
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../../..');
const native = path.join(root, 'state_tests/runtime/arkts/native');
const finalV18 = require('../task14_full_native_v18/install.cjs');
const preparedCore = require('../task14_full_native_v12/install.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const read = file => fs.readFileSync(file, 'utf8');

function replaceOnce(source, before, after) {
  if (source.split(before).length !== 2) throw new Error('Task14 candidate V19 hook changed: ' + before);
  return source.replace(before, after);
}

function suiteSource() { return read(path.join(__dirname, 'Task14CandidateV19.suite.js')); }
function adapterSource() { return read(path.join(__dirname, 'Task14CandidateV19.adapter.js')); }
function e2eSource() {
  return replaceOnce(finalV18.e2eSource(),
    `    if (matches.length !== 2) throw new Error('Expected one Task14 self-signed certificate list item');
    return matches[0];`,
    `    if (matches.length === 0) throw new Error('Task14 evaluator certificate list item missing');
    return matches[0];`);
}
function coreSource() { return preparedCore.coreSource(); }

function bridgeSource() {
  const contract = JSON.parse(read(path.join(root, 'benchmark_tasks/14_join_room_by_address/transitions.json')));
  let code = read(path.join(native, 'Task14DeviceUi.js'));
  code = "import fs from '@ohos.file.fs';\nimport fileUri from '@ohos.file.fileuri';\n" +
    "import certificateManager from '@ohos.security.certManager';\nimport wantConstant from '@ohos.app.ability.wantConstant';\n" +
    "import http from '@ohos.net.http';\nimport matrixNativeAddon from 'libmatrix_native.so';\n" +
    "import { task14NativeE2EConfig, createTask14NativeE2E } from './Task14NativeE2E';\n" +
    "import { evaluateTask14CandidateV19 } from './Task14CandidateV19.adapter';\n" + code;
  code = replaceOnce(code, 'TASK14_CASES[caseSpec.caseId] !== caseSpec.key',
    JSON.stringify(Object.fromEntries(contract.cases.map(item => [item.caseId, item.key]))) +
      '[caseSpec.caseId] !== caseSpec.key');
  const begin = "    return config.realFlowV2 === true && caseSpec.caseId === 'jr_state_001_entry_opens_address_flow' ?";
  const finish = 'evaluateTask14UI(args, config, ports, record);';
  const start = code.indexOf(begin), end = code.indexOf(finish, start) + finish.length;
  if (start < 0 || end < start) throw new Error('Task14 candidate V19 dispatch hook changed');
  code = code.slice(0, start) + '    return evaluateTask14CandidateV19(args, config, ports, record);' + code.slice(end);
  code = replaceOnce(code, 'bridge.evaluateTask14UI = async args => {', `bridge.evaluateTask14UI = async args => {
    const appContext = abilityDelegatorRegistry.getAbilityDelegator().getAppContext();
    const e2e = createTask14NativeE2E(task14NativeE2EConfig(abilityDelegatorRegistry.getArguments().parameters),
      appContext.getApplicationContext(), appContext.createModuleContext('entry_test'), ports.createDriver(), ON,
      { fs, fileUri, certificateManager, wantConstant, http, matrixNativeAddon,
        abilityDelegator: abilityDelegatorRegistry.getAbilityDelegator() });
    await e2e.prepare(config.bundleName);
    ports.providerControl = e2e.control;
    bridge.task14E2E = e2e;`);
  code = replaceOnce(code, 'bridge.dispose = async function() {', `bridge.dispose = async function() {
    if (bridge.task14E2E) { await bridge.task14E2E.cleanup(); delete bridge.task14E2E; }`);
  return code;
}

function expectedFixtures() {
  const replacements = new Map([
    ['Task14DeviceUi.js', bridgeSource()], ['Task14DeviceUi.core.js', coreSource()],
    ['Task14NativeE2E.js', e2eSource()], ['Task14CandidateV19.suite.js', suiteSource()],
    ['Task14CandidateV19.adapter.js', adapterSource()]
  ]);
  const base = ['Task14DeviceUi.js', 'Task14DeviceUi.d.ts', 'Task14DeviceUi.core.js',
    'Task14DeviceUi.suite.js', 'Task14DeviceUi.adapter.js', 'Task14PageObserver.js',
    'Task14AncestorObserver.js', 'Task14FrameAcquisition.js', 'Task14RealFlowV2Observer.js',
    'Task14RealFlowV2Frame.js', 'Task14RealFlowV2.suite.js', 'Task14RealFlowV2.adapter.js'];
  return base.concat(['Task14NativeE2E.js', 'Task14CandidateV19.suite.js', 'Task14CandidateV19.adapter.js'])
    .map(name => ({ name, sha256: hash(replacements.has(name) ? replacements.get(name) :
      fs.readFileSync(path.join(native, name))) })).sort((a, b) => a.name.localeCompare(b.name));
}

function requireChain(work) {
  const files = {
    page: 'entry/src/main/ets/pages/StartChat.ets',
    view: 'entry/src/main/ets/components/JoinRoomByAddressView.ets',
    owner: 'entry/src/main/ets/features/JoinRoomByAddressOwner.ets',
    service: 'entry/src/main/ets/matrix/production/ConfiguredStartChatService.ets',
    rooms: 'entry/src/main/ets/matrix/production/ConfiguredSessionRooms.ets',
    bridge: 'entry/src/main/ets/nativebridge/AddonNativeMatrixBridge.ets',
    routes: 'entry/src/main/ets/composition/StartChatRoutes.ets'
  };
  for (const file of Object.values(files)) if (!fs.existsSync(path.join(work, file)))
    throw new Error('Candidate Task14 production boundary missing: ' + file);
  const source = key => read(path.join(work, files[key]));
  const checks = [
    [source('page'), 'JoinRoomByAddressView({'], [source('page'), 'openAddressFlow()'],
    [source('view'), 'new JoinRoomByAddressOwner(runtime.foundation.startChat, new StartChatRoutes(runtime))'],
    [source('owner'), 'this.service.resolveRoomAddress(alias)'],
    [source('service'), 'this.rooms.resolveRoomAlias(parsed.alias)'],
    [source('rooms'), 'this.bridge.resolveRoomAlias(binding.handle, alias)'],
    [source('bridge'), 'matrixNativeAddon.resolveRoomAlias(handle, alias)'],
    [source('routes'), "router.replaceUrl({ url: 'pages/Room', params: params })"],
    [source('routes'), 'serverNames: servers.slice()']
  ];
  for (const [text, token] of checks) if (!text.includes(token))
    throw new Error('Candidate Task14 production chain changed: ' + token);
  return files;
}

function install(work, options = {}) {
  const deadline = Number(options.deadlineEpochMs || process.env.LTB_TASK14_ROUTE_DEADLINE_EPOCH_MS);
  if (!Number.isFinite(deadline) || deadline <= Date.now()) throw new Error('Whole task deadline unavailable');
  const report = require(path.join(native, 'Task14DeviceUi.install.cjs')).install(work,
    { ...options, mode: 'after-page-ready', presenterClass: 'JoinRoomByAddressOwner' });
  const chain = requireChain(work);
  const prefix = '@bundle:' + report.config.bundleName + '/' + report.config.moduleName + '/ets/';
  const config = { ...report.config, deadlineEpochMs: deadline, entryRoute: 'pages/StartChat',
    addressRoute: 'pages/StartChat', presenterLoadedByEntry: true, preparedForegroundEntry: true,
    fullNativeProtocol: 'task14.candidate-native.v19',
    productionModuleUrl: prefix + 'features/JoinRoomByAddressOwner' };
  const caFile = process.env.TASK14_NATIVE_E2E_CA_DER;
  if (!caFile) throw new Error('Task14 external Matrix TLS CA missing');
  const resolvedCA = fs.realpathSync(caFile);
  const rawRoot = path.join(work, 'entry/src/ohosTest/resources/rawfile');
  fs.mkdirSync(rawRoot, { recursive: true });
  const installedCA = path.join(rawRoot, 'task14-ca.der');
  fs.copyFileSync(resolvedCA, installedCA);
  const json5 = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
  const moduleFile = path.join(work, 'entry/src/ohosTest/module.json5');
  const moduleConfig = json5.parse(read(moduleFile));
  const permissions = moduleConfig.module.requestPermissions || [];
  if (!permissions.some(item => item.name === 'ohos.permission.ACCESS_CERT_MANAGER'))
    permissions.push({ name: 'ohos.permission.ACCESS_CERT_MANAGER' });
  moduleConfig.module.requestPermissions = permissions;
  fs.writeFileSync(moduleFile, JSON.stringify(moduleConfig, null, 2) + '\n');

  const testRoot = path.join(work, 'entry/src/test');
  const generated = new Map([
    ['Task14DeviceUi.js', bridgeSource()], ['Task14DeviceUi.core.js', coreSource()],
    ['Task14NativeE2E.js', e2eSource()], ['Task14CandidateV19.suite.js', suiteSource()],
    ['Task14CandidateV19.adapter.js', adapterSource()]
  ]);
  for (const [name, source] of generated) fs.writeFileSync(path.join(testRoot, name), source);
  const fixtureNames = new Set(generated.keys());
  report.fixtures = report.fixtures.map(item => fixtureNames.has(path.basename(item.path)) ?
    { ...item, sha256: hash(generated.get(path.basename(item.path))), derivedBy: __filename } : item);
  for (const name of ['Task14NativeE2E.js', 'Task14CandidateV19.suite.js', 'Task14CandidateV19.adapter.js'])
    if (!report.fixtures.some(item => path.basename(item.path) === name)) report.fixtures.push({
      path: 'entry/src/test/' + name, source: __filename, sha256: hash(generated.get(name)), derivedBy: __filename });
  const suite = replaceOnce(read(report.suiteFile), JSON.stringify(JSON.stringify(report.config)),
    JSON.stringify(JSON.stringify(config)));
  fs.writeFileSync(report.suiteFile, suite);
  for (const item of report.production)
    if (hash(fs.readFileSync(path.join(work, item.path))) !== item.sha256) throw new Error('Production changed');
  return { ...report, config, fixtures: report.fixtures, suiteSha256: hash(suite),
    protocol: config.fullNativeProtocol,
    e2e: { enabled: true, caSource: resolvedCA, caSha256: hash(fs.readFileSync(resolvedCA)),
      installedPath: path.relative(work, installedCA), testPermission: 'ohos.permission.ACCESS_CERT_MANAGER' },
    controlledBoundary: { production: chain, externalLeaf: 'matrix_sdk::Client.resolve_room_alias',
      provider: 'evaluator-owned nonce-bound Matrix HTTPS server', applicationMethodsReplaced: false,
      verdictSource: 'physical ArkUI, router state/params, and provider transcript' },
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) },
    upstreamInstaller: report.installer,
    scope: 'All nine canonical cases against an arbitrary candidate source; no production substitution' };
}

module.exports = { install, suiteSource, adapterSource, e2eSource, coreSource, bridgeSource,
  expectedFixtures, requireChain };
