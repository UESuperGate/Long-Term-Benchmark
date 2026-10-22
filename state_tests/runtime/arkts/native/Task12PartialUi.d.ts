import type { Driver, On } from '@ohos.UiTest';
import type { Task12PartialLaunch } from './Task12PartialLaunchNative';
export function configureTask12Partial(configJson: string): void;
export function runTask12Partial(caseJson: string, bundleName: string, driver: Driver, selectors: On,
  launch: Task12PartialLaunch, dismissKeyboard: () => Promise<void>): Promise<string>;
