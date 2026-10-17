import { DomainResult } from '../../core/DomainResult';
import {
  RoomListFilter,
  RoomListObserver,
  RoomListPage,
  RoomListSnapshot
} from './RoomModels';

export interface RoomListSubscription {
  subscriptionId: number;
  close(): void;
}

/** Production boundary to be implemented by the Matrix Rust native bridge. */
export interface RoomListDataSource {
  loadInitial(pageSize: number, filter: RoomListFilter): Promise<DomainResult<RoomListPage>>;
  loadMore(offset: number, pageSize: number, filter: RoomListFilter): Promise<DomainResult<RoomListPage>>;
  refresh(filter: RoomListFilter): Promise<DomainResult<RoomListPage>>;
  subscribeVisibleRooms(roomIds: string[]): Promise<DomainResult<boolean>>;
}

export interface RoomListService {
  getSnapshot(): RoomListSnapshot;
  subscribe(observer: RoomListObserver): RoomListSubscription;
  start(): Promise<DomainResult<RoomListSnapshot>>;
  refresh(): Promise<DomainResult<RoomListSnapshot>>;
  loadMore(): Promise<DomainResult<RoomListSnapshot>>;
  updateFilter(filter: RoomListFilter): Promise<DomainResult<RoomListSnapshot>>;
  selectRoom(roomId: string | null): DomainResult<RoomListSnapshot>;
  updateVisibleRooms(roomIds: string[]): Promise<DomainResult<boolean>>;
  setOffline(isOffline: boolean): void;
}
