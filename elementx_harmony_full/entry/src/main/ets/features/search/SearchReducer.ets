import { DomainError, DomainErrorCode } from '../../core/DomainResult';
import {
  MessageSearchResult,
  RoomSearchResult,
  SearchDomain,
  SearchPage,
  SearchPhase,
  SearchSnapshot,
  UserSearchResult
} from '../../matrix/api/RoomManagementModels';

export class SearchReducer {
  private snapshot: SearchSnapshot = {
    phase: SearchPhase.Idle,
    query: '',
    domain: SearchDomain.Rooms,
    roomId: null,
    rooms: [],
    users: [],
    messages: [],
    nextOffset: null,
    isLoadingMore: false,
    error: null
  };

  getSnapshot(): SearchSnapshot {
    return {
      phase: this.snapshot.phase,
      query: this.snapshot.query,
      domain: this.snapshot.domain,
      roomId: this.snapshot.roomId,
      rooms: this.snapshot.rooms.slice(),
      users: this.snapshot.users.slice(),
      messages: this.snapshot.messages.slice(),
      nextOffset: this.snapshot.nextOffset,
      isLoadingMore: this.snapshot.isLoadingMore,
      error: this.snapshot.error
    };
  }

  begin(query: string, domain: SearchDomain, roomId: string | null, append: boolean): SearchSnapshot {
    if (!append) {
      this.snapshot.query = query;
      this.snapshot.domain = domain;
      this.snapshot.roomId = roomId;
      this.snapshot.rooms = [];
      this.snapshot.users = [];
      this.snapshot.messages = [];
      this.snapshot.nextOffset = null;
      this.snapshot.phase = SearchPhase.Searching;
    }
    this.snapshot.isLoadingMore = append;
    this.snapshot.error = null;
    return this.getSnapshot();
  }

  succeed(page: SearchPage, append: boolean): SearchSnapshot {
    if (append) {
      this.snapshot.rooms = this.mergeRooms(this.snapshot.rooms, page.rooms);
      this.snapshot.users = this.mergeUsers(this.snapshot.users, page.users);
      this.snapshot.messages = this.mergeMessages(this.snapshot.messages, page.messages);
    } else {
      this.snapshot.rooms = this.mergeRooms([], page.rooms);
      this.snapshot.users = this.mergeUsers([], page.users);
      this.snapshot.messages = this.mergeMessages([], page.messages);
    }
    this.snapshot.nextOffset = page.nextOffset;
    this.snapshot.isLoadingMore = false;
    this.snapshot.error = null;
    const count = this.snapshot.rooms.length + this.snapshot.users.length + this.snapshot.messages.length;
    this.snapshot.phase = count === 0 ? SearchPhase.Empty : SearchPhase.Ready;
    return this.getSnapshot();
  }

  fail(error: DomainError): SearchSnapshot {
    this.snapshot.isLoadingMore = false;
    this.snapshot.error = error;
    this.snapshot.phase = error.code === DomainErrorCode.NetworkUnavailable ?
      SearchPhase.Offline : SearchPhase.Error;
    return this.getSnapshot();
  }

  private mergeRooms(current: RoomSearchResult[], incoming: RoomSearchResult[]): RoomSearchResult[] {
    const merged = current.slice();
    incoming.forEach((item: RoomSearchResult) => {
      const index = merged.findIndex((candidate: RoomSearchResult) => candidate.roomId === item.roomId);
      if (index >= 0) {
        merged[index] = item;
      } else {
        merged.push(item);
      }
    });
    return merged;
  }

  private mergeUsers(current: UserSearchResult[], incoming: UserSearchResult[]): UserSearchResult[] {
    const merged = current.slice();
    incoming.forEach((item: UserSearchResult) => {
      const index = merged.findIndex((candidate: UserSearchResult) => candidate.userId === item.userId);
      if (index >= 0) {
        merged[index] = item;
      } else {
        merged.push(item);
      }
    });
    return merged;
  }

  private mergeMessages(current: MessageSearchResult[], incoming: MessageSearchResult[]): MessageSearchResult[] {
    const merged = current.slice();
    incoming.forEach((item: MessageSearchResult) => {
      const index = merged.findIndex((candidate: MessageSearchResult) => candidate.eventId === item.eventId);
      if (index >= 0) {
        merged[index] = item;
      } else {
        merged.push(item);
      }
    });
    merged.sort((left: MessageSearchResult, right: MessageSearchResult) => right.timestampMs - left.timestampMs);
    return merged;
  }
}
