import { GlobalSearchPresenter, GlobalSearchTarget, SearchResultState } from '../features/GlobalSearchFeature';

@Entry
@Component
struct Index {
  private presenter: GlobalSearchPresenter = new GlobalSearchPresenter();
  @State private query: string = '';
  @State private target: GlobalSearchTarget = GlobalSearchTarget.Rooms;
  @State private resultState: SearchResultState = SearchResultState.Uninitialized;
  @State private results: string[] = [];

  build() {
    Column() {
      this.Header()
      Column({ space: 14 }) {
        TextInput({ text: this.query, placeholder: 'Search rooms and messages' })
          .id('global_search_input')
          .onChange((value: string) => {
            this.presenter.updateQuery(value);
            this.refresh();
          })
        Row({ space: 10 }) {
          Button('Rooms')
            .enabled(this.target !== GlobalSearchTarget.Rooms)
            .onClick(() => {
              this.presenter.updateTarget(GlobalSearchTarget.Rooms);
              this.refresh();
            })
          Button('Messages')
            .enabled(this.target !== GlobalSearchTarget.Messages)
            .onClick(() => {
              this.presenter.updateTarget(GlobalSearchTarget.Messages);
              this.refresh();
            })
          Button('Clear')
            .enabled(this.query.length > 0)
            .onClick(() => {
              this.presenter.clearQuery();
              this.refresh();
            })
        }
        Text(`State: ${this.resultState}`)
          .fontSize(13)
          .fontColor('#64748B')
          .width('100%')
        if (this.resultState === SearchResultState.Uninitialized) {
          Text('Enter a query to search')
            .fontColor('#64748B')
            .width('100%')
        }
        ForEach(this.results, (result: string) => {
          Text(result)
            .fontSize(16)
            .padding(14)
            .width('100%')
            .backgroundColor('#FFFFFF')
            .borderRadius(6)
        })
      }
      .padding(20)
      .width('100%')
      .layoutWeight(1)
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }

  private refresh(): void {
    this.query = this.presenter.query;
    this.target = this.presenter.target;
    this.resultState = this.presenter.resultState;
    this.results = this.presenter.results.slice();
  }

  @Builder
  Header() {
    Column({ space: 4 }) {
      Text('Global search')
        .fontSize(24)
        .fontWeight(FontWeight.Bold)
      Text('Android v26.09.2 behavior: no recent search history')
        .fontSize(13)
        .fontColor('#64748B')
    }
    .alignItems(HorizontalAlign.Start)
    .padding(20)
    .width('100%')
    .backgroundColor('#FFFFFF')
  }
}
