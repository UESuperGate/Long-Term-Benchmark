'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const previous = require('../task14_full_native_v17/install.cjs');
const ownerBase = require('../task14_full_native_v15/install.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');

function replaceOnce(source, before, after) {
  if (source.split(before).length !== 2) throw Error('Task14 V18 derivation changed: ' + before);
  return source.replace(before, after);
}

function ownerSource() {
  return replaceOnce(ownerBase.ownerSource(),
    `    async providerStatus() { return providerControl('status', {}); },`,
    `    async releaseProvider(alias) {
      const receipt = await providerControl('release', { alias });
      record({ method: 'Task14.providerRequestReleasedV18', alias,
        providerReceipt: clone(receipt), externalLeaf: 'matrix_sdk::Client.resolve_room_alias' });
      return receipt;
    },
    async providerStatus() { return providerControl('status', {}); },`);
}

function routesSource() {
  let source = previous.routesSource()
    .replace('runTask14ConfiguredRoutesV17', 'runTask14ConfiguredRoutesV18')
    .replaceAll('task14.configured-routes.v17', 'task14.configured-routes.v18')
    .replaceAll('configuredRoutesEpisodeV17', 'configuredRoutesEpisodeV18');
  source = replaceOnce(source,
    `    const state = owner.read();
    const requests = state.resolverRequests?.filter(row => row.alias === alias && row.samePageResolver && !row.settled) || [];
    const external = await providerStatus();
    const held = external.held?.filter(row => row.caseId === spec.caseId && row.alias === alias) || [];
    if (state.available && requests.length === 1 && held.length === 1) {
      return { state, request: requests[0], held: held[0] };
    }`,
    `    const state = owner.read();
    const calls = state.calls?.filter(row => row.instanceId === state.instanceId &&
      row.method === 'resolveWithTimeout' && row.args?.[0] === alias) || [];
    const external = await providerStatus();
    const held = external.held?.filter(row => row.caseId === spec.caseId && row.alias === alias) || [];
    if (state.available && calls.length === 1 && held.length === 1) {
      return { state, ownerCall: calls[0], held: held[0] };
    }`);
  source = source.replaceAll('Own configured resolver and nonce-bound provider request were not jointly held; NS',
    'Original page-owner resolveWithTimeout and nonce-bound provider request were not jointly held; NS');
  source = replaceOnce(source,
    `      await owner.resolveExternal(pending.request.id, { roomId: spec.given.roomId, servers: spec.given.servers });`,
    `      await owner.releaseProvider(alias);`);
  source = replaceOnce(source,
    `    const requestCount = owner.read().resolverRequests.length;`,
    `    const requestCount = owner.read().calls.filter(row => row.instanceId === ownerId &&
      row.method === 'resolveWithTimeout' && row.args?.[0] === alias).length;`);
  source = replaceOnce(source,
    `      await owner.resolveExternal(pending.request.id, { roomId: spec.event.roomId, servers: spec.event.servers });`,
    `      await owner.releaseProvider(alias);`);
  source = replaceOnce(source,
    `      await owner.settle(pending.request.id);`,
    `      await owner.releaseProvider(alias);`);
  source = replaceOnce(source,
    `        passed: state.resolverRequests.length === requestCount && state.navigationCount === 1 &&
          after.routeName === 'pages/Room' && after.controls.roomId?.text === spec.event.roomId,
        observed: { before: requestCount, after: state.resolverRequests.length,
          navigationCount: state.navigationCount, routeName: after.routeName,`,
    `        passed: state.calls.filter(row => row.instanceId === ownerId && row.method === 'resolveWithTimeout' &&
          row.args?.[0] === alias).length === requestCount && state.navigationCount === 1 &&
          after.routeName === 'pages/Room' && after.controls.roomId?.text === spec.event.roomId,
        observed: { before: requestCount,
          after: state.calls.filter(row => row.instanceId === ownerId && row.method === 'resolveWithTimeout' &&
            row.args?.[0] === alias).length,
          navigationCount: state.navigationCount, routeName: after.routeName,`);
  return source;
}

function adapterSource() {
  let source = previous.adapterSource()
    .replace("import { runTask14ConfiguredRoutesV17 } from './Task14ConfiguredRoutesV17.suite';",
      "import { runTask14ConfiguredRoutesV18 } from './Task14ConfiguredRoutesV18.suite';")
    .replace('evaluateTask14FullNativeV17', 'evaluateTask14FullNativeV18')
    .replaceAll('task14.full-nine-configured-sdk.v17', 'task14.full-nine-configured-sdk.v18')
    .replaceAll('fullNativeEpisodeV17', 'fullNativeEpisodeV18');
  source = replaceOnce(source,
    `raw.transition = await runTask14ConfiguredRoutesV17(spec, config, session, owner,
      () => owner.providerStatus(), emit, args.trace);`,
    `raw.transition = await runTask14ConfiguredRoutesV18(spec, config, session, owner,
      () => owner.providerStatus(), emit, args.trace);`);
  source = replaceOnce(source,
    `  const transition = raw.transition;
  if (transition && transition.eventExecuted === undefined) {`,
    `  const transition = raw.transition;
  if (transition && transition.failure === undefined && !transition.unsupported &&
      Array.isArray(transition.unsupportedInvariants) && transition.unsupportedInvariants.length === 0) {
    transition.failure = null;
  }
  if (transition && transition.eventExecuted === undefined) {`);
  return source;
}

function bridgeSource() {
  return previous.bridgeSource()
    .replace("import { evaluateTask14FullNativeV17 } from './Task14FullNativeV17.adapter';",
      "import { evaluateTask14FullNativeV18 } from './Task14FullNativeV18.adapter';")
    .replace('return evaluateTask14FullNativeV17(args, config, ports, record);',
      'return evaluateTask14FullNativeV18(args, config, ports, record);');
}

function expectedFixtures() {
  return previous.expectedFixtures()
    .filter(item => !['Task14JoinOwnerV3.js', 'Task14ConfiguredRoutesV17.suite.js',
      'Task14FullNativeV17.adapter.js', 'Task14DeviceUi.js'].includes(item.name))
    .concat([
      { name: 'Task14JoinOwnerV3.js', sha256: hash(ownerSource()) },
      { name: 'Task14ConfiguredRoutesV18.suite.js', sha256: hash(routesSource()) },
      { name: 'Task14FullNativeV18.adapter.js', sha256: hash(adapterSource()) },
      { name: 'Task14DeviceUi.js', sha256: hash(bridgeSource()) }
    ]);
}

function install(work, options = {}) {
  const report = previous.install(work, options);
  const testRoot = path.join(work, 'entry/src/test');
  const oldConfig = report.config;
  const config = { ...oldConfig, fullNativeProtocol: 'task14.full-nine-configured-sdk.v18' };
  const owner = ownerSource(), routes = routesSource(), adapter = adapterSource(), bridge = bridgeSource();
  fs.writeFileSync(path.join(testRoot, 'Task14JoinOwnerV3.js'), owner);
  fs.rmSync(path.join(testRoot, 'Task14ConfiguredRoutesV17.suite.js'));
  fs.rmSync(path.join(testRoot, 'Task14FullNativeV17.adapter.js'));
  fs.writeFileSync(path.join(testRoot, 'Task14ConfiguredRoutesV18.suite.js'), routes);
  fs.writeFileSync(path.join(testRoot, 'Task14FullNativeV18.adapter.js'), adapter);
  fs.writeFileSync(path.join(testRoot, 'Task14DeviceUi.js'), bridge);
  const suite = replaceOnce(fs.readFileSync(report.suiteFile, 'utf8'), JSON.stringify(JSON.stringify(oldConfig)),
    JSON.stringify(JSON.stringify(config)));
  fs.writeFileSync(report.suiteFile, suite);
  const replacements = new Map(expectedFixtures().map(item => [item.name, item]));
  const fixtures = report.fixtures
    .filter(item => !['Task14ConfiguredRoutesV17.suite.js',
      'Task14FullNativeV17.adapter.js'].includes(path.basename(item.path)))
    .map(item => replacements.has(path.basename(item.path)) ?
      { ...item, sha256: replacements.get(path.basename(item.path)).sha256, derivedBy: __filename } : item);
  for (const [name, source] of [['Task14ConfiguredRoutesV18.suite.js', routes],
    ['Task14FullNativeV18.adapter.js', adapter]]) {
    if (!fixtures.some(item => path.basename(item.path) === name)) fixtures.push({
      path: 'entry/src/test/' + name, source: __filename, sha256: hash(source), derivedBy: __filename
    });
  }
  for (const item of report.production) {
    if (hash(fs.readFileSync(path.join(work, item.path))) !== item.sha256) throw Error('Production changed');
  }
  return { ...report, config, fixtures, suiteSha256: hash(suite), protocol: config.fullNativeProtocol,
    controlledBoundary: { ...report.controlledBoundary,
      asyncAdmission: 'same original page-owner resolveWithTimeout call plus nonce-bound provider hold',
      externalSettlement: 'real provider /__task14/release response, never local state replacement',
      legacySchemaNormalization: 'missing failure is normalized only with empty unsupportedInvariants' },
    predecessor: { protocol: report.protocol, installer: report.installer },
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) } };
}

module.exports = { install, ownerSource, routesSource, adapterSource, bridgeSource,
  expectedFixtures, scalarSource: previous.scalarSource, e2eSource: previous.e2eSource,
  pageObserverAlias: previous.pageObserverAlias };
