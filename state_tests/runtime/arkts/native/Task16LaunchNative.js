import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import window from '@ohos.window';
import { createTask16LaunchController, createTask16LaunchLease } from './Task16Launch';
const leases = createTask16LaunchLease(bundleName => {
  const delegator = abilityDelegatorRegistry.getAbilityDelegator();
  return createTask16LaunchController({ delegator,
    applicationContext: delegator.getAppContext().getApplicationContext(),
    getLastWindow: context => window.getLastWindow(context),
    delay: milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds))
  }, bundleName);
});
export function createTask16Launch(bundleName) { return leases.acquire(bundleName); }
export async function releaseTask16Launch(bundleName) { await leases.release(bundleName); }
