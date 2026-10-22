'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const previous = require('../task14_full_native_v16/install.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');

function replaceOnce(source, before, after) {
  if (source.split(before).length !== 2) throw Error('Task14 V17 derivation changed: ' + before);
  return source.replace(before, after);
}

function scalarSource() {
  let source = previous.scalarSource()
    .replace('runTask14ScalarCasesV16', 'runTask14ScalarCasesV17')
    .replaceAll('task14.same-page-scalar.v16', 'task14.same-page-scalar.v17');
  source = replaceOnce(source,
    'export async function runTask14ScalarCasesV17(spec, config, session, observer, clock, emit, providerStatus) {',
    'export async function runTask14ScalarCasesV17(spec, config, session, observer, clock, emit, providerStatus, trace = () => {}) {');
  source = replaceOnce(source,
    `    result.frames.push(clone(sample));
    return sample;`,
    `    result.frames.push(clone(sample));
    if (label === 'before:event' || label === 'after:event') trace(label, clone(sample));
    return sample;`);
  return source;
}

function routesSource() {
  let source = previous.routesSource()
    .replace('runTask14ConfiguredRoutesV16', 'runTask14ConfiguredRoutesV17')
    .replaceAll('task14.configured-routes.v16', 'task14.configured-routes.v17')
    .replaceAll('configuredRoutesEpisodeV16', 'configuredRoutesEpisodeV17');
  source = replaceOnce(source,
    `result.invariantChecks.push({ description: 'room navigation happens once', passed: opens.length === 1,
        observed: { openCalls: opens, routeName: after.routeName, renderedRoomId: after.controls.roomId?.text || null } });`,
    `result.invariantChecks.push({ description: 'room navigation happens once',
        passed: opens.length === 1 && after.routeName === 'pages/Room' &&
          after.controls.roomId?.text === spec.given.roomId,
        observed: { openCalls: opens, routeName: after.routeName,
          renderedRoomId: after.controls.roomId?.text || null } });`);
  source = replaceOnce(source,
    `result.invariantChecks.push({ description: 'continue does not issue a second alias-resolution request',
        passed: state.resolverRequests.length === requestCount,
        observed: { before: requestCount, after: state.resolverRequests.length } });`,
    `result.invariantChecks.push({ description: 'continue does not issue a second alias-resolution request',
        passed: state.resolverRequests.length === requestCount && state.navigationCount === 1 &&
          after.routeName === 'pages/Room' && after.controls.roomId?.text === spec.event.roomId,
        observed: { before: requestCount, after: state.resolverRequests.length,
          navigationCount: state.navigationCount, routeName: after.routeName,
          renderedRoomId: after.controls.roomId?.text || null } });`);
  return source;
}

function adapterSource() {
  let source = previous.adapterSource()
    .replace("import { runTask14ScalarCasesV16 } from './Task14ScalarCasesV16';",
      "import { runTask14ScalarCasesV17 } from './Task14ScalarCasesV17';")
    .replace("import { runTask14ConfiguredRoutesV16 } from './Task14ConfiguredRoutesV16.suite';",
      "import { runTask14ConfiguredRoutesV17 } from './Task14ConfiguredRoutesV17.suite';")
    .replace('evaluateTask14FullNativeV16', 'evaluateTask14FullNativeV17')
    .replaceAll('task14.full-nine-configured-sdk.v16', 'task14.full-nine-configured-sdk.v17')
    .replaceAll('fullNativeEpisodeV16', 'fullNativeEpisodeV17');
  source = replaceOnce(source,
    `raw.transition = await runTask14ScalarCasesV16(spec, config, session, owner, clock, emit,
      () => owner.providerStatus());`,
    `raw.transition = await runTask14ScalarCasesV17(spec, config, session, owner, clock, emit,
      () => owner.providerStatus(), args.trace);`);
  source = replaceOnce(source,
    `raw.transition = await runTask14ConfiguredRoutesV16(spec, config, session, owner,
      () => owner.providerStatus(), emit, args.trace);`,
    `raw.transition = await runTask14ConfiguredRoutesV17(spec, config, session, owner,
      () => owner.providerStatus(), emit, args.trace);`);
  return source;
}

function bridgeSource() {
  return previous.bridgeSource()
    .replace("import { evaluateTask14FullNativeV16 } from './Task14FullNativeV16.adapter';",
      "import { evaluateTask14FullNativeV17 } from './Task14FullNativeV17.adapter';")
    .replace('return evaluateTask14FullNativeV16(args, config, ports, record);',
      'return evaluateTask14FullNativeV17(args, config, ports, record);');
}

function expectedFixtures() {
  return previous.expectedFixtures()
    .filter(item => !['Task14ScalarCasesV16.js', 'Task14ConfiguredRoutesV16.suite.js',
      'Task14FullNativeV16.adapter.js', 'Task14DeviceUi.js'].includes(item.name))
    .concat([
      { name: 'Task14ScalarCasesV17.js', sha256: hash(scalarSource()) },
      { name: 'Task14ConfiguredRoutesV17.suite.js', sha256: hash(routesSource()) },
      { name: 'Task14FullNativeV17.adapter.js', sha256: hash(adapterSource()) },
      { name: 'Task14DeviceUi.js', sha256: hash(bridgeSource()) }
    ]);
}

function install(work, options = {}) {
  const report = previous.install(work, options);
  const testRoot = path.join(work, 'entry/src/test');
  const oldConfig = report.config;
  const config = { ...oldConfig, fullNativeProtocol: 'task14.full-nine-configured-sdk.v17' };
  const scalar = scalarSource(), routes = routesSource(), adapter = adapterSource(), bridge = bridgeSource();
  fs.rmSync(path.join(testRoot, 'Task14ScalarCasesV16.js'));
  fs.rmSync(path.join(testRoot, 'Task14ConfiguredRoutesV16.suite.js'));
  fs.rmSync(path.join(testRoot, 'Task14FullNativeV16.adapter.js'));
  fs.writeFileSync(path.join(testRoot, 'Task14ScalarCasesV17.js'), scalar);
  fs.writeFileSync(path.join(testRoot, 'Task14ConfiguredRoutesV17.suite.js'), routes);
  fs.writeFileSync(path.join(testRoot, 'Task14FullNativeV17.adapter.js'), adapter);
  fs.writeFileSync(path.join(testRoot, 'Task14DeviceUi.js'), bridge);
  const suite = replaceOnce(fs.readFileSync(report.suiteFile, 'utf8'), JSON.stringify(JSON.stringify(oldConfig)),
    JSON.stringify(JSON.stringify(config)));
  fs.writeFileSync(report.suiteFile, suite);
  const replacements = new Map(expectedFixtures().map(item => [item.name, item]));
  const fixtures = report.fixtures
    .filter(item => !['Task14ScalarCasesV16.js', 'Task14ConfiguredRoutesV16.suite.js',
      'Task14FullNativeV16.adapter.js'].includes(path.basename(item.path)))
    .map(item => replacements.has(path.basename(item.path)) ?
      { ...item, sha256: replacements.get(path.basename(item.path)).sha256, derivedBy: __filename } : item);
  for (const [name, source] of [['Task14ScalarCasesV17.js', scalar],
    ['Task14ConfiguredRoutesV17.suite.js', routes], ['Task14FullNativeV17.adapter.js', adapter]]) {
    if (!fixtures.some(item => path.basename(item.path) === name)) fixtures.push({
      path: 'entry/src/test/' + name, source: __filename, sha256: hash(source), derivedBy: __filename
    });
  }
  for (const item of report.production) {
    if (hash(fs.readFileSync(path.join(work, item.path))) !== item.sha256) throw Error('Production changed');
  }
  return { ...report, config, fixtures, suiteSha256: hash(suite), protocol: config.fullNativeProtocol,
    controlledBoundary: { ...report.controlledBoundary,
      checkpointAdmission: 'scalar before/after physical frames are forwarded to the canonical evaluator trace',
      roomRouteAdmission: 'navigation cases require a stable physical pages/Room render with canonical room_id' },
    predecessor: { protocol: report.protocol, installer: report.installer },
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) } };
}

module.exports = { install, scalarSource, routesSource, adapterSource, bridgeSource,
  expectedFixtures, e2eSource: previous.e2eSource, pageObserverAlias: previous.pageObserverAlias };
