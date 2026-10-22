// Device ohosTest ONLY. No Previewer import and no source-replacement UI.
import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import window from '@ohos.window';
import { Driver, ON } from '@ohos.UiTest';
import { createDeviceUiAugment } from './Tasks08_11DeviceUi.core';
import { createOriginalRoomObserverFactory } from './Tasks08_11DeviceUi.binding';
import { installRoomObserver } from './Tasks08_11RoomObserver';

let configuredAugment;

export function configureDeviceUi(config) {
  if (configuredAugment) throw new Error('Device UI configuration is single-use per test process');
  // Variable standard import preserves the explicit app OHM request instead of
  // compiling a relative .ets import into entry_test's separate module record.
  const observerFactory = createOriginalRoomObserverFactory(config, url => import(url), installRoomObserver);
  configuredAugment = createDeviceUiAugment({
    getDelegator: () => abilityDelegatorRegistry.getAbilityDelegator(),
    getApplicationContext: () => abilityDelegatorRegistry.getAbilityDelegator().getAppContext().getApplicationContext(),
    createDriver: () => Driver.create(),
    selectorById: (id, bundleName) => ON.id(id).inWindow(bundleName),
    getLastWindow: context => window.getLastWindow(context),
    mainWindowType: window.WindowType && window.WindowType.TYPE_MAIN,
    getInspectorTree: () => getInspectorTree(),
    getInspectorByKey: id => getInspectorByKey(id),
    emitDiagnostic: data => console.info('TASKS08_11_IMPORT_DIAGNOSTIC ' + JSON.stringify(data)),
    delay: ms => new Promise(resolve => setTimeout(resolve, ms))
  }, config, observerFactory);
}

export async function augment(bridge) {
  if (!configuredAugment) throw new Error('Configure Tasks08_11DeviceUi with the original app OHM URL before starting EntryAbility');
  return configuredAugment(bridge);
}
