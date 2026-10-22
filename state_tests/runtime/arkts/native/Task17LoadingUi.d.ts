import type { Driver, On } from '@ohos.UiTest';
import type { Task17LoadingLaunch } from './Task17LoadingLaunchNative';
export function configureTask17Loading(configJson: string): void;
export function runTask17LoadingUi(caseJson: string, bundleName: string, driver: Driver, selectors: On,
  launch: Task17LoadingLaunch, preferences: Object, alreadyStarted?: boolean): Promise<string>;
