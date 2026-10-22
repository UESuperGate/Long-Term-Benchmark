import { Driver, ON } from '@ohos.UiTest';
import { createTask17OwnerLaunch } from './Task17OwnerLaunchNative';
import { runTask17OwnerNativeSdk } from './Task17OwnerNativeSdk';

export async function runTask17OwnerProbe(caseJson: string, bundleName: string): Promise<string> {
  return runTask17OwnerNativeSdk(caseJson, bundleName, Driver.create(), ON,
    createTask17OwnerLaunch(bundleName));
}
