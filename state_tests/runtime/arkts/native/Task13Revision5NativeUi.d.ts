import type { Driver } from '@ohos.UiTest';
export function configureTask13Revision5Binding(configJson: string): void;
export function configureTask13InventoryValidator(validator: (json: string) => string): void;
export function loadTask13Revision5Production(): Promise<Object>;
export function runTask13Revision5NativeUi(caseJson: string, bundleName: string, driver: Driver,
  ON: Object, launch: Object): Promise<string>;
