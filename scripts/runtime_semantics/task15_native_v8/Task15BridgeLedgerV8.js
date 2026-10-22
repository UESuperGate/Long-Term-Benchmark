// Transparent application-owned bridge tracing. Only the external HTTPS server
// supplies responses; no AccountClient/transport/store method is substituted.
const objects=new WeakMap();let nextObject=0;
export const task15BridgeReceiverIdV8=value=>{
  if(!value||(typeof value!=='object'&&typeof value!=='function'))return null;
  if(!objects.has(value))objects.set(value,++nextObject);return objects.get(value);
};
const clone=value=>value===undefined?undefined:JSON.parse(JSON.stringify(value));
const session=value=>value?Object.fromEntries(['schemaVersion','homeserver','userId','deviceId','authMode','phase']
  .filter(key=>value[key]!==undefined).map(key=>[key,value[key]])):null;
export function observeTask15BridgeLedgerV8(account,native){
  const calls=[],restores=[],stack=[];let sequence=0,disposed=false;
  const shape=(name,receiver)=>name==='AccountClient'?{
    transportId:task15BridgeReceiverIdV8(receiver.transport),storeId:task15BridgeReceiverIdV8(receiver.store),
    session:session(receiver.session),closed:receiver.closed,initialized:receiver.initialized,operation:receiver.operation}:{};
  const wrap=(Class,className,method)=>{
    const proto=Class?.prototype,descriptor=proto&&Object.getOwnPropertyDescriptor(proto,method);
    if(!descriptor?.configurable||typeof descriptor.value!=='function')throw Error('Unknown original bridge method: '+className+'.'+method);
    Object.defineProperty(proto,method,{...descriptor,value:function(...args){
      const call={id:++sequence,className,method,receiverId:task15BridgeReceiverIdV8(this),
        parentCallId:stack.at(-1)?.id||null,startedAt:Date.now(),stack:String(new Error().stack),
        args:clone(className==='NativeAccountSessionStore'&&method!=='read'?[session(args[0])]:args),
        before:shape(className,this),calledOriginal:true,returned:false};
      calls.push(call);stack.push(call);let result;
      const finish=(status,value)=>{
        call.settlement={status,at:Date.now()};call.after=shape(className,this);
        if(status==='fulfilled')call.settlement.value=clone(className==='NativeAccountSessionStore'&&method==='read'?session(value):value);
        else call.settlement.error=String(value);
      };
      try{result=descriptor.value.apply(this,args);call.returned=true;}
      catch(error){finish('threw',error);throw error;}
      finally{stack.pop();}
      if(result&&typeof result.then==='function')result.then(value=>finish('fulfilled',value),error=>finish('rejected',error));
      else finish('fulfilled',result);
      return result;
    }});
    restores.push(()=>Object.defineProperty(proto,method,descriptor));
  };
  try{
    for(const method of ['restore','canDeactivateAccount','login','deactivateAccount','sendDeactivation','requireSuccess','completeCleanup'])
      wrap(account.AccountClient,'AccountClient',method);
    for(const method of ['post','close'])wrap(native.NativeAccountTransport,'NativeAccountTransport',method);
    for(const method of ['read','save','clear'])wrap(native.NativeAccountSessionStore,'NativeAccountSessionStore',method);
  }catch(error){for(const restore of restores.reverse())restore();throw error;}
  return {read:()=>clone({protocol:'task15.changed-body-ledger.v8',calls,allWrappersPassOriginal:true,
    controlledBoundary:'external HTTPS server only',systemHttpReplaced:false}),
    dispose(){if(disposed)return;disposed=true;for(const restore of restores.reverse())restore();}};
}
