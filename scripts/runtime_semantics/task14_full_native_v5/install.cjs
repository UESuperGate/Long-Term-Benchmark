'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../../..'),native=path.join(root,'state_tests/runtime/arkts/native');
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
const replace=(text,old,next)=>{if(text.split(old).length!==2)throw Error('Full-native hook changed: '+old);return text.replace(old,next);};
const contract=JSON.parse(fs.readFileSync(path.join(root,'benchmark_tasks/14_join_room_by_address/transitions.json')));
function bridgeSource(){
  let code=fs.readFileSync(path.join(native,'Task14DeviceUi.js'),'utf8');
  code="import { evaluateTask14FullNativeV5 } from './Task14FullNativeV5.adapter';\n"+code;
  code=replace(code,'TASK14_CASES[caseSpec.caseId] !== caseSpec.key',
    JSON.stringify(Object.fromEntries(contract.cases.map(c=>[c.caseId,c.key])))+'[caseSpec.caseId] !== caseSpec.key');
  const begin="    return config.realFlowV2 === true && caseSpec.caseId === 'jr_state_001_entry_opens_address_flow' ?";
  const finish='evaluateTask14UI(args, config, ports, record);';
  const start=code.indexOf(begin),end=code.indexOf(finish,start)+finish.length;
  if(start<0||end<start)throw Error('Full-native dispatch hook changed');
  return code.slice(0,start)+'    return evaluateTask14FullNativeV5(args, config, ports, record);'+code.slice(end);
}
function extraFiles(){return [[path.join(__dirname,'Task14JoinOwnerV6.js'),'Task14JoinOwnerV3.js'],
  [path.join(__dirname,'../task14_real_routes_v3/Task14RealRoutesV3.suite.js'),'Task14RealRoutesV3.suite.js']].concat(
  ['Task14OwnerClockV5.js','Task14ScalarCasesV5.js','Task14FullNativeV5.adapter.js'].map(name=>[path.join(__dirname,name),name]));}
const pageObserverAlias="export { installTask14Observer } from './Task14JoinOwnerV3';\n";
function install(work,options={}){
  const deadline=Number(options.deadlineEpochMs||process.env.LTB_TASK14_ROUTE_DEADLINE_EPOCH_MS);
  if(!Number.isFinite(deadline)||deadline<=Date.now())throw Error('Whole task deadline unavailable');
  const report=require(path.join(native,'Task14DeviceUi.install.cjs')).install(work,{...options,mode:'after-page-ready'});
  const ts=require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
  const methodBody=file=>{
    const text=fs.readFileSync(file,'utf8'),tree=ts.createSourceFile(file,text,ts.ScriptTarget.Latest,true),found=[];
    for(const node of tree.statements)if(ts.isClassDeclaration(node)&&node.name?.text==='DemoRoomGateway')
      for(const member of node.members)if(ts.isMethodDeclaration(member)&&member.name.getText(tree)==='resolveAlias'&&member.body)
        found.push(ts.createPrinter({removeComments:true}).printNode(ts.EmitHint.Unspecified,member.body,tree));
    if(found.length!==1)throw Error('Unreviewed legacy gateway leaf shape; NS');return hash(found[0]);
  };
  const baseline=path.join(root,'14_join_room_by_address_base_25_02_0/entry/src/main/ets/features/ChatFeature.ets');
  const candidate=path.join(work,'entry/src/main/ets/features/ChatFeature.ets');
  if(hash(fs.readFileSync(baseline))!=='83b55bd2f427636c0bfcbe3604358aacc8aa868cd675d8e7f8f20b656fb0efa1')
    throw Error('Reviewed pre-existing legacy gateway source changed; NS, not a new source approval');
  const baselineMethod=methodBody(baseline),candidateMethod=methodBody(candidate);
  if(baselineMethod!==candidateMethod)throw Error('Candidate changed legacy leaf logic; no fixture bypass permitted; NS');
  const config={...report.config,deadlineEpochMs:deadline,fullNativeProtocol:'task14.full-nine-original-owner.v5'};
  for(const key of ['productionModuleUrl','chatFeatureModuleUrl','chatRoutesModuleUrl','chatRuntimeModuleUrl'])
    if(!config[key])throw Error('Unknown actual native namespace: '+key+'; NS');
  const testRoot=path.join(work,'entry/src/test'),bridge=bridgeSource();
  fs.writeFileSync(path.join(testRoot,'Task14DeviceUi.js'),bridge);
  report.fixtures=report.fixtures.map(item=>item.path.endsWith('/Task14DeviceUi.js')?{...item,sha256:hash(bridge),derivedBy:__filename}:item);
  for(const [source,name]of extraFiles()){
    if(fs.existsSync(path.join(testRoot,name)))throw Error('Refuse fixture collision: '+name);
    fs.copyFileSync(source,path.join(testRoot,name));report.fixtures.push({path:'entry/src/test/'+name,source,sha256:hash(fs.readFileSync(source))});
  }
  // All suites share the same configured leaf namespace. Copying the module
  // under a second filename would create a separate unconfigured singleton.
  const observerPath='entry/src/test/Task14PageObserver.js';
  if(report.fixtures.filter(item=>item.path===observerPath).length!==1)throw Error('Original observer fixture inventory changed');
  fs.writeFileSync(path.join(work,observerPath),pageObserverAlias);
  report.fixtures=report.fixtures.map(item=>item.path===observerPath?
    {...item,sha256:hash(pageObserverAlias),derivedBy:__filename}:item);
  const suite=replace(fs.readFileSync(report.suiteFile,'utf8'),JSON.stringify(JSON.stringify(report.config)),JSON.stringify(JSON.stringify(config)));
  fs.writeFileSync(report.suiteFile,suite);
  for(const item of report.production)if(hash(fs.readFileSync(path.join(work,item.path)))!==item.sha256)throw Error('Production changed');
  return {...report,config,suiteSha256:hash(suite),protocol:config.fullNativeProtocol,
    legacyLeafEligibility:{baselineSource:baseline,baselineSourceSha256:hash(fs.readFileSync(baseline)),
      candidateSource:'entry/src/main/ets/features/ChatFeature.ets',candidateSourceSha256:hash(fs.readFileSync(candidate)),
      baselineMethodSha256:baselineMethod,candidateMethodSha256:candidateMethod,
      newBridgeMode:'pass_through_original',leaf:'DemoRoomGateway.resolveAlias'},
    installer:{file:__filename,sha256:hash(fs.readFileSync(__filename))},upstreamInstaller:report.installer,
    scope:'All nine canonical cases; original native owner/UI/routes; controlled resolver and owner-scoped SDK timer leaf; independent admission only'};
}
module.exports={install,bridgeSource,extraFiles,pageObserverAlias};
