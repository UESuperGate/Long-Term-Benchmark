import { DomainError } from '../core/DomainResult';
import {
  RoomListFilter,
  RoomListPage,
  RoomListPhase,
  RoomListSnapshot,
  RoomSummary
} from '../matrix/api/RoomModels';
import { roomMatchesFilter } from './RoomListFilters';

function roomTimestamp(room: RoomSummary): number {
  return room.latestEventTimestampMs === null ? -1 : room.latestEventTimestampMs;
}

function sortRooms(rooms: RoomSummary[]): RoomSummary[] {
  return rooms.sort((left: RoomSummary, right: RoomSummary) => {
    const byTimestamp = roomTimestamp(right) - roomTimestamp(left);
    if (byTimestamp !== 0) {
      return byTimestamp;
    }
    return left.roomId.localeCompare(right.roomId);
  });
}

export class RoomListReducer {
  private snapshot: RoomListSnapshot;

  constructor(filter: RoomListFilter) {
    this.snapshot = {
      phase: RoomListPhase.Loading,
      rooms: [],
      selectedRoomId: null,
      filter: filter,
      loadedCount: 0,
      totalCount: 0,
      hasMore: false,
      isRefreshing: false,
      error: null
    };
  }

  getSnapshot(): RoomListSnapshot {
    return {
      phase: this.snapshot.phase,
      rooms: this.snapshot.rooms.slice(),
      selectedRoomId: this.snapshot.selectedRoomId,
      filter: this.snapshot.filter,
      loadedCount: this.snapshot.loadedCount,
      totalCount: this.snapshot.totalCount,
      hasMore: this.snapshot.hasMore,
      isRefreshing: this.snapshot.isRefreshing,
      error: this.snapshot.error
    };
  }

  beginLoading(refreshing: boolean): RoomListSnapshot {
    this.snapshot.isRefreshing = refreshing;
    this.snapshot.error = null;
    if (this.snapshot.rooms.length === 0) {
      this.snapshot.phase = RoomListPhase.Loading;
    }
    return this.getSnapshot();
  }

  replace(page: RoomListPage): RoomListSnapshot {
    this.snapshot.rooms = this.filteredUnique(page.rooms);
    this.snapshot.loadedCount = this.snapshot.rooms.length;
    this.snapshot.totalCount = page.totalCount;
    this.snapshot.hasMore = page.hasMore;
    this.snapshot.isRefreshing = false;
    this.snapshot.error = null;
    this.snapshot.phase = this.snapshot.rooms.length === 0 ? RoomListPhase.Empty : RoomListPhase.Ready;
    this.dropInvalidSelection();
    return this.getSnapshot();
  }

  append(page: RoomListPage): RoomListSnapshot {
    const merged = this.snapshot.rooms.slice();
    page.rooms.forEach((room: RoomSummary) => {
      const index = merged.findIndex((candidate: RoomSummary) => candidate.roomId === room.roomId);
      if (index >= 0) {
        merged[index] = room;
      } else {
        merged.push(room);
      }
    });
    this.snapshot.rooms = this.filteredUnique(merged);
    this.snapshot.loadedCount = this.snapshot.rooms.length;
    this.snapshot.totalCount = page.totalCount;
    this.snapshot.hasMore = page.hasMore;
    this.snapshot.isRefreshing = false;
    this.snapshot.error = null;
    this.snapshot.phase = this.snapshot.rooms.length === 0 ? RoomListPhase.Empty : RoomListPhase.Ready;
    this.dropInvalidSelection();
    return this.getSnapshot();
  }

  updateFilter(filter: RoomListFilter): RoomListSnapshot {
    this.snapshot.filter = filter;
    this.snapshot.rooms = [];
    this.snapshot.loadedCount = 0;
    this.snapshot.totalCount = 0;
    this.snapshot.hasMore = false;
    this.snapshot.phase = RoomListPhase.Loading;
    this.snapshot.error = null;
    this.dropInvalidSelection();
    return this.getSnapshot();
  }

  select(roomId: string | null): boolean {
    if (roomId !== null && !this.snapshot.rooms.some((room: RoomSummary) => room.roomId === roomId)) {
      return false;
    }
    this.snapshot.selectedRoomId = roomId;
    return true;
  }

  fail(error: DomainError, offline: boolean): RoomListSnapshot {
    this.snapshot.phase = offline ? RoomListPhase.Offline : RoomListPhase.Error;
    this.snapshot.error = error;
    this.snapshot.isRefreshing = false;
    return this.getSnapshot();
  }

  setOffline(isOffline: boolean): RoomListSnapshot {
    if (isOffline) {
      this.snapshot.phase = RoomListPhase.Offline;
    } else {
      this.snapshot.phase = this.snapshot.rooms.length === 0 ? RoomListPhase.Empty : RoomListPhase.Ready;
      this.snapshot.error = null;
    }
    return this.getSnapshot();
  }

  private filteredUnique(rooms: RoomSummary[]): RoomSummary[] {
    const unique: RoomSummary[] = [];
    rooms.forEach((room: RoomSummary) => {
      if (!roomMatchesFilter(room, this.snapshot.filter)) {
        return;
      }
      const index = unique.findIndex((candidate: RoomSummary) => candidate.roomId === room.roomId);
      if (index >= 0) {
        unique[index] = room;
      } else {
        unique.push(room);
      }
    });
    return sortRooms(unique);
  }

  private dropInvalidSelection(): void {
    if (this.snapshot.selectedRoomId !== null &&
      !this.snapshot.rooms.some((room: RoomSummary) => room.roomId === this.snapshot.selectedRoomId)) {
      this.snapshot.selectedRoomId = null;
    }
  }
}
