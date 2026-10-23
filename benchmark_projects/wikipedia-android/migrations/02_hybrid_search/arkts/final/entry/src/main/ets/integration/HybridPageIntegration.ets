import { common } from '@kit.AbilityKit';

export interface HybridIntegrationSettings {
  language: string;
  experimentGroup: string;
  remoteEnabled: boolean;
  hybridEnabled: boolean;
  query: string;
}

export interface HybridIntegrationState {
  phase: string;
  lexicalTitles: string[];
  semanticTitles: string[];
  retryAvailable: boolean;
  notice?: string;
}

export interface HybridIntegrationFeedbackPayload {
  elementId: string;
  query: string;
  position: number;
  title: string;
}

export interface HybridIntegrationJsonTransport {
  getJson(url: string): Promise<Record<string, Object>>;
}

export interface HybridIntegrationFeedbackLeaf {
  submit(payload: HybridIntegrationFeedbackPayload): Promise<void>;
}

export interface HybridIntegrationStandardSearchLeaf {
  request(query: string): void;
}

export interface HybridIntegrationInput {
  settings: HybridIntegrationSettings;
  transport: HybridIntegrationJsonTransport;
  feedback: HybridIntegrationFeedbackLeaf;
  standardSearch: HybridIntegrationStandardSearchLeaf;
}

export interface HybridPageOwner {
  mount(context: common.UIAbilityContext, input: HybridIntegrationInput): Promise<void>;
  openHybrid(): void;
  submit(): Promise<void>;
  retry(): Promise<void>;
  rate(title: string, position: number, positive: boolean): Promise<void>;
  optOut(): Promise<void>;
  updateQuery(query: string): void;
  currentState(): HybridIntegrationState;
  currentMode(): string;
  currentQuery(): string;
  sections(): string[];
  featureAvailable(): boolean;
  ownerId(): string;
}

export class CallbackHybridPageOwner implements HybridPageOwner {
  private mountAction: (context: common.UIAbilityContext, input: HybridIntegrationInput) => Promise<void>;
  private openAction: () => void;
  private submitAction: () => Promise<void>;
  private retryAction: () => Promise<void>;
  private rateAction: (title: string, position: number, positive: boolean) => Promise<void>;
  private optOutAction: () => Promise<void>;
  private queryAction: (query: string) => void;
  private stateReader: () => HybridIntegrationState;
  private modeReader: () => string;
  private queryReader: () => string;
  private sectionsReader: () => string[];
  private featureReader: () => boolean;
  private ownerReader: () => string;

  constructor(
    mountAction: (context: common.UIAbilityContext, input: HybridIntegrationInput) => Promise<void>,
    openAction: () => void, submitAction: () => Promise<void>, retryAction: () => Promise<void>,
    rateAction: (title: string, position: number, positive: boolean) => Promise<void>,
    optOutAction: () => Promise<void>, queryAction: (query: string) => void,
    stateReader: () => HybridIntegrationState, modeReader: () => string,
    queryReader: () => string, sectionsReader: () => string[], featureReader: () => boolean,
    ownerReader: () => string
  ) {
    this.mountAction = mountAction;
    this.openAction = openAction;
    this.submitAction = submitAction;
    this.retryAction = retryAction;
    this.rateAction = rateAction;
    this.optOutAction = optOutAction;
    this.queryAction = queryAction;
    this.stateReader = stateReader;
    this.modeReader = modeReader;
    this.queryReader = queryReader;
    this.sectionsReader = sectionsReader;
    this.featureReader = featureReader;
    this.ownerReader = ownerReader;
  }

  mount(context: common.UIAbilityContext, input: HybridIntegrationInput): Promise<void> {
    return this.mountAction(context, input);
  }

  openHybrid(): void { this.openAction(); }
  submit(): Promise<void> { return this.submitAction(); }
  retry(): Promise<void> { return this.retryAction(); }
  rate(title: string, position: number, positive: boolean): Promise<void> {
    return this.rateAction(title, position, positive);
  }
  optOut(): Promise<void> { return this.optOutAction(); }
  updateQuery(query: string): void { this.queryAction(query); }
  currentState(): HybridIntegrationState { return this.stateReader(); }
  currentMode(): string { return this.modeReader(); }
  currentQuery(): string { return this.queryReader(); }
  sections(): string[] { return this.sectionsReader(); }
  featureAvailable(): boolean { return this.featureReader(); }
  ownerId(): string { return this.ownerReader(); }
}
