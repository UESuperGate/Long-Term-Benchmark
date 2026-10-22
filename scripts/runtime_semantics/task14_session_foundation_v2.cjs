'use strict';
// Structured import/export graph and OFFLINE-only host test loader.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),vm=require('node:vm');
const ts=require('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/typescript');
const hash=data=>crypto.createHash('sha256').update(data).digest('hex');
function graph(foundation,reusable){
  const seed='composition/Task14SessionFoundation.ets',pending=[seed],records=[],seen=new Set();
  while(pending.length){
    const name=pending.shift();if(seen.has(name))continue;seen.add(name);
    if(name.startsWith('../')||path.isAbsolute(name))throw Error('Import leaves source scope');
    const own=path.join(foundation,name),original=fs.existsSync(own)?own:path.join(reusable,name),bytes=fs.readFileSync(original);
    const ast=ts.createSourceFile(name,bytes.toString(),ts.ScriptTarget.Latest,true),imports=[];
    for(const statement of ast.statements)if((ts.isImportDeclaration(statement)||ts.isExportDeclaration(statement))&&statement.moduleSpecifier){
      if(!ts.isStringLiteral(statement.moduleSpecifier))throw Error('Unknown module specifier');
      const specifier=statement.moduleSpecifier.text;
      if(specifier.startsWith('.')){const target=path.posix.normalize(path.posix.join(path.posix.dirname(name),specifier))+'.ets';
        imports.push({specifier,target});pending.push(target);}
      else imports.push({specifier,external:true});
    }
    records.push({path:name,original,bytes:bytes.length,sha256:hash(bytes),imports});
  }
  return records.sort((a,b)=>a.path.localeCompare(b.path));
}
function loader(root,external){
  const cache=new Map();
  function load(name){
    name=path.normalize(name);if(cache.has(name))return cache.get(name);
    const file=path.join(root,name+'.ets'),code=fs.readFileSync(file,'utf8');
    const result=ts.transpileModule(code,{fileName:file,reportDiagnostics:true,
      compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}});
    if(result.diagnostics.some(item=>item.category===ts.DiagnosticCategory.Error))throw Error('Syntax transform failed: '+name);
    const module={exports:{}};cache.set(name,module.exports);
    vm.runInNewContext('(function(require,module,exports){'+result.outputText+'\n})',
      {Map,Set,Uint8Array,ArrayBuffer,TextEncoder,TextDecoder,console,Date},{filename:file})((specifier)=>{
        if(specifier.startsWith('.'))return load(path.join(path.dirname(name),specifier));
        if(!(specifier in external))throw Error('Unresolved external: '+specifier);
        return {default:external[specifier]};
      },module,module.exports);
    cache.set(name,module.exports);return module.exports;
  }
  return load;
}
module.exports={graph,loader};
if(require.main===module)process.stdout.write(JSON.stringify(graph(process.argv[2],process.argv[3])));
