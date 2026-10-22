import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import window from '@ohos.window';
import { Driver, ON } from '@ohos.UiTest';
import { evaluateTask11Strict } from './Task11Adapter';
import { TASK11_CASES } from './Task11Suite';

let config;

export function configureTask11Strict(configJson) {
  if (config) throw new Error('Task11 strict configuration is single-use per process');
  config = JSON.parse(configJson);
}

export function attachTask11Strict(bridge, taskId, caseSpec) {
  if (taskId !== '11_room_upgrade_navigation' || !TASK11_CASES.includes(caseSpec.caseId)) return false;
  if (!config || typeof bridge.setObservationRecorder !== 'function')
    throw new Error('Task11 strict native configuration/recorder unavailable');
  const originalRecorder = bridge.setObservationRecorder;
  const originalDispose = bridge.dispose;
  let recorder;
  let used = false;
  bridge.setObservationRecorder = function(callback) {
    recorder = callback;
    return originalRecorder.call(this, callback);
  };
  const record = event => {
    const value = { ...event, caseId: caseSpec.caseId, traceDigest: caseSpec.traceDigest,
      role: config.role, backend: 'device_uitest', bundleName: config.bundleName };
    if (recorder) recorder(value);
    if (event.method.includes('ModuleImport') || event.method.includes('givenEstablished'))
      console.info('TASK11_STRICT_BINDING ' + JSON.stringify(value));
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
  bridge.evaluateTask11Strict = async args => {
    if (used || args.taskId !== taskId || args.caseSpec.caseId !== caseSpec.caseId ||
        args.caseSpec.traceDigest !== caseSpec.traceDigest)
      throw new Error('Task11 strict requires one unchanged canonical case per cold process');
    used = true;
    return evaluateTask11Strict(args, config, ports, record);
  };
  bridge.dispose = async function() {
    bridge.setObservationRecorder = originalRecorder;
    delete bridge.evaluateTask11Strict;
    recorder = undefined;
    return originalDispose.call(bridge);
  };
  return true;
}
