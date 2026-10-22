import preferences from '@ohos.data.preferences';
import { runTask17LoadingUi } from './Task17LoadingUi';

// Keep the actual SDK module object inside JS; ArkTS forbids namespace values.
export function runTask17LoadingNativeSdk(caseJson, bundleName, driver, selectors, launch) {
  return runTask17LoadingUi(caseJson, bundleName, driver, selectors, launch, preferences);
}
