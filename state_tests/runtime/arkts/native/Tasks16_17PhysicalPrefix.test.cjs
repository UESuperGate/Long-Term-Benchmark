'use strict';
// Transport mocks test routing only, never semantic calibration.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
function moduleAt(name) {
  const module = {exports:{}};
  const code = ts.transpileModule(fs.readFileSync(path.join(__dirname,name+'.js'),'utf8'), {
    compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS}}).outputText;
  new Function('exports','module','require',code)(module.exports,module,dependency=>moduleAt(dependency));
  return module.exports;
}
function scene(task, noChange=false) {
  let changed=false, launches=0, disposed=0, clicks=0;
  const identity=task.startsWith('16');
  const node=(text,type='Text',id='')=>({getText:async()=>text,getType:async()=>type,getId:async()=>id,
    isEnabled:async()=>true,isClickable:async()=>type==='Button',getBounds:async()=>({left:1,right:99,top:1,bottom:99}),
    click:async()=>{clicks++;if(!noChange)changed=true;}});
  const inventory=()=>identity ? [node('Chat backup'),node('Enable backup','Button'),node('Recover','Button'),
    node(changed?'Backup state: enabled':'Backup state: disabled')] :
    [node('Design team'),node('Next','Button','pinned_banner_next'),node(changed?'Welcome to the room':'Please read the room rules')];
  function selector(values={}) {
    return {...values,text(value){return selector({...values,textValue:value});},type(value){return selector({...values,typeValue:value});},
      id(value){return selector({...values,idValue:value});},inWindow(){return selector(values);}};
  }
  const driver={delayMs:async()=>{},findComponents:async query=>Promise.all(inventory().map(async n=>
    (!query.textValue||await n.getText()===query.textValue)&&(!query.typeValue||await n.getType()===query.typeValue)&&
    (!query.idValue||await n.getId()===query.idValue)?n:null)).then(rows=>rows.filter(Boolean))};
  const launch={start:async()=>{launches++;},check:async()=>({hostVerified:true,focused:true,bundleName:'unit-only'}),
    current:()=>({abilityContext:{}}),
    read:()=>({launches,clicks,disposed}),dispose:async()=>{disposed++;}};
  return {driver,ON:selector(),launch,read:()=>({launches,clicks,disposed})};
}
for(const task of ['16_identity_reset','17_pinned_messages']) {
  test(task+' missing module still launches physical page and clicks original control',async()=>{
    const probe=moduleAt('Tasks16_17PagePortsUi'),f=scene(task);
    let imports=0,importBeforeReady=false;
    probe.configurePagePortsBinding(JSON.stringify({taskId:task,bundleName:'unit-only',productionModuleUrl:'missing'}),
      async()=>{imports++;importBeforeReady=f.read().launches!==1;throw new Error('Module missing, not a semantic failure');});
    const raw=JSON.parse(await probe.runPagePortsUi(JSON.stringify({taskId:task,caseId:'unit',invariants:['original']}),
      'unit-only',f.driver,f.ON,f.launch,{getPreferences:async()=>({get:async()=>''})}));
    assert.equal(raw.classification,'physical_prefix_completed');
    assert.equal(imports,1);assert.equal(importBeforeReady,false);
    assert.deepEqual(f.read(),{launches:1,clicks:1,disposed:1});
    assert.equal(raw.observed,null);assert.deepEqual(raw.invariantChecks,[]);
    assert.deepEqual(raw.unevaluatedInvariants,['original']);
    assert.ok(raw.frames.every(frame=>frame.inventory.length>0));
  });
}
test('missing module plus no rendered state transition stays unavailable',async()=>{
  const probe=moduleAt('Tasks16_17PhysicalPrefix'),f=scene('16_identity_reset',true);
  const raw=await probe.runPhysicalPrefix({taskId:'16_identity_reset',invariants:['original']},'unit-only',f.driver,f.ON,f.launch);
  assert.equal(raw.eventExecuted,false);assert.ok(raw.failure);assert.equal(raw.classification,'unverified');
});
