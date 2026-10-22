import type { Driver } from '@ohos.UiTest';
export interface Task12PartialLaunch {
  start(): Promise<void>;
  check(driver: Driver): Promise<Object>;
  read(): Object;
  dispose(): Promise<void>;
}
export function createTask12PartialLaunch(bundleName: string): Task12PartialLaunch;
