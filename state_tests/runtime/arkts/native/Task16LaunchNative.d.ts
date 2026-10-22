import type { Driver } from '@ohos.UiTest';
export interface Task16Launch {
  start(): Promise<void>;
  check(driver: Driver): Promise<Object>;
  read(): Object;
  retain(): void;
  dispose(): Promise<void>;
}
export function createTask16Launch(bundleName: string): Task16Launch;
export function releaseTask16Launch(bundleName: string): Promise<void>;
