import abilityDelegatorRegistry from '@ohos.app.ability.abilityDelegatorRegistry';
import window from '@ohos.window';
import { createTask17LaunchController } from './Task17LoadingLaunch';
export function createTask17LoadingLaunch(bundleName) {
  const delegator = abilityDelegatorRegistry.getAbilityDelegator();
  const launch = createTask17LaunchController({ delegator,
    applicationContext: delegator.getAppContext().getApplicationContext(),
    getLastWindow: context => window.getLastWindow(context)
  }, bundleName);
  launch.getInspectorTree = () => getInspectorTree();
  return launch;
}
