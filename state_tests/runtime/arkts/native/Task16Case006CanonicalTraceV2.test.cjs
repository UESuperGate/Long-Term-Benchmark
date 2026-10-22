'use strict';
// Offline only: synthetic trace units and real source-copy installer checks.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const installer=require('./Tasks16_17PagePortsV2.install.cjs');
const modulePromise=import('data:text/javascript;base64,'+fs.readFileSync(path.join(__dirname,'Task16Case006CanonicalTraceV2.js')).toString('base64'));
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
function data(){return {ownerCount:2,current:{ownerId:13,managerId:14,sdkPortMatches:true},
  owners:[{ownerId:3,managerId:4,disposed:true,serviceAvailable:false,sdkPortId:null},
    {ownerId:13,managerId:14,sdkPortMatches:true}],managerTransitions:[
      {managerId:4,from:'uninitialized',to:'loading'},{managerId:4,from:'loading',to:'failure'},
      {managerId:14,from:'uninitialized',to:'loading'},{managerId:14,from:'loading',to:'failure'},
      {managerId:14,from:'failure',to:'uninitialized'},{managerId:14,from:'uninitialized',to:'loading'}]};}
test('actual canonical scope retains ALL warmup and input arrays unchanged',async()=>{
  const {canonicalManagerTraceV2:select}=await modulePromise;
  const input=data(),before=JSON.stringify(input),result=select(input,{warmupOwnerId:3});
  assert.equal(JSON.stringify(input),before);assert.equal(result.allTransitions.length,6);
  assert.equal(result.retiredWarmupTransitions.length,2);assert.equal(result.canonicalTransitions.length,4);
  assert.equal(result.canonicalManagerId,14);assert.equal(result.retiredWarmupManagerId,4);
});
test('unknown manager cannot be silently filtered',async()=>{
  const {canonicalManagerTraceV2:select}=await modulePromise;
  const input=data();input.managerTransitions.push({managerId:999,from:'loading',to:'failure'});
  assert.throws(()=>select(input,{warmupOwnerId:3}),/unknown manager/);
});
test('retired identity must actually be disposed, unavailable and unbound',async()=>{
  const {canonicalManagerTraceV2:select}=await modulePromise;
  for(const [key,value] of [['disposed',false],['serviceAvailable',true],['sdkPortId',22]]){
    const input=data();input.owners[0][key]=value;
    assert.throws(()=>select(input,{warmupOwnerId:3}),/retired warm-up/);
  }
});
test('canonical discontinuity is unavailable, never a manufactured failure sequence',async()=>{
  const {canonicalManagerTraceV2:select}=await modulePromise;
  const input=data();input.managerTransitions[3].from='success';
  assert.throws(()=>select(input,{warmupOwnerId:3}),/discontinuous/);
});
test('new derived fixture changes only the exact case006 sequence block',()=>{
  const original=fs.readFileSync(path.join(__dirname,'Tasks16_17PagePortsUi.js'),'utf8');
  const generated=installer.compose();
  assert.ok(generated.endsWith(original.replace(
    '          const transitions = observer.read().managerTransitions;\n          const stateSequence = [transitions[0]?.from, ...transitions.map(value => value.to)];',
    '          raw.canonicalManagerTrace = canonicalManagerTraceV2(observer.read(), raw.bootstrap);\n          const transitions = raw.canonicalManagerTrace.canonicalTransitions;\n          const stateSequence = [transitions[0]?.from, ...transitions.map(value => value.to)];')));
  assert.ok(generated.includes('await launch.start()'));
});
const root=path.resolve(__dirname,'../../../..');
for(const [task,source] of [['16_identity_reset','16_identity_reset_base_0_5_0'],
  ['16_identity_reset','final_dev_nodes/16_identity_reset_final_0_5_1'],
  ['17_pinned_messages','17_pinned_messages_base_0_5_1'],
  ['17_pinned_messages','final_dev_nodes/17_pinned_messages_final_0_5_3']]){
  test('v2 installer does not change production for '+task+' '+source,t=>{
    const work=fs.mkdtempSync(path.join(os.tmpdir(),'ltb-v2-generator-only-'));
    t.after(()=>fs.rmSync(work,{recursive:true,force:true}));
    fs.mkdirSync(path.join(work,'entry/src/test'),{recursive:true});
    fs.cpSync(path.join(root,source,'entry/src/main'),path.join(work,'entry/src/main'),{recursive:true});
    fs.cpSync(path.join(root,source,'AppScope'),path.join(work,'AppScope'),{recursive:true});
    fs.writeFileSync(path.join(work,'entry/src/test/native-bundle.js'),
      "if (candidateUI) await bridge.ui.navigate(candidateUI.route);\nmodule.exports.runCase({ ...context, native: bridge, caseSpec });");
    fs.writeFileSync(path.join(work,'entry/src/test/NativeBundle.test.ets'),'export default function nativeBundleTests(): void {}');
    const previous=process.env.LTB_PAGE_PORTS_TASK;process.env.LTB_PAGE_PORTS_TASK=task;
    let result;try{result=installer.install(work);}finally{if(previous===undefined)delete process.env.LTB_PAGE_PORTS_TASK;else process.env.LTB_PAGE_PORTS_TASK=previous;}
    assert.equal(result.productionUnchanged,true);assert.equal(result.fixtures.length,12);
    const installed=fs.readFileSync(path.join(work,'entry/src/test/Tasks16_17PagePortsUi.js'));
    assert.equal(hash(installed),result.case006Derivation.installedUiSha256);
    const ui=result.fixtures.find(row=>row.installedPath==='entry/src/test/Tasks16_17PagePortsUi.js');
    assert.equal(ui.sha256,hash(installed));assert.notEqual(ui.sourceSha256,ui.sha256);
    for(const item of result.production)assert.equal(hash(fs.readFileSync(path.join(work,item.path))),item.sha256);
  });
}
