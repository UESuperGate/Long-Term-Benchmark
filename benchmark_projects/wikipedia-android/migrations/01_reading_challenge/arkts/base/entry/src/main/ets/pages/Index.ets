import {
  CallbackReadingPageOwner,
  ReadingIntegrationState,
  ReadingPageOwner
} from '../integration/ReadingPageIntegration';

@Entry
@Component
struct Index {
  @State articleTitle: string = 'Ada Lovelace';
  @State articleOpen: boolean = false;
  private runtimeOwnerId: string = 'Index:' + String(Date.now());

  async aboutToAppear(): Promise<void> {
  }

  private openArticle(): void {
    this.articleOpen = true;
  }

  createRuntimeOwner(): ReadingPageOwner {
    return new CallbackReadingPageOwner(
      async (): Promise<void> => {},
      async (): Promise<void> => {},
      async (): Promise<void> => {},
      async (): Promise<void> => { this.openArticle(); },
      (): ReadingIntegrationState => ({
        name: this.articleOpen ? 'article_open' : 'standard', streak: 0
      }),
      (): boolean => this.articleOpen,
      (): boolean => false,
      (): string => this.runtimeOwnerId
    );
  }

  build() {
    Column({ space: 16 }) {
      Text('Wikipedia')
        .fontSize(28)
        .fontWeight(FontWeight.Bold)
      Text(this.articleTitle)
        .fontSize(22)
      Button(this.articleOpen ? 'Article open' : 'Open article')
        .onClick(() => {
          this.openArticle();
        })
    }
    .width('100%')
    .height('100%')
    .padding(24)
    .justifyContent(FlexAlign.Center)
  }
}
