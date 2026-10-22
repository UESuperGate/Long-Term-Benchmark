import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import window from '@ohos.window';
import { createTask16LaunchController } from './Task16Launch';

// Each canonical case owns a fresh original ability, including its destruction.
export function createTask13Launch(bundleName) {
  const delegator = abilityDelegatorRegistry.getAbilityDelegator();
  return createTask16LaunchController({
    delegator,
    applicationContext: delegator.getAppContext().getApplicationContext(),
    getLastWindow: context => window.getLastWindow(context),
    delay: milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds))
  }, bundleName);
}
