import type { Driver } from '@ohos.UiTest';
export interface Task13Launch {
  start(): Promise<void>;
  check(driver: Driver): Promise<Object>;
  read(): Object;
  dispose(): Promise<void>;
}
export function createTask13Launch(bundleName: string): Task13Launch;
