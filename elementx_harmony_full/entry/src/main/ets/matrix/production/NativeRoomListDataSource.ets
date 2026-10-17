import { RootNavigationStateMachine } from '../../appnav/RootNavigationStateMachine';
import {
  DomainErrorCode,
  DomainFailure,
  DomainResult
} from '../../core/DomainResult';
import {
  NativeBridgeError,
  NativeBridgeErrorCode,
  NativeDataOperationResult,
  NativeMatrixBridge
} from '../../nativebridge/Index';
import {
  RoomListFilter,
  RoomListPage,
  RoomSummary
} from '../api/RoomModels';
import { RoomListDataSource } from '../api/RoomListService';

interface NativeRoomListEnvelope {
  rooms: RoomSummary[];
  totalCount: number;
}

/** SDK-backed room-list source. It performs a bounded sync before each refresh. */
export class NativeRoomListDataSource implements RoomListDataSource {
  private readonly bridge: NativeMatrixBridge;
  private readonly rootNavigation: RootNavigationStateMachine;
  private cachedRooms: RoomSummary[] = [];

  constructor(bridge: NativeMatrixBridge, rootNavigation: RootNavigationStateMachine) {
    this.bridge = bridge;
    this.rootNavigation = rootNavigation;
  }

  async loadInitial(_pageSize: number, _filter: RoomListFilter): Promise<DomainResult<RoomListPage>> {
    return this.sync();
  }

  async loadMore(offset: number, pageSize: number, _filter: RoomListFilter): Promise<DomainResult<RoomListPage>> {
    const rooms = this.cachedRooms.slice(offset, offset + pageSize);
    return DomainResult.succeed<RoomListPage>({
      rooms: rooms,
      totalCount: this.cachedRooms.length,
      hasMore: offset + rooms.length < this.cachedRooms.length
    });
  }

  async refresh(_filter: RoomListFilter): Promise<DomainResult<RoomListPage>> {
    return this.sync();
  }

  async subscribeVisibleRooms(_roomIds: string[]): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(true);
  }

  private async sync(): Promise<DomainResult<RoomListPage>> {
    const handle = this.currentHandle();
    if (handle === null) {
      return DomainResult.fail<RoomListPage>(new DomainFailure(
        DomainErrorCode.SessionMissing,
        'An authenticated Matrix SDK client is required to load rooms',
        false
      ));
    }
    try {
      const result = await this.bridge.syncRooms(handle);
      if (!result.ok || result.value === null) {
        return DomainResult.fail<RoomListPage>(this.nativeFailure(result));
      }
      const envelope = JSON.parse(result.value) as NativeRoomListEnvelope;
      if (!Array.isArray(envelope.rooms) || typeof envelope.totalCount !== 'number') {
        return DomainResult.fail<RoomListPage>(new DomainFailure(
          DomainErrorCode.Unknown,
          'Native room-list response is malformed',
          false
        ));
      }
      this.cachedRooms = envelope.rooms.slice();
      return DomainResult.succeed<RoomListPage>({
        rooms: this.cachedRooms.slice(),
        totalCount: envelope.totalCount,
        hasMore: false
      });
    } catch (error) {
      return DomainResult.fail<RoomListPage>(new DomainFailure(
        DomainErrorCode.NetworkUnavailable,
        'Matrix room sync could not reach the homeserver',
        true
      ));
    }
  }

  private currentHandle(): number | null {
    const sessionHandle = this.rootNavigation.getState().sessionHandle;
    if (sessionHandle === null || !sessionHandle.runtimeId.startsWith('native:')) {
      return null;
    }
    const handle = Number(sessionHandle.runtimeId.substring('native:'.length));
    return Number.isSafeInteger(handle) && handle > 0 ? handle : null;
  }

  private nativeFailure(result: NativeDataOperationResult): DomainFailure {
    const error: NativeBridgeError | null = result.error;
    const offline = error !== null && error.code === NativeBridgeErrorCode.SyncFailed;
    return new DomainFailure(
      offline ? DomainErrorCode.NetworkUnavailable : DomainErrorCode.ServiceUnavailable,
      error === null ? 'Native room sync failed' : error.message,
      error === null ? true : error.retryable
    );
  }
}
