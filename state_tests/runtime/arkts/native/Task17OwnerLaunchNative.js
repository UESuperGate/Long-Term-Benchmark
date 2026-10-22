import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import window from '@ohos.window';
import { createTask17OwnerLaunchController } from './Task17OwnerLaunch';

export function createTask17OwnerLaunch(bundleName) {
  const delegator = abilityDelegatorRegistry.getAbilityDelegator();
  return createTask17OwnerLaunchController({ delegator,
    applicationContext: delegator.getAppContext().getApplicationContext(),
    getLastWindow: context => window.getLastWindow(context)
  }, bundleName);
}
