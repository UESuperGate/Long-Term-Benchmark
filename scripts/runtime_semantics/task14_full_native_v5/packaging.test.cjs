'use strict';
// Real source + bundle generator + installers, NOT Hvigor/SDK/device execution.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const test=require('node:test'),assert=require('node:assert/strict'),cp=require('node:child_process');
const root=path.resolve(__dirname,'../../..'),installer=require('./install.cjs');
const generate=require('../arkts_native_bundle.cjs').generate;
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
const source=path.join(root,'final_dev_nodes/14_join_room_by_address_final_25_03_0');
function withWork(fn){
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'ltb-task14-full-offline-unit-'));
  try{
    const work=path.join(temp,'work'),evidence=path.join(temp,'evidence');
    fs.cpSync(source,work,{recursive:true,filter:file=>!['.git','build','.hvigor','oh_modules','node_modules'].includes(path.basename(file))});
    fs.mkdirSync(path.join(work,'entry/src/test'),{recursive:true});fs.mkdirSync(evidence);
    generate(work,evidence,'14_join_room_by_address','agent',source,true,
      {device:true,caseId:'jr_state_009_dismiss_closes_flow'});
    return fn(work,evidence);
  }finally{fs.rmSync(temp,{recursive:true,force:true});}
}
test('real final: all-nine dispatch, one legacy leaf module, exact compiled fixture hashes, unchanged production',()=>withWork(work=>{
  const report=installer.install(work,{deadlineEpochMs:Date.now()+60000});
  assert.equal(report.productionUnchanged,true);
  assert.equal(report.protocol,'task14.full-nine-original-owner.v5');
  assert.equal(report.legacyLeafEligibility.newBridgeMode,'pass_through_original');
  assert.equal(report.legacyLeafEligibility.baselineMethodSha256,report.legacyLeafEligibility.candidateMethodSha256);
  for(const item of report.production)assert.equal(hash(fs.readFileSync(path.join(source,item.path))),item.sha256);
  for(const item of report.fixtures)assert.equal(hash(fs.readFileSync(path.join(work,item.path))),item.sha256);
  const expected=JSON.parse(cp.execFileSync('python3',['-B','-c',
    'import json; from scripts.runtime_semantics.task14_full_native_packaging_v5 import expected_fixtures; print(json.dumps(expected_fixtures()))'],
    {cwd:root,env:{...process.env,PYTHONPATH:'scripts:.'},encoding:'utf8',timeout:10000}));
  const order=(a,b)=>a.name.localeCompare(b.name);
  assert.deepEqual(report.fixtures.map(item=>({name:path.basename(item.path),sha256:item.sha256})).sort(order),expected.sort(order));
  const alias=fs.readFileSync(path.join(work,'entry/src/test/Task14PageObserver.js'),'utf8');
  assert.equal(alias,installer.pageObserverAlias);
  const oldBypass="bridgeDescriptor.value.call(this,alias)";
  assert.ok(fs.readFileSync(path.join(work,'entry/src/test/Task14JoinOwnerV3.js'),'utf8').includes(oldBypass));
  if(process.env.LTB_OFFLINE_RECEIPT_DIR)fs.writeFileSync(path.join(process.env.LTB_OFFLINE_RECEIPT_DIR,'task14-full-final.json'),
    JSON.stringify({sdkCompiled:false,deviceStarted:false,productionUnchanged:true,fixtures:report.fixtures,
      legacyLeafEligibility:report.legacyLeafEligibility},null,2)+'\n',{flag:'wx'});
}));
test('modified old leaf: refuse external fixture, never source-inferred semantic FAIL',()=>withWork(work=>{
  const file=path.join(work,'entry/src/main/ets/features/ChatFeature.ets');
  const code=fs.readFileSync(file,'utf8');
  assert.equal(code.split("alias === '#lobby:demo.local'").length,2);
  fs.writeFileSync(file,code.replace("alias === '#lobby:demo.local'","alias === '#changed:example.org'"));
  assert.throws(()=>installer.install(work,{deadlineEpochMs:Date.now()+60000}),/changed legacy leaf logic/);
}));
