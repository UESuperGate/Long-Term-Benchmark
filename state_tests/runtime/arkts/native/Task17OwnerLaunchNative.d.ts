import type { Driver } from '@ohos.UiTest';
export interface Task17OwnerLaunch {
  start(): Promise<void>;
  restart(prepare: () => Promise<void>): Promise<void>;
  check(driver: Driver): Promise<Object>;
  current(): Object;
  read(): Object;
  dispose(): Promise<void>;
}
export function createTask17OwnerLaunch(bundleName: string): Task17OwnerLaunch;
