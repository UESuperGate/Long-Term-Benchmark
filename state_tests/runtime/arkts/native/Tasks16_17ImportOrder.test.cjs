'use strict';
// Full fixture flow with host UI/lifecycle doubles, never native runtime proof.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const ts=require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const root=path.resolve(__dirname,'../../../..');
function loadModules(){
  const cache=new Map();
  function load(file){
    if(cache.has(file))return cache.get(file).exports;
    const module={exports:{}};cache.set(file,module);
    const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS}}).outputText;
    new Function('exports','module','require',code)(module.exports,module,name=>{
      if(name==='@ohos.data.preferences')return{default:{getPreferences:async()=>({put:async()=>{},flush:async()=>{}})}};
      const base=path.resolve(path.dirname(file),name);return load(base+(fs.existsSync(base+'.ets')?'.ets':'.js'));
    });return module.exports;
  }return load;
}
const drain=async()=>{for(let i=0;i<50;i++)await Promise.resolve();};
function selector(values={}){return{...values,id(id){return selector({...values,idValue:id});},
  text(text){return selector({...values,textValue:text});},type(type){return selector({...values,typeValue:type});},inWindow(){return selector(values);}};}
function fixture(task,{ready=true,remount=true}={}){
  const identity=task.startsWith('16'),load=loadModules();
  const project=identity?'16_identity_reset_final_0_5_1':'17_pinned_messages_final_0_5_3';
  const folder=path.join(root,'final_dev_nodes',project,'entry/src/main/ets/features');
  const types=load(path.join(folder,identity?'IdentityResetFeature.ets':'PinnedMessagesFeature.ets'));
  const services=identity?load(path.join(folder,'IdentityResetServices.ets')):undefined;
  if(identity)services.IdentityResetSession.configure(undefined);else types.PinnedMessagesSession.configureRoom(undefined);
  let started=false,checks=0,imports=0,disposed=false,presenter,screen='room_timeline',remounts=0;
  const create=()=>{
    presenter=identity?new types.IdentityResetPresenter(new types.IdentityResetFlowManager(services.IdentityResetSession.createService())):
      types.PinnedMessagesSession.createPresenter();
    screen='room_timeline';presenter.subscribe(()=>{});
    if(!identity){presenter.startRoom({});presenter.parent.load().catch(()=>{});}
  };
  const runClick=id=>{
    if(id==='identity_reset_continue')presenter.continue();
    if(id==='identity_reset_confirm')presenter.confirmReset();
    if(id==='open_pinned_messages'){screen='pinned_messages';presenter.openPinnedMessages({});}
    if(id==='pinned_messages_back')screen='room_timeline';
  };
  const item=(text,type='Text',id='')=>({getText:async()=>text,getType:async()=>type,getId:async()=>id,isEnabled:async()=>true,
    isClickable:async()=>type==='Button',getBounds:async()=>({left:1,right:200,top:1,bottom:200}),click:async()=>{runClick(id);await drain();}});
  const inventory=()=>{
    if(!started||!ready)return[];
    if(identity){const rows=[item('Reset cryptographic identity'),item('Continue','Button','identity_reset_continue')];
      if(presenter.confirmationVisible)rows.push(item('Reset identity','Button','identity_reset_confirm'));
      if(presenter.errorMessage)rows.push(item(presenter.errorMessage));
      return rows;
    }
    const rows=[item('Design team')];
    if(screen==='room_timeline')rows.push(item('Open','Button','open_pinned_messages'));
    else {rows.push(item('Back','Button','pinned_messages_back'));
      if(presenter.listState==='loading')rows.push(item('Loading','Text','pinned_messages_loading'));
      if(presenter.listState==='failed')rows.push(item(presenter.errorMessage,'Text','pinned_messages_failed'));}
    return rows;
  };
  const driver={delayMs:async()=>{await drain();if(!ready)throw new Error('unit unavailable page');},
    findComponents:async q=>{const rows=[];for(const n of inventory())if((!q.idValue||await n.getId()===q.idValue)&&
      (!q.textValue||await n.getText()===q.textValue)&&(!q.typeValue||await n.getType()===q.typeValue))rows.push(n);return rows;}};
  const launch={start:async()=>{assert.equal(started,false);started=true;create();await drain();},
    check:async()=>{checks++;if(!started||!ready)throw new Error('not ready');return{hostVerified:true,focused:true,bundleName:'unit-only'};},
    current:()=>({abilityContext:{},uiContext:{getRouter:()=>({replaceUrl:async()=>{
      remounts++;if(remount){await presenter.dispose();create();await drain();}else throw new Error('unit remount rejected');}})}}),
    read:()=>({started,checks,imports,remounts}),dispose:async()=>{disposed=true;}};
  const probe=load(path.join(__dirname,'Tasks16_17PagePortsUi.js'));
  probe.configurePagePortsBinding(JSON.stringify({taskId:task,bundleName:'unit-only',productionModuleUrl:'actual-types',serviceModuleUrl:'actual-services'}),async url=>{
    assert.ok(started&&checks>0,'import before original Ability/page ready');imports++;return url==='actual-types'?types:services;
  });
  const contract=JSON.parse(fs.readFileSync(path.join(root,'benchmark_tasks',task,'transitions.json')));
  const spec={taskId:task,...contract.cases[0]};
  return{run:async()=>JSON.parse(await probe.runPagePortsUi(JSON.stringify(spec),'unit-only',driver,selector(),launch,
    {getPreferences:async()=>({get:async()=>''})})),read:()=>({started,checks,imports,remounts,disposed})};
}
for(const task of ['16_identity_reset','17_pinned_messages']){
  test(task+' imports only after actual Ability/page readiness; keeps unavailable warmup and real remount',async()=>{
    const f=fixture(task),raw=await f.run();
    assert.equal(raw.failure,undefined);assert.equal(raw.eventExecuted,true);
    assert.deepEqual(raw.bootstrap.setupEvents.map(e=>e.name),['ability_started','original_page_ready','original_module_imported',
      'unconfigured_owner_observed','external_ports_connected','original_page_remounted']);
    assert.equal(raw.sdkSetupOrder,'original_ability_profile_ready_then_original_module_then_external_ports');
    const unavailable=raw.bootstrap.frames[1];assert.equal(unavailable.owner.current.serviceAvailable,false);
    assert.deepEqual(unavailable.externalSdk,[]);assert.match(unavailable.owner.current.errorMessage,/SDK service unavailable/);
    const owners=raw.bootstrap.frames[2].owner.owners;assert.equal(owners.length,2);
    assert.equal(owners[0].disposed,true);assert.equal(owners[0].sdkPortMatches,false);
    assert.equal(owners[1].sdkPortMatches,true);assert.equal(f.read().remounts,1);assert.equal(f.read().disposed,true);
  });
}
test('failed readiness cannot import/configure an original module',async()=>{
  const f=fixture('16_identity_reset',{ready:false}),raw=await f.run();
  assert.equal(raw.eventExecuted,false);assert.match(raw.failure.message,/unit unavailable page/);
  assert.equal(f.read().imports,0);assert.equal(f.read().remounts,0);
});
test('failed framework remount remains unsupported; port config cannot relabel initial owner',async()=>{
  const f=fixture('16_identity_reset',{remount:false}),raw=await f.run();
  assert.equal(raw.eventExecuted,false);assert.match(raw.failure.message,/remount rejected/);
  assert.equal(raw.ownerDiagnostic.current.sdkPortMatches,false);assert.equal(raw.ownerDiagnostic.ownerCount,1);
});
