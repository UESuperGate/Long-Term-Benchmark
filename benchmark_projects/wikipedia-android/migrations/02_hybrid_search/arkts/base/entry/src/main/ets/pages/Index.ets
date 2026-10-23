import {
  CallbackHybridPageOwner,
  HybridIntegrationInput,
  HybridIntegrationState,
  HybridPageOwner
} from '../integration/HybridPageIntegration';

@Entry
@Component
struct Index {
  @State query: string = '';
  @State phase: string = 'idle';
  private runtimeOwnerId: string = 'Index:' + String(Date.now());

  async aboutToAppear(): Promise<void> {
  }

  private updateQuery(value: string): void {
    this.query = value;
  }

  private submitSearch(): void {
    this.phase = this.query.length > 0 ? 'standard_success' : 'idle';
  }

  createRuntimeOwner(): HybridPageOwner {
    return new CallbackHybridPageOwner(
      async (_context, input: HybridIntegrationInput): Promise<void> => {
        this.updateQuery(input.settings.query);
      },
      (): void => {},
      async (): Promise<void> => { this.submitSearch(); },
      async (): Promise<void> => {},
      async (): Promise<void> => {},
      async (): Promise<void> => {},
      (query: string): void => { this.updateQuery(query); },
      (): HybridIntegrationState => ({
        phase: this.phase, lexicalTitles: [], semanticTitles: [], retryAvailable: false
      }),
      (): string => 'standard',
      (): string => this.query,
      (): string[] => [],
      (): boolean => false,
      (): string => this.runtimeOwnerId
    );
  }

  build() {
    Column({ space: 16 }) {
      Text('Wikipedia Search')
        .fontSize(28)
        .fontWeight(FontWeight.Bold)
      TextInput({ text: this.query, placeholder: 'Search Wikipedia' })
        .onChange((value: string) => {
          this.updateQuery(value);
        })
      Button('Search')
        .onClick(() => {
          this.submitSearch();
        })
      Text(this.phase)
    }
    .width('100%')
    .height('100%')
    .padding(24)
  }
}
