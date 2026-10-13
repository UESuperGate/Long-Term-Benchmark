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
  query: string = '';
  target: GlobalSearchTarget = GlobalSearchTarget.Rooms;
  resultState: SearchResultState = SearchResultState.Uninitialized;
  results: string[] = [];

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
}
