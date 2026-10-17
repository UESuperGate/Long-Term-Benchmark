import {
  RoomCategory,
  RoomListFilter,
  RoomListFilterKind,
  RoomSummary
} from '../matrix/api/RoomModels';

function emptyFilter(kind: RoomListFilterKind): RoomListFilter {
  return {
    kind: kind,
    filters: [],
    roomIds: [],
    category: null,
    pattern: null
  };
}

export class RoomListFilters {
  static all(filters: RoomListFilter[] = []): RoomListFilter {
    const value = emptyFilter(RoomListFilterKind.All);
    value.filters = filters;
    return value;
  }

  static any(filters: RoomListFilter[]): RoomListFilter {
    const value = emptyFilter(RoomListFilterKind.Any);
    value.filters = filters;
    return value;
  }

  static identifiers(roomIds: string[]): RoomListFilter {
    const value = emptyFilter(RoomListFilterKind.Identifiers);
    value.roomIds = roomIds;
    return value;
  }

  static unread(): RoomListFilter {
    return emptyFilter(RoomListFilterKind.Unread);
  }

  static favorite(): RoomListFilter {
    return emptyFilter(RoomListFilterKind.Favorite);
  }

  static invite(): RoomListFilter {
    return emptyFilter(RoomListFilterKind.Invite);
  }

  static category(category: RoomCategory): RoomListFilter {
    const value = emptyFilter(RoomListFilterKind.Category);
    value.category = category;
    return value;
  }

  static normalizedName(pattern: string): RoomListFilter {
    const value = emptyFilter(RoomListFilterKind.NormalizedName);
    value.pattern = pattern;
    return value;
  }

  static none(): RoomListFilter {
    return emptyFilter(RoomListFilterKind.None);
  }
}

export function roomMatchesFilter(room: RoomSummary, filter: RoomListFilter): boolean {
  switch (filter.kind) {
    case RoomListFilterKind.All:
      return filter.filters.every((child: RoomListFilter) => roomMatchesFilter(room, child));
    case RoomListFilterKind.Any:
      return filter.filters.some((child: RoomListFilter) => roomMatchesFilter(room, child));
    case RoomListFilterKind.Identifiers:
      return filter.roomIds.includes(room.roomId);
    case RoomListFilterKind.Unread:
      return room.isMarkedUnread || room.unreadNotificationCount > 0 || room.unreadMentionCount > 0;
    case RoomListFilterKind.Favorite:
      return room.isFavorite;
    case RoomListFilterKind.Invite:
      return room.membership === 'invited';
    case RoomListFilterKind.Category:
      return filter.category !== null && room.category === filter.category;
    case RoomListFilterKind.NormalizedName:
      return filter.pattern !== null &&
        room.displayName.toLocaleLowerCase().includes(filter.pattern.trim().toLocaleLowerCase());
    case RoomListFilterKind.None:
      return false;
    default:
      return false;
  }
}
