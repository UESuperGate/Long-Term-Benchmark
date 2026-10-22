'use strict';
// OFFLINE diagnostics ONLY. No generated SDK/OS leaf value is native evidence.
const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const ast = require('./task14_entry_overlay_v4_ast.cjs');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const out = path.resolve(__dirname, '../../experiment_results/runtime_transition_20261021/task14_startchat_preservation_v5');
const project = role => path.join(out, 'projects', role);
const clean = value => JSON.parse(JSON.stringify(value));
const read = (role, name) => fs.readFileSync(path.join(project(role), 'entry/src/main/ets', name), 'utf8');
const data = value => ({ok: true, value: JSON.stringify(value), error: null});
const failure = code => ({ok: false, value: null, error: {code, message: code, nativeCode: 19, retryable: true}});

function environment(role = 'final') {
  const calls = [], routeCalls = [], prefs = new Map(), secure = new Map();
  let existing = null, failOp = null, createdRoom = '!created:unit';
  const person = {userId: '@other:unit', displayName: null, avatarUrl: null, isUnresolved: false};
  const addon = {
    getBridgeStatus: () => ({availability: 'ready', sdkLinked: true, abiVersion: 5, contractVersion: '5'}),
    async restoreClient(...args) { calls.push(['restore', ...args]); return {ok: true, client: {handle: 37, state: 'ready'}, error: null}; },
    async getClientStatus(handle) { return {ok: true, client: {handle, state: 'ready'}, error: null}; },
    async releaseClient(handle) { return {ok: true, client: {handle, state: 'released'}, error: null}; },
    async syncRooms() { return data({rooms: [], totalCount: 0}); },
    async resolveRoomAlias(...args) { calls.push(['alias', ...args]); return {ok: false, value: null, error: {code: 'room_not_found', nativeCode: 12, message: 'not found'}}; },
    async startChatOperation(handle, operation, raw) {
      const args = JSON.parse(raw); calls.push([operation, handle, args]);
      if (failOp === operation) return failure('start_chat_failed');
      switch (operation) {
        case 'search_users': return data({users: [person], limited: false});
        case 'find_dm': return data({roomId: existing});
        case 'create_dm': existing = '!dm:unit'; return data({roomId: existing, isNew: true});
        case 'create_room': return data({roomId: createdRoom});
        case 'recent_dms': return data({rooms: [{roomId: '!recent:unit', userId: person.userId, displayName: null}]});
        case 'track_room': return data({recorded: true});
        case 'user_permalink': return data({url: 'https://matrix.to/#/@unit:user-domain.unit'});
        default: throw Error('No unbound native leaf: ' + operation);
      }
    }
  };
  const alias = q => new TextDecoder().decode(q.get('ALIAS'));
  const asset = {Tag: Object.fromEntries(['ALIAS','SECRET','RETURN_TYPE','RETURN_LIMIT','ACCESSIBILITY','AUTH_TYPE','SYNC_TYPE','CONFLICT_RESOLUTION'].map(k => [k,k])),
    ReturnType: {ALL: 1}, Accessibility: {DEVICE_FIRST_UNLOCKED: 1}, AuthType: {NONE: 0}, SyncType: {NEVER: 0}, ConflictResolution: {OVERWRITE: 1},
    query: async q => secure.has(alias(q)) ? [new Map([['SECRET', secure.get(alias(q))]])] : [],
    add: async q => { secure.set(alias(q), q.get('SECRET')); }, remove: async q => { secure.delete(alias(q)); }};
  const preferences = {getPreferences: async () => ({get: async (k,d) => prefs.get(k) ?? d, put: async (k,v) => { prefs.set(k,v); },
    delete: async k => { prefs.delete(k); }, flush: async () => {}})};
  const http = {RequestMethod: {GET:'GET',POST:'POST'}, HttpDataType: {STRING:'STRING'}, createHttp: () => ({
    request: async url => ({responseCode: 200, result: JSON.stringify(url.includes('/.well-known/') ?
      {'m.homeserver': {base_url: 'https://configured-api.unit/client-prefix'}} :
      {user_id: '@unit:user-domain.unit', device_id: 'UNIT', access_token: 'UNIT-not-real'})}), destroy() {}})};
  const router = {async pushUrl(args) { routeCalls.push(['push', clean(args)]); }, async replaceUrl(args) { routeCalls.push(['replace', clean(args)]); }};
  const external = {'libmatrix_native.so': addon, '@ohos.net.http': http, '@ohos.data.preferences': preferences,
    '@ohos.security.asset': asset, '@ohos.util': {TextEncoder,TextDecoder}, '@ohos.router': router};
  const cache = new Map();
  function load(name) {
    name = path.normalize(name); if (cache.has(name)) return cache.get(name);
    const file = path.join(project(role), 'entry/src/main/ets', name + '.ets');
    const result = ts.transpileModule(fs.readFileSync(file, 'utf8'), {fileName:file, reportDiagnostics:true,
      compilerOptions: {module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}});
    assert.equal(result.diagnostics.some(d => d.category === ts.DiagnosticCategory.Error), false);
    const module = {exports:{}}; cache.set(name,module.exports);
    vm.runInNewContext('(function(require,module,exports){' + result.outputText + '\n})',
      {Map,Set,Uint8Array,ArrayBuffer,TextEncoder,TextDecoder,Date,console,setTimeout,clearTimeout}, {filename:file})(specifier => {
      if (specifier.startsWith('.')) return load(path.join(path.dirname(name),specifier));
      if (!(specifier in external)) throw Error('Unbound platform/native leaf: ' + specifier);
      return {default:external[specifier]};
    }, module,module.exports);
    cache.set(name,module.exports); return module.exports;
  }
  async function login() {
    const Runtime = load('composition/SessionEntryRuntime').SessionEntryRuntime;
    const runtime = await Runtime.open({unitOnlyContext: true});
    await runtime.login({homeserver:'login.unit',username:'unit',password:'UNIT',deviceDisplayName:'UNIT'});
    assert.equal(runtime.loggedIn(),true); return runtime;
  }
  async function owners(confirmNewDM = role === 'final') {
    const runtime = await login(), classes = load('features/ConfiguredStartChatOwner');
    const Routes = load('composition/StartChatRoutes').StartChatRoutes, routes = new Routes(runtime);
    return {runtime,routes,dm:new classes.ConfiguredStartChatOwner(runtime.foundation.startChat,routes,confirmNewDM,'@unit:user-domain.unit'),
      create:new classes.ConfiguredCreateRoomOwner(runtime.foundation.startChat,routes,'@unit:user-domain.unit')};
  }
  return {load,login,owners,calls,routeCalls,addon,person,setExisting: value => { existing=value; },
    fail: operation => { failOp=operation; }, badCreated: () => { createdRoom='NOT-A-ROOM'; }};
}

test('both actual registered entry graphs retain reachable DM/search/create/invite menu and real CreateRoom page', () => {
  for (const role of ['base','final']) {
    const graph = ast.graph(project(role)), names = graph.map(row => row.path);
    for (const name of ['pages/CreateRoom.ets','components/ConfiguredStartChatMenu.ets','features/ConfiguredStartChatOwner.ets',
      'matrix/production/ConfiguredStartChatService.ets','nativebridge/AddonNativeMatrixBridge.ets']) assert.ok(names.includes(name), role+': '+name);
    assert.equal(graph.some(row => row.constructors.some(name => /Demo|Fixture|Unavailable/.test(name))), false);
    const menu = read(role,'components/ConfiguredStartChatMenu.ets');
    for (const id of ['people_search_input','create_room_action','invite_friends_action','recent_dm_']) assert.ok(menu.includes(id));
    assert.equal(names.includes('features/JoinRoomByAddressFeature.ets'),role==='final');
  }
});
test('base/final original DM confirmation version difference is explicit, not inferred by scorer', () => {
  assert.match(read('base','pages/StartChat.ets'),/confirmNewDM: false/);
  assert.match(read('final','pages/StartChat.ets'),/confirmNewDM: true/);
  assert.doesNotMatch(read('base','pages/StartChat.ets'),/showJoinAddress: true/);
});
test('original Task14 final address presenter bytes and V3 alias module remain unchanged except ABI metadata outside it', () => {
  const previous = path.join(out,'../task14_configured_client_native_v3/staged');
  assert.deepEqual(fs.readFileSync(path.join(previous,'entry/src/main/ets/features/JoinRoomByAddressFeature.ets')),
    fs.readFileSync(path.join(project('final'),'entry/src/main/ets/features/JoinRoomByAddressFeature.ets')));
  assert.deepEqual(fs.readFileSync(path.join(previous,'native/matrix-sdk-bridge/src/task14.rs')),
    fs.readFileSync(path.join(out,'native-prerequisite/native/matrix-sdk-bridge/src/task14.rs')));
});
function nativeBoundary(source) {
  for (const operation of ['client_for_handle(handle)?','client.search_users(term, 10)', 'client.get_dm_room(&id)',
    'client.create_room(', 'get_recently_visited_rooms()', 'track_recently_visited_room(id)', 'fetch_user_profile_of(&id)']) {
    assert.ok(source.includes(operation),operation);
  }
  assert.doesNotMatch(source,/Client::builder|homeserver_url\(|reqwest::Client|demo\.local/);
}
test('new native operations actually call the configured SDK Client, no new client/HTTP/fixture room synthesis', () => {
  nativeBoundary(fs.readFileSync(path.join(out,'native-prerequisite/native/matrix-sdk-bridge/src/startchat.rs'),'utf8'));
});
test('negative SDK bypass/new-client substitution cannot inherit the source boundary check', () => {
  const source=fs.readFileSync(path.join(out,'native-prerequisite/native/matrix-sdk-bridge/src/startchat.rs'),'utf8');
  assert.throws(()=>nativeBoundary(source.replace('client_for_handle(handle)?','Client::builder().build()')));
  assert.throws(()=>nativeBoundary(source.replaceAll('client.create_room(', 'invented_room(')));
});
test('native private/DM creation stays encrypted, call power levels retained; public alias/preset forwarded', () => {
  const source=fs.readFileSync(path.join(out,'native-prerequisite/native/matrix-sdk-bridge/src/startchat.rs'),'utf8');
  for(const token of ['with_recommended_defaults()', 'RoomPreset::TrustedPrivateChat', 'RoomPreset::PrivateChat',
    'RoomPreset::PublicChat','request.room_alias_name = parameters.room_alias_name','m.call.member','org.matrix.msc3401.call.member']) assert.ok(source.includes(token));
  const manifest=fs.readFileSync(path.join(out,'native-prerequisite/native/matrix-sdk-bridge/Cargo.toml'),'utf8');
  assert.ok(manifest.includes('"e2e-encryption"')); // source dependency feature only, NOT compiled crypto proof
});
test('HOST ONLY: existing DM opens SDK ID and never creates, on both versions', async () => {
  for(const role of ['base','final']) {
    const e=environment(role);e.setExisting('!existing:unit');const {dm}=await e.owners();await dm.select(e.person);
    assert.equal(e.calls.some(row=>row[0]==='create_dm'),false);
    assert.equal(e.routeCalls.at(-1)[1].params.roomId,'!existing:unit');
  }
});
test('HOST ONLY: Android base automatically creates missing DM through native dispatcher', async () => {
  const e=environment('base'),{dm}=await e.owners();await dm.select(e.person);
  assert.equal(dm.dmState,'success');assert.ok(e.calls.some(row=>row[0]==='create_dm'));
  assert.equal(e.routeCalls.at(-1)[1].params.roomId,'!dm:unit');
});
test('HOST ONLY: Android final missing DM requires confirmation before any create SDK action', async () => {
  const e=environment(),{dm}=await e.owners();await dm.select(e.person);
  assert.equal(dm.dmState,'confirming');assert.equal(e.calls.some(row=>row[0]==='create_dm'),false);
  assert.equal(e.routeCalls.length,0);await dm.confirm();
  assert.ok(e.calls.some(row=>row[0]==='create_dm'));assert.equal(dm.dmState,'success');
});
test('confirmation cancellation does not create or navigate', async () => {
  const e=environment(),{dm}=await e.owners();await dm.select(e.person);dm.cancelDM();
  assert.equal(dm.dmState,'idle');assert.equal(e.calls.some(row=>row[0]==='create_dm'),false);assert.equal(e.routeCalls.length,0);
});
test('SDK create error is not a synthetic DM/room success', async () => {
  const e=environment('base'),{dm}=await e.owners();e.fail('create_dm');await dm.select(e.person);
  assert.equal(dm.dmState,'failure');assert.equal(e.routeCalls.length,0);assert.notEqual(dm.error,'');
});
test('recent suggestions call native visit-order operation, not all rooms/timestamps/seeded people', async () => {
  const e=environment(),{dm}=await e.owners();await dm.loadRecent();
  assert.ok(e.calls.some(row=>row[0]==='recent_dms'));assert.equal(dm.recent[0].roomId,'!recent:unit');
  const native=fs.readFileSync(path.join(out,'native-prerequisite/native/matrix-sdk-bridge/src/startchat.rs'),'utf8');
  assert.match(native,/room.active_members_count\(\) > 2/);assert.match(native,/seen.insert/);
});
test('search short query makes no SDK directory call; actual debounce cancels obsolete query', async () => {
  const e=environment(),{dm}=await e.owners();await dm.search('ab');
  assert.equal(e.calls.some(row=>row[0]==='search_users'),false);
  const old=dm.search('old');const current=dm.search('new');await Promise.all([old,current]);
  const calls=e.calls.filter(row=>row[0]==='search_users');assert.equal(calls.length,1);assert.equal(calls[0][2].term,'new');
});
test('entered MXID optimistic row is explicitly unresolved, never an invented SDK profile/Room', async () => {
  const e=environment(),{dm}=await e.owners();const action=dm.search('@typed:unit');
  assert.equal(dm.results[0].userId,'@typed:unit');assert.equal(dm.results[0].isUnresolved,true);assert.equal(e.routeCalls.length,0);
  await action;
});
test('private create preserves raw name/topic/member parameters and only routes after SDK created ID', async () => {
  const e=environment(),{create}=await e.owners();create.name=' Raw name ';create.topic='topic';create.toggleInvite('@other:unit',true);
  await create.submit();const request=e.calls.find(row=>row[0]==='create_room')[2];
  assert.deepEqual(request,{name:' Raw name ',topic:'topic',invite:['@other:unit'],visibility:'private',roomAliasName:null,joinRule:null});
  assert.equal(e.routeCalls.at(-1)[1].params.roomId,'!created:unit');
});
test('public alias availability requires actual absence, preserves actual configured user domain', async () => {
  const e=environment(),{create}=await e.owners();create.name='public';create.visibility='public';assert.equal(create.isValid(),false);
  await create.updateAlias('local');assert.equal(create.isValid(),true);
  assert.equal(e.calls.find(row=>row[0]==='alias')[2],'#local:user-domain.unit');await create.submit();
  const request=e.calls.find(row=>row[0]==='create_room')[2];assert.equal(request.roomAliasName,'local');assert.equal(request.visibility,'public');
});
test('alias transport error is NOT availability and cannot submit public create', async () => {
  const e=environment(),{create}=await e.owners();e.addon.resolveRoomAlias=async()=>failure('alias_resolve_failed');
  create.name='public';create.visibility='public';await create.updateAlias('local');assert.equal(create.isValid(),false);await create.submit();
  assert.equal(e.calls.some(row=>row[0]==='create_room'),false);
});
test('invalid created ID is rejected; no fabricated room route', async () => {
  const e=environment(),{create}=await e.owners();e.badCreated();create.name='name';await create.submit();
  assert.equal(e.routeCalls.length,0);assert.notEqual(create.error,'');
});
test('invite friends gets permalink from configured native SDK and executes real app-owned OS adapter body', async () => {
  const e=environment(),{routes}=await e.owners(),wants=[];
  await routes.inviteFriends({async startAbility(want){wants.push(clean(want));}});
  assert.ok(e.calls.some(row=>row[0]==='user_permalink'));assert.equal(wants[0].action,'ohos.want.action.sendData');
  assert.equal(wants[0].parameters['ohos.extra.param.key.shareUrl'],'https://matrix.to/#/@unit:user-domain.unit');
});
test('ABI4 is rejected by successor, existing v3 worker/source remain independent', async () => {
  const e=environment(),{dm}=await e.owners();e.addon.getBridgeStatus=()=>({availability:'ready',sdkLinked:true,abiVersion:4,contractVersion:'4'});
  await dm.select(e.person);assert.equal(dm.dmState,'failure');assert.equal(e.routeCalls.length,0);
  assert.match(fs.readFileSync(path.join(project('base'),'entry/src/main/cpp/CMakeLists.txt'),'utf8'),/TASK14_ABI5_ARCHIVE_SHA256/);
});
