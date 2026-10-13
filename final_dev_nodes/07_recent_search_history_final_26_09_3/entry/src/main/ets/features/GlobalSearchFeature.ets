import common from '@ohos.app.ability.common';
import { SearchHistoryResult, SearchHistoryResultType, SearchHistoryStore } from './SearchHistory';

export enum GlobalSearchTarget {
  Rooms = 'rooms',
  Messages = 'messages'
}

export enum SearchResultState {
  Uninitialized = 'uninitialized',
  Loading = 'loading',
  Success = 'success'
}

export class GlobalSearchPresenter {
  private readonly store: SearchHistoryStore;
  query: string = '';
  target: GlobalSearchTarget = GlobalSearchTarget.Rooms;
  resultState: SearchResultState = SearchResultState.Uninitialized;
  results: string[] = [];
  history: SearchHistoryResult[] = [];
  historyLoaded: boolean = false;

  constructor(store: SearchHistoryStore) {
    this.store = store;
  }

  async openSearch(context: common.Context, accessibleRoomIds: string[]): Promise<void> {
    const stored = await this.store.load(context);
    this.history = stored.filter((item: SearchHistoryResult) => {
      return item.type === SearchHistoryResultType.Query || accessibleRoomIds.includes(item.value);
    });
    this.historyLoaded = true;
  }

  updateQuery(query: string): void {
    this.query = query;
    if (query.trim().length === 0) {
      this.resultState = SearchResultState.Uninitialized;
      this.results = [];
      return;
    }
    this.resultState = SearchResultState.Loading;
    this.results = this.target === GlobalSearchTarget.Rooms ? ['Design', 'Engineering'] : ['Roadmap notes'];
    this.resultState = SearchResultState.Success;
  }

  updateTarget(target: GlobalSearchTarget): void {
    this.target = target;
    if (this.query.trim().length > 0) {
      this.updateQuery(this.query);
    }
  }

  clearQuery(): void {
    this.query = '';
    this.results = [];
    this.resultState = SearchResultState.Uninitialized;
  }

  async saveQueryToHistory(context: common.Context): Promise<void> {
    const term = this.query.trim();
    if (term.length === 0) {
      return;
    }
    this.history = await this.store.add(context, SearchHistoryResult.query(term));
  }

  async saveRoomToHistory(context: common.Context, roomId: string): Promise<void> {
    this.history = await this.store.add(context, SearchHistoryResult.room(roomId));
  }

  selectHistoryResult(result: SearchHistoryResult): void {
    if (result.type === SearchHistoryResultType.Query) {
      this.query = result.value;
      this.target = GlobalSearchTarget.Rooms;
      this.resultState = SearchResultState.Loading;
    }
  }

  async clearHistory(context: common.Context): Promise<void> {
    await this.store.clear(context);
    this.history = [];
  }
}
