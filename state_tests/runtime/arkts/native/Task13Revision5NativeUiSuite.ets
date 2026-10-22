import { Driver, ON } from '@ohos.UiTest';
import { runTask13Revision5NativeUi } from './Task13Revision5NativeUi';
import { createTask13Launch } from './Task13LaunchNative';

export async function runTask13Revision5Probe(caseJson: string, bundleName: string): Promise<string> {
  let driver: Driver = Driver.create();
  for (let attempt: number = 0; !driver && attempt < 40; attempt += 1) {
    await new Promise<void>((resolve) => setTimeout(resolve, 100));
    driver = Driver.create();
  }
  if (!driver) {
    throw new Error('Task13 UiTest driver unavailable after bounded initialization wait');
  }
  return runTask13Revision5NativeUi(caseJson, bundleName, driver, ON, createTask13Launch(bundleName));
}
