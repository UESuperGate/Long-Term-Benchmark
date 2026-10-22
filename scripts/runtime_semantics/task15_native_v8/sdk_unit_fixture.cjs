'use strict';
// Host-only unit: ORIGINAL production bodies with synthetic system SDK leaves.
// Never installed into a HAP and never admissible as native runtime evidence.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../../..');
const ts=require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const hash=value=>crypto.createHash('sha256').update(String(value)).digest('hex');
async function fixture(){
  const files=new Map(),directories=new Set(),records=[],sdkHttp=[],sdkEffects=[];
  const asset={Tag:Object.fromEntries(['ALIAS','RETURN_TYPE','RETURN_LIMIT','SECRET','ACCESSIBILITY','AUTH_TYPE','SYNC_TYPE','CONFLICT_RESOLUTION'].map(k=>[k,k])),
    ReturnType:{ALL:1},Accessibility:{DEVICE_FIRST_UNLOCKED:1},AuthType:{NONE:0},SyncType:{NEVER:0},ConflictResolution:{OVERWRITE:1},
    query:async()=>records.slice(),add:async value=>{records.splice(0,records.length,value);sdkEffects.push('asset.add');},
    remove:async()=>{records.splice(0);sdkEffects.push('asset.remove');}};
  const filesystem={OpenMode:{CREATE:1,READ_WRITE:2,TRUNC:4},mkdir:async name=>{directories.add(name);},
    stat:async name=>({isDirectory:()=>directories.has(name)}),open:async name=>({fd:name}),
    write:async(fd,body)=>{files.set(fd,body);sdkEffects.push('fs.write');},close:async()=>{},
    readText:async name=>{if(!files.has(name))throw Error('UNIT missing metadata');return files.get(name);},
    access:async name=>directories.has(name),rmdir:async name=>{
      directories.delete(name);for(const key of files.keys())if(key.startsWith(name+'/'))files.delete(key);sdkEffects.push('fs.rmdir');}};
  const util={TextEncoder,TextDecoder:class {decodeWithStream(value){return new TextDecoder().decode(value);}}};
  const provider={nonce:'a'.repeat(32),loginCount:0,deactivationCount:0,requests:[]};
  const http={RequestMethod:{POST:'POST'},HttpDataType:{STRING:'STRING'},createHttp:()=>({
    async request(url,options){
      const body=JSON.parse(options.extraData),pathname=new URL(url).pathname;sdkHttp.push({url,options});
      const record={sequence:provider.requests.length+1,kind:pathname.endsWith('/login')?'login':'deactivation',
        path:pathname,method:options.method,secure:true};
      if(record.kind==='login'){
        provider.loginCount++;record.body={type:body.type,user:body.identifier.user,passwordSha256:hash(body.password)};
        record.responseStatus=200;provider.requests.push(record);
        return {responseCode:200,result:JSON.stringify({user_id:'@unit:task15.test',device_id:'UNIT',access_token:'unit-token'})};
      }
      provider.deactivationCount++;record.number=provider.deactivationCount;
      record.authorizationSha256=hash(options.header.Authorization);
      record.body={erase:body.erase,hasAuth:!!body.auth,...(body.auth?{authType:body.auth.type,user:body.auth.identifier.user,
        passwordSha256:hash(body.auth.password),session:body.auth.session}:{})};
      record.responseStatus=body.auth?200:401;provider.requests.push(record);
      return {responseCode:record.responseStatus,result:JSON.stringify(body.auth?{}:{errcode:'M_UNAUTHORIZED',error:'unit',session:'unit-challenge'})};
    },destroy(){sdkEffects.push('http.destroy');}})};
  const load=(file,require)=>{
    const module={exports:{}},source=fs.readFileSync(file,'utf8');
    const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
    vm.runInNewContext('(function(require,module,exports){'+code+'\n})',{TextEncoder,TextDecoder,Uint8Array,Map,Set,console})(require,module,module.exports);
    return module.exports;
  };
  const directory=path.join(root,'final_dev_nodes/15_account_deactivation_final_0_6_3/entry/src/main/ets/services');
  const account=load(path.join(directory,'AccountClient.ets'),name=>{throw Error('Unexpected account import '+name);});
  const native=load(path.join(directory,'NativeAccountClient.ets'),name=>{
    if(name==='./AccountClient')return account;
    const values={'@ohos.net.http':http,'@ohos.security.asset':asset,'@ohos.util':util,'@ohos.file.fs':filesystem};
    if(name in values)return {default:values[name]};throw Error('Unexpected SDK import '+name);
  });
  const module=await import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync(path.join(__dirname,'Task15BridgeLedgerV8.js'))).toString('base64')+'#'+Math.random());
  const original=Object.getOwnPropertyDescriptor(account.AccountClient.prototype,'deactivateAccount');
  const ledger=module.observeTask15BridgeLedgerV8(account,native);
  let result;
  try{
    const client=native.createAccountClient({filesDir:'/unit/files',cacheDir:'/unit/cache'});
    await client.restore();await client.login('https://unit.test','unit','login-secret');
    const receiverId=module.task15BridgeReceiverIdV8(client);
    await client.deactivateAccount('secret',true);
    const calls=ledger.read();
    result={UNIT_ONLY_NOT_NATIVE_RUNTIME:true,ledger:calls,provider,receiverId,sdkEffects,sdkHttp,
      persistedAssetCount:records.length,remainingMetadataFiles:files.size,
      sessionRemoved:client.userId()==='',factoryBodyWasOriginal:true};
  }finally{ledger.dispose();}
  result.originalDescriptorRestored=Object.getOwnPropertyDescriptor(account.AccountClient.prototype,'deactivateAccount').value===original.value;
  return result;
}
module.exports={fixture};
