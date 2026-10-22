import { Driver, ON } from '@ohos.UiTest';
import { runTask08StrictNativeUi } from './Task08StrictNativeUi';
import { createTask08Launch } from './Task08LaunchNative';

export async function runTask08StrictProbe(caseJson: string, bundleName: string): Promise<string> {
  let driver: Driver = Driver.create();
  for (let attempt: number = 0; !driver && attempt < 40; attempt += 1) {
    await new Promise<void>((resolve) => setTimeout(resolve, 100));
    driver = Driver.create();
  }
  if (!driver) throw new Error('Task08 UiTest driver unavailable after bounded initialization wait');
  return runTask08StrictNativeUi(caseJson, bundleName, driver, ON, createTask08Launch(bundleName));
}
