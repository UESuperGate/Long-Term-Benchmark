import { DomainError } from '../../core/DomainResult';

export const TIMELINE_CONTRACT_VERSION: string = '1';

export enum TimelineContentKind {
  Text = 'text',
  Image = 'image',
  Video = 'video',
  Audio = 'audio',
  File = 'file',
  Gallery = 'gallery',
  Poll = 'poll',
  Call = 'call',
  Location = 'location',
  State = 'state',
  UnableToDecrypt = 'unable_to_decrypt',
  Redacted = 'redacted'
}

export interface TimelineContent {
  kind: TimelineContentKind;
}

export interface TextContent extends TimelineContent {
  body: string;
  formattedBody: string | null;
}

export interface MediaDescriptor {
  sourceUrl: string;
  fileName: string;
  mimeType: string;
  sizeBytes: number | null;
  width: number | null;
  height: number | null;
  durationMs: number | null;
  thumbnailUrl: string | null;
}

export interface MediaContent extends TimelineContent {
  caption: string | null;
  media: MediaDescriptor;
}

export interface GalleryContent extends TimelineContent {
  caption: string | null;
  items: MediaDescriptor[];
}

export enum PollKind {
  Disclosed = 'disclosed',
  Undisclosed = 'undisclosed'
}

export interface PollAnswer {
  id: string;
  text: string;
  voteCount: number;
  isSelectedByCurrentUser: boolean;
}

export interface PollContent extends TimelineContent {
  question: string;
  pollKind: PollKind;
  maxSelections: number;
  answers: PollAnswer[];
  isEnded: boolean;
}

export enum CallKind {
  LegacyInvite = 'legacy_invite',
  Notification = 'notification'
}

export interface CallContent extends TimelineContent {
  callKind: CallKind;
  callId: string | null;
  isVideo: boolean;
  isActive: boolean;
}

export interface LocationContent extends TimelineContent {
  body: string;
  geoUri: string;
  description: string | null;
  zoomLevel: number | null;
  isLive: boolean;
  expiresAtMs: number | null;
}

export interface StateContent extends TimelineContent {
  eventType: string;
  stateKey: string;
  summary: string;
}

export enum UnableToDecryptCause {
  MissingMegolmSession = 'missing_megolm_session',
  Withheld = 'withheld',
  Membership = 'membership',
  HistoricalMessage = 'historical_message',
  DeviceLinkProblem = 'device_link_problem',
  Unknown = 'unknown'
}

export interface UnableToDecryptContent extends TimelineContent {
  sessionId: string | null;
  cause: UnableToDecryptCause;
}

export interface RedactedContent extends TimelineContent {
  reason: string | null;
}

export enum TimelineRelationKind {
  None = 'none',
  Reply = 'reply',
  Replacement = 'replacement',
  Reaction = 'reaction',
  Redaction = 'redaction'
}

export interface TimelineRelation {
  kind: TimelineRelationKind;
  targetEventId: string;
  key: string | null;
}

export enum LocalSendState {
  Queued = 'queued',
  Uploading = 'uploading',
  Sending = 'sending',
  Failed = 'failed',
  Sent = 'sent',
  Cancelled = 'cancelled'
}

export interface ReactionSummary {
  key: string;
  count: number;
  reactedByCurrentUser: boolean;
  senderIds: string[];
}

export interface TimelineEvent {
  stableId: string;
  eventId: string | null;
  transactionId: string | null;
  senderId: string;
  senderDisplayName: string | null;
  timestampMs: number;
  order: number;
  isOwn: boolean;
  isRemote: boolean;
  isEditable: boolean;
  canBeRepliedTo: boolean;
  isEdited: boolean;
  replyToEventId: string | null;
  content: TimelineContent;
  reactions: ReactionSummary[];
  localSendState: LocalSendState | null;
  revision: number;
}

/** Raw SDK event. Relation events are reduced into their target and are not rendered directly. */
export interface TimelineEventInput {
  eventId: string | null;
  transactionId: string | null;
  senderId: string;
  senderDisplayName: string | null;
  timestampMs: number;
  order: number;
  isOwn: boolean;
  content: TimelineContent;
  relation: TimelineRelation | null;
}

export enum PaginationDirection {
  Backwards = 'backwards',
  Forwards = 'forwards'
}

export interface PaginationState {
  isPaginating: boolean;
  hasMore: boolean;
  error: DomainError | null;
}

export enum TimelinePhase {
  Loading = 'loading',
  Ready = 'ready',
  Empty = 'empty',
  Offline = 'offline',
  Error = 'error'
}

export interface TimelineSnapshot {
  roomId: string;
  phase: TimelinePhase;
  items: TimelineEvent[];
  backwardPagination: PaginationState;
  forwardPagination: PaginationState;
  sendQueue: SendQueueEntry[];
  error: DomainError | null;
}

export interface TimelineObserver {
  onTimelineChanged(snapshot: TimelineSnapshot): void;
}

export interface TimelinePage {
  events: TimelineEventInput[];
  direction: PaginationDirection;
  hasMore: boolean;
}

export interface SendQueueEntry {
  transactionId: string;
  eventId: string | null;
  stableId: string;
  state: LocalSendState;
  progress: number | null;
  error: DomainError | null;
}

export interface TimelineSendRequest {
  transactionId: string;
  content: TimelineContent;
  replyToEventId: string | null;
}
