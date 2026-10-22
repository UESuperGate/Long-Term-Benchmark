import type { Driver } from '@ohos.UiTest';
export interface Task15Launch {
  start(): Promise<void>;
  check(driver: Driver): Promise<Object>;
  read(): Object;
  dispose(): Promise<void>;
}
export function createTask15Launch(bundleName: string): Task15Launch;
