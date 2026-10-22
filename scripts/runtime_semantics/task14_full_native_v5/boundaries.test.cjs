'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const load=async name=>import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync(path.join(__dirname,name))).toString('base64')+'#'+Math.random());
async function fixture(){
  const module=await load('Task14JoinOwnerV6.js');let bridgeBodyCalls=0,returnedPromise;
  class DemoRoomGateway { async resolveAlias(){throw Error('Original external leaf must be controlled in this synthetic unit');} }
  class SessionRoomAliasResolver {
    resolveRoomAlias(alias){bridgeBodyCalls++;returnedPromise=this.gateway.resolveAlias(alias).then(roomId=>
      roomId===undefined?undefined:{roomId,servers:['demo.local']});return returnedPromise;}
    constructor(gateway){this.gateway=gateway;}
  }
  class JoinRoomByAddressPresenter {
    constructor(){this.resolver=new SessionRoomAliasResolver(new DemoRoomGateway());this.address='';}
    visibleAddressState(){return 'unknown';}
    updateAddress(value){this.address=value;return this.resolver.resolveRoomAlias(value);}
  }
  const leaf=Object.getOwnPropertyDescriptor(DemoRoomGateway.prototype,'resolveAlias');
  const bridge=Object.getOwnPropertyDescriptor(SessionRoomAliasResolver.prototype,'resolveRoomAlias');
  module.configureTask14LegacyLeafV6({DemoRoomGateway});
  const observer=module.installTask14JoinOwnerV6({JoinRoomByAddressPresenter});
  observer.bindExternalResolver({SessionRoomAliasResolver});
  const presenter=new JoinRoomByAddressPresenter();presenter.visibleAddressState();
  return {module,observer,presenter,DemoRoomGateway,SessionRoomAliasResolver,leaf,bridge,
    bodyCalls:()=>bridgeBodyCalls,promise:()=>returnedPromise};
}
test('synthetic: new bridge body and original returned Promise are preserved; servers are NOT injected',async()=>{
  const f=await fixture();try{
    const result=f.presenter.updateAddress('#team:example.org');assert.equal(result,f.promise());assert.equal(f.bodyCalls(),1);
    f.observer.resolveExternal(1,{roomId:'!team:example.org',servers:['example.org']});
    assert.deepEqual(await result,{roomId:'!team:example.org',servers:['demo.local']});
    const state=f.observer.read();assert.equal(state.originalBridgeCalls[0].calledOriginal,true);
    assert.deepEqual(state.originalBridgeCalls[0].value.servers,['demo.local']);
    assert.equal(state.resolverRequests[0].externalLeaf,'DemoRoomGateway.resolveAlias');
  }finally{f.observer.dispose();}
});
test('synthetic: same alias concurrent requests stay bound to their own synchronous bridge call',async()=>{
  const f=await fixture();try{
    const first=f.presenter.updateAddress('#same:example.org'),second=f.presenter.updateAddress('#same:example.org');
    assert.deepEqual(f.observer.read().resolverRequests.map(r=>r.bridgeCallId),[1,2]);
    f.observer.resolveExternal(2,{roomId:'!second'});f.observer.resolveExternal(1,{roomId:'!first'});
    assert.equal((await first).roomId,'!first');assert.equal((await second).roomId,'!second');
  }finally{f.observer.dispose();}
});
test('synthetic: direct leaf call / different gateway cannot acquire original-bridge eligibility',async()=>{
  const f=await fixture();try{
    assert.throws(()=>f.presenter.resolver.gateway.resolveAlias('#x'),/original new bridge/);
    assert.throws(()=>new f.DemoRoomGateway().resolveAlias('#x'),/original new bridge/);
  }finally{f.observer.dispose();}
});
test('synthetic: unrelated bridge receiver is refused, not scored as missing feature',async()=>{
  const f=await fixture();try{
    assert.throws(()=>new f.SessionRoomAliasResolver(new f.DemoRoomGateway()).resolveRoomAlias('#x'),/actual page owner/);
    assert.equal(f.bodyCalls(),0);
  }finally{f.observer.dispose();}
});
test('synthetic: rejected original bridge records failure without fabricated output',async()=>{
  const f=await fixture();try{
    const result=f.presenter.updateAddress('#missing');f.observer.settle(1);await assert.rejects(result,/External directory failure/);
    assert.equal(f.observer.read().originalBridgeCalls[0].settlement,'rejected');
    assert.equal(f.observer.read().originalBridgeCalls[0].value,undefined);
  }finally{f.observer.dispose();}
});
test('synthetic: disposal restores exact original bridge and leaf descriptors',async()=>{
  const f=await fixture();f.observer.dispose();
  assert.deepEqual(Object.getOwnPropertyDescriptor(f.SessionRoomAliasResolver.prototype,'resolveRoomAlias'),f.bridge);
  assert.deepEqual(Object.getOwnPropertyDescriptor(f.DemoRoomGateway.prototype,'resolveAlias'),f.leaf);
});
test('all original Task14 suites import the ONE configured observer module',()=>{
  const installer=require('./install.cjs');
  assert.equal(installer.pageObserverAlias,"export { installTask14Observer } from './Task14JoinOwnerV3';\n");
  assert.equal(installer.extraFiles().filter(([,name])=>name==='Task14JoinOwnerV3.js').length,1);
  const bridge=installer.bridgeSource();assert.match(bridge,/evaluateTask14FullNativeV5\(args/);
  for(let n=1;n<=9;n++)assert.match(bridge,new RegExp('jr_state_00'+n+'_'));
});
test('synthetic SDK clock: unrelated timers pass through; actual callback times drive evidence',async()=>{
  const {installTask14OwnerClockV5}=await load('Task14OwnerClockV5.js');
  const saved=globalThis.setTimeout;
  class JoinRoomByAddressPresenter { schedule(callback){return setTimeout(callback,300);} }
  const original=JoinRoomByAddressPresenter.prototype.schedule,clock=installTask14OwnerClockV5({JoinRoomByAddressPresenter},()=>{});
  try{
    let outside=false,inside=false;await new Promise(resolve=>setTimeout(()=>{outside=true;resolve();},1));
    assert.equal(outside,true);assert.equal(clock.read().timers.length,0);
    new JoinRoomByAddressPresenter().schedule(()=>{inside=true;});
    await clock.advance(299);assert.equal(inside,false);assert.equal(clock.read().now,299);
    await clock.advance(1);assert.equal(inside,true);
    assert.equal(clock.read().calls.find(c=>c.method==='timerCallback').at,300);
  }finally{clock.dispose();}
  assert.equal(globalThis.setTimeout,saved);assert.equal(JoinRoomByAddressPresenter.prototype.schedule,original);
});
test('synthetic SDK clock: cancelled callback never fires and receiver identity cannot be switched',async()=>{
  const {installTask14OwnerClockV5}=await load('Task14OwnerClockV5.js');
  class JoinRoomByAddressPresenter { schedule(callback){return setTimeout(callback,300);} cancel(id){clearTimeout(id);} }
  const clock=installTask14OwnerClockV5({JoinRoomByAddressPresenter},()=>{});
  try{
    const owner=new JoinRoomByAddressPresenter();let fired=false;const id=owner.schedule(()=>{fired=true;});owner.cancel(id);
    assert.throws(()=>new JoinRoomByAddressPresenter().schedule(()=>{}),/crossed original page owners/);
    await clock.advance(10000);assert.equal(fired,false);assert.equal(clock.read().timers[0].cancelled,true);
  }finally{clock.dispose();}
});
