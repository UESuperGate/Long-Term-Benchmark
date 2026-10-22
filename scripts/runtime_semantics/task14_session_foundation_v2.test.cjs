'use strict';
// OFFLINE prerequisites only. NO successful native client/session/semantic score.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {loader,graph}=require('./task14_session_foundation_v2.cjs');
const root=process.env.TASK14_FOUNDATION;
if(!root)throw Error('Explicit staged foundation required; never use an active task');
function environment(){
  const prefs=new Map(),secure=new Map(),httpCalls=[],assetCalls=[];
  const aliases=q=>new TextDecoder().decode(q.get('ALIAS'));
  const asset={Tag:Object.fromEntries(['ALIAS','SECRET','RETURN_TYPE','RETURN_LIMIT','ACCESSIBILITY','AUTH_TYPE','SYNC_TYPE','CONFLICT_RESOLUTION'].map(k=>[k,k])),
    ReturnType:{ALL:1},Accessibility:{DEVICE_FIRST_UNLOCKED:1},AuthType:{NONE:0},SyncType:{NEVER:0},ConflictResolution:{OVERWRITE:1},
    async query(q){assetCalls.push('query');const bytes=secure.get(aliases(q));return bytes?[new Map([['SECRET',bytes]])]:[];},
    async add(q){assetCalls.push('add');secure.set(aliases(q),q.get('SECRET'));},async remove(q){assetCalls.push('remove');secure.delete(aliases(q));}};
  const preferences={getPreferences:async()=>({get:async(k,d)=>prefs.get(k)??d,put:async(k,v)=>{prefs.set(k,v);},
    delete:async k=>{prefs.delete(k);},flush:async()=>{}})};
  const http={RequestMethod:{GET:'GET',POST:'POST'},HttpDataType:{STRING:'STRING'},createHttp:()=>({
    async request(url,options){httpCalls.push({url,method:options.method});return {responseCode:200,
      result:JSON.stringify({'m.homeserver':{base_url:'https://configured-api.unit/path-prefix'}})};},destroy(){}})};
  // Empty import surface permits HOST syntax/module loading only. No ready or
  // restore callback is fabricated; actual native calls fail closed.
  const nativeAddon=Object.freeze({});
  const load=loader(root,{'@ohos.data.preferences':preferences,'@ohos.security.asset':asset,'@ohos.util':{TextEncoder,TextDecoder},
    '@ohos.net.http':http,'libmatrix_native.so':nativeAddon});
  return {load,prefs,secure,httpCalls,assetCalls,nativeAddon};
}
function session(){
  return {metadata:{sessionId:'@unit:user-domain.unit',userId:'@unit:user-domain.unit',deviceId:'UNIT',
    homeserverUrl:'https://configured-api.unit/path-prefix',loginType:'password',loginTimestampMs:1,isTokenValid:true,
    position:1,lastUsageIndex:1,userDisplayName:null,userAvatarUrl:null},
    credential:{sessionId:'@unit:user-domain.unit',accessToken:'UNIT-memory-only-not-real',refreshToken:null,databasePassphrase:null}};
}
async function persistence(e){
  const Metadata=e.load('session/platform/PreferencesSessionMetadataStore').PreferencesSessionMetadataStore;
  const Credential=e.load('session/platform/AssetSessionCredentialStore').AssetSessionCredentialStore;
  const Persistence=e.load('session/SessionPersistence').SessionPersistence;
  return new Persistence(await Metadata.create({}),new Credential());
}
test('structured source graph is self-contained except declared platform/native imports, no fixture adapter',()=>{
  const rows=graph(root,root),names=rows.map(row=>row.path);
  assert.ok(names.includes('matrix/production/NativeMatrixAuthenticationService.ets'));
  assert.ok(names.includes('session/platform/AssetSessionCredentialStore.ets'));
  assert.ok(names.includes('nativebridge/AddonNativeMatrixBridge.ets'));
  assert.equal(names.some(name=>/Fixture|PersistentSessionStore|RoomAliasDirectory|ReconstructedRoot/.test(name)),false);
  const source=fs.readFileSync(path.join(root,'composition/Task14SessionFoundation.ets'),'utf8');
  assert.equal(/matrix\.org|demo\.local|https:\/\//.test(source),false);
  const e=environment();for(const row of rows)e.load(row.path.slice(0,-4));
  assert.deepEqual(Object.keys(e.nativeAddon),[]);
});
test('reused original discovery returns configured API origin, not a userId or room alias domain',async()=>{
  const e=environment(),Auth=e.load('matrix/production/NativeMatrixAuthenticationService').NativeMatrixAuthenticationService;
  const Unavailable=e.load('nativebridge/UnavailableNativeMatrixBridge').UnavailableNativeMatrixBridge;
  const auth=new Auth(new Unavailable());
  const resolved=await auth.resolveHomeserver('login-input.unit');
  assert.equal(resolved.success,true);assert.equal(resolved.value.canonicalUrl,'https://configured-api.unit/path-prefix');
  assert.equal(e.httpCalls.length,1);assert.equal(e.httpCalls[0].url,'https://login-input.unit/.well-known/matrix/client');
  // This is ONLY HTTP mapping evidence; it has not created a Client.
  const result=await auth.loginWithPassword(resolved.value,{username:'unit',password:'UNIT',deviceDisplayName:'UNIT'});
  assert.equal(result.success,false);assert.equal(result.error.code,'native_bridge_unavailable');
  assert.equal(e.httpCalls.some(call=>call.method==='POST'),false);
});
test('original platform-backed stores split configured homeserver metadata from credentials',async()=>{
  const e=environment(),store=await persistence(e),value=session();
  assert.equal((await store.save(value)).success,true);
  const restored=await store.loadLatest();assert.equal(restored.success,true);
  assert.equal(restored.value.session.metadata.homeserverUrl,value.metadata.homeserverUrl);
  assert.equal(restored.value.session.credential.accessToken,value.credential.accessToken);
  assert.equal(e.secure.size,1);assert.ok(e.assetCalls.includes('add'));
  for(const text of e.prefs.values())assert.equal(text.includes('accessToken'),false);
  assert.equal(JSON.stringify([...e.prefs.values()]).includes(value.credential.accessToken),false);
});
test('actual original RootSessionCoordinator does not promote stored metadata to a restored Client',async()=>{
  const e=environment(),store=await persistence(e);await store.save(session());
  const Auth=e.load('matrix/production/NativeMatrixAuthenticationService').NativeMatrixAuthenticationService;
  const Unavailable=e.load('nativebridge/UnavailableNativeMatrixBridge').UnavailableNativeMatrixBridge;
  const Nav=e.load('appnav/RootNavigationStateMachine').RootNavigationStateMachine;
  const Root=e.load('appnav/RootSessionCoordinator').RootSessionCoordinator,nav=new Nav();
  await new Root(new Auth(new Unavailable()),store,nav).restoreLatestSession();
  assert.equal(nav.getState().phase,'error');assert.equal(nav.getState().error.code,'native_bridge_unavailable');
  assert.equal(nav.getState().sessionHandle,null);assert.equal(nav.getState().session,null);
  assert.equal(e.httpCalls.length,0);
});
test('absent session stays signed out, empty UI login input never fabricates a configured Client',async()=>{
  const e=environment(),Foundation=e.load('composition/Task14SessionFoundation').Task14SessionFoundation;
  const f=await Foundation.create({});await f.sessionCoordinator.restoreLatestSession();
  assert.equal(f.rootNavigation.getState().phase,'signed_out');
  await f.passwordLogin.submit({homeserver:'',username:'unit',password:'UNIT',deviceDisplayName:'UNIT'});
  assert.equal(f.rootNavigation.getState().phase,'error');assert.equal(f.rootNavigation.getState().sessionHandle,null);
  assert.equal(e.httpCalls.length,0);assert.equal(e.secure.size,0);
});
test('new composition keeps missing native ABI unavailable, never substitutes a fake restored handle',async()=>{
  const e=environment(),Foundation=e.load('composition/Task14SessionFoundation').Task14SessionFoundation;
  const f=await Foundation.create({});await f.passwordLogin.submit({homeserver:'login-input.unit',username:'unit',password:'UNIT',deviceDisplayName:'UNIT'});
  assert.equal(f.rootNavigation.getState().phase,'error');assert.equal(f.rootNavigation.getState().error.code,'native_bridge_unavailable');
  assert.equal(f.rootNavigation.getState().sessionHandle,null);assert.equal(e.httpCalls.some(call=>call.method==='POST'),false);
  assert.equal(e.secure.size,0);assert.deepEqual(Object.keys(e.nativeAddon),[]);
});
test('cross-session/empty credentials are rejected by original persistence, not repaired with defaults',async()=>{
  const e=environment(),store=await persistence(e),value=session();
  value.credential.sessionId='@other:user-domain.unit';assert.equal((await store.save(value)).success,false);
  value.credential.sessionId=value.metadata.sessionId;value.credential.accessToken='';
  assert.equal((await store.save(value)).success,false);assert.equal(e.secure.size,0);assert.equal(e.prefs.size,0);
});
