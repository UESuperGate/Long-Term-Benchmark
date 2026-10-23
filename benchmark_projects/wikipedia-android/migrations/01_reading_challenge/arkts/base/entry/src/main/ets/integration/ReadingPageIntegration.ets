import { common } from '@kit.AbilityKit';

export interface ReadingIntegrationState {
  name: string;
  streak: number;
}

export interface ReadingIntegrationClock {
  today(): string;
}

export interface ReadingIntegrationEffects {
  heartbeat(state: ReadingIntegrationState): void;
  updateWidget(): void;
  refreshSurface(): void;
}

export interface ReadingIntegrationInput {
  clock: ReadingIntegrationClock;
  effects: ReadingIntegrationEffects;
}

export interface ReadingPageOwner {
  mount(context: common.UIAbilityContext, input: ReadingIntegrationInput): Promise<void>;
  refresh(): Promise<void>;
  enroll(): Promise<void>;
  openArticle(): Promise<void>;
  currentState(): ReadingIntegrationState;
  articleOpen(): boolean;
  featureAvailable(): boolean;
  ownerId(): string;
}

export class CallbackReadingPageOwner implements ReadingPageOwner {
  private mountAction: (context: common.UIAbilityContext, input: ReadingIntegrationInput) => Promise<void>;
  private refreshAction: () => Promise<void>;
  private enrollAction: () => Promise<void>;
  private openArticleAction: () => Promise<void>;
  private stateReader: () => ReadingIntegrationState;
  private articleReader: () => boolean;
  private featureReader: () => boolean;
  private ownerReader: () => string;

  constructor(
    mountAction: (context: common.UIAbilityContext, input: ReadingIntegrationInput) => Promise<void>,
    refreshAction: () => Promise<void>, enrollAction: () => Promise<void>,
    openArticleAction: () => Promise<void>, stateReader: () => ReadingIntegrationState,
    articleReader: () => boolean, featureReader: () => boolean, ownerReader: () => string
  ) {
    this.mountAction = mountAction;
    this.refreshAction = refreshAction;
    this.enrollAction = enrollAction;
    this.openArticleAction = openArticleAction;
    this.stateReader = stateReader;
    this.articleReader = articleReader;
    this.featureReader = featureReader;
    this.ownerReader = ownerReader;
  }

  mount(context: common.UIAbilityContext, input: ReadingIntegrationInput): Promise<void> {
    return this.mountAction(context, input);
  }

  refresh(): Promise<void> { return this.refreshAction(); }
  enroll(): Promise<void> { return this.enrollAction(); }
  openArticle(): Promise<void> { return this.openArticleAction(); }
  currentState(): ReadingIntegrationState { return this.stateReader(); }
  articleOpen(): boolean { return this.articleReader(); }
  featureAvailable(): boolean { return this.featureReader(); }
  ownerId(): string { return this.ownerReader(); }
}
