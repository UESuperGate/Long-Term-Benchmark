import { Driver, ON } from '@ohos.UiTest';
import inputMethod from '@ohos.inputMethod';
import { runTask12Partial } from './Task12PartialUi';
import { createTask12PartialLaunch } from './Task12PartialLaunchNative';
export async function runTask12PartialProbe(caseJson: string, bundleName: string): Promise<string> {
  return runTask12Partial(caseJson, bundleName, Driver.create(), ON, createTask12PartialLaunch(bundleName),
    async (): Promise<void> => { await inputMethod.getController().hideTextInput(); });
}
