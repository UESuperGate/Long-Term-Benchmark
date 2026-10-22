'use strict';
// OFFLINE UNIT TESTS ONLY. The N-API leaf below is a test double, NEVER native evidence.
const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const root = path.resolve(__dirname, '../../experiment_results/runtime_transition_20261021/task14_configured_client_native_v3');
const staged = path.join(root, 'staged'), ets = path.join(staged, 'entry/src/main/ets');
const before = path.join(root, 'before-source');
const clean = v => JSON.parse(JSON.stringify(v));
const data = v => ({ok: true, error: null, value: JSON.stringify(v)});
const failure = (code, nativeCode = 15) => ({ok: false, value: null, error: {code, nativeCode, message: code, retryable: true}});

function loadFactory(external) {
  const cache = new Map();
  function load(name) {
    name = path.normalize(name);
    if (cache.has(name)) return cache.get(name);
    const file = path.join(ets, name + '.ets'), source = fs.readFileSync(file, 'utf8');
    const result = ts.transpileModule(source, {fileName: file, reportDiagnostics: true,
      compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020}});
    assert.equal(result.diagnostics.some(row => row.category === ts.DiagnosticCategory.Error), false, name);
    const module = {exports: {}};
    cache.set(name, module.exports);
    vm.runInNewContext('(function(require,module,exports){' + result.outputText + '\n})',
      {Map, Set, Date, console, setTimeout, clearTimeout}, {filename: file})((specifier) => {
      if (specifier.startsWith('.')) return load(path.join(path.dirname(name), specifier));
      if (!(specifier in external)) throw Error('Unbound external module: ' + specifier);
      return {default: external[specifier]};
    }, module, module.exports);
    cache.set(name, module.exports);
    return module.exports;
  }
  return load;
}

function environment({session = true, abi = 4} = {}) {
  const calls = [];
  let joined = false;
  const addon = {
    getBridgeStatus: () => ({availability: 'ready', sdkLinked: true, abiVersion: abi, contractVersion: String(abi)}),
    async getClientStatus(handle) { calls.push(['status', handle]); return {ok: true, error: null, client: {handle, state: 'ready'}}; },
    async resolveRoomAlias(...args) { calls.push(['alias', ...args]); return data({roomId: '!returned:room-domain.unit', servers: ['b.unit:8448', 'a.unit', 'b.unit:8448']}); },
    async previewRoom(...args) { calls.push(['preview', ...args]); return data({roomId: '!returned:room-domain.unit', canonicalAlias: '#name:alias-domain.unit',
      name: 'Unit data, NOT a native room', topic: null, avatarUrl: null, joinedMembers: 2, membership: joined ? 'joined' : null}); },
    async joinRoom(...args) { calls.push(['join', ...args]); joined = true; return data({roomId: '!returned:room-domain.unit', membership: 'joined'}); },
    async loadTimeline(...args) { calls.push(['timeline', ...args]); return data({events: [], end: null}); }
  };
  const load = loadFactory({'libmatrix_native.so': addon}), Nav = load('appnav/RootNavigationStateMachine').RootNavigationStateMachine;
  const nav = new Nav();
  const metadata = {sessionId: '@unit:user-domain.unit', userId: '@unit:user-domain.unit', deviceId: 'UNIT',
    homeserverUrl: 'https://configured-client.unit/client-prefix', isTokenValid: true};
  function login(runtimeId = 'native:47') {
    const attempt = nav.beginAuthentication('password');
    assert.equal(nav.completeAuthentication(attempt, metadata, {sessionId: metadata.sessionId, runtimeId}), true);
  }
  if (session) login();
  const Bridge = load('nativebridge/AddonNativeMatrixBridge').AddonNativeMatrixBridge;
  const Rooms = load('matrix/production/ConfiguredSessionRooms').ConfiguredSessionRooms;
  const rooms = new Rooms(new Bridge(), nav);
  const Owner = load('features/ConfiguredRoomPageOwner').ConfiguredRoomPageOwner;
  return {load, nav, metadata, login, calls, addon, rooms, owner: new Owner(rooms)};
}

function nativeBoundary(source) {
  assert.match(source, /let client = client_for_handle\(handle\)\?/);
  assert.match(source, /client\.user_id\(\)\.is_none\(\)/);
  for (const expected of ['client.resolve_room_alias(&alias)', 'client.get_room_preview(&id, servers)',
    'client.join_room_by_id_or_alias(&id, &servers)']) assert.ok(source.includes(expected), expected);
  assert.doesNotMatch(source, /Client::builder|homeserver_url\(|reqwest::Client|https:\/\/.*alias|demo\.local|Fixture/);
  assert.match(source, /client_api_error_kind\(\)/);
}

test('all staged plain ArkTS sources parse offline, never claimed to be ArkVM compilation', () => {
  const files = [];
  function walk(p) { for (const name of fs.readdirSync(p)) { const q = path.join(p, name); if (fs.statSync(q).isDirectory()) walk(q); else if (q.endsWith('.ets')) files.push(q); } }
  walk(ets);
  for (const file of files) {
    const ast = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true);
    assert.deepEqual(ast.parseDiagnostics, [], file);
  }
  assert.ok(files.length >= 24);
});
test('SDK operations use configured authenticated registry Client, not new host/client', () => {
  nativeBoundary(fs.readFileSync(path.join(staged, 'native/matrix-sdk-bridge/src/task14.rs'), 'utf8'));
});
test('negative: replacing registry with a new Client breaks source admission', () => {
  const source = fs.readFileSync(path.join(staged, 'native/matrix-sdk-bridge/src/task14.rs'), 'utf8');
  assert.throws(() => nativeBoundary(source.replace('client_for_handle(handle)?', 'matrix_sdk::Client::builder().build()')));
});
test('negative: dropped SDK via arguments break source admission', () => {
  const source = fs.readFileSync(path.join(staged, 'native/matrix-sdk-bridge/src/task14.rs'), 'utf8');
  assert.throws(() => nativeBoundary(source.replace('client.join_room_by_id_or_alias(&id, &servers)', 'client.join_room_by_id_or_alias(&id, &[])')));
});
test('ABI 4 required across Rust, C header and ArkTS; no old binary copied', () => {
  assert.match(fs.readFileSync(path.join(staged, 'native/matrix-sdk-bridge/src/lib.rs'), 'utf8'), /ABI_VERSION: u32 = 4/);
  assert.match(fs.readFileSync(path.join(staged, 'entry/src/main/cpp/matrix_bridge_contract.h'), 'utf8'), /kContractVersion = "4"/);
  assert.match(fs.readFileSync(path.join(ets, 'nativebridge/NativeMatrixBridgeTypes.ets'), 'utf8'), /VERSION: string = '4'/);
  assert.equal(fs.existsSync(path.join(staged, 'native/matrix-sdk-bridge/target')), false);
});
test('native library is the actual Addon import and N-API dispatch covers all three exports', () => {
  const addon = fs.readFileSync(path.join(ets, 'nativebridge/AddonNativeMatrixBridge.ets'), 'utf8');
  assert.match(addon, /import matrixNativeAddon from 'libmatrix_native.so'/);
  const cpp = fs.readFileSync(path.join(staged, 'entry/src/main/cpp/matrix_native_addon.cpp'), 'utf8');
  for (const name of ['resolve_room_alias', 'preview_room', 'join_room']) assert.ok(cpp.includes('elementx_matrix_bridge_' + name + '('));
  for (const name of ['resolveRoomAlias', 'previewRoom', 'joinRoom']) assert.ok(cpp.includes('"' + name + '"'));
});
test('persistent login/restore and secure stores remain original production, not fixture session', () => {
  for (const name of ['session/SessionPersistence.ets', 'session/platform/AssetSessionCredentialStore.ets',
    'session/platform/PreferencesSessionMetadataStore.ets', 'appnav/RootSessionCoordinator.ets',
    'features/login/PasswordLoginCoordinator.ets', 'services/MatrixClientServerApi.ets']) {
    const relative = 'entry/src/main/ets/' + name;
    assert.deepEqual(fs.readFileSync(path.join(staged, relative)), fs.readFileSync(path.join(before, relative)));
  }
  const factory = fs.readFileSync(path.join(ets, 'composition/Task14SessionFoundation.ets'), 'utf8');
  assert.match(factory, /new ConfiguredSessionRooms\(bridge, navigation\)/);
  assert.doesNotMatch(factory, /JoinRoomByAddress/);
  assert.match(fs.readFileSync(path.join(ets, 'composition/Task14FinalAddressComposition.ets'), 'utf8'),
    /new JoinRoomByAddressPresenter\(foundation.rooms, navigator\)/);
  assert.doesNotMatch(factory, /Demo|Fixture|matrix\.org|demo\.local|https:\/\//);
});
test('signed-out session cannot call native alias/preview/join', async () => {
  const e = environment({session: false});
  for (const action of [() => e.rooms.resolveRoomAlias('#name:alias-domain.unit'),
    () => e.rooms.previewRoom('!id:room-domain.unit', []), () => e.rooms.joinRoom('!id:room-domain.unit', [])]) {
    await assert.rejects(action, error => error.code === 'session_unavailable');
  }
  assert.deepEqual(e.calls, []);
});
test('old ABI cannot use new aliases or be accepted as native readiness', async () => {
  const e = environment({abi: 3});
  await assert.rejects(() => e.rooms.resolveRoomAlias('#name:alias-domain.unit'), error => error.code === 'native_unavailable');
  assert.deepEqual(e.calls, []);
});
test('invalid runtime handle is not repaired or guessed', async () => {
  for (const handle of ['47', 'native:0', 'native:NaN', 'native:1.1', 'native:9007199254740992']) {
    const e = environment({session: false}); e.login(handle);
    await assert.rejects(() => e.rooms.resolveRoomAlias('#name:alias-domain.unit'));
    assert.deepEqual(e.calls, []);
  }
});
test('native registry missing/released client rejects before resolving alias', async () => {
  const e = environment();
  e.addon.getClientStatus = async () => ({ok: false, error: {code: 'client_not_found'}, client: null});
  await assert.rejects(() => e.rooms.resolveRoomAlias('#name:alias-domain.unit'), error => error.code === 'client_unavailable');
  assert.equal(e.calls.some(row => row[0] === 'alias'), false);
});
test('HOST MAPPING ONLY: SDK result servers retain order/port/duplicates and differ from configured client host', async () => {
  const e = environment(), result = await e.rooms.resolveRoomAlias('#name:alias-domain.unit');
  assert.deepEqual(clean(result.servers), ['b.unit:8448', 'a.unit', 'b.unit:8448']);
  assert.deepEqual(e.calls, [['status', 47], ['alias', 47, '#name:alias-domain.unit']]);
  assert.equal(result.roomId, '!returned:room-domain.unit');
});
test('HOST MAPPING ONLY: actual empty SDK servers are not filled with alias/homeserver domain', async () => {
  const e = environment(); e.addon.resolveRoomAlias = async () => data({roomId: '!id:unit', servers: []});
  assert.deepEqual(clean((await e.rooms.resolveRoomAlias('#name:alias-domain.unit')).servers), []);
});
test('only real native room_not_found maps to absence, SDK/auth/transport errors remain errors', async () => {
  const e = environment();
  e.addon.resolveRoomAlias = async () => failure('room_not_found', 12);
  assert.equal(await e.rooms.resolveRoomAlias('#name:alias-domain.unit'), undefined);
  for (const code of ['alias_resolve_failed', 'matrix_sdk_unavailable', 'authentication_required', 'runtime_unavailable']) {
    e.addon.resolveRoomAlias = async () => failure(code);
    await assert.rejects(() => e.rooms.resolveRoomAlias('#name:alias-domain.unit'), error => error.code === code);
  }
});
test('negative: malformed alias payload is never RoomFound', async () => {
  const e = environment();
  for (const value of [{roomId: '!id:unit', servers: 'wrong'}, {roomId: '!id:unit', servers: [1]}, {}, null]) {
    e.addon.resolveRoomAlias = async () => data(value);
    await assert.rejects(() => e.rooms.resolveRoomAlias('#name:alias-domain.unit'));
  }
});
test('negative: successful-value plus error envelope is rejected', async () => {
  const e = environment(); e.addon.resolveRoomAlias = async () => ({...data({roomId: '!id:unit', servers: []}), error: {code: 'bad'}});
  await assert.rejects(() => e.rooms.resolveRoomAlias('#name:alias-domain.unit'));
});
test('session replacement during native operation cannot surface a stale success', async () => {
  const e = environment(); let finish;
  e.addon.resolveRoomAlias = () => new Promise(resolve => { finish = resolve; });
  const pending = e.rooms.resolveRoomAlias('#name:alias-domain.unit');
  await new Promise(resolve => setImmediate(resolve));
  e.nav.resetToSignedOut(); finish(data({roomId: '!id:unit', servers: []}));
  await assert.rejects(() => pending, error => error.code === 'stale_session');
});
test('same user new login attempt/handle does not admit old completion', async () => {
  const e = environment(); let finish;
  e.addon.resolveRoomAlias = () => new Promise(resolve => { finish = resolve; });
  const pending = e.rooms.resolveRoomAlias('#name:alias-domain.unit');
  await new Promise(resolve => setImmediate(resolve));
  e.login('native:48'); finish(data({roomId: '!id:unit', servers: []}));
  await assert.rejects(() => pending, error => error.code === 'stale_session');
});
test('HOST MAPPING ONLY: opening actual room preview does not invent join/timeline', async () => {
  const e = environment();
  await e.owner.open({roomId: '!returned:room-domain.unit', serverNames: ['via-b.unit', 'via-a.unit']});
  assert.equal(e.owner.preview.membership, null);
  assert.equal(e.owner.timeline, null);
  assert.equal(e.calls.some(row => row[0] === 'join' || row[0] === 'timeline'), false);
  assert.deepEqual(e.calls.find(row => row[0] === 'preview'), ['preview', 47, '!returned:room-domain.unit', '["via-b.unit","via-a.unit"]']);
});
test('HOST MAPPING ONLY: explicit join passes via, waits for SDK Room then loads SDK timeline', async () => {
  const e = environment();
  await e.owner.open({roomId: '!returned:room-domain.unit', serverNames: ['via-b.unit', 'via-a.unit']});
  await e.owner.join();
  assert.equal(e.owner.preview.membership, 'joined');
  assert.equal(e.owner.timeline, '{"events":[],"end":null}');
  assert.deepEqual(e.calls.find(row => row[0] === 'join'), ['join', 47, '!returned:room-domain.unit', '["via-b.unit","via-a.unit"]']);
  assert.ok(e.calls.findIndex(row => row[0] === 'join') < e.calls.findIndex(row => row[0] === 'timeline'));
});
test('negative: failed join never supplies joined state or timeline', async () => {
  const e = environment();
  await e.owner.open({roomId: '!returned:room-domain.unit', serverNames: []});
  e.addon.joinRoom = async () => failure('room_join_failed', 17);
  await e.owner.join();
  assert.equal(e.owner.preview.membership, null);
  assert.equal(e.owner.timeline, null);
  assert.equal(e.owner.error, 'room_join_failed');
  assert.equal(e.calls.some(row => row[0] === 'timeline'), false);
});
test('closed owner cannot publish pending native preview', async () => {
  const e = environment(); let finish;
  e.addon.previewRoom = () => new Promise(resolve => { finish = resolve; });
  const pending = e.owner.open({roomId: '!id:unit', serverNames: []});
  await new Promise(resolve => setImmediate(resolve));
  e.owner.close();
  finish(data({roomId: '!id:unit', canonicalAlias: null, name: null, topic: null, avatarUrl: null, joinedMembers: 0, membership: null}));
  await pending;
  assert.equal(e.owner.preview, null); assert.equal(e.owner.timeline, null); assert.equal(e.owner.loading, false);
});
test('unknown native membership/shape is not invented as joined preview', async () => {
  const e = environment();
  e.addon.previewRoom = async () => data({roomId: '!id:unit', name: null, topic: null, canonicalAlias: null,
    avatarUrl: null, joinedMembers: 1, membership: 'new-sdk-unknown'});
  await e.owner.open({roomId: '!id:unit', serverNames: []});
  assert.equal(e.owner.preview, null); assert.equal(e.owner.timeline, null); assert.notEqual(e.owner.error, '');
});
test('mutation: ignoring SDK join failure would be rejected by error envelope', async () => {
  const e = environment(); e.addon.joinRoom = async () => failure('room_join_failed', 17);
  await assert.rejects(() => e.rooms.joinRoom('!id:unit', ['via.unit']), error => error.nativeCode === 17);
});
