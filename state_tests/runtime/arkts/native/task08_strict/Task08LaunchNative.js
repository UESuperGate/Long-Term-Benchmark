import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import window from '@ohos.window';
import { createTask16LaunchController } from './Task16Launch';

// Task08's batch cases each own a fresh original Ability lifecycle. The shared
// Task16 classification lease deliberately defers termination and is unsuitable.
export function createTask08Launch(bundleName) {
  const delegator = abilityDelegatorRegistry.getAbilityDelegator();
  return createTask16LaunchController({ delegator,
    applicationContext: delegator.getAppContext().getApplicationContext(),
    getLastWindow: context => window.getLastWindow(context),
    delay: milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds))
  }, bundleName);
}
