'use strict';
// OFFLINE ONLY. SDK/OS/router leaves below are UNIT doubles, never runtime score evidence.
const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const ast = require('./task14_entry_overlay_v4_ast.cjs');
const root = path.resolve(__dirname, '../../experiment_results/runtime_transition_20261021/task14_entry_rendered_overlay_v4');
const project = role => path.join(root, 'workspaces', role + '-review');
const source = (role, name) => fs.readFileSync(path.join(project(role), 'entry/src/main/ets', name), 'utf8');
const clean = value => JSON.parse(JSON.stringify(value));
const data = value => ({ok: true, error: null, value: JSON.stringify(value)});
const failed = code => ({ok: false, error: {code, message: code, nativeCode: 16, retryable: true}, value: null});

function loader(role, external) {
  const cache = new Map();
  function load(name) {
    name = path.normalize(name);
    if (cache.has(name)) return cache.get(name);
    const file = path.join(project(role), 'entry/src/main/ets', name + '.ets');
    const result = ts.transpileModule(fs.readFileSync(file, 'utf8'), {fileName: file, reportDiagnostics: true,
      compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020}});
    assert.equal(result.diagnostics.some(d => d.category === ts.DiagnosticCategory.Error), false);
    const module = {exports: {}}; cache.set(name, module.exports);
    const unitTimer = (fn, ms) => { const timer = setTimeout(fn, ms); if (ms >= 10000) timer.unref(); return timer; };
    vm.runInNewContext('(function(require,module,exports){' + result.outputText + '\n})',
      {Map, Set, Uint8Array, ArrayBuffer, TextEncoder, TextDecoder, console, Date, setTimeout: unitTimer, clearTimeout}, {filename: file})(specifier => {
      if (specifier.startsWith('.')) return load(path.join(path.dirname(name), specifier));
      if (!(specifier in external)) throw Error('Unknown external ' + specifier);
      return {default: external[specifier]};
    }, module, module.exports);
    cache.set(name, module.exports); return module.exports;
  }
  return load;
}

function environment(role = 'final', stores = {prefs: new Map(), secure: new Map()}) {
  const calls = [], httpCalls = [], contexts = [], routerCalls = [];
  let joined = false;
  const addon = {
    getBridgeStatus: () => ({availability: 'ready', sdkLinked: true, abiVersion: 4, contractVersion: '4'}),
    async restoreClient(...args) { calls.push(['restore', ...args]); return {ok: true, error: null, client: {handle: 17, state: 'ready'}}; },
    async getClientStatus(handle) { calls.push(['status', handle]); return {ok: true, error: null, client: {handle, state: 'ready'}}; },
    async releaseClient(handle) { calls.push(['release', handle]); return {ok: true, error: null, client: {handle, state: 'released'}}; },
    async syncRooms(handle) { calls.push(['sync', handle]); return data({rooms: [{roomId: '!existing:room.unit', displayName: 'Unit native-leaf double', membership: 'joined'}], totalCount: 1}); },
    async resolveRoomAlias(...args) { calls.push(['alias', ...args]); return data({roomId: '!resolved:room.unit', servers: ['z.via.unit', 'a.via.unit:8448']}); },
    async previewRoom(...args) { calls.push(['preview', ...args]); return data({roomId: '!resolved:room.unit', name: 'Unit preview only', topic: null,
      canonicalAlias: null, avatarUrl: null, joinedMembers: 2, membership: joined ? 'joined' : null}); },
    async joinRoom(...args) { calls.push(['join', ...args]); joined = true; return data({roomId: '!resolved:room.unit', membership: 'joined'}); },
    async loadTimeline(...args) { calls.push(['timeline', ...args]); return data({events: [{sender: '@other:unit', content: {body: 'Unit body only'}}], end: null}); }
  };
  const alias = q => new TextDecoder().decode(q.get('ALIAS'));
  const asset = {Tag: Object.fromEntries(['ALIAS','SECRET','RETURN_TYPE','RETURN_LIMIT','ACCESSIBILITY','AUTH_TYPE','SYNC_TYPE','CONFLICT_RESOLUTION'].map(k => [k, k])),
    ReturnType: {ALL: 1}, Accessibility: {DEVICE_FIRST_UNLOCKED: 1}, AuthType: {NONE: 0}, SyncType: {NEVER: 0}, ConflictResolution: {OVERWRITE: 1},
    async query(q) { const bytes = stores.secure.get(alias(q)); return bytes ? [new Map([['SECRET', bytes]])] : []; },
    async add(q) { stores.secure.set(alias(q), q.get('SECRET')); }, async remove(q) { stores.secure.delete(alias(q)); }};
  const preferences = {async getPreferences(context) { contexts.push(context); return {
    get: async (key, fallback) => stores.prefs.get(key) ?? fallback, put: async (key, value) => { stores.prefs.set(key, value); },
    delete: async key => { stores.prefs.delete(key); }, flush: async () => {}}; }};
  const http = {RequestMethod: {GET: 'GET', POST: 'POST'}, HttpDataType: {STRING: 'STRING'}, createHttp: () => ({
    async request(url, options) {
      httpCalls.push({url, options});
      if (url.includes('/.well-known/')) return {responseCode: 200, result: JSON.stringify({'m.homeserver': {base_url: 'https://configured-api.unit/client-prefix'}})};
      if (url.endsWith('/_matrix/client/v3/login')) return {responseCode: 200, result: JSON.stringify({user_id: '@unit:user-domain.unit', device_id: 'UNIT', access_token: 'UNIT-SECRET-not-real'})};
      throw Error('No unbound HTTP behavior: ' + url);
    }, destroy() {}})};
  const router = {async pushUrl(args) { routerCalls.push(['push', clean(args)]); }, async replaceUrl(args) { routerCalls.push(['replace', clean(args)]); }};
  const load = loader(role, {'libmatrix_native.so': addon, '@ohos.router': router, '@ohos.net.http': http,
    '@ohos.data.preferences': preferences, '@ohos.security.asset': asset, '@ohos.util': {TextEncoder, TextDecoder}});
  const Runtime = load('composition/SessionEntryRuntime').SessionEntryRuntime;
  const context = {unitContextIdentity: 'not-a-device-context'};
  const login = async runtime => runtime.login({homeserver: 'login-input.unit', username: 'unit', password: 'UNIT-password', deviceDisplayName: 'UNIT'});
  return {load, Runtime, context, login, stores, calls, httpCalls, contexts, routerCalls, addon, router, asset, preferences};
}

test('both complete registered entry graphs parse with SDK ArkUI parser, NO emitter/renderer', () => {
  for (const role of ['base', 'final']) {
    const rows = ast.graph(project(role));
    assert.ok(rows.some(row => row.path === 'entryability/EntryAbility.ets'));
    assert.ok(rows.some(row => row.path === 'pages/Index.ets'));
    assert.ok(rows.some(row => row.path === 'pages/Room.ets'));
    assert.ok(rows.some(row => row.path === 'composition/Task14SessionFoundation.ets'));
    assert.equal(rows.some(row => row.path.includes('ChatRuntime') || row.path.includes('RoomAliasDirectory')), false);
    assert.equal(rows.some(row => row.constructors.some(name => /Demo|Fixture|Unavailable/.test(name))), false);
    assert.equal(rows.some(row => row.path.includes('JoinRoomByAddressFeature')), role === 'final');
  }
});
test('main/Room and shared entry/session bodies are identical across roles', () => {
  for (const name of ['pages/Index.ets', 'pages/Room.ets', 'composition/SessionEntryRuntime.ets',
    'composition/SessionRoutes.ets', 'matrix/production/ConfiguredSessionRooms.ets', 'features/ConfiguredRoomPageOwner.ets']) {
    assert.equal(source('base', name), source('final', name), name);
  }
});
test('final-only presenter retains exact V3 original bytes and no base address UI/import', () => {
  const original = fs.readFileSync(path.join(root, '../task14_configured_client_native_v3/staged/entry/src/main/ets/features/JoinRoomByAddressFeature.ets'), 'utf8');
  assert.equal(source('final', 'features/JoinRoomByAddressFeature.ets'), original);
  assert.doesNotMatch(source('base', 'pages/StartChat.ets'), /join_room_by_address|JoinRoomByAddress|FinalAddress/);
});
test('rendered login input/real Context and owner state bindings are explicit, no constant config/session', () => {
  const index = source('final', 'pages/Index.ets'), room = source('final', 'pages/Room.ets');
  for (const field of ['homeserver', 'username', 'password']) assert.ok(index.includes(field + ': this.' + field));
  assert.match(index, /getContext\(this\) as common.UIAbilityContext/);
  assert.doesNotMatch(index, /native:\d|https:\/\/|demo\.local|matrix\.org/);
  assert.match(room, /runtime.foundation.createRoomPageOwner\(\)/);
  assert.match(room, /this.owner.open\(this.route\)/);
  assert.match(room, /this.owner.join\(\)/);
  assert.match(room, /this.owner.preview/);
  assert.match(room, /this.owner.timeline/);
});
const ids = values => values.map(value => "'" + value + "'");
test('source control closure identifies every expected interactive control', () => {
  ast.assertClosed('Index.ets', source('final', 'pages/Index.ets'), [...ids(['login_homeserver','login_username','login_password','login_submit',
    'restore_session_retry','start_chat_action','rooms_refresh']), "'session_room_' + room.roomId"]);
  ast.assertClosed('Room.ets', source('final', 'pages/Room.ets'), ids(['room_back','room_join','room_reload']));
  ast.assertClosed('StartChat.ets', source('base', 'pages/StartChat.ets'), ids(['start_chat_back']));
  ast.assertClosed('StartChat.ets', source('final', 'pages/StartChat.ets'), ids(['join_room_by_address','start_chat_back','room_address_input','join_room_continue','join_room_cancel']));
});
test('unknown/renamed source control cannot inherit reviewed closure', () => {
  const before = source('base', 'pages/StartChat.ets');
  assert.throws(() => ast.assertClosed('StartChat.ets', before.replace("'start_chat_back'", "'alternate_button'"), ids(['start_chat_back'])));
  assert.throws(() => ast.assertClosed('StartChat.ets', before.replace("Text('Start a chat')", "Button('Unknown').onClick(() => {})\n      Text('Start a chat')"), ids(['start_chat_back'])));
});
test('ABI4 package integration requires explicit archive+hash, no old default/implicit archive', () => {
  const cmake = fs.readFileSync(path.join(project('final'), 'entry/src/main/cpp/CMakeLists.txt'), 'utf8');
  assert.match(cmake, /TASK14_ABI4_ARCHIVE_SHA256/);
  assert.match(cmake, /file\(SHA256/);
  assert.match(cmake, /--no-undefined/);
  assert.doesNotMatch(cmake, /target\/aarch64|123126682|\.\.\/.*native\/matrix-sdk-bridge/);
});
test('empty real-store lookup remains signed out with no invented Client/native call', async () => {
  const e = environment(), runtime = await e.Runtime.open(e.context);
  assert.equal(runtime.loggedIn(), false);
  assert.equal(runtime.foundation.rootNavigation.getState().sessionHandle, null);
  assert.deepEqual(e.calls, []); assert.deepEqual(e.httpCalls, []);
  assert.equal(e.contexts[0], e.context);
});
test('empty input does not trigger fallback host/login/session', async () => {
  const e = environment(), runtime = await e.Runtime.open(e.context);
  await runtime.login({homeserver: '', username: 'unit', password: 'unit', deviceDisplayName: 'UNIT'});
  assert.equal(runtime.loggedIn(), false); assert.equal(runtime.foundation.rootNavigation.getState().error.code, 'invalid_input');
  assert.deepEqual(e.calls, []); assert.deepEqual(e.httpCalls, []);
});
test('HOST ONLY: original discovery/login, Asset/Preferences persistence then SDK registry restore and sync are wired', async () => {
  const e = environment(), runtime = await e.Runtime.open(e.context);
  await e.login(runtime);
  assert.equal(runtime.loggedIn(), true);
  assert.equal(e.httpCalls[0].url, 'https://login-input.unit/.well-known/matrix/client');
  assert.equal(e.httpCalls[1].url, 'https://configured-api.unit/client-prefix/_matrix/client/v3/login');
  assert.equal(e.calls.find(row => row[0] === 'restore')[1], 'https://configured-api.unit/client-prefix');
  assert.ok(e.calls.some(row => row[0] === 'sync'));
  assert.equal(e.stores.secure.size, 1);
  assert.equal(JSON.stringify([...e.stores.prefs.values()]).includes('UNIT-SECRET'), false);
  assert.equal(runtime.rooms[0].roomId, '!existing:room.unit');
});
test('HOST ONLY: process restart uses stored configured URL/secure token, never alias-domain rediscovery', async () => {
  const first = environment(), runtime = await first.Runtime.open(first.context); await first.login(runtime);
  const second = environment('final', first.stores), restored = await second.Runtime.open(second.context);
  assert.equal(restored.loggedIn(), true); assert.deepEqual(second.httpCalls, []);
  const call = second.calls.find(row => row[0] === 'restore');
  assert.equal(call[1], 'https://configured-api.unit/client-prefix');
  assert.equal(call[4], 'UNIT-SECRET-not-real');
  assert.ok(second.calls.some(row => row[0] === 'sync'));
});
test('missing secure credential fails closed without preferences secret fallback', async () => {
  const first = environment(), runtime = await first.Runtime.open(first.context); await first.login(runtime);
  first.stores.secure.clear();
  const second = environment('final', first.stores), restored = await second.Runtime.open(second.context);
  assert.equal(restored.loggedIn(), false); assert.deepEqual(second.calls, []);
  assert.equal(restored.foundation.rootNavigation.getState().error.code, 'credential_missing');
});
test('HOST ONLY: explicit restore retry rereads OS stores and syncs after a native capability recovery', async () => {
  const first = environment(), signedIn = await first.Runtime.open(first.context); await first.login(signedIn);
  const next = environment('final', first.stores), ready = next.addon.getBridgeStatus;
  next.addon.getBridgeStatus = () => ({availability: 'unavailable', sdkLinked: false, abiVersion: 4, contractVersion: '4'});
  const runtime = await next.Runtime.open(next.context);
  assert.equal(runtime.loggedIn(), false);
  next.addon.getBridgeStatus = ready;
  await runtime.restore();
  assert.equal(runtime.loggedIn(), true); assert.notEqual(runtime.rooms.length, 0);
  assert.equal(next.calls.find(row => row[0] === 'restore')[1], 'https://configured-api.unit/client-prefix');
  assert.ok(next.calls.some(row => row[0] === 'sync')); assert.deepEqual(next.httpCalls, []);
});
test('SDK unavailable blocks login before password HTTP and cannot expose signed-in UI state', async () => {
  const e = environment(), runtime = await e.Runtime.open(e.context);
  e.addon.getBridgeStatus = () => ({availability: 'unavailable', sdkLinked: false, abiVersion: 4, contractVersion: '4'});
  await e.login(runtime);
  assert.equal(runtime.loggedIn(), false); assert.equal(e.httpCalls.length, 1); assert.deepEqual(e.calls, []);
});
test('secure-store denied releases original native handle, does not complete login', async () => {
  const e = environment(), runtime = await e.Runtime.open(e.context);
  e.asset.add = async () => { throw Object.assign(Error('denied'), {code: 201}); };
  await e.login(runtime);
  assert.equal(runtime.loggedIn(), false); assert.equal(e.stores.prefs.size, 0);
  assert.ok(e.calls.some(row => row[0] === 'release'));
});
test('OS Context failure can retry real initialization but never creates empty fake preferences', async () => {
  const e = environment(), original = e.preferences.getPreferences;
  e.preferences.getPreferences = async () => { throw Error('real-context-unavailable-unit'); };
  await assert.rejects(() => e.Runtime.open(e.context));
  e.preferences.getPreferences = original;
  assert.equal((await e.Runtime.open(e.context)).loggedIn(), false); assert.deepEqual(e.calls, []);
});
test('malformed SDK room list surfaces error, never manufactures a successful list', async () => {
  const e = environment(), runtime = await e.Runtime.open(e.context);
  e.addon.syncRooms = async () => data({rooms: [{roomId: 'fake'}], totalCount: 1});
  await e.login(runtime);
  assert.notEqual(runtime.roomsError, ''); assert.deepEqual(clean(runtime.rooms), []);
});
test('HOST ONLY: main route requires real completed session; missing room server list is rejected', async () => {
  const e = environment(), runtime = await e.Runtime.open(e.context), routes = e.load('composition/SessionRoutes');
  await assert.rejects(() => routes.SessionRoutes.startChat(runtime));
  await e.login(runtime); await routes.SessionRoutes.startChat(runtime);
  assert.deepEqual(e.routerCalls[0], ['push', {url: 'pages/StartChat'}]);
  assert.throws(() => routes.requireRoomRoute({roomId: '!id:unit'}));
});
test('HOST ONLY: ORIGINAL final presenter -> actual app-owned navigator -> native-leaf preview; no projected join', async () => {
  const e = environment(), runtime = await e.Runtime.open(e.context); await e.login(runtime);
  const Navigator = e.load('composition/FinalAddressRouteOwner').FinalAddressRouteOwner, navigator = new Navigator();
  const composition = e.load('composition/Task14FinalAddressComposition').Task14FinalAddressComposition;
  const presenter = composition.createPresenter(runtime.foundation, navigator);
  navigator.showAddress();
  await presenter.updateAddress('#room:alias-domain.unit');
  assert.equal(presenter.addressState, 'room_found');
  presenter.continue(); await navigator.navigation;
  assert.equal(navigator.addressVisible, false);
  const route = e.routerCalls.find(row => row[0] === 'replace')[1];
  assert.deepEqual(route, {url: 'pages/Room', params: {roomId: '!resolved:room.unit', serverNames: ['z.via.unit','a.via.unit:8448']}});
  const owner = runtime.foundation.createRoomPageOwner(); await owner.open(route.params);
  assert.equal(owner.preview.membership, null); assert.equal(owner.timeline, null);
  assert.equal(e.calls.some(row => row[0] === 'join'), false);
  await owner.join(); assert.equal(owner.preview.membership, 'joined'); assert.notEqual(owner.timeline, null);
});
test('route failure restores dialog with error instead of claiming successful Room navigation', async () => {
  const e = environment(), Navigator = e.load('composition/FinalAddressRouteOwner').FinalAddressRouteOwner;
  e.router.replaceUrl = async () => { throw Error('native-router-unavailable-unit'); };
  const nav = new Navigator(); nav.openRoom('!id:unit', ['via.unit']); await nav.navigation;
  assert.equal(nav.addressVisible, true); assert.equal(nav.navigationError, 'native-router-unavailable-unit');
  assert.equal(e.calls.some(row => row[0] === 'preview'), false);
});
test('native preview failure never invents loaded room or timeline', async () => {
  const e = environment(), runtime = await e.Runtime.open(e.context); await e.login(runtime);
  e.addon.previewRoom = async () => failed('room_preview_failed');
  const owner = runtime.foundation.createRoomPageOwner(); await owner.open({roomId: '!id:unit', serverNames: []});
  assert.equal(owner.preview, null); assert.equal(owner.timeline, null); assert.equal(owner.error, 'room_preview_failed');
});
test('timeline display maps real body or exact unknown event JSON, never fabricated/decrypted text', () => {
  const rows = environment().load('composition/SessionEntryRuntime').timelineRows;
  const event = {type: 'm.room.encrypted', sender: '@other:unit', content: {ciphertext: 'UNIT'}};
  assert.equal(rows(JSON.stringify({events: [event], end: null}))[0].content, JSON.stringify(event));
  assert.throws(() => rows(JSON.stringify({events: [null], end: null})));
});
