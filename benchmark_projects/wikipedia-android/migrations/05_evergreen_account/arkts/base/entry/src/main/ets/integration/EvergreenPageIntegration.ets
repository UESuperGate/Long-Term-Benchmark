import { common } from '@kit.AbilityKit';

export interface EvergreenEffect { name: string; interaction?: string; count?: number; maximum?: number; result?: string; source?: string; createAccountFirst?: boolean; historyCutoffDays?: number; qualifyingDays?: number; }
export interface EvergreenLeaf { emit(effect: EvergreenEffect): Promise<void>; }
export interface EvergreenInput { state: Record<string, Object>; persistence: Record<string, Object>; leaf: EvergreenLeaf; }

export interface EvergreenPageOwner {
  mount(context: common.UIAbilityContext, input: EvergreenInput): Promise<void>;
  dispatch(event: Record<string, Object>): Promise<void>;
  ordinaryLaunchWouldShow(): Promise<boolean>;
  currentState(): Record<string, Object>;
  currentPersistence(): Record<string, Object>;
  currentDecision(): Record<string, Object>;
  currentDecisionAfterRelaunch(): Record<string, Object>;
  currentRouting(): Record<string, Object>;
  currentHistoryDays(): string[];
  featureAvailable(): boolean;
  ownerId(): string;
}

export class CallbackEvergreenPageOwner implements EvergreenPageOwner {
  private mountAction: (context: common.UIAbilityContext, input: EvergreenInput) => Promise<void>;
  private dispatchAction: (event: Record<string, Object>) => Promise<void>;
  private ordinaryProbe: () => Promise<boolean>;
  private stateReader: () => Record<string, Object>;
  private persistenceReader: () => Record<string, Object>;
  private decisionReader: () => Record<string, Object>;
  private decisionAfterReader: () => Record<string, Object>;
  private routingReader: () => Record<string, Object>;
  private historyReader: () => string[];
  private featureReader: () => boolean;
  private ownerReader: () => string;

  constructor(
    mountAction: (context: common.UIAbilityContext, input: EvergreenInput) => Promise<void>,
    dispatchAction: (event: Record<string, Object>) => Promise<void>, ordinaryProbe: () => Promise<boolean>,
    stateReader: () => Record<string, Object>, persistenceReader: () => Record<string, Object>,
    decisionReader: () => Record<string, Object>, decisionAfterReader: () => Record<string, Object>,
    routingReader: () => Record<string, Object>, historyReader: () => string[],
    featureReader: () => boolean, ownerReader: () => string
  ) {
    this.mountAction = mountAction; this.dispatchAction = dispatchAction; this.ordinaryProbe = ordinaryProbe;
    this.stateReader = stateReader; this.persistenceReader = persistenceReader; this.decisionReader = decisionReader;
    this.decisionAfterReader = decisionAfterReader; this.routingReader = routingReader; this.historyReader = historyReader;
    this.featureReader = featureReader; this.ownerReader = ownerReader;
  }

  mount(context: common.UIAbilityContext, input: EvergreenInput): Promise<void> { return this.mountAction(context, input); }
  dispatch(event: Record<string, Object>): Promise<void> { return this.dispatchAction(event); }
  ordinaryLaunchWouldShow(): Promise<boolean> { return this.ordinaryProbe(); }
  currentState(): Record<string, Object> { return this.stateReader(); }
  currentPersistence(): Record<string, Object> { return this.persistenceReader(); }
  currentDecision(): Record<string, Object> { return this.decisionReader(); }
  currentDecisionAfterRelaunch(): Record<string, Object> { return this.decisionAfterReader(); }
  currentRouting(): Record<string, Object> { return this.routingReader(); }
  currentHistoryDays(): string[] { return this.historyReader(); }
  featureAvailable(): boolean { return this.featureReader(); }
  ownerId(): string { return this.ownerReader(); }
}
