import { ReadReceiptSummary, RoomSummary, TimelineEvent, TimelineEventKind, TimelineMediaItem } from '../model/ElementModels';

export interface MatrixSyncMappingResult {
  rooms: RoomSummary[];
  timeline: TimelineEvent[];
  roomTimelines: RoomTimelineMapping[];
  nextBatch: string;
}

export interface RoomTimelineMapping {
  roomId: string;
  events: TimelineEvent[];
}

interface MatrixSyncRoot {
  next_batch?: string;
  rooms?: MatrixSyncRooms;
  account_data?: MatrixEventContainer;
}

interface MatrixSyncRooms {
  join?: Record<string, MatrixJoinedRoom>;
}

interface MatrixJoinedRoom {
  state?: MatrixEventContainer;
  timeline?: MatrixEventContainer;
  ephemeral?: MatrixEventContainer;
  account_data?: MatrixEventContainer;
  unread_notifications?: MatrixUnreadNotifications;
}

interface MatrixEventContainer {
  events?: MatrixEvent[];
}

interface MatrixUnreadNotifications {
  notification_count?: number;
}

interface MatrixEvent {
  event_id?: string;
  sender?: string;
  type?: string;
  origin_server_ts?: number;
  content?: MatrixEventContent;
}

interface MatrixEventContent {
  name?: string;
  topic?: string;
  body?: string;
  msgtype?: string;
  url?: string;
  info?: MatrixEventContentInfo;
  tags?: Record<string, object>;
  unread?: boolean;
}

interface MatrixEventContentInfo {
  mimetype?: string;
  size?: number;
}

interface MatrixRoomMetadata {
  name: string;
  topic: string;
}

interface MatrixRoomAccountData {
  isMarkedUnread: boolean;
  isFavorite: boolean;
}

interface MatrixReceiptUserContent {
  ts?: number;
}

type MatrixReceiptUsers = Record<string, MatrixReceiptUserContent>;
type MatrixReceiptTypes = Record<string, MatrixReceiptUsers>;
type MatrixReceiptContent = Record<string, MatrixReceiptTypes>;
type MatrixReadReceiptsByEvent = Record<string, ReadReceiptSummary[]>;
type MatrixDirectRoomContent = Record<string, string[]>;

export class MatrixSyncMapper {
  map(raw: string): MatrixSyncMappingResult {
    try {
      const root = JSON.parse(raw) as MatrixSyncRoot;
      const joinedRooms = root.rooms?.join;
      if (joinedRooms === undefined) {
        return this.empty(root.next_batch ?? '');
      }

      const rooms: RoomSummary[] = [];
      const timeline: TimelineEvent[] = [];
      const roomTimelines: RoomTimelineMapping[] = [];
      const directRoomIds = this.directRoomIds(root.account_data?.events ?? []);
      Object.keys(joinedRooms).forEach((roomId: string) => {
        const joinedRoom = joinedRooms[roomId];
        const metadata = this.roomMetadata(roomId, joinedRoom.state?.events ?? []);
        const accountData = this.roomAccountData(joinedRoom.account_data?.events ?? []);
        rooms.push({
          id: roomId,
          name: metadata.name,
          topic: metadata.topic,
          unreadCount: joinedRoom.unread_notifications?.notification_count ?? 0,
          isMarkedUnread: accountData.isMarkedUnread,
          isFavorite: accountData.isFavorite,
          isDirect: directRoomIds.includes(roomId)
        });
        const roomTimeline = this.timelineEvents(roomId, joinedRoom.timeline?.events ?? [], joinedRoom.ephemeral?.events ?? []);
        timeline.push(...roomTimeline);
        roomTimelines.push({
          roomId: roomId,
          events: roomTimeline
        });
      });

      return {
        rooms: rooms,
        timeline: timeline,
        roomTimelines: roomTimelines,
        nextBatch: root.next_batch ?? ''
      };
    } catch (error) {
      return this.empty('');
    }
  }

  private roomMetadata(roomId: string, events: MatrixEvent[]): MatrixRoomMetadata {
    const metadata: MatrixRoomMetadata = {
      name: this.fallbackRoomName(roomId),
      topic: 'Matrix room'
    };
    events.forEach((event: MatrixEvent) => {
      if (event.type === 'm.room.name' && event.content?.name !== undefined && event.content.name.length > 0) {
        metadata.name = event.content.name;
      }
      if (event.type === 'm.room.topic' && event.content?.topic !== undefined && event.content.topic.length > 0) {
        metadata.topic = event.content.topic;
      }
    });
    return metadata;
  }

  private directRoomIds(events: MatrixEvent[]): string[] {
    const result: string[] = [];
    events.forEach((event: MatrixEvent) => {
      if (event.type !== 'm.direct' || event.content === undefined) {
        return;
      }
      const content = event.content as MatrixDirectRoomContent;
      Object.keys(content).forEach((userId: string) => {
        const roomIds = content[userId];
        if (!Array.isArray(roomIds)) {
          return;
        }
        roomIds.forEach((roomId: string) => {
          if (roomId.length > 0 && !result.includes(roomId)) {
            result.push(roomId);
          }
        });
      });
    });
    return result;
  }

  private roomAccountData(events: MatrixEvent[]): MatrixRoomAccountData {
    const accountData: MatrixRoomAccountData = {
      isMarkedUnread: false,
      isFavorite: false
    };
    events.forEach((event: MatrixEvent) => {
      if (event.type === 'm.marked_unread') {
        accountData.isMarkedUnread = event.content?.unread === true;
      }
      if (event.type === 'm.tag' && event.content?.tags !== undefined) {
        accountData.isFavorite = event.content.tags['m.favourite'] !== undefined;
      }
    });
    return accountData;
  }

  private timelineEvents(roomId: string, events: MatrixEvent[], receiptEvents: MatrixEvent[]): TimelineEvent[] {
    const result: TimelineEvent[] = [];
    const receiptsByEvent = this.readReceiptsByEvent(receiptEvents);
    events.forEach((event: MatrixEvent) => {
      if (event.type !== 'm.room.message' || event.content?.body === undefined) {
        return;
      }
      const kind = this.timelineKind(event.content.msgtype ?? '');
      const eventId = event.event_id ?? `${roomId}-${result.length}`;
      const senderUserId = event.sender ?? '';
      result.push({
        id: eventId,
        roomId: roomId,
        sender: senderUserId.length > 0 ? this.displayNameFromUserId(senderUserId) : '',
        senderUserId: senderUserId,
        timestamp: this.timestampLabel(event.origin_server_ts ?? 0),
        kind: kind,
        body: event.content.body,
        mediaCount: kind === TimelineEventKind.Gallery ? 1 : 0,
        mediaUri: event.content.url ?? '',
        mimeType: event.content.info?.mimetype ?? '',
        mediaSize: event.content.info?.size ?? 0,
        mediaItems: this.mediaItems(event.content.url ?? '', event.content.info?.mimetype ?? '', event.content.info?.size ?? 0),
        readReceipts: receiptsByEvent[eventId] ?? [],
        supported: true
      });
    });
    return result;
  }

  private readReceiptsByEvent(events: MatrixEvent[]): MatrixReadReceiptsByEvent {
    const receiptsByEvent: MatrixReadReceiptsByEvent = {};
    events.forEach((event: MatrixEvent) => {
      if (event.type !== 'm.receipt' || event.content === undefined) {
        return;
      }
      const receiptContent = event.content as MatrixReceiptContent;
      Object.keys(receiptContent).forEach((eventId: string) => {
        const receiptTypes = receiptContent[eventId];
        const publicReceipts = receiptTypes['m.read'];
        if (publicReceipts === undefined) {
          return;
        }
        const eventReceipts = receiptsByEvent[eventId] ?? [];
        Object.keys(publicReceipts).forEach((userId: string) => {
          const receipt = publicReceipts[userId];
          eventReceipts.push({
            userId: userId,
            displayName: this.displayNameFromUserId(userId),
            avatarInitials: this.initialsFromUserId(userId),
            timestamp: this.timestampLabel(receipt.ts ?? 0)
          });
        });
        receiptsByEvent[eventId] = eventReceipts;
      });
    });
    return receiptsByEvent;
  }

  private timelineKind(msgtype: string): TimelineEventKind {
    if (msgtype === 'm.image') {
      return TimelineEventKind.Image;
    }
    if (msgtype === 'm.video') {
      return TimelineEventKind.Video;
    }
    if (msgtype === 'm.audio') {
      return TimelineEventKind.Audio;
    }
    if (msgtype === 'm.file') {
      return TimelineEventKind.File;
    }
    if (msgtype === 'm.emote') {
      return TimelineEventKind.Emote;
    }
    return TimelineEventKind.Text;
  }

  private mediaItems(uri: string, mimeType: string, size: number): TimelineMediaItem[] {
    if (uri.length === 0 && mimeType.length === 0) {
      return [];
    }
    return [
      {
        uri: uri,
        mimeType: mimeType,
        size: size
      }
    ];
  }

  private timestampLabel(timestamp: number): string {
    if (timestamp <= 0) {
      return 'sync';
    }
    const date = new Date(timestamp);
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
  }

  private displayNameFromUserId(userId: string): string {
    let value = userId;
    if (value.startsWith('@')) {
      value = value.substring(1);
    }
    const homeserverIndex = value.indexOf(':');
    if (homeserverIndex > 0) {
      value = value.substring(0, homeserverIndex);
    }
    if (value.length === 0) {
      return userId;
    }
    return value;
  }

  private initialsFromUserId(userId: string): string {
    const displayName = this.displayNameFromUserId(userId);
    if (displayName.length <= 1) {
      return displayName.toUpperCase();
    }
    return displayName.substring(0, 2).toUpperCase();
  }

  private fallbackRoomName(roomId: string): string {
    if (roomId.length <= 12) {
      return roomId;
    }
    return `${roomId.substring(0, 8)}...${roomId.substring(roomId.length - 4)}`;
  }

  private empty(nextBatch: string): MatrixSyncMappingResult {
    return {
      rooms: [],
      timeline: [],
      roomTimelines: [],
      nextBatch: nextBatch
    };
  }
}
