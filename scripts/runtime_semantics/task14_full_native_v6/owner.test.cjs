'use strict';
const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const source = path.join(__dirname, 'Task14JoinOwnerV7.js');
function load() {
  const result = ts.transpileModule(fs.readFileSync(source, 'utf8'), { fileName: source,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } });
  const module = { exports: {} };
  vm.runInNewContext('(function(module,exports){' + result.outputText + '\n})',
    { console, Promise, Error, JSON, Object, WeakMap, WeakSet, Set }, { filename: source })(module, module.exports);
  return module.exports;
}
function fixture() {
  let page = 0, rooms = 0, native = 0, release;
  class AddonNativeMatrixBridge { resolveRoomAlias() { native++; return new Promise(resolve => { release = resolve; }); } }
  class ConfiguredSessionRooms { constructor(bridge) { this.bridge = bridge; }
    async resolveRoomAlias(alias) { rooms++; const result = await this.bridge.resolveRoomAlias(47, alias);
      if (!result.ok && result.error?.code === 'room_not_found') return undefined;
      if (!result.ok) throw Error(result.error?.code); return JSON.parse(result.value); } }
  class ConfiguredRoomAliasResolver { constructor(value) { this.rooms = value; }
    async resolveRoomAlias(alias) { page++; return this.rooms.resolveRoomAlias(alias); } }
  class JoinRoomByAddressPresenter { constructor(resolver) { this.resolver = resolver;
      this.navigator = { addressVisible: true, openRoom() {} }; this.address = ''; this.addressState = 'unknown'; }
    visibleAddressState() { return this.addressState; }
    updateAddress(alias) { this.address = alias; this.addressState = 'resolving';
      return this.resolver.resolveRoomAlias(alias).then(value => { this.resolvedRoom = value;
        this.addressState = value ? 'room_found' : 'room_not_found'; return value; }); } }
  return { AddonNativeMatrixBridge, ConfiguredSessionRooms, ConfiguredRoomAliasResolver,
    JoinRoomByAddressPresenter, finish: value => release(value), counts: () => ({ page, rooms, native }) };
}
test('observer calls original native bridge and provider control only releases network response', async () => {
  const api = load(), f = fixture(); let control;
  api.configureTask14ConfiguredNamespacesV7({ ConfiguredSessionRooms: f.ConfiguredSessionRooms },
    { AddonNativeMatrixBridge: f.AddonNativeMatrixBridge });
  const observer = api.installTask14JoinOwnerV7({ JoinRoomByAddressPresenter: f.JoinRoomByAddressPresenter },
    async (kind, value) => { control = { kind, value }; f.finish({ ok: true, error: null,
      value: JSON.stringify({ roomId: value.expectedRoomId, servers: value.expectedServers }) });
      return { released: true }; });
  observer.bindExternalResolver();
  const presenter = new f.JoinRoomByAddressPresenter(new f.ConfiguredRoomAliasResolver(
    new f.ConfiguredSessionRooms(new f.AddonNativeMatrixBridge())));
  presenter.visibleAddressState(); const pending = presenter.updateAddress('#room:unit.test');
  const request = observer.read().resolverRequests[0];
  assert.equal(request.externalLeaf, 'matrix_sdk::Client.resolve_room_alias');
  await observer.resolveExternal(request.id, { roomId: '!id:unit.test', servers: ['via.unit.test'] });
  assert.deepEqual(await pending, { roomId: '!id:unit.test', servers: ['via.unit.test'] });
  assert.deepEqual(f.counts(), { page: 1, rooms: 1, native: 1 });
  assert.equal(control.kind, 'release');
  assert.equal(control.value.alias, '#room:unit.test');
  assert.equal(control.value.expectedOutcome, 'success');
  const state = observer.read();
  assert.equal(state.originalBridgeCalls[0].calledOriginal, true);
  assert.equal(state.configuredRoomCalls[0].calledOriginal, true);
  assert.equal(state.nativeBridgeCalls[0].calledOriginal, true);
  observer.dispose();
});
