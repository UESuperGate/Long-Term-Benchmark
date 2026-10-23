import { common } from '@kit.AbilityKit';

export interface SavedEffect {
  name?: string;
  leaf?: string;
  status?: string;
  exception?: string;
  list?: string;
  article?: string;
  tab?: string;
  predicate?: string;
  delayMillis?: number;
  accentInsensitive?: boolean;
  count?: number;
  lists?: string[];
  force?: boolean;
  surfaces?: string[];
  surface?: string;
  fromRefresh?: boolean;
  attempt?: number;
  whileRefreshing?: boolean;
  setsRefreshing?: boolean;
}

export interface SavedLeaf { emit(effect: SavedEffect): Promise<void>; }
export interface SavedInput {
  state: Record<string, Object>;
  persistence: Record<string, Object>;
  leaf: SavedLeaf;
}

export interface SavedPageOwner {
  mount(context: common.UIAbilityContext, input: SavedInput): Promise<void>;
  openSavedSurface(): Promise<void>;
  selectSavedTab(tab: string): Promise<void>;
  enterSavedSearchQuery(query: string, elapsedMillis: number): Promise<void>;
  selectArticleFilter(filter: string): Promise<void>;
  selectAllVisibleRows(): Promise<void>;
  openSaveArticleSheet(): Promise<void>;
  cancelUnsaveConfirmation(): Promise<void>;
  undoArticleDeletion(): Promise<void>;
  resumeQueuedCollectionToggle(): Promise<void>;
  retryPullToRefreshAndCompleteSync(): Promise<void>;
  currentState(): Record<string, Object>;
  currentPersistence(): Record<string, Object>;
  featureAvailable(): boolean;
  ownerId(): string;
}

export class CallbackSavedPageOwner implements SavedPageOwner {
  private mountAction: (context: common.UIAbilityContext, input: SavedInput) => Promise<void>;
  private actions: Array<(...args: Object[]) => Promise<void>>;
  private stateReader: () => Record<string, Object>;
  private persistenceReader: () => Record<string, Object>;
  private featureReader: () => boolean;
  private ownerReader: () => string;

  constructor(
    mountAction: (context: common.UIAbilityContext, input: SavedInput) => Promise<void>,
    actions: Array<(...args: Object[]) => Promise<void>>,
    stateReader: () => Record<string, Object>, persistenceReader: () => Record<string, Object>,
    featureReader: () => boolean, ownerReader: () => string
  ) {
    this.mountAction = mountAction;
    this.actions = actions;
    this.stateReader = stateReader;
    this.persistenceReader = persistenceReader;
    this.featureReader = featureReader;
    this.ownerReader = ownerReader;
  }

  mount(context: common.UIAbilityContext, input: SavedInput): Promise<void> { return this.mountAction(context, input); }
  openSavedSurface(): Promise<void> { return this.actions[0](); }
  selectSavedTab(tab: string): Promise<void> { return this.actions[1](tab); }
  enterSavedSearchQuery(query: string, elapsedMillis: number): Promise<void> { return this.actions[2](query, elapsedMillis); }
  selectArticleFilter(filter: string): Promise<void> { return this.actions[3](filter); }
  selectAllVisibleRows(): Promise<void> { return this.actions[4](); }
  openSaveArticleSheet(): Promise<void> { return this.actions[5](); }
  cancelUnsaveConfirmation(): Promise<void> { return this.actions[6](); }
  undoArticleDeletion(): Promise<void> { return this.actions[7](); }
  resumeQueuedCollectionToggle(): Promise<void> { return this.actions[8](); }
  retryPullToRefreshAndCompleteSync(): Promise<void> { return this.actions[9](); }
  currentState(): Record<string, Object> { return this.stateReader(); }
  currentPersistence(): Record<string, Object> { return this.persistenceReader(); }
  featureAvailable(): boolean { return this.featureReader(); }
  ownerId(): string { return this.ownerReader(); }
}
