import { Driver, ON } from '@ohos.UiTest';
import { runTask17LoadingNativeSdk } from './Task17LoadingNativeSdk';
import { createTask17LoadingLaunch } from './Task17LoadingLaunchNative';
export async function runTask17LoadingProbe(caseJson: string, bundleName: string): Promise<string> {
  return runTask17LoadingNativeSdk(caseJson, bundleName, Driver.create(), ON, createTask17LoadingLaunch(bundleName));
}
