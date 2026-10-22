import type { Driver, On } from '@ohos.UiTest';
import type { Task16Launch } from './Task16LaunchNative';
export function configureTask16Binding(configJson: string): void;
export function runTask16NativeUi(caseJson: string, bundleName: string, driver: Driver, selectors: On,
  launch: Task16Launch): Promise<string>;
