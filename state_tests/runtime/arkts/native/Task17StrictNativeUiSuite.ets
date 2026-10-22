import { Driver, ON } from '@ohos.UiTest';
import { createTask17LoadingLaunch } from './Task17LoadingLaunchNative';
import { runTask17StrictNativeSdk } from './Task17StrictNativeSdk';

export async function runTask17StrictProbe(caseJson: string, bundleName: string): Promise<string> {
  return runTask17StrictNativeSdk(caseJson, bundleName, Driver.create(), ON,
    createTask17LoadingLaunch(bundleName));
}
