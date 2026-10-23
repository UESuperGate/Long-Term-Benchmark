import { common } from '@kit.AbilityKit';
import {
  FeedbackLeaf,
  FeedbackPayload,
  HybridSearchSettings,
  HybridSearchState,
  SearchHttpLeaf,
  StandardSearchLeaf
} from '../model/HybridSearchModels';
import { HttpSearchLeaf, SearchJsonTransport } from '../model/HttpSearchLeaf';
import { HybridSearchPageStore } from '../model/HybridSearchPageStore';
import {
  CallbackHybridPageOwner,
  HybridIntegrationFeedbackLeaf,
  HybridIntegrationInput,
  HybridIntegrationStandardSearchLeaf,
  HybridIntegrationState,
  HybridPageOwner
} from '../integration/HybridPageIntegration';

class PageFeedbackLeaf implements FeedbackLeaf {
  private onSubmit: (message: string) => void;

  constructor(onSubmit: (message: string) => void) {
    this.onSubmit = onSubmit;
  }

  async submit(payload: FeedbackPayload): Promise<void> {
    this.onSubmit(payload.elementId + ':' + String(payload.position));
  }
}

class PageStandardSearchLeaf implements StandardSearchLeaf {
  private onRequest: (query: string) => void;

  constructor(onRequest: (query: string) => void) {
    this.onRequest = onRequest;
  }

  request(query: string): void {
    this.onRequest(query);
  }
}

@Entry
@Component
struct Index {
  @State query: string = 'Paris';
  @State mode: string = 'standard';
  @State phase: string = 'idle';
  @State lexical: string[] = [];
  @State semantic: string[] = [];
  @State notice: string = '';
  @State feedback: string = '';
  private page?: HybridSearchPageStore;
  private runtimeOwnerId: string = 'Index:' + String(Date.now());

  async aboutToAppear(): Promise<void> {
    const context = getContext(this) as common.UIAbilityContext;
    await this.initialize(context, {
      language: 'fr',
      experimentGroup: 'lexicalsemantic',
      remoteEnabled: true,
      hybridEnabled: true,
      query: this.query
    }, new HttpSearchLeaf(), new PageFeedbackLeaf((message: string) => {
      this.feedback = message;
    }), new PageStandardSearchLeaf((query: string) => {
      this.query = query;
    }));
  }

  private async initialize(context: common.UIAbilityContext, settings: HybridSearchSettings,
    httpLeaf: SearchHttpLeaf, feedbackLeaf: FeedbackLeaf,
    standardSearchLeaf: StandardSearchLeaf): Promise<void> {
    this.query = settings.query;
    this.page = await HybridSearchPageStore.create(
      context,
      settings,
      httpLeaf,
      feedbackLeaf,
      standardSearchLeaf
    );
    this.sync(this.page.viewModel.state);
  }

  private openHybrid(): void {
    if (this.page) {
      this.page.openHybrid();
      this.sync(this.page.viewModel.state);
    }
  }

  private async submitSearch(): Promise<void> {
    if (this.page) {
      this.sync(await this.page.submit());
    }
  }

  private async retrySearch(): Promise<void> {
    if (this.page) {
      this.sync(await this.page.retry());
    }
  }

  private async rateResult(title: string, position: number, positive: boolean): Promise<void> {
    if (this.page) {
      await this.page.rate(title, position, positive);
    }
  }

  private async optOut(): Promise<void> {
    if (this.page) {
      await this.page.optOut();
      this.sync(this.page.viewModel.state);
    }
  }

  private updateQuery(value: string): void {
    this.query = value;
    this.page?.updateQuery(value);
  }

  private sync(state: HybridSearchState): void {
    this.mode = this.page?.mode ?? 'standard';
    this.phase = state.phase;
    this.lexical = state.lexicalTitles;
    this.semantic = state.semanticTitles;
    this.notice = state.notice ?? '';
  }

  createRuntimeOwner(): HybridPageOwner {
    return new CallbackHybridPageOwner(
      async (context: common.UIAbilityContext, input: HybridIntegrationInput): Promise<void> => {
        await this.initialize(
          context,
          input.settings as HybridSearchSettings,
          new HttpSearchLeaf(input.transport as SearchJsonTransport),
          input.feedback as HybridIntegrationFeedbackLeaf as FeedbackLeaf,
          input.standardSearch as HybridIntegrationStandardSearchLeaf as StandardSearchLeaf
        );
      },
      (): void => { this.openHybrid(); },
      async (): Promise<void> => { await this.submitSearch(); },
      async (): Promise<void> => { await this.retrySearch(); },
      async (title: string, position: number, positive: boolean): Promise<void> => {
        await this.rateResult(title, position, positive);
      },
      async (): Promise<void> => { await this.optOut(); },
      (query: string): void => { this.updateQuery(query); },
      (): HybridIntegrationState => this.page ? this.page.viewModel.state : {
        phase: this.phase, lexicalTitles: this.lexical, semanticTitles: this.semantic,
        retryAvailable: this.phase === 'error', notice: this.notice
      },
      (): string => this.page ? this.page.mode : this.mode,
      (): string => this.query,
      (): string[] => this.page ? this.page.sections() : [],
      (): boolean => this.page !== undefined,
      (): string => this.runtimeOwnerId
    );
  }

  build() {
    Column({ space: 12 }) {
      Text('Wikipedia Hybrid Search')
        .fontSize(26)
        .fontWeight(FontWeight.Bold)
      TextInput({ text: this.query, placeholder: 'Search Wikipedia' })
        .onChange((value: string) => {
          this.updateQuery(value);
        })
      Row({ space: 8 }) {
        Button('Open hybrid')
          .onClick(() => {
            this.openHybrid();
          })
        Button('Search')
          .onClick(async () => {
            await this.submitSearch();
          })
        Button('Opt out')
          .onClick(async () => {
            await this.optOut();
          })
      }
      Text('Mode: ' + this.mode + ' / ' + this.phase)
      Text(this.notice)
        .fontColor('#B32424')
      if (this.phase === 'error') {
        Button('Retry')
          .onClick(async () => {
            await this.retrySearch();
          })
      }
      ForEach(this.page?.sections() ?? [], (section: string) => {
        if (section === 'lexical') {
          Column() {
            Text('Lexical results').fontWeight(FontWeight.Bold)
            ForEach(this.lexical, (title: string) => {
              Text(title)
            })
          }
        } else {
          Column() {
            Text('Semantic results').fontWeight(FontWeight.Bold)
            ForEach(this.semantic, (title: string, index: number) => {
              Row({ space: 8 }) {
                Text(title).layoutWeight(1)
                Button('Useful').onClick(() => this.rateResult(title, index, true))
                Button('Not useful').onClick(() => this.rateResult(title, index, false))
              }
            })
          }
        }
      })
      Text(this.feedback)
        .fontSize(12)
    }
    .width('100%')
    .height('100%')
    .padding(20)
  }
}
