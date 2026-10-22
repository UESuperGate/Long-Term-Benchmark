import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import window from '@ohos.window';
import { Driver, ON } from '@ohos.UiTest';
import { evaluateTask09Strict } from './Task09Adapter';
import { TASK09_CASES } from './Task09Suite';

let config;

export function configureTask09Strict(configJson) {
  if (config) throw new Error('Task09 strict configuration is single-use per process');
  config = JSON.parse(configJson);
}

export function attachTask09Strict(bridge, taskId, caseSpec) {
  if (taskId !== '09_spaces_lifecycle' || !TASK09_CASES.includes(caseSpec.caseId)) return false;
  if (!config || typeof bridge.setObservationRecorder !== 'function')
    throw new Error('Task09 strict native configuration/recorder unavailable');
  const originalRecorder = bridge.setObservationRecorder;
  const originalDispose = bridge.dispose;
  let recorder;
  let used = false;
  bridge.setObservationRecorder = function(callback) { recorder = callback; return originalRecorder.call(this, callback); };
  const record = event => {
    const value = { ...event, caseId: caseSpec.caseId, traceDigest: caseSpec.traceDigest,
      role: config.role, backend: 'device_uitest', bundleName: config.bundleName,
      available: event.method === 'Task09.originalRepositoryCall' || event.method === 'after:event',
      productionSources: config.productionSources };
    if (recorder) recorder(value);
    if (event.method.includes('ModuleImport') || event.method.includes('external'))
      console.info('TASK09_STRICT_BINDING ' + JSON.stringify(value));
  };
  const ports = {
    getDelegator: () => abilityDelegatorRegistry.getAbilityDelegator(),
    getApplicationContext: () => abilityDelegatorRegistry.getAbilityDelegator().getAppContext().getApplicationContext(),
    createDriver: () => Driver.create(),
    selector: (spec, bundleName) => {
      let selector = ON;
      if (spec.id) selector = selector.id(spec.id);
      if (spec.type) selector = selector.type(spec.type);
      if (spec.text !== undefined) selector = selector.text(spec.text);
      return selector.inWindow(bundleName);
    },
    getLastWindow: context => window.getLastWindow(context),
    getInspectorTree: () => getInspectorTree(),
    importModule: url => import(url),
    delay: milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds))
  };
  bridge.evaluateTask09Strict = async args => {
    if (used || args.taskId !== taskId || args.caseSpec.caseId !== caseSpec.caseId ||
        args.caseSpec.traceDigest !== caseSpec.traceDigest)
      throw new Error('Task09 strict requires one unchanged canonical case per cold process');
    used = true;
    return evaluateTask09Strict(args, config, ports, record);
  };
  bridge.dispose = async function() {
    bridge.setObservationRecorder = originalRecorder;
    delete bridge.evaluateTask09Strict;
    recorder = undefined;
    return originalDispose.call(bridge);
  };
  return true;
}
