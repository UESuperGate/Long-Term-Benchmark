'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const importFile=async name=>import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync(path.join(__dirname,name))).toString('base64')+'#'+Math.random());
test('host SDK-leaf unit: ORIGINAL login/auth/deactivate/HTTP/store cleanup bodies execute',async()=>{
  const f=await require('./sdk_unit_fixture.cjs').fixture();
  assert.equal(f.UNIT_ONLY_NOT_NATIVE_RUNTIME,true);assert.equal(f.provider.deactivationCount,2);
  assert.deepEqual(f.provider.requests.map(r=>r.responseStatus),[200,401,200]);
  assert.equal(f.provider.requests[1].body.hasAuth,false);assert.equal(f.provider.requests[2].body.hasAuth,true);
  assert.equal(f.provider.requests[2].body.session,'unit-challenge');
  assert.equal(f.persistedAssetCount,0);assert.equal(f.remainingMetadataFiles,0);assert.equal(f.sessionRemoved,true);
  assert.equal(f.originalDescriptorRestored,true);
  for(const key of ['AccountClient.deactivateAccount','AccountClient.sendDeactivation','AccountClient.requireSuccess','AccountClient.completeCleanup',
    'NativeAccountTransport.post','NativeAccountTransport.close','NativeAccountSessionStore.save','NativeAccountSessionStore.clear'])
    assert.ok(f.ledger.calls.some(c=>c.className+'.'+c.method===key&&c.calledOriginal),key);
});
test('synthetic cold lifecycle: real destroy/create callbacks are required; monitor stays original',async()=>{
  const source=require('./lifecycle.cjs').source();
  const {createTask15LaunchController}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
  let monitor,lifecycle,current,count=0;
  const context={abilityInfo:{bundleName:'unit',name:'EntryAbility',moduleName:'entry'},
    async terminateSelf(){monitor.onAbilityDestroy(current);lifecycle.onWindowStageDestroy(current);lifecycle.onAbilityDestroy(current);}};
  const delegator={addAbilityMonitor:async value=>{monitor=value;},removeAbilityMonitor:async()=>{},
    async startAbility(){current={context};count++;monitor.onAbilityCreate(current);
      lifecycle.onWindowStageCreate(current,{getMainWindow:async()=>({})});monitor.onAbilityForeground(current);}};
  const controller=createTask15LaunchController({delegator,applicationContext:{on:(_,value)=>{lifecycle=value;return 1;},off:async()=>{}}},'unit');
  await controller.start();assert.equal(controller.originalContext(),context);
  await controller.coldRestart();await controller.coldRestart();assert.equal(count,3);
  assert.equal(controller.read().destroyed,false);assert.equal(controller.read().lifecycleError,undefined);
  assert.equal(controller.read().events.filter(e=>e.method==='abilityDestroy').length,2);
  await controller.dispose();
});
test('synthetic lifecycle: foreign concurrent instance is rejected, never treated as cold restart',async()=>{
  const {createTask15LaunchController}=await import('data:text/javascript;base64,'+Buffer.from(require('./lifecycle.cjs').source()).toString('base64')+'#2');
  let monitor;
  const context={abilityInfo:{bundleName:'unit',name:'EntryAbility',moduleName:'entry'}};
  const ports={delegator:{addAbilityMonitor:async m=>{monitor=m;},removeAbilityMonitor:async()=>{},
    startAbility:async()=>{monitor.onAbilityCreate({context});}},applicationContext:{on:()=>1,off:async()=>{}}};
  const launch=createTask15LaunchController(ports,'unit');await launch.start();monitor.onAbilityCreate({context});
  assert.match(launch.read().lifecycleError,/Multiple/);await assert.rejects(launch.coldRestart(),/No live original/);await launch.dispose();
});
test('synthetic capability algorithm: original SDK persisted input, three own cold epochs, restored positive',async()=>{
  const {runTask15CapabilityPairV8}=await importFile('Task15CapabilityPairV8.js');
  let session={authMode:'matrix',phase:'active',userId:'@unit',deviceId:'UNIT'},obs,disposed=0,sequence=0,cold=0;
  const ledgerCalls=[],events=[];
  const ledger={read:()=>({calls:ledgerCalls.slice()})};
  const makeObserver=()=>({read:()=>({available:true,state:{serverCanDeactivateAccount:session.authMode==='matrix'}}),dispose(){disposed++;}});
  obs=makeObserver();
  class Store{async read(){ledgerCalls.push({method:'read'});return {...session};}async save(value){ledgerCalls.push({method:'save'});session={...value};}}
  const launch={originalContext:()=>({filesDir:'unit',cacheDir:'unit'}),read:()=>({events:events.slice()}),
    async coldRestart(){cold++;events.push({method:'unit_real_callback',cold});}};
  const result={sessionId:'unit-own-capability',frames:[]};
  const capture=async label=>{const frame={label,sequence:++sequence,pageOwner:obs.read()};result.frames.push(frame);return frame;};
  await runTask15CapabilityPairV8({ports:{launch,deadlineEpochMs:Date.now()+5000,driver:{delayMs:async()=>{}},observePage:makeObserver},
    namespace:{},services:{},nativeNamespace:{NativeAccountSessionStore:Store,createAccountClient(){throw Error('Detached client forbidden');}},
    binding:{ownerBinding:{}},result,capture,receipt:async(kind,target,run)=>{await run();return {sequence:++sequence,kind,target};},
    ledger,observer:()=>obs,replaceObserver:value=>{obs=value;}});
  assert.equal(cold,3);assert.equal(disposed,3);assert.equal(session.authMode,'matrix');
  assert.equal(result.capabilityPair.complete,true);assert.equal(result.capabilityPair.restored,true);
  assert.deepEqual(result.frames.map(f=>f.label),['before_event','after_event','capability:unsupported_after','capability:restored_positive']);
});
