import common from '@ohos.app.ability.common';
import { GlobalSearchPresenter, GlobalSearchTarget, SearchResultState } from '../features/GlobalSearchFeature';
import { SearchHistoryResult, SearchHistoryResultType, SearchHistoryStore } from '../features/SearchHistory';

@Entry
@Component
struct Index {
  private presenter: GlobalSearchPresenter = new GlobalSearchPresenter(new SearchHistoryStore());
  private context: common.Context = getContext(this);
  @State private query: string = '';
  @State private target: GlobalSearchTarget = GlobalSearchTarget.Rooms;
  @State private resultState: SearchResultState = SearchResultState.Uninitialized;
  @State private results: string[] = [];
  @State private history: SearchHistoryResult[] = [];
  @State private historyLoaded: boolean = false;

  aboutToAppear(): void {
    this.presenter.openSearch(this.context, ['!design:example.org', '!engineering:example.org'])
      .then(() => this.refresh());
  }

  build() {
    Column() {
      this.Header()
      Scroll() {
        Column({ space: 14 }) {
          TextInput({ text: this.query, placeholder: 'Search rooms and messages' })
            .id('global_search_input')
            .onChange((value: string) => {
              this.presenter.updateQuery(value);
              this.refresh();
            })
            .onSubmit(() => {
              this.presenter.saveQueryToHistory(this.context).then(() => this.refresh());
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

          if (this.query.length === 0) {
            Row() {
              Text('Recent')
                .fontSize(18)
                .fontWeight(FontWeight.Bold)
                .layoutWeight(1)
              Button('Clear history')
                .enabled(this.history.length > 0)
                .onClick(() => {
                  this.presenter.clearHistory(this.context).then(() => this.refresh());
                })
            }
            .width('100%')
            if (this.historyLoaded && this.history.length === 0) {
              Text('No recent searches')
                .id('recent_search_empty')
                .fontColor('#64748B')
                .width('100%')
            }
            ForEach(this.history, (item: SearchHistoryResult) => {
              Button(item.type === SearchHistoryResultType.Query ? item.value : `Room ${item.value}`)
                .id(`recent_${item.id}`)
                .width('100%')
                .onClick(() => {
                  this.presenter.selectHistoryResult(item);
                  this.refresh();
                })
            }, (item: SearchHistoryResult) => item.id)
          }

          Text(`State: ${this.resultState}`)
            .fontSize(13)
            .fontColor('#64748B')
            .width('100%')
          ForEach(this.results, (result: string) => {
            Button(result)
              .width('100%')
              .onClick(() => {
                const roomId = result === 'Design' ? '!design:example.org' : '!engineering:example.org';
                this.presenter.saveRoomToHistory(this.context, roomId).then(() => this.refresh());
              })
          })
        }
        .padding(20)
        .width('100%')
      }
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
    this.history = this.presenter.history.slice();
    this.historyLoaded = this.presenter.historyLoaded;
  }

  @Builder
  Header() {
    Column({ space: 4 }) {
      Text('Global search')
        .fontSize(24)
        .fontWeight(FontWeight.Bold)
      Text('Android v26.09.3 behavior: persistent recent queries and rooms')
        .fontSize(13)
        .fontColor('#64748B')
    }
    .alignItems(HorizontalAlign.Start)
    .padding(20)
    .width('100%')
    .backgroundColor('#FFFFFF')
  }
}
