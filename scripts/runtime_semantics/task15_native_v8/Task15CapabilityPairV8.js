// An actual persisted SDK/session input and actual cold ORIGINAL app lifecycles.
// No detached AccountClient, presenter event, getter, render or field assignment.
export async function runTask15CapabilityPairV8(tools){
  const {ports,namespace,services,nativeNamespace,binding,result,capture,receipt,ledger}=tools;
  const need=(value,reason)=>{if(!value)throw Error(reason);};
  const budget=()=>need(Date.now()<ports.deadlineEpochMs,'Original deadline exhausted');
  const pair={protocol:'task15.capability-cold-original-owner.v8',parentEpisodeId:result.sessionId,
    phases:[],fixtures:[],complete:false,restored:false};
  const context=ports.launch.originalContext();
  const store=new nativeNamespace.NativeAccountSessionStore(context.filesDir,context.cacheDir);
  const original=await store.read();
  need(original&&original.authMode==='matrix'&&original.phase==='active','Real authenticated matrix session given missing');
  const phase=async(label,eventPhase)=>{
    budget();const prior=tools.observer().read();
    const previousLifecycle=ports.launch.read();
    tools.observer().dispose();
    tools.replaceObserver(ports.observePage({...namespace,AccountClient:services.AccountClient},binding.ownerBinding,result.sessionId));
    const event=await receipt('cold_settings_load','original_settings',()=>ports.launch.coldRestart(),{},eventPhase);
    // Fixed observation delay; only original lifecycle receiver acquisition may
    // be awaited. Never poll for capability/entry/success expected values.
    for(let attempt=0;attempt<30&&!tools.observer().read().available;attempt++){
      budget();await ports.driver.delayMs(50);
    }
    need(tools.observer().read().available,'Original cold page lifecycle/render receiver unavailable');
    await ports.driver.delayMs(300);
    const frame=await capture(label);
    pair.phases.push({label,eventSequence:event.sequence,previousOwner:prior,previousLifecycle,
      lifecycle:ports.launch.read(),frameSequence:frame.sequence,bridgeLedger:ledger.read()});
    return frame;
  };
  try{
    const before=await capture('before_event');
    need(before.pageOwner.state.serverCanDeactivateAccount===true,'Original supported capability given not observed');
    pair.supportedBeforeSequence=before.sequence;
    await phase('after_event','event');
    const unsupported={...original,authMode:'oidc'};
    const saveStart=ledger.read().calls.length;
    await store.save(unsupported);const stored=await store.read();
    need(stored&&stored.authMode==='oidc'&&stored.phase==='active'&&stored.userId===original.userId&&stored.deviceId===original.deviceId,
      'System-backed unsupported session input did not persist');
    pair.fixtures.push({kind:'system_persisted_unsupported_session',bridgeCallStart:saveStart,
      bridgeCallEnd:ledger.read().calls.length,session:{authMode:stored.authMode,phase:stored.phase,userId:stored.userId,deviceId:stored.deviceId}});
    await phase('capability:unsupported_after','invariant');
    const restoreStart=ledger.read().calls.length;
    await store.save(original);const restored=await store.read();
    need(restored&&restored.authMode==='matrix'&&restored.userId===original.userId,'Original matrix input restoration failed');
    pair.fixtures.push({kind:'system_persisted_matrix_restore',bridgeCallStart:restoreStart,
      bridgeCallEnd:ledger.read().calls.length,session:{authMode:restored.authMode,phase:restored.phase,userId:restored.userId,deviceId:restored.deviceId}});
    await phase('capability:restored_positive','invariant');
    pair.restored=true;pair.complete=true;
  }finally{
    if(!pair.restored){await store.save(original);pair.recoveryRestoredInput=true;}
    pair.bridgeLedger=ledger.read();pair.finishedAt=Date.now();
    result.capabilityPair=pair;
  }
  return pair;
}
