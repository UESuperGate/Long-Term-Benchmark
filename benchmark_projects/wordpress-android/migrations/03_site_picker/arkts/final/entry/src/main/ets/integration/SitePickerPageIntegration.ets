import { common } from '@kit.AbilityKit';

export interface SitePickerEffect {
  name: string;
  source?: string;
  localId?: number;
  localIds?: number[];
  count?: number;
  siteId?: number;
  selectedMetric?: string;
  selectedPeriodType?: string;
  customStart?: string;
  customEnd?: string;
  originPeriodType?: string;
  origin?: string;
  metric?: string;
  period?: Object;
  forceRefresh?: boolean;
  result?: Object;
  views?: number;
  errorCode?: string;
  classification?: string;
  destination?: string;
  state?: string[];
}

export interface SitePickerLeaf {
  emit(effect: SitePickerEffect): Promise<void>;
}

export interface SitePickerInput {
  state: Record<string, Object>;
  persistence: Record<string, Object>;
  leaf: SitePickerLeaf;
}

export interface SitePickerPageOwner {
  mount(context: common.UIAbilityContext, input: SitePickerInput, initialize: boolean): Promise<void>;
  invoke(name: string, event: Record<string, Object>): Promise<void>;
  currentState(): Record<string, Object>;
  currentPersistence(): Record<string, Object>;
  ownerId(): string;
  controllerId(): string;
  storeSource(): string;
  featureAvailable(): boolean;
}
