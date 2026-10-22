export interface Tasks08_11DeviceUiConfig {
  bundleName: string;
  abilityName: string;
  moduleName: string;
  entryRoute: string;
  allowedRoutes: string[];
  productionModuleUrl: string;
  presenterExport: string;
  originalModuleImportMode: string;
  timeoutMs?: number;
}
export function configureDeviceUi(config: Tasks08_11DeviceUiConfig): void;
export function augment(bridge: Object): Promise<Object>;
