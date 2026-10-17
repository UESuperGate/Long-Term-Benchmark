export enum TimelineEventKind {
  Text = 'text',
  Emote = 'emote',
  Image = 'image',
  Video = 'video',
  Audio = 'audio',
  File = 'file',
  Gallery = 'gallery',
  ActiveCall = 'active_call',
  LiveLocation = 'live_location',
  Unsupported = 'unsupported'
}

export interface RoomSummary {
  id: string;
  name: string;
  topic: string;
  unreadCount: number;
  isMarkedUnread: boolean;
  isFavorite: boolean;
  isDirect: boolean;
}

export interface ReadReceiptSummary {
  userId: string;
  displayName: string;
  avatarInitials: string;
  timestamp: string;
}

export interface TimelineMediaItem {
  uri: string;
  mimeType: string;
  size?: number;
}

export interface TimelineEvent {
  id: string;
  roomId: string;
  sender: string;
  senderUserId?: string;
  timestamp: string;
  kind: TimelineEventKind;
  body: string;
  mediaCount?: number;
  mediaUri?: string;
  mimeType?: string;
  mediaSize?: number;
  caption?: string;
  mediaItems?: TimelineMediaItem[];
  readReceipts?: ReadReceiptSummary[];
  supported: boolean;
}

export interface AccountProfile {
  userId: string;
  displayName: string;
  avatarInitials: string;
  avatarUrl: string;
  userStatus: string;
  canSetUserStatus: boolean;
}

export interface BaseFeatureFlags {
  userStatus: boolean;
  galleryMessages: boolean;
  activeCallTimeline: boolean;
  liveLocationSharing: boolean;
  richLinkNewDevice: boolean;
}

export interface ScenarioInfo {
  scenarioId: string;
  taskFamily: string;
  baseVersion: string;
  finalVersion: string;
  description: string;
  intentionallyAbsent: string[];
  flags: BaseFeatureFlags;
}
