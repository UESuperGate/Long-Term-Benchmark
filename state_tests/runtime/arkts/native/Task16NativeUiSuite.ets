import { Driver, ON } from '@ohos.UiTest';
import { runTask16NativeUi } from './Task16NativeUi';
import { createTask16Launch } from './Task16LaunchNative';
export async function runTask16Probe(caseJson: string, bundleName: string): Promise<string> {
  return runTask16NativeUi(caseJson, bundleName, Driver.create(), ON, createTask16Launch(bundleName));
}
