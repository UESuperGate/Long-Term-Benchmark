import { common } from '@kit.AbilityKit';

export interface ExploreEffect {
  name?: string;
  leaf?: string;
  attempt?: number;
  language?: string;
  date?: string;
  logicalAge?: number;
  attemptForLogicalAge?: number;
  batch?: number;
  value?: number;
  result?: string;
  surfaces?: string[];
}

export interface ExploreLeaf {
  emit(effect: ExploreEffect): Promise<void>;
}

export interface ExploreInput {
  state: Record<string, Object>;
  persistence: Record<string, Object>;
  leaf: ExploreLeaf;
}

export interface ExplorePageOwner {
  mount(context: common.UIAbilityContext, input: ExploreInput): Promise<void>;
  recreateHomeSurface(): Promise<void>;
  selectHomeTab(tab: string): Promise<void>;
  retryCommunityLoad(): Promise<void>;
  retryCommunityLoadMore(): Promise<void>;
  resumeHomeSurface(): Promise<void>;
  finishInterestEditing(): Promise<void>;
  retryForYouLoad(): Promise<void>;
  confirmAllModulesOff(): Promise<void>;
  currentState(): Record<string, Object>;
  currentPersistence(): Record<string, Object>;
  featureAvailable(): boolean;
  ownerId(): string;
}

export class CallbackExplorePageOwner implements ExplorePageOwner {
  private mountAction: (context: common.UIAbilityContext, input: ExploreInput) => Promise<void>;
  private recreateAction: () => Promise<void>;
  private selectAction: (tab: string) => Promise<void>;
  private retryCommunityAction: () => Promise<void>;
  private retryMoreAction: () => Promise<void>;
  private resumeAction: () => Promise<void>;
  private finishInterestAction: () => Promise<void>;
  private retryForYouAction: () => Promise<void>;
  private hideModulesAction: () => Promise<void>;
  private stateReader: () => Record<string, Object>;
  private persistenceReader: () => Record<string, Object>;
  private featureReader: () => boolean;
  private ownerReader: () => string;

  constructor(
    mountAction: (context: common.UIAbilityContext, input: ExploreInput) => Promise<void>,
    recreateAction: () => Promise<void>, selectAction: (tab: string) => Promise<void>,
    retryCommunityAction: () => Promise<void>, retryMoreAction: () => Promise<void>,
    resumeAction: () => Promise<void>, finishInterestAction: () => Promise<void>,
    retryForYouAction: () => Promise<void>, hideModulesAction: () => Promise<void>,
    stateReader: () => Record<string, Object>, persistenceReader: () => Record<string, Object>,
    featureReader: () => boolean, ownerReader: () => string
  ) {
    this.mountAction = mountAction;
    this.recreateAction = recreateAction;
    this.selectAction = selectAction;
    this.retryCommunityAction = retryCommunityAction;
    this.retryMoreAction = retryMoreAction;
    this.resumeAction = resumeAction;
    this.finishInterestAction = finishInterestAction;
    this.retryForYouAction = retryForYouAction;
    this.hideModulesAction = hideModulesAction;
    this.stateReader = stateReader;
    this.persistenceReader = persistenceReader;
    this.featureReader = featureReader;
    this.ownerReader = ownerReader;
  }

  mount(context: common.UIAbilityContext, input: ExploreInput): Promise<void> { return this.mountAction(context, input); }
  recreateHomeSurface(): Promise<void> { return this.recreateAction(); }
  selectHomeTab(tab: string): Promise<void> { return this.selectAction(tab); }
  retryCommunityLoad(): Promise<void> { return this.retryCommunityAction(); }
  retryCommunityLoadMore(): Promise<void> { return this.retryMoreAction(); }
  resumeHomeSurface(): Promise<void> { return this.resumeAction(); }
  finishInterestEditing(): Promise<void> { return this.finishInterestAction(); }
  retryForYouLoad(): Promise<void> { return this.retryForYouAction(); }
  confirmAllModulesOff(): Promise<void> { return this.hideModulesAction(); }
  currentState(): Record<string, Object> { return this.stateReader(); }
  currentPersistence(): Record<string, Object> { return this.persistenceReader(); }
  featureAvailable(): boolean { return this.featureReader(); }
  ownerId(): string { return this.ownerReader(); }
}
