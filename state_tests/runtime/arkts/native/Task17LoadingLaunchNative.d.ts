import type { Driver } from '@ohos.UiTest';
export interface Task17LoadingLaunch {
  start(): Promise<void>;
  check(driver: Driver): Promise<Object>;
  current(): Object;
  read(): Object;
  getInspectorTree(): Object | string;
  dispose(): Promise<void>;
}
export function createTask17LoadingLaunch(bundleName: string): Task17LoadingLaunch;
