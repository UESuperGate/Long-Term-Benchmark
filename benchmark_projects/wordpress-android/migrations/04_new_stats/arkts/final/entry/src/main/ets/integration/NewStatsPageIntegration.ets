import { common } from '@kit.AbilityKit';

export interface NewStatsEffect {
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

export interface NewStatsLeaf {
  emit(effect: NewStatsEffect): Promise<void>;
}

export interface NewStatsInput {
  state: Record<string, Object>;
  persistence: Record<string, Object>;
  leaf: NewStatsLeaf;
}

export interface NewStatsPageOwner {
  mount(context: common.UIAbilityContext, input: NewStatsInput, initialize: boolean): Promise<void>;
  invoke(name: string, event: Record<string, Object>): Promise<void>;
  currentState(): Record<string, Object>;
  currentPersistence(): Record<string, Object>;
  ownerId(): string;
  controllerId(): string;
  storeSource(): string;
  featureAvailable(): boolean;
}
