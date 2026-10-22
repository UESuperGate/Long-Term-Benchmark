'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const previous = require('../task14_full_native_v15/install.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const read = name => fs.readFileSync(path.join(__dirname, name), 'utf8');

function replaceOnce(source, before, after) {
  if (source.split(before).length !== 2) throw Error('Task14 V16 derivation changed: ' + before);
  return source.replace(before, after);
}

function scalarSource() { return read('Task14ScalarCasesV16.js'); }
function routesSource() { return read('Task14ConfiguredRoutesV16.suite.js'); }
function entrySource() { return read('Task14EntryV16.suite.js'); }

function adapterSource() {
  let source = previous.adapterSource()
    .replace("import { runTask14ScalarCasesV15 } from './Task14ScalarCasesV15';",
      "import { runTask14ScalarCasesV16 } from './Task14ScalarCasesV16';")
    .replace("import { runTask14RealRoutesV6 } from './Task14RealRoutesV6.suite';",
      "import { runTask14ConfiguredRoutesV16 } from './Task14ConfiguredRoutesV16.suite';")
    .replace("import { runTask14RealFlowV2 } from './Task14RealFlowV2.suite';",
      "import { runTask14EntryV16 } from './Task14EntryV16.suite';")
    .replace('evaluateTask14FullNativeV15', 'evaluateTask14FullNativeV16')
    .replaceAll('task14.full-nine-configured-sdk.v15', 'task14.full-nine-configured-sdk.v16')
    .replaceAll('fullNativeEpisodeV15', 'fullNativeEpisodeV16');
  source = replaceOnce(source,
    `raw.transition = await runTask14ScalarCasesV15(spec, config, session, owner, clock, emit,
      () => owner.providerStatus());`,
    `raw.transition = await runTask14ScalarCasesV16(spec, config, session, owner, clock, emit,
      () => owner.providerStatus());`);
  source = replaceOnce(source,
    `raw.transition = await runTask14RealFlowV2(spec, config, session, ports.importModule, emit, args.trace);`,
    `raw.transition = await runTask14EntryV16(spec, config, session, ports.importModule, emit, args.trace);`);
  source = replaceOnce(source,
    `else if (['invalid_after_continue', 'not_found_recovers'].includes(spec.key))
      raw.transition = await runTask14TransitionV6(spec, config, session, ports.importModule, emit, args.trace);
    else raw.transition = await runTask14RealRoutesV6(spec, config, session, ports.importModule, emit, args.trace);`,
    `else if (spec.key === 'invalid_after_continue')
      raw.transition = await runTask14TransitionV6(spec, config, session, ports.importModule, emit, args.trace);
    else raw.transition = await runTask14ConfiguredRoutesV16(spec, config, session, owner,
      () => owner.providerStatus(), emit, args.trace);`);
  source = replaceOnce(source,
    `  return { observed: {}, invariantChecks: [], evidence: [{ fullNativeEpisodeV16: raw }],
    unsupported: 'Fresh configured SDK episode requires independent admission',
    observationLevel: 'native_candidate_ui_and_matrix_sdk_https' };`,
    `  const transition = raw.transition;
  if (transition && transition.eventExecuted === undefined) {
    transition.eventExecuted = raw.actions.length > 0 && raw.actions.every(item => item.executed === true);
  }
  const invariantDescriptions = new Set((transition?.invariantChecks || []).map(item => item.description));
  const admitted = raw.failure === null && raw.entryExecuted === true && raw.released === true &&
    transition && transition.failure === null && !transition.unsupported && transition.eventExecuted === true &&
    transition.observed && Object.keys(transition.observed).length > 0 &&
    raw.actions.length > 0 && raw.actions.every(item => item.executed === true) &&
    (args.caseSpec.invariants || []).every(item => invariantDescriptions.has(item));
  if (!admitted) return { observed: {}, invariantChecks: [], evidence: [{ fullNativeEpisodeV16: raw }],
    unsupported: 'Fresh configured SDK episode failed independent admission',
    observationLevel: 'native_candidate_ui_and_matrix_sdk_https' };
  return { observed: clone(transition.observed), invariantChecks: clone(transition.invariantChecks),
    evidence: [{ fullNativeEpisodeV16: raw }],
    observationLevel: 'native_candidate_ui_and_matrix_sdk_https' };`);
  return source;
}

function bridgeSource() {
  return previous.bridgeSource()
    .replace("import { evaluateTask14FullNativeV15 } from './Task14FullNativeV15.adapter';",
      "import { evaluateTask14FullNativeV16 } from './Task14FullNativeV16.adapter';")
    .replace('return evaluateTask14FullNativeV15(args, config, ports, record);',
      'return evaluateTask14FullNativeV16(args, config, ports, record);');
}

function expectedFixtures() {
  return previous.expectedFixtures()
    .filter(item => !['Task14ScalarCasesV15.js', 'Task14FullNativeV15.adapter.js',
      'Task14DeviceUi.js'].includes(item.name))
    .concat([
      { name: 'Task14ScalarCasesV16.js', sha256: hash(scalarSource()) },
      { name: 'Task14ConfiguredRoutesV16.suite.js', sha256: hash(routesSource()) },
      { name: 'Task14EntryV16.suite.js', sha256: hash(entrySource()) },
      { name: 'Task14FullNativeV16.adapter.js', sha256: hash(adapterSource()) },
      { name: 'Task14DeviceUi.js', sha256: hash(bridgeSource()) }
    ]);
}

function install(work, options = {}) {
  const report = previous.install(work, options);
  const testRoot = path.join(work, 'entry/src/test');
  const oldConfig = report.config;
  const config = { ...oldConfig, fullNativeProtocol: 'task14.full-nine-configured-sdk.v16' };
  const scalar = scalarSource(), routes = routesSource(), entry = entrySource();
  const adapter = adapterSource(), bridge = bridgeSource();
  fs.rmSync(path.join(testRoot, 'Task14ScalarCasesV15.js'));
  fs.writeFileSync(path.join(testRoot, 'Task14ScalarCasesV16.js'), scalar);
  fs.writeFileSync(path.join(testRoot, 'Task14ConfiguredRoutesV16.suite.js'), routes);
  fs.writeFileSync(path.join(testRoot, 'Task14EntryV16.suite.js'), entry);
  fs.rmSync(path.join(testRoot, 'Task14FullNativeV15.adapter.js'));
  fs.writeFileSync(path.join(testRoot, 'Task14FullNativeV16.adapter.js'), adapter);
  fs.writeFileSync(path.join(testRoot, 'Task14DeviceUi.js'), bridge);
  const suite = replaceOnce(fs.readFileSync(report.suiteFile, 'utf8'), JSON.stringify(JSON.stringify(oldConfig)),
    JSON.stringify(JSON.stringify(config)));
  fs.writeFileSync(report.suiteFile, suite);
  const replacements = new Map(expectedFixtures().map(item => [item.name, item]));
  const fixtures = report.fixtures
    .filter(item => !['Task14ScalarCasesV15.js', 'Task14FullNativeV15.adapter.js'].includes(path.basename(item.path)))
    .map(item => replacements.has(path.basename(item.path)) ?
      { ...item, sha256: replacements.get(path.basename(item.path)).sha256, derivedBy: __filename } : item);
  for (const [name, source] of [['Task14ScalarCasesV16.js', scalar],
    ['Task14ConfiguredRoutesV16.suite.js', routes], ['Task14EntryV16.suite.js', entry],
    ['Task14FullNativeV16.adapter.js', adapter]]) {
    if (!fixtures.some(item => path.basename(item.path) === name)) fixtures.push({
      path: 'entry/src/test/' + name, source: __filename, sha256: hash(source), derivedBy: __filename
    });
  }
  for (const item of report.production) {
    if (hash(fs.readFileSync(path.join(work, item.path))) !== item.sha256) throw Error('Production changed');
  }
  return { ...report, config, fixtures, suiteSha256: hash(suite), protocol: config.fullNativeProtocol,
    controlledBoundary: { ...report.controlledBoundary,
      admission: 'physical action + original owner + nonce provider + measured observed/invariants',
      activeRouteOwner: 'FinalAddressRouteOwner and physical pages/Room, never legacy ChatFeature routes' },
    predecessor: { protocol: report.protocol, installer: report.installer },
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) } };
}

module.exports = { install, scalarSource, routesSource, entrySource, adapterSource,
  bridgeSource, expectedFixtures, e2eSource: previous.e2eSource,
  pageObserverAlias: previous.pageObserverAlias };
