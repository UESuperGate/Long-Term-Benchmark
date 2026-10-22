import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import window from '@ohos.window';
import { createTask12PartialLaunchController } from './Task12PartialLaunch';
export function createTask12PartialLaunch(bundleName) {
  const delegator = abilityDelegatorRegistry.getAbilityDelegator();
  return createTask12PartialLaunchController({ delegator,
    applicationContext: delegator.getAppContext().getApplicationContext(),
    getLastWindow: context => window.getLastWindow(context)
  }, bundleName);
}
