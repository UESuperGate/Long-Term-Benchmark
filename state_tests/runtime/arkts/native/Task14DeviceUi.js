import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import window from '@ohos.window';
import inputMethod from '@ohos.inputMethod';
import { Driver, ON } from '@ohos.UiTest';
import { evaluateTask14UI } from './Task14DeviceUi.adapter';
import { evaluateTask14RealFlowV2 } from './Task14RealFlowV2.adapter';
import { TASK14_CASES } from './Task14DeviceUi.suite';

let config;
export function configureTask14DeviceUI(configJson) {
  if (config) throw new Error('Task14 device configuration is single-use per process');
  config = JSON.parse(configJson);
}

export function attachTask14DeviceUI(bridge, taskId, caseSpec) {
  if (taskId !== '14_join_room_by_address' || TASK14_CASES[caseSpec.caseId] !== caseSpec.key) return false;
  if (!config || typeof bridge.setObservationRecorder !== 'function') throw new Error('Task14 native configuration/recorder unavailable');
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
      bundleName: config.bundleName, backend: 'device_uitest' };
    if (recorder) recorder(value);
    if (event.method.includes('ModuleImport') || event.method.includes('ModuleBound'))
      console.info('TASK14_ORIGINAL_MODULE_BINDING ' + JSON.stringify(value));
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
    dismissKeyboard: () => inputMethod.getController().hideTextInput(),
    delay: ms => new Promise(resolve => setTimeout(resolve, ms))
  };
  bridge.evaluateTask14UI = async args => {
    if (used) throw new Error('Task14 requires one canonical case per cold process');
    used = true;
    if (args.taskId !== taskId || args.caseSpec.caseId !== caseSpec.caseId || args.caseSpec.traceDigest !== caseSpec.traceDigest)
      throw new Error('Task14 canonical identity changed across bridge');
    return config.realFlowV2 === true && caseSpec.caseId === 'jr_state_001_entry_opens_address_flow' ?
      evaluateTask14RealFlowV2(args, config, ports, record) : evaluateTask14UI(args, config, ports, record);
  };
  bridge.dispose = async function() {
    bridge.setObservationRecorder = originalRecorder;
    delete bridge.evaluateTask14UI;
    recorder = undefined;
    return originalDispose.call(bridge);
  };
  return true;
}
