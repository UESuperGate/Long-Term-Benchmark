// New migrated resolver/navigation bridges are NEVER replaced. The only
// controlled response is the source-reviewed legacy DemoRoomGateway leaf.
let legacyNamespace;
const nativeReceivers=new WeakMap();
let nativeReceiverSequence=0;
const receiverId=value=>{
  if(!nativeReceivers.has(value))nativeReceivers.set(value,++nativeReceiverSequence);
  return nativeReceivers.get(value);
};
export function configureTask14LegacyLeafV6(namespace) {
  if(legacyNamespace)throw Error('Legacy leaf namespace is single-use');
  if(typeof namespace?.DemoRoomGateway!=='function')throw Error('Original legacy gateway namespace unavailable');
  legacyNamespace=namespace;
}
const clone=value=>value===undefined?undefined:JSON.parse(JSON.stringify(value));
export function installTask14JoinOwnerV6(namespace,record=()=>{}) {
  const proto=namespace.JoinRoomByAddressPresenter?.prototype;
  if(!proto)throw Error('Original native presenter namespace unavailable');
  const receivers=[],calls=[],navigation=[],requests=[],bridgeCalls=[],restores=[],navigators=new Set();
  let active,projection,bound=false,disposed=false;
  const bridgeStack=[];
  for(const name of Object.getOwnPropertyNames(proto)) {
    const descriptor=Object.getOwnPropertyDescriptor(proto,name);
    if(name==='constructor'||!descriptor.configurable)continue;
    const original=typeof descriptor.value==='function'?descriptor.value:descriptor.get;
    if(typeof original!=='function')continue;
    const invoke=function(...args){
      active=this;if(!receivers.includes(this))receivers.push(this);
      const call={sequence:calls.length+1,instanceId:receivers.indexOf(this)+1,nativeReceiverId:receiverId(this),
        method:name,stack:String(new Error().stack),args:clone(args.map(a=>typeof a==='function'?'[callback]':a))};
      calls.push(call);record({method:'Task14.originalPresenterCall',call});
      try {const result=original.apply(this,args);call.returned=true;if(name==='visibleAddressState')projection=result;return result;}
      catch(error){call.error=String(error);throw error;}
    };
    Object.defineProperty(proto,name,typeof descriptor.value==='function'?{...descriptor,value:invoke}:{...descriptor,get:invoke});
    restores.push(()=>Object.defineProperty(proto,name,descriptor));
  }
  const ownBridge=receiver=>!!active && active.resolver===receiver;
  const ownLeaf=request=>!!active&&active.resolver?.gateway===request.receiver&&bridgeCalls.some(call=>
    call.id===request.bridgeCallId&&call.receiver===active.resolver&&call.calledOriginal===true);
  const bindNavigator=nav=>{
    if(!nav||navigators.has(nav))return;navigators.add(nav);
    for(const name of ['openRoom','back','dismissJoinRoomByAddress']){
      if(typeof nav[name]!=='function')continue;
      const descriptor=Object.getOwnPropertyDescriptor(nav,name),original=nav[name];
      Object.defineProperty(nav,name,{configurable:true,writable:true,value:function(...args){
        navigation.push({receiver:this,method:name,args:clone(args),stack:String(new Error().stack)});
        return original.apply(this,args);
      }});
      restores.push(()=>descriptor?Object.defineProperty(nav,name,descriptor):delete nav[name]);
    }
  };
  const state=value=>value==='not_found'?'room_not_found':value;
  return {
    read(){
      if(!active)return {available:false,reason:'No actual original page receiver observed'};
      bindNavigator(active.navigator);
      return clone({available:true,instanceId:receivers.indexOf(active)+1,nativeReceiverId:receiverId(active),instanceCount:receivers.length,
        boundaryProtocol:'task14.original-bridge-legacy-leaf.v6',address:active.address,
        addressState:state(active.addressState??active.state),internalAddressState:state(active.internalAddressState??active.addressState??active.state),
        visibleAddressState:state(projection),validationRequested:active.validationRequested,resolvedRoom:active.resolvedRoom,
        addressFlowVisible:active.navigator?.addressFlowVisible,closed:active.closed??active.dismissed,
        navigationCount:navigation.filter(c=>c.receiver===active.navigator&&c.method==='openRoom').length,
        pendingNavigation:active.pendingNavigation,calls,
        navigationCalls:navigation.filter(c=>c.receiver===active.navigator).map(({method,args,stack})=>({method,args,stack})),
        resolverRequests:requests.map(r=>({id:r.id,alias:r.alias,settled:r.settled,samePageResolver:ownLeaf(r),
          bridgeCallId:r.bridgeCallId,externalLeaf:'DemoRoomGateway.resolveAlias'})),
        originalBridgeCalls:bridgeCalls.map(c=>({id:c.id,alias:c.alias,calledOriginal:c.calledOriginal,
          returned:c.returned,settlement:c.settlement,value:c.value,error:c.error,
          receiverIsPageResolver:ownBridge(c.receiver),leafIsOriginalGateway:c.receiver.gateway===c.leafReceiver}))});
    },
    bindExternalResolver(resolverNamespace){
      if(bound||!legacyNamespace)throw Error('Reviewed legacy leaf namespace/configuration missing');
      const Bridge=resolverNamespace.SessionRoomAliasResolver;
      const Legacy=legacyNamespace.DemoRoomGateway;
      const bridgeDescriptor=Bridge&&Object.getOwnPropertyDescriptor(Bridge.prototype,'resolveRoomAlias');
      const leafDescriptor=Legacy&&Object.getOwnPropertyDescriptor(Legacy.prototype,'resolveAlias');
      if(!bridgeDescriptor?.configurable||typeof bridgeDescriptor.value!=='function'||
        !leafDescriptor?.configurable||typeof leafDescriptor.value!=='function')
        throw Error('Unknown resolver bridge/legacy leaf shape; NS, never replace candidate bridge');
      Object.defineProperty(Bridge.prototype,'resolveRoomAlias',{...bridgeDescriptor,value:function(alias){
        const call={id:bridgeCalls.length+1,receiver:this,alias,calledOriginal:false,returned:false,leafReceiver:this.gateway};
        bridgeCalls.push(call);
        if(!ownBridge(this))throw Error('Resolver bridge is not this actual page owner\'s original resolver');
        call.calledOriginal=true;bridgeStack.push(call);
        let result;
        try {result=bridgeDescriptor.value.call(this,alias);call.returned=true;}
        catch(error){call.error=String(error);call.settlement='threw';throw error;}
        finally {bridgeStack.pop();}
        record({method:'Task14.originalAliasBridgeEnteredV6',id:call.id,alias,calledOriginal:true});
        if(result&&typeof result.then==='function')result.then(value=>{
          call.settlement='fulfilled';call.value=clone(value);
          record({method:'Task14.originalAliasBridgeFulfilledV6',id:call.id,value:clone(value)});
        },error=>{call.settlement='rejected';call.error=String(error);});
        return result;
      }});
      restores.push(()=>Object.defineProperty(Bridge.prototype,'resolveRoomAlias',bridgeDescriptor));
      Object.defineProperty(Legacy.prototype,'resolveAlias',{...leafDescriptor,value:function(alias){
        const bridge=bridgeStack.at(-1);
        if(!bridge||bridge.receiver!==active?.resolver||bridge.receiver.gateway!==this||bridge.alias!==alias)
          throw Error('Legacy leaf did not originate from actual original new bridge');
        const request={id:requests.length+1,alias,receiver:this,bridgeCallId:bridge.id,settled:false};
        const result=new Promise((resolve,reject)=>{request.resolve=resolve;request.reject=reject;});
        requests.push(request);
        record({method:'Task14.externalResolverRequested',requestId:request.id,alias,
          boundary:'legacy DemoRoomGateway.resolveAlias',bridgeCallId:bridge.id,originalNewBridgeExecuted:true});
        return result;
      }});
      restores.push(()=>Object.defineProperty(Legacy.prototype,'resolveAlias',leafDescriptor));bound=true;
      return {protocol:'task14.original-bridge-legacy-leaf.v6',newBridge:'SessionRoomAliasResolver.resolveRoomAlias',
        newBridgeMode:'pass_through_original',externalLeaf:'DemoRoomGateway.resolveAlias',leafResultType:'string | undefined'};
    },
    resolveExternal(id,response){
      const request=requests.find(r=>r.id===id);if(!request||request.settled||!ownLeaf(request))throw Error('Unknown own legacy request');
      request.settled=true;
      record({method:'Task14.externalResolverResolved',requestId:id,alias:request.alias,response:{roomId:response?.roomId},
        samePageResolver:true,bridgeCallId:request.bridgeCallId,externalLeafResultType:'string | undefined'});
      // The immutable legacy contract returns a string. Never inject servers
      // into the newly migrated bridge's return value or presenter state.
      request.resolve(response?.roomId);
    },
    settle(id){const r=requests.find(r=>r.id===id);if(!r||r.settled||!ownLeaf(r))throw Error('Unknown own legacy request');
      r.settled=true;record({method:'Task14.externalResolverRejectedV6',requestId:id,bridgeCallId:r.bridgeCallId,
        samePageResolver:true,externalLeaf:'DemoRoomGateway.resolveAlias'});r.reject(Error('External directory failure'));},
    dispose(){if(disposed)return;disposed=true;
      for(const r of requests)if(!r.settled){r.settled=true;r.reject(Error('Owned external leaf disposed'));}
      for(const restore of restores.reverse())restore();}
  };
}
// Existing producer import spelling is a transport alias, not old source bytes.
export const installTask14JoinOwnerV3=installTask14JoinOwnerV6;
export const installTask14Observer=installTask14JoinOwnerV6;
