import type { Driver } from '@ohos.UiTest';
export interface Task08Launch {
  start(): Promise<void>;
  check(driver: Driver): Promise<Object>;
  read(): Object;
  dispose(): Promise<void>;
}
export function createTask08Launch(bundleName: string): Task08Launch;
