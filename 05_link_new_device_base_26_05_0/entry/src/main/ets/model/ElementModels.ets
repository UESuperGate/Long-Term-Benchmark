export enum TimelineEventKind {
  Text = 'text',
  Image = 'image',
  Video = 'video',
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
  isDirect: boolean;
}

export interface TimelineEvent {
  id: string;
  sender: string;
  timestamp: string;
  kind: TimelineEventKind;
  body: string;
  mediaCount?: number;
  supported: boolean;
}

export interface AccountProfile {
  userId: string;
  displayName: string;
  avatarInitials: string;
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
