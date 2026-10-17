import { DomainError } from '../../core/DomainResult';

export const ROOM_LIST_CONTRACT_VERSION: string = '1';

export enum RoomMembership {
  Joined = 'joined',
  Invited = 'invited',
  Left = 'left',
  Knocked = 'knocked'
}

export enum RoomCategory {
  Group = 'group',
  People = 'people',
  Space = 'space'
}

export interface RoomSummary {
  roomId: string;
  displayName: string;
  canonicalAlias: string | null;
  avatarUrl: string | null;
  membership: RoomMembership;
  category: RoomCategory;
  isFavorite: boolean;
  isDirect: boolean;
  isMarkedUnread: boolean;
  unreadNotificationCount: number;
  unreadMentionCount: number;
  activeMembersCount: number;
  latestEventTimestampMs: number | null;
  latestEventPreview: string | null;
}

export enum RoomListFilterKind {
  All = 'all',
  Any = 'any',
  Identifiers = 'identifiers',
  Unread = 'unread',
  Favorite = 'favorite',
  Invite = 'invite',
  Category = 'category',
  NormalizedName = 'normalized_name',
  None = 'none'
}

/** A serializable filter tree suitable for crossing the native bridge. */
export interface RoomListFilter {
  kind: RoomListFilterKind;
  filters: RoomListFilter[];
  roomIds: string[];
  category: RoomCategory | null;
  pattern: string | null;
}

export enum RoomListPhase {
  Loading = 'loading',
  Ready = 'ready',
  Empty = 'empty',
  Offline = 'offline',
  Error = 'error'
}

export interface RoomListSnapshot {
  phase: RoomListPhase;
  rooms: RoomSummary[];
  selectedRoomId: string | null;
  filter: RoomListFilter;
  loadedCount: number;
  totalCount: number;
  hasMore: boolean;
  isRefreshing: boolean;
  error: DomainError | null;
}

export interface RoomListObserver {
  onRoomListChanged(snapshot: RoomListSnapshot): void;
}

export interface RoomListPage {
  rooms: RoomSummary[];
  totalCount: number;
  hasMore: boolean;
}
