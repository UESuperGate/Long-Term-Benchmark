import {
  DomainErrorCode,
  DomainFailure,
  DomainResult,
  unexpectedFailure
} from '../core/DomainResult';
import {
  RoomListFilter,
  RoomListObserver,
  RoomListPage,
  RoomListSnapshot
} from '../matrix/api/RoomModels';
import {
  RoomListDataSource,
  RoomListService,
  RoomListSubscription
} from '../matrix/api/RoomListService';
import { RoomListFilters } from './RoomListFilters';
import { RoomListReducer } from './RoomListReducer';

class ControllerRoomListSubscription implements RoomListSubscription {
  readonly subscriptionId: number;
  private readonly onClose: (subscriptionId: number) => void;
  private closed: boolean = false;

  constructor(subscriptionId: number, onClose: (subscriptionId: number) => void) {
    this.subscriptionId = subscriptionId;
    this.onClose = onClose;
  }

  close(): void {
    if (!this.closed) {
      this.closed = true;
      this.onClose(this.subscriptionId);
    }
  }
}

export class RoomListController implements RoomListService {
  private readonly source: RoomListDataSource;
  private readonly pageSize: number;
  private readonly reducer: RoomListReducer;
  private readonly observers: Map<number, RoomListObserver> = new Map<number, RoomListObserver>();
  private nextObserverId: number = 1;
  private operationGeneration: number = 0;

  constructor(source: RoomListDataSource, pageSize: number = 20, filter: RoomListFilter = RoomListFilters.all()) {
    this.source = source;
    this.pageSize = pageSize;
    this.reducer = new RoomListReducer(filter);
  }

  getSnapshot(): RoomListSnapshot {
    return this.reducer.getSnapshot();
  }

  subscribe(observer: RoomListObserver): RoomListSubscription {
    const id = this.nextObserverId++;
    this.observers.set(id, observer);
    observer.onRoomListChanged(this.getSnapshot());
    return new ControllerRoomListSubscription(id, (subscriptionId: number) => this.observers.delete(subscriptionId));
  }

  async start(): Promise<DomainResult<RoomListSnapshot>> {
    const generation = ++this.operationGeneration;
    this.publish(this.reducer.beginLoading(false));
    return this.completePage(generation, await this.source.loadInitial(this.pageSize, this.getSnapshot().filter), false);
  }

  async refresh(): Promise<DomainResult<RoomListSnapshot>> {
    const generation = ++this.operationGeneration;
    this.publish(this.reducer.beginLoading(true));
    return this.completePage(generation, await this.source.refresh(this.getSnapshot().filter), false);
  }

  async loadMore(): Promise<DomainResult<RoomListSnapshot>> {
    const current = this.getSnapshot();
    if (!current.hasMore) {
      return DomainResult.succeed<RoomListSnapshot>(current);
    }
    const generation = ++this.operationGeneration;
    return this.completePage(
      generation,
      await this.source.loadMore(current.loadedCount, this.pageSize, current.filter),
      true
    );
  }

  async updateFilter(filter: RoomListFilter): Promise<DomainResult<RoomListSnapshot>> {
    ++this.operationGeneration;
    this.publish(this.reducer.updateFilter(filter));
    return this.start();
  }

  selectRoom(roomId: string | null): DomainResult<RoomListSnapshot> {
    if (!this.reducer.select(roomId)) {
      return DomainResult.fail<RoomListSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        `Cannot select unknown room ${roomId}`,
        false
      ));
    }
    const snapshot = this.getSnapshot();
    this.publish(snapshot);
    return DomainResult.succeed<RoomListSnapshot>(snapshot);
  }

  async updateVisibleRooms(roomIds: string[]): Promise<DomainResult<boolean>> {
    return this.source.subscribeVisibleRooms(roomIds);
  }

  setOffline(isOffline: boolean): void {
    this.publish(this.reducer.setOffline(isOffline));
  }

  private completePage(
    generation: number,
    result: DomainResult<RoomListPage>,
    append: boolean
  ): DomainResult<RoomListSnapshot> {
    if (generation !== this.operationGeneration) {
      return DomainResult.fail<RoomListSnapshot>(new DomainFailure(
        DomainErrorCode.Cancelled,
        'Room list operation superseded by a newer request',
        true
      ));
    }
    if (!result.success || result.value === null) {
      const error = result.error === null ? unexpectedFailure('room list') : result.error;
      this.publish(this.reducer.fail(error, error.code === DomainErrorCode.NetworkUnavailable));
      return DomainResult.fail<RoomListSnapshot>(error);
    }
    const snapshot = append ? this.reducer.append(result.value) : this.reducer.replace(result.value);
    this.publish(snapshot);
    return DomainResult.succeed<RoomListSnapshot>(snapshot);
  }

  private publish(snapshot: RoomListSnapshot): void {
    this.observers.forEach((observer: RoomListObserver) => observer.onRoomListChanged(snapshot));
  }
}
