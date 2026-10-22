'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const original=path.join(__dirname,'task14_real_routes_v4/install.cjs');
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
function adapterSource(){
  const file=path.join(__dirname,'task14_real_routes_v4/Task14RealRoutesV4.adapter.js');
  let code=fs.readFileSync(file,'utf8');
  const old='for (const source of config.productionSources || []) args.load(source.path);';
  if(code.split(old).length!==2)throw Error('Exact v4 metadata anchor changed');
  code=code.replace(old,"for (const source of config.productionSources || []) if (source.path.startsWith('entry/src/main/ets/features/')) args.load(source.path);");
  const protocol="'task14.arkts.actual-route-envelope.v4'";
  if(code.split(protocol).length!==2)throw Error('Exact v4 protocol changed');
  return code.replace(protocol,"'task14.arkts.actual-route-envelope.v5'");
}
function install(work,options={}){
  const report=require(original).install(work,options);
  const file=path.join(work,'entry/src/test/Task14RealRoutesV4.adapter.js'),code=adapterSource();
  fs.writeFileSync(file,code);
  report.fixtures=report.fixtures.map(item=>item.path.endsWith('/Task14RealRoutesV4.adapter.js')?
    {...item,sha256:hash(code),derivedBy:__filename}:item);
  return {...report,protocol:'task14.arkts.actual-route-envelope.v5',upstreamInstaller:report.installer,
    installer:{file:__filename,sha256:hash(fs.readFileSync(__filename))},
    derivation:'Fresh v5 execution; feature-only metadata registration. Original app import/UI/production behavior unchanged.'};
}
module.exports={install,adapterSource};
