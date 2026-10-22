import preferences from '@ohos.data.preferences';
import { runTask17StrictNativeUi } from './Task17StrictNativeUi';

export function runTask17StrictNativeSdk(caseJson, bundleName, driver, selectors, launch) {
  return runTask17StrictNativeUi(caseJson, bundleName, driver, selectors, launch, preferences);
}
