'use strict';
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const previous = require('../task14_full_native_v12/install.cjs');
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const replace = (text, old, next) => {
  if (text.split(old).length !== 2) throw Error('Task14 V13 derivation changed: ' + old);
  return text.replace(old, next);
};

function ownerSource() {
  let source = fs.readFileSync(path.join(__dirname, '../task14_full_native_v6/Task14JoinOwnerV7.js'), 'utf8');
  source = replace(source,
    `      Object.defineProperty(Bridge.prototype, 'resolveRoomAlias', { ...nativeDescriptor, value: function(handle, alias) {
        const parent = roomStack.at(-1);
        const call = { id: nativeCalls.length + 1, roomCallId: parent?.id, receiver: this,
          handle, alias, calledOriginal: false, returned: false };
        nativeCalls.push(call);
        if (!parent || parent.receiver !== active?.resolver?.rooms || parent.bridgeReceiver !== this || !ownNative(this))
          throw Error('Native bridge call did not originate from actual configured rooms');
        call.calledOriginal = true;`,
    `      Object.defineProperty(Bridge.prototype, 'resolveRoomAlias', { ...nativeDescriptor, value: function(handle, alias) {
        // ConfiguredSessionRooms awaits its binding before invoking the bridge, so
        // a synchronous call stack cannot survive to this continuation. Correlate
        // only an unambiguous pending call owned by the same page objects.
        const candidates = roomCalls.filter(item => item.receiver === active?.resolver?.rooms &&
          item.bridgeReceiver === this && item.alias === alias && item.calledOriginal && item.returned &&
          item.nativeCallId === undefined && item.settlement === undefined);
        const parent = candidates.length === 1 ? candidates[0] : undefined;
        const call = { id: nativeCalls.length + 1, roomCallId: parent?.id, receiver: this,
          handle, alias, calledOriginal: false, returned: false, correlationCandidates: candidates.length };
        nativeCalls.push(call);
        if (!parent || !ownRooms(parent.receiver) || !ownNative(this))
          throw Error('Native bridge call lacks one unambiguous async page-owned rooms origin');
        parent.nativeCallId = call.id;
        call.calledOriginal = true;`);
  source = source
    .replaceAll('Task14.configuredPageResolverEnteredV7', 'Task14.configuredPageResolverEnteredV8')
    .replaceAll('Task14.configuredRoomsEnteredV7', 'Task14.configuredRoomsEnteredV8')
    .replaceAll('Task14.originalNativeBridgeEnteredV7', 'Task14.originalNativeBridgeEnteredV8')
    .replaceAll('Task14.externalResolverRejectedV7', 'Task14.externalResolverRejectedV8')
    .replaceAll('task14.configured-native-sdk-provider.v7', 'task14.configured-native-sdk-provider.v8');
  return source;
}

function adapterSource() {
  return previous.adapterSource()
    .replace('evaluateTask14FullNativeV12', 'evaluateTask14FullNativeV13')
    .replaceAll('task14.full-nine-configured-sdk.v12', 'task14.full-nine-configured-sdk.v13')
    .replaceAll('fullNativeEpisodeV12', 'fullNativeEpisodeV13');
}

function bridgeSource() {
  return previous.bridgeSource()
    .replace("import { evaluateTask14FullNativeV12 } from './Task14FullNativeV12.adapter';",
      "import { evaluateTask14FullNativeV13 } from './Task14FullNativeV13.adapter';")
    .replace('return evaluateTask14FullNativeV12(args, config, ports, record);',
      'return evaluateTask14FullNativeV13(args, config, ports, record);');
}

function expectedFixtures() {
  return previous.expectedFixtures()
    .filter(item => !['Task14JoinOwnerV3.js', 'Task14FullNativeV12.adapter.js',
      'Task14DeviceUi.js'].includes(item.name))
    .concat([
      { name: 'Task14JoinOwnerV3.js', sha256: hash(ownerSource()) },
      { name: 'Task14FullNativeV13.adapter.js', sha256: hash(adapterSource()) },
      { name: 'Task14DeviceUi.js', sha256: hash(bridgeSource()) }
    ]);
}

function install(work, options = {}) {
  const report = previous.install(work, options);
  const testRoot = path.join(work, 'entry/src/test');
  const oldConfig = report.config;
  const config = { ...oldConfig, fullNativeProtocol: 'task14.full-nine-configured-sdk.v13' };
  const owner = ownerSource(), adapter = adapterSource(), bridge = bridgeSource();
  fs.writeFileSync(path.join(testRoot, 'Task14JoinOwnerV3.js'), owner);
  fs.rmSync(path.join(testRoot, 'Task14FullNativeV12.adapter.js'));
  fs.writeFileSync(path.join(testRoot, 'Task14FullNativeV13.adapter.js'), adapter);
  fs.writeFileSync(path.join(testRoot, 'Task14DeviceUi.js'), bridge);
  const suite = replace(fs.readFileSync(report.suiteFile, 'utf8'), JSON.stringify(JSON.stringify(oldConfig)),
    JSON.stringify(JSON.stringify(config)));
  fs.writeFileSync(report.suiteFile, suite);
  const replacements = new Map(expectedFixtures().map(item => [item.name, item]));
  const fixtures = report.fixtures
    .filter(item => path.basename(item.path) !== 'Task14FullNativeV12.adapter.js')
    .map(item => replacements.has(path.basename(item.path)) ?
      { ...item, sha256: replacements.get(path.basename(item.path)).sha256, derivedBy: __filename } : item);
  fixtures.push({ path: 'entry/src/test/Task14FullNativeV13.adapter.js', source: __filename,
    sha256: hash(adapter), derivedBy: __filename });
  for (const item of report.production) {
    if (hash(fs.readFileSync(path.join(work, item.path))) !== item.sha256) throw Error('Production changed');
  }
  return { ...report, config, fixtures, suiteSha256: hash(suite), protocol: config.fullNativeProtocol,
    controlledBoundary: { ...report.controlledBoundary,
      asyncCorrelation: 'unique pending call with same page-owned rooms, bridge, and alias' },
    predecessor: { protocol: report.protocol, installer: report.installer },
    installer: { file: __filename, sha256: hash(fs.readFileSync(__filename)) } };
}

module.exports = { install, e2eSource: previous.e2eSource, coreSource: previous.coreSource,
  ownerSource, adapterSource, bridgeSource, expectedFixtures,
  pageObserverAlias: previous.pageObserverAlias };
