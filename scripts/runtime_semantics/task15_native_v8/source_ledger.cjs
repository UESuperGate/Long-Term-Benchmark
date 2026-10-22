'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const ts=require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const root=path.resolve(__dirname,'../../..'),api=require(path.join(root,'state_tests/runtime/arkts/native/CandidateApiBindings.cjs'));
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
function describe(source){
  const records=[];
  for(const name of ['AccountClient','NativeAccountTransport','NativeAccountSessionStore']){
    const binding=api.exportedClass(source,name),file=binding.path,text=fs.readFileSync(path.join(source,file),'utf8');
    const tree=ts.createSourceFile(file,text,ts.ScriptTarget.Latest,true);
    const matches=tree.statements.filter(n=>ts.isClassDeclaration(n)&&n.name?.text===name);
    if(matches.length!==1)throw Error('Unknown application bridge class');
    for(const node of matches[0].members)if(ts.isMethodDeclaration(node)&&node.body){
      const start=node.getStart(tree),end=node.getEnd();
      records.push({className:name,method:node.name.getText(tree),path:file,sourceSha256:hash(text),
        sourceSpan:{start,end},bodySha256:hash(text.slice(start,end)),fixtureMode:'pass_through_original'});
    }
    for(const node of tree.statements)if(ts.isFunctionDeclaration(node)&&node.name?.text==='createAccountClient'){
      const start=node.getStart(tree),end=node.getEnd();
      records.push({className:'module',method:'createAccountClient',path:file,sourceSha256:hash(text),
        sourceSpan:{start,end},bodySha256:hash(text.slice(start,end)),fixtureMode:'original_page_creation_object_graph_not_replaced'});
    }
  }
  const unique=new Map(records.map(row=>[row.path+':'+row.className+':'+row.method,row]));
  return {protocol:'task15.app-owned-changed-body-scope.v8',source:fs.realpathSync(source),
    records:[...unique.values()],sourceMetadataIsNotExecution:true,controlledResponses:'external HTTPS server only'};
}
module.exports={describe};
if(require.main===module)process.stdout.write(JSON.stringify(describe(process.argv[2])));
