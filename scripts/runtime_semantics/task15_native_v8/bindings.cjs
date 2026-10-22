'use strict';
// Binding discovery only. Runtime/profile proof remains mandatory.
const fs=require('node:fs'),path=require('node:path');
const binder=require('../task15_page_owner_packaging_v6.cjs');
const ts=require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
function texts(source,file){
  const scanner=ts.createScanner(ts.ScriptTarget.Latest,true,ts.LanguageVariant.Standard,source),t=[];
  for(let kind=scanner.scan();kind!==ts.SyntaxKind.EndOfFileToken;kind=scanner.scan())
    t.push({kind,text:scanner.getTokenText(),value:scanner.getTokenValue()});
  const result=[];
  for(let i=0;i<t.length;i++)if(t[i].text==='Text'&&t[i+1]?.text==='('){
    let depth=1,j=i+2;for(;j<t.length&&depth;j++){if(t[j].text==='(')depth++;if(t[j].text===')')depth--;}
    if(depth)throw Error('Unbalanced Text binding');
    const args=t.slice(i+2,j-1).map(v=>v.text);let id;
    for(let k=j;k+3<t.length&&t[k].text==='.';){
      const name=t[k+1].text;if(t[k+2].text!=='(')break;
      let n=k+3,d=1;for(;n<t.length&&d;n++){if(t[n].text==='(')d++;if(t[n].text===')')d--;}
      if(name==='id'){if(n!==k+5||t[k+3].kind!==ts.SyntaxKind.StringLiteral)throw Error('Unknown dynamic Text ID');id=t[k+3].value;}
      k=n;
    }
    if(id)result.push({file,id,type:'Text',args});
  }
  return result;
}
function discover(source){
  const base=binder.discover(source),controls=[],labels=[];
  for(const file of base.sourceFiles){
    const code=fs.readFileSync(path.join(source,file.path),'utf8');
    controls.push(...binder.controls(code,file.path));labels.push(...texts(code,file.path));
  }
  const unique=(values,name)=>{if(values.length!==1)throw Error('Unknown/ambiguous capability '+name);return values[0];};
  const signOut=unique(controls.filter(c=>c.type==='Button'&&c.label==='Sign out'&&c.handlers.some(h=>h.includes('signOut'))),'sign-out control');
  const session=unique(labels.filter(c=>c.file===signOut.file&&c.args.length===3&&c.args[0]==='this'&&c.args[1]==='.'),'session text');
  return {signOut,session,selectors:{session:{id:session.id},signOut:signOut.id?{id:signOut.id}:{type:'Button',text:signOut.label}}};
}
module.exports={discover,texts};
if(require.main===module)process.stdout.write(JSON.stringify(discover(fs.realpathSync(process.argv[2]))));
