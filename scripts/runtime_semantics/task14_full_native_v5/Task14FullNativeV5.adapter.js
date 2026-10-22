import { startTask14Page } from './Task14DeviceUi.core';
import { installTask14JoinOwnerV3, configureTask14LegacyLeafV6 } from './Task14JoinOwnerV3';
import { runTask14RealRoutesV3 } from './Task14RealRoutesV3.suite';
import { runTask14RealFlowV2 } from './Task14RealFlowV2.suite';
import { runTask14Transition } from './Task14DeviceUi.suite';
import { installTask14OwnerClockV5 } from './Task14OwnerClockV5';
import { runTask14ScalarCasesV5 } from './Task14ScalarCasesV5';
const clone = value => value===undefined?undefined:JSON.parse(JSON.stringify(value));
export async function evaluateTask14FullNativeV5(args,config,ports,record) {
  const nonce=args.native?.capabilities?.execution?.nonce;
  const raw={protocol:'task14.full-nine-original-owner.v5',taskId:args.taskId,caseId:args.caseSpec.caseId,
    traceDigest:args.caseSpec.traceDigest,nonce,sessionId:nonce+':'+args.caseSpec.caseId,productionSources:config.productionSources,
    samples:[],actions:[],records:[],entryExecuted:false,released:false,failure:null};
  let original, owner, clock, sequence=0;
  const emit=event=>{raw.records.push({sequence:++sequence,at:Date.now(),clockAt:clock?.read().now,event:clone(event)});record(event);};
  try {
    if(!/^[a-f0-9]{32}$/.test(nonce||'') || Date.now()>=config.deadlineEpochMs) throw Error('Fresh native nonce/deadline missing');
    // Register the presenter's bundled class metadata, not unrelated entry/
    // SDK files or a second detached ChatRuntime singleton graph.
    args.load(config.presenterSourcePath);
    original=await startTask14Page(ports,config,emit);raw.entryExecuted=true;
    const ready=await original.observeBracketed('original:ready',{search:[{id:'people_search_input'}]},()=>({}));
    if(!ready.controls.search.visible) throw Error('Original root positive control absent');
    const namespace=await ports.importModule(config.productionModuleUrl);
    configureTask14LegacyLeafV6(await ports.importModule(config.chatFeatureModuleUrl));
    owner=installTask14JoinOwnerV3(namespace,emit);
    const scalar=['update_trims_and_debounces','valid_address_resolves','timeout_recovers'].includes(args.caseSpec.key);
    if(scalar) {
      owner.bindExternalResolver(config.resolverModuleUrl?await ports.importModule(config.resolverModuleUrl):namespace);
      clock=installTask14OwnerClockV5(namespace,emit);
    }
    const session={...original,
      observeBracketed:async(label,selectors,read=()=>owner.read())=>{
        const beginSequence=++sequence;
        const frame=await original.observeBracketed(label,selectors,read);
        frame.pageOwner=owner.read();frame.acquisition={beginSequence,endSequence:++sequence,sessionId:raw.sessionId};
        raw.samples.push(clone(frame));return frame;
      },
      action:async(kind,control,value)=>{
        const action={kind,control:clone(control),value,beginSequence:++sequence,sessionId:raw.sessionId,executed:false};
        raw.actions.push(action);try{await original.action(kind,control,value);action.executed=true;}
        finally{action.endSequence=++sequence;}
      }};
    session.observe=(label,selectors)=>session.observeBracketed(label,selectors,()=>owner.read());
    const spec={...args.caseSpec,taskId:args.taskId};
    if(scalar)raw.transition=await runTask14ScalarCasesV5(spec,config,session,owner,clock,emit);
    else if(spec.key==='entry_opens_address_flow')raw.transition=await runTask14RealFlowV2(spec,config,session,ports.importModule,emit,args.trace);
    else if(['invalid_after_continue','not_found_recovers'].includes(spec.key))raw.transition=await runTask14Transition(spec,config,session,ports.importModule,emit,args.trace);
    else raw.transition=await runTask14RealRoutesV3(spec,config,session,ports.importModule,emit,args.trace);
  }catch(error){raw.failure=String(error);}
  finally{
    try{clock?.dispose();owner?.dispose();if(original){await original.release();raw.released=true;}}
    catch(error){raw.failure='Owned runtime cleanup: '+String(error);}
    raw.finishedAt=Date.now();raw.deadlineEpochMs=config.deadlineEpochMs;
  }
  emit({method:'Task14.fullNativeEpisodeV5',available:raw.entryExecuted,caseId:raw.caseId,sessionId:raw.sessionId});
  return {observed:{},invariantChecks:[],evidence:[{fullNativeEpisodeV5:raw}],
    unsupported:'Fresh original-owner episode requires independent full-nine admission',observationLevel:'native_candidate_ui'};
}
