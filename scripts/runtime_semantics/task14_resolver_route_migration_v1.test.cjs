'use strict';
// OFFLINE original-body/parameter units only. No HAP, ArkVM, native UI or
// benchmark score. Only system HTTP/router leaves supply controlled effects.
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const ts=require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const root=path.resolve(__dirname,'../..');
const source=process.env.TASK14_REPAIR_SOURCE||path.join(root,'final_dev_nodes/14_join_room_by_address_final_25_03_0');
const phase=process.env.TASK14_REPAIR_PHASE||'after';
const features=path.join(source,'entry/src/main/ets/features');
const read=name=>fs.readFileSync(path.join(features,name+'.ets'),'utf8');
function environment(t,options={}){
  const calls=[],timers=new Set(),cache=new Map();let currentParams;
  const router={
    async replaceUrl(args){calls.push({kind:'router.replace',url:args.url,params:args.params});
      if(options.routeError)throw Error('UNIT route unavailable');currentParams=args.params;},
    async pushUrl(args){calls.push({kind:'router.push',url:args.url});},getParams:()=>currentParams,
    getLength:()=>2,back(){calls.push({kind:'router.back'});}};
  const http={RequestMethod:{GET:'GET'},HttpDataType:{STRING:'STRING'},createHttp(){
    calls.push({kind:'http.create'});
    return {async request(url,args){calls.push({kind:'http.request',url,args});
      if(options.httpError)throw Error('UNIT system network failure');
      return {responseCode:options.status??200,result:options.body??JSON.stringify({room_id:'!actual:remote.test',servers:options.servers??['b.test','a.test']})};},
      destroy(){calls.push({kind:'http.destroy'});}};}};
  const context={console,Map,Set,Promise,encodeURIComponent,
    setTimeout(fn,ms){const id=setTimeout(()=>{timers.delete(id);fn();},ms);timers.add(id);return id;},clearTimeout};
  t.after(()=>{for(const id of timers)clearTimeout(id);});
  function compile(code,file,imports){
    const result=ts.transpileModule(code,{fileName:file,reportDiagnostics:true,
      compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}});
    const errors=(result.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error);
    assert.equal(errors.length,0,'TypeScript syntax-only transformation, not ArkTS SDK compilation');
    const module={exports:{}};
    vm.runInNewContext('(function(require,module,exports){'+result.outputText+'\n})',context,{filename:file})(imports,module,module.exports);
    return module.exports;
  }
  const load=name=>{
    if(cache.has(name))return cache.get(name);
    const code=options.mutate?.(name,read(name))??read(name);
    const value=compile(code,name+'.ets',specifier=>{
      if(specifier==='@ohos.router')return {default:router};
      if(specifier==='@ohos.net.http')return {default:http};
      if(specifier.startsWith('./'))return load(specifier.slice(2));
      throw Error('Unexpected external dependency '+specifier);
    });cache.set(name,value);return value;
  };
  const runtime=load('ChatRuntime'),chat=load('ChatFeature'),join=load('JoinRoomRuntime'),domain=load('JoinRoomByAddressFeature');
  const navigator=new join.RoutedJoinRoomNavigator(runtime.chatNavigator);
  const resolver=new join.SessionRoomAliasResolver(runtime.roomGateway);
  const presenter=new domain.JoinRoomByAddressPresenter(resolver,navigator);
  const getRoom=chat.DemoRoomGateway.prototype.getRoom;
  chat.DemoRoomGateway.prototype.getRoom=function(...args){calls.push({kind:'original.getRoom',args});return getRoom.apply(this,args);};
  async function pageAppear(){
    // Execute ONLY the original lifecycle method text. This is deliberately
    // NOT a native page-owner/UI admission fixture.
    const code=fs.readFileSync(path.join(source,'entry/src/main/ets/pages/Room.ets'),'utf8');
    const scanner=ts.createScanner(ts.ScriptTarget.Latest,true,ts.LanguageVariant.Standard,code);
    let start,end,depth=0,seen=false;
    for(let token=scanner.scan();token!==ts.SyntaxKind.EndOfFileToken;token=scanner.scan()){
      if(start===undefined&&scanner.getTokenText()==='aboutToAppear')start=scanner.getTokenPos();
      if(start!==undefined&&scanner.getTokenText()==='{'){depth++;seen=true;}
      if(seen&&scanner.getTokenText()==='}'&&--depth===0){end=scanner.getTextPos();break;}
    }
    assert.ok(start!==undefined&&end,'Exact original Room lifecycle method span');
    const Page=compile('export class LifecycleOnly {'+code.slice(start,end)+'}', 'Room-lifecycle-ONLY.ts',()=>{throw Error('No import');}).LifecycleOnly;
    context.router=router;
    const page=new Page();page.presenter=new chat.RoomPresenter(runtime.roomGateway);
    let refreshed=false;page.refresh=()=>{refreshed=true;};page.aboutToAppear();
    for(let i=0;i<20&&!refreshed;i++)await new Promise(resolve=>setImmediate(resolve));
    assert.equal(refreshed,true);return page;
  }
  return {calls,router,load,runtime,chat,join,domain,navigator,resolver,presenter,pageAppear};
}

if(phase==='before'){
  test('BEFORE evidence: original resolver invents demo.local and router loses servers',async t=>{
    const e=environment(t);
    // Pre-repair LEGACY leaf diagnostic only; no new application bridge mock.
    const resolver=new e.join.SessionRoomAliasResolver({resolveAlias:async()=> '!remote:foreign.test'});
    const resolved=await resolver.resolveRoomAlias('#remote:foreign.test');
    assert.equal(resolved.roomId,'!remote:foreign.test');
    assert.deepEqual(Array.from(resolved.servers),['demo.local']);
    e.navigator.openRoom(resolved.roomId,['one.test','two.test']);await e.navigator.navigation;
    const route=e.calls.find(c=>c.kind==='router.replace');
    assert.equal(route.params.roomId,resolved.roomId);assert.equal(route.params.serverNames,undefined);
  });
  test('BEFORE evidence: original local alias remains a usable stored room',async t=>{
    const e=environment(t);const resolved=await e.resolver.resolveRoomAlias('#lobby:demo.local');
    const room=await e.runtime.roomGateway.getRoom(resolved.roomId);
    assert.equal(room.name,'Lobby');
  });
}else{
  for(const servers of [['b.test','a.test','b.test'],[]]){
    test('AFTER entire original HTTP/gateway/resolver/presenter/route path preserves '+JSON.stringify(servers),async t=>{
      const e=environment(t,{servers});
      e.navigator.showJoinRoomByAddress();await e.presenter.updateAddress('  #remote:origin.test  ');e.presenter.continue();
      await e.navigator.navigation;
      const request=e.calls.find(c=>c.kind==='http.request'),route=e.calls.find(c=>c.kind==='router.replace');
      assert.equal(request.url,'https://origin.test/_matrix/client/v3/directory/room/%23remote%3Aorigin.test');
      assert.equal(request.args.method,'GET');assert.equal(e.calls.filter(c=>c.kind==='http.destroy').length,1);
      assert.equal(e.presenter.address,'#remote:origin.test');assert.equal(e.presenter.resolvedRoom.roomId,'!actual:remote.test');
      assert.deepEqual(Array.from(e.presenter.resolvedRoom.servers),servers);
      assert.equal(route.url,'pages/Room');assert.equal(route.params.roomId,'!actual:remote.test');
      assert.deepEqual(Array.from(route.params.serverNames),servers);
      assert.equal(e.navigator.addressFlowVisible,false);
      const page=await e.pageAppear();
      const load=e.calls.find(c=>c.kind==='original.getRoom');
      assert.deepEqual(Array.from(load.args[1]),servers);
      assert.equal(page.presenter.room,undefined);assert.equal(page.presenter.error,'Room not found in this session');
      // Navigation and metadata are proven at the unit boundary, NOT remote join/timeline success.
      assert.equal(e.calls.filter(c=>c.kind==='router.replace').length,1);
    });
  }
  test('pending Continue uses the same original resolver result and server list',async t=>{
    const e=environment(t,{servers:['not-alias-domain.test']});
    const pending=e.presenter.updateAddress('#remote:origin.test');e.presenter.continue();await pending;await e.navigator.navigation;
    const route=e.calls.find(c=>c.kind==='router.replace');
    assert.deepEqual(Array.from(route.params.serverNames),['not-alias-domain.test']);
  });
  test('local session lookup, original Room load, DM/create navigation remain compatible',async t=>{
    const e=environment(t);
    const result=await e.resolver.resolveRoomAlias('#lobby:demo.local');e.navigator.openRoom(result.roomId,result.servers);await e.navigator.navigation;
    const page=await e.pageAppear();assert.equal(page.presenter.room.name,'Lobby');assert.equal(page.presenter.error,'');
    assert.equal(e.calls.filter(c=>c.kind==='http.request').length,0);
    await e.runtime.startChatPresenter.selectPerson('@alice:demo.local');
    const routes=e.calls.filter(c=>c.kind==='router.replace');assert.deepEqual(Array.from(routes.at(-1).params.serverNames),[]);
    const create=new e.chat.CreateRoomPresenter(e.runtime.roomGateway,e.runtime.chatNavigator);create.setName('Unit room');await create.submit();
    assert.equal((await e.runtime.roomGateway.getRoom(create.createdRoomId)).name,'Unit room');
    assert.deepEqual(Array.from(e.calls.filter(c=>c.kind==='router.replace').at(-1).params.serverNames),[]);
  });
  test('route parameters defensively copy caller server lists',async t=>{
    const e=environment(t);const servers=['first.test','second.test'];e.navigator.openRoom('!id:test',servers);servers.push('late.test');
    await e.navigator.navigation;
    assert.deepEqual(Array.from(e.calls.find(c=>c.kind==='router.replace').params.serverNames),['first.test','second.test']);
    assert.deepEqual(Array.from(e.navigator.openedServers),['first.test','second.test']);
  });
  for(const options of [{status:404},{status:503},{body:'not-json'},{body:'{"room_id":"!x:test"}'},
    {body:'{"room_id":"!x:test","servers":[1]}'},{httpError:true}]){
    test('directory not-found/error/malformed response never fabricates room/servers '+JSON.stringify(options),async t=>{
      const e=environment(t,options);await e.presenter.updateAddress('#remote:origin.test');e.presenter.continue();
      assert.equal(e.presenter.addressState,e.domain.RoomAddressState.RoomNotFound);
      assert.equal(e.presenter.resolvedRoom,undefined);assert.equal(e.calls.some(c=>c.kind==='router.replace'),false);
      assert.equal(e.calls.filter(c=>c.kind==='http.destroy').length,1);
    });
  }
  test('route failure keeps error recovery; original navigation body is not substituted',async t=>{
    const e=environment(t,{routeError:true});e.navigator.openRoom('!id:test',['server.test']);await e.navigator.navigation;
    assert.equal(e.navigator.navigationError,'UNIT route unavailable');assert.equal(e.navigator.addressFlowVisible,true);
    e.navigator.openRoom('!again:test',['next.test']);await e.navigator.navigation;
    assert.equal(e.calls.filter(c=>c.kind==='router.replace').length,2);
  });
  test('reintroduced hardcoded resolver and dropped route arguments are detected (UNIT mutations)',async t=>{
    for(const kind of ['resolver','route','page']){
      const e=environment(t,{servers:['real.test'],mutate:(name,code)=>{
        if(kind==='resolver'&&name==='JoinRoomRuntime')return code.replace('resolved.servers.slice()',"['demo.local']");
        if(kind==='route'&&name==='JoinRoomRuntime')return code.replace('this.routes.openRoom(roomIdOrAlias, serverNames)','this.routes.openRoom(roomIdOrAlias)');
        if(kind==='page'&&name==='ChatFeature')return code.replace('this.gateway.getRoom(roomId, serverNames.slice())','this.gateway.getRoom(roomId)');
        return code;
      }});
      await e.presenter.updateAddress('#remote:origin.test');e.presenter.continue();await e.navigator.navigation;
      if(kind==='page'){await e.pageAppear();assert.equal(e.calls.find(c=>c.kind==='original.getRoom').args[1],undefined);}
      else assert.notDeepEqual(Array.from(e.calls.find(c=>c.kind==='router.replace').params.serverNames),['real.test']);
    }
  });
  test('production singleton wiring uses system HTTP leaf and declares Internet permission',t=>{
    const e=environment(t);assert.ok(e.runtime.roomGateway instanceof e.chat.DemoRoomGateway);
    const json5=require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5');
    const module=json5.parse(fs.readFileSync(path.join(source,'entry/src/main/module.json5'),'utf8'));
    assert.ok(module.module.requestPermissions.some(p=>p.name==='ohos.permission.INTERNET'));
  });
}
