import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import window from '@ohos.window';
import { createTask15LaunchController } from './Task15Launch';

export function createTask15Launch(bundleName) {
  const delegator = abilityDelegatorRegistry.getAbilityDelegator();
  return createTask15LaunchController({ delegator,
    applicationContext: delegator.getAppContext().getApplicationContext(),
    getLastWindow: context => window.getLastWindow(context)
  }, bundleName);
}
