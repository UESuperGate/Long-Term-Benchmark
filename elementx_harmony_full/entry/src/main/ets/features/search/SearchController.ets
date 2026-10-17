import {
  DomainErrorCode,
  DomainFailure,
  DomainResult,
  unexpectedFailure
} from '../../core/DomainResult';
import { ObservableState } from '../../core/ObservableState';
import {
  SearchDomain,
  SearchRequest,
  SearchSnapshot
} from '../../matrix/api/RoomManagementModels';
import { SearchDataSource } from '../../matrix/api/RoomManagementServices';
import { SearchReducer } from './SearchReducer';

export class SearchController {
  readonly state: ObservableState<SearchSnapshot>;
  private readonly source: SearchDataSource;
  private readonly reducer: SearchReducer = new SearchReducer();
  private readonly pageSize: number;
  private generation: number = 0;
  private loadingMore: boolean = false;
  private lastFailedRequest: SearchRequest | null = null;

  constructor(source: SearchDataSource, pageSize: number = 20) {
    this.source = source;
    this.pageSize = pageSize;
    this.state = new ObservableState<SearchSnapshot>(this.reducer.getSnapshot());
  }

  getSnapshot(): SearchSnapshot {
    return this.reducer.getSnapshot();
  }

  search(query: string, domain: SearchDomain, roomId: string | null = null): Promise<DomainResult<SearchSnapshot>> {
    const normalized = query.trim();
    if (normalized.length === 0) {
      return Promise.resolve(DomainResult.fail<SearchSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Search query must not be empty',
        false
      )));
    }
    if (domain === SearchDomain.Messages && (roomId === null || roomId.length === 0)) {
      return Promise.resolve(DomainResult.fail<SearchSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Message search requires a room id',
        false
      )));
    }
    const request: SearchRequest = {
      query: normalized,
      domain: domain,
      roomId: roomId,
      offset: 0,
      limit: this.pageSize
    };
    return this.execute(request, false, ++this.generation);
  }

  loadMore(): Promise<DomainResult<SearchSnapshot>> {
    const snapshot = this.getSnapshot();
    if (this.loadingMore) {
      return Promise.resolve(DomainResult.fail<SearchSnapshot>(new DomainFailure(
        DomainErrorCode.ServiceUnavailable,
        'Search pagination is already in progress',
        true
      )));
    }
    if (snapshot.nextOffset === null) {
      return Promise.resolve(DomainResult.succeed<SearchSnapshot>(snapshot));
    }
    const request: SearchRequest = {
      query: snapshot.query,
      domain: snapshot.domain,
      roomId: snapshot.roomId,
      offset: snapshot.nextOffset,
      limit: this.pageSize
    };
    this.loadingMore = true;
    return this.execute(request, true, this.generation);
  }

  retry(): Promise<DomainResult<SearchSnapshot>> {
    if (this.lastFailedRequest === null) {
      return Promise.resolve(DomainResult.fail<SearchSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'There is no failed search to retry',
        false
      )));
    }
    const request = this.lastFailedRequest;
    const append = request.offset > 0;
    if (!append) {
      this.generation += 1;
    }
    if (append) {
      this.loadingMore = true;
    }
    return this.execute(request, append, this.generation);
  }

  private async execute(
    request: SearchRequest,
    append: boolean,
    generation: number
  ): Promise<DomainResult<SearchSnapshot>> {
    this.publish(this.reducer.begin(request.query, request.domain, request.roomId, append));
    const result = await this.source.search(request);
    if (generation !== this.generation) {
      this.loadingMore = false;
      return DomainResult.fail<SearchSnapshot>(new DomainFailure(
        DomainErrorCode.Cancelled,
        'Search was superseded by a newer query',
        true
      ));
    }
    this.loadingMore = false;
    if (!result.success || result.value === null) {
      const error = result.error === null ? unexpectedFailure('search') : result.error;
      this.lastFailedRequest = request;
      this.publish(this.reducer.fail(error));
      return DomainResult.fail<SearchSnapshot>(error);
    }
    this.lastFailedRequest = null;
    const snapshot = this.reducer.succeed(result.value, append);
    this.publish(snapshot);
    return DomainResult.succeed<SearchSnapshot>(snapshot);
  }

  private publish(snapshot: SearchSnapshot): void {
    this.state.setValue(snapshot);
  }
}
