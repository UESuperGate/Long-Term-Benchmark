'use strict';
// Host-only instrumentation tests. No native page/calibration claims.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const root=path.resolve(__dirname,'../../../..');
function modules() {
  const cache=new Map();
  function load(file) {
    file=path.resolve(file);
    if(cache.has(file))return cache.get(file).exports;
    const result={exports:{}};cache.set(file,result);
    const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS}}).outputText;
    new Function('exports','module','require',code)(result.exports,result,name=>{
      const resolved=path.resolve(path.dirname(file),name);
      return load(resolved+(fs.existsSync(resolved+'.ets')?'.ets':'.js'));
    });
    return result.exports;
  }
  return load;
}
function fixture() {
  const load=modules(),feature=path.join(root,'final_dev_nodes/16_identity_reset_final_0_5_1/entry/src/main/ets/features');
  const types=load(path.join(feature,'IdentityResetFeature.ets'));
  const services=load(path.join(feature,'IdentityResetServices.ets'));
  const sdk=load(path.join(__dirname,'Tasks16_17SdkBoundary.js'));
  const bindings=load(path.join(__dirname,'Task16Case003DomainInvariant.js')).createCase003Bindings();
  const control=sdk.createIdentitySdkControl();
  const observer=sdk.observePageOwner(types,'16_identity_reset',control.port,control.handles,
    {capture:bindings.capture,scope:()=>bindings.scope()});
  services.IdentityResetSession.configure(control.port);
  // Unit-owned objects only. The native driver must retain actual page receivers
  // instead; these constructions are never used as benchmark evidence.
  const manager=new types.IdentityResetFlowManager(services.IdentityResetSession.createService());
  const presenter=new types.IdentityResetPresenter(manager);
  presenter.subscribe(()=>{});
  return {bindings,observer,control,manager,presenter};
}
test('retains original callback only from primary scope; missing binding cannot invoke anything',()=>{
  const bindings=modules()(path.join(__dirname,'Task16Case003DomainInvariant.js')).createCase003Bindings();
  assert.throws(()=>bindings.productionBindings(),/Primary UI/);
  bindings.capture({kind:'presenter',method:'confirmReset',receiver:{}});
  assert.throws(()=>bindings.productionBindings(),/Primary UI/);
});
test('actual production methods reenter same receiver, two manager entries, one held SDK request and same settled handle',async()=>{
  const f=fixture();
  try {
    f.presenter.continue();
    f.bindings.scope('primary_ui');
    function startConfirmedReset(){return f.presenter.confirmReset();}
    const primary=startConfirmedReset();f.bindings.scope('runtime');
    const bound=f.bindings.productionBindings();
    assert.equal(bound.presenterReceiver,f.presenter);assert.equal(bound.managerReceiver,f.manager);
    assert.equal(f.observer.read().managerInvocations.length,1);
    f.bindings.scope('domain_invariant_loading');
    const repeated=bound.presenterMethod.call(bound.presenterReceiver);f.bindings.scope('runtime');
    const held=f.observer.read().managerInvocations;
    assert.equal(held.length,2);assert.equal(f.control.requests.length,1);
    assert.deepEqual(held.map(row=>row.stateAtEntry),['uninitialized','loading']);
    assert.equal(held[0].pendingAfterReturnId,held[1].pendingAtEntryId);
    assert.ok(held.every(row=>!row.settled));
    const sdkHandle=f.control.deliverHandle(0,'password');await Promise.all([primary,repeated]);
    f.bindings.scope('domain_invariant_cached_success');
    const result=await bound.managerMethod.call(bound.managerReceiver);f.bindings.scope('runtime');
    assert.equal(result,f.manager.currentHandle);assert.equal(result.sdkHandle,sdkHandle);
    const rows=f.observer.read().managerInvocations;
    assert.equal(rows.length,3);assert.ok(rows.every(row=>row.settled));
    assert.ok(rows.every(row=>row.returnedHandleId===rows[0].returnedHandleId));
    assert.ok(rows.every(row=>row.originalMethodId===rows[0].originalMethodId));
    assert.equal(rows[2].stateAtEntry,'success');assert.equal(f.control.requests.length,1);
    assert.equal(f.observer.read().ownerCount,1);
  }finally {f.observer.dispose();}
});
test('different manager receiver or replaced public method invalidates binding',()=>{
  for(const changed of ['receiver','callback']) {
    const f=fixture();
    try {
      f.bindings.scope('primary_ui');f.presenter.confirmReset();f.bindings.scope('runtime');
      if(changed==='receiver')f.presenter.manager={};
      else f.presenter.confirmReset=()=>Promise.resolve();
      assert.throws(()=>f.bindings.productionBindings(),/exact original|binding changed/);
    }finally {f.observer.dispose();}
  }
});
