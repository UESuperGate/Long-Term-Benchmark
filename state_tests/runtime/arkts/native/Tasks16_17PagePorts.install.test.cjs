'use strict';
// Generator-only tests. No compiler, model, device or production writes.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {install}=require('./Tasks16_17PagePorts.install.cjs');
const root=path.resolve(__dirname,'../../../..');
for(const [task,source] of [
  ['16_identity_reset','16_identity_reset_base_0_5_0'],
  ['16_identity_reset','final_dev_nodes/16_identity_reset_final_0_5_1'],
  ['17_pinned_messages','17_pinned_messages_base_0_5_1'],
  ['17_pinned_messages','final_dev_nodes/17_pinned_messages_final_0_5_3']]){
  test('explicit '+task+' generator preserves production in '+source,t=>{
    const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'ltb-import-order-unit-'));
    t.after(()=>fs.rmSync(temporary,{recursive:true,force:true}));
    const candidate=path.join(temporary,'arbitrary-standalone-agent');
    fs.mkdirSync(path.join(candidate,'entry/src/test'),{recursive:true});
    fs.cpSync(path.join(root,source,'entry/src/main'),path.join(candidate,'entry/src/main'),{recursive:true});
    fs.cpSync(path.join(root,source,'AppScope'),path.join(candidate,'AppScope'),{recursive:true});
    const tests=path.join(candidate,'entry/src/test');
    fs.writeFileSync(path.join(tests,'native-bundle.js'),
      "const taskId='explicit-only'; if (candidateUI) await bridge.ui.navigate(candidateUI.route);\n"+
      'module.exports.runCase({ ...context, native: bridge, caseSpec });');
    fs.writeFileSync(path.join(tests,'NativeBundle.test.ets'),'export default function nativeBundleTests(): void {}');
    const prior=process.env.LTB_PAGE_PORTS_TASK;process.env.LTB_PAGE_PORTS_TASK=task;
    let result;try{result=install(candidate);}finally{if(prior===undefined)delete process.env.LTB_PAGE_PORTS_TASK;else process.env.LTB_PAGE_PORTS_TASK=prior;}
    assert.equal(result.productionUnchanged,true);assert.equal(result.fixtures.length,12);
    assert.ok(result.fixtures.every(fixture=>fs.existsSync(path.join(candidate,fixture.installedPath))));
    const ui=fs.readFileSync(path.join(tests,'Tasks16_17PagePortsUi.js'),'utf8');
    assert.ok(ui.indexOf('await launch.start()')<ui.indexOf('await binding.importModule(config.productionModuleUrl)'));
    assert.match(ui,/original_ability_profile_ready_then_original_module_then_external_ports/);
    assert.match(ui,/replaceUrl\(\{ url: 'pages\/Index' \}\)/);
    assert.ok(!result.production.some(item=>item.path.startsWith('entry/src/test/')));
  });
}
