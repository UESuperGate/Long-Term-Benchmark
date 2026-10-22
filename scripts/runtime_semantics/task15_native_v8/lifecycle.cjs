'use strict';
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../../..');
function replace(source,old,next){if(source.split(old).length!==2)throw Error('Frozen lifecycle hook changed: '+old);return source.replace(old,next);}
function source(){
  let code=fs.readFileSync(path.join(root,'state_tests/runtime/arkts/native/Task15Launch.js'),'utf8');
  code=replace(code,'let lifecycleError, lastReady;','let lifecycleError, lastReady, restarting=false, epoch=0;');
  code=replace(code,"events.push({ method, at: Date.now(), identity: identity(value) })",
    "events.push({ method, epoch, at: Date.now(), identity: identity(value) })");
  code=replace(code,"if (ability && ability !== value) lifecycleError = 'Multiple candidate ability instances';",`if (ability && ability !== value) {
        if (!restarting || !destroyed || stage) lifecycleError = 'Multiple candidate ability instances';
        else { restarting=false;destroyed=false;foreground=false;lastReady=undefined; }
      }
      epoch++;`);
  code=replace(code,'    read() { return',`    originalContext() {
      if (!ability || destroyed || disposed || lifecycleError) throw Error('No live original app context');
      return ability.context;
    },
    async diagnosticMainWindow() {
      if(!stage || disposed || destroyed)throw Error('No original WindowStage');return stage.getMainWindow();
    },
    async coldRestart() {
      if(!registered || disposed || destroyed || lifecycleError || !ability || !stage)throw Error('No live original ability to cold restart');
      const old=ability;record('coldRestartRequested',old);
      await old.context.terminateSelf();
      for(let attempt=0;attempt<100 && (!destroyed || stage);attempt++)await new Promise(resolve=>setTimeout(resolve,25));
      if(!destroyed || stage)throw Error('Actual original destruction not observed; no assumed cold reload');
      restarting=true;
      await ports.delegator.startAbility({bundleName,abilityName:'EntryAbility',moduleName:'entry'});
      record('coldRestartReturned',ability);
    },
    read() { return`);
  return code;
}
module.exports={source};
