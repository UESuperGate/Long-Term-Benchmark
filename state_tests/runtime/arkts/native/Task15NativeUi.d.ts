import type { Driver, On } from '@ohos.UiTest';
import type { Task15Launch } from './Task15LaunchNative';
export function configureTask15Binding(configJson: string): void;
export function runTask15NativeUi(caseJson: string, bundleName: string, driver: Driver, selectors: On,
  launch: Task15Launch, integration?: Object, inspector?: Object,
  dismissKeyboard?: () => Promise<void>): Promise<string>;
