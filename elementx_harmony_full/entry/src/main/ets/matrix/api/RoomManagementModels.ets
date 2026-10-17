import { DomainError } from '../../core/DomainResult';

export const ROOM_MANAGEMENT_CONTRACT_VERSION: string = '1';

export enum RoomVisibility {
  Private = 'private',
  Public = 'public'
}

export enum RoomJoinRule {
  Invite = 'invite',
  Knock = 'knock',
  Public = 'public',
  Restricted = 'restricted'
}

export enum RoomMembershipState {
  Unknown = 'unknown',
  Invited = 'invited',
  Knocked = 'knocked',
  Joined = 'joined',
  Left = 'left',
  Banned = 'banned'
}

export enum RoomMemberRole {
  Member = 'member',
  Moderator = 'moderator',
  Administrator = 'administrator',
  Owner = 'owner'
}

export interface CreateRoomRequest {
  name: string;
  topic: string | null;
  avatarUrl: string | null;
  visibility: RoomVisibility;
  joinRule: RoomJoinRule;
  inviteUserIds: string[];
  parentSpaceId: string | null;
  isEncrypted: boolean;
}

export interface RoomDetailsPatch {
  name: string | null;
  topic: string | null;
  avatarUrl: string | null;
  removeAvatar: boolean;
  visibility: RoomVisibility | null;
  joinRule: RoomJoinRule | null;
}

export interface ManagedRoomDetails {
  roomId: string;
  name: string;
  topic: string | null;
  avatarUrl: string | null;
  canonicalAlias: string | null;
  visibility: RoomVisibility;
  joinRule: RoomJoinRule;
  membership: RoomMembershipState;
  isEncrypted: boolean;
  memberCount: number;
}

export interface RoomMember {
  userId: string;
  displayName: string | null;
  avatarUrl: string | null;
  membership: RoomMembershipState;
  role: RoomMemberRole;
  isCurrentUser: boolean;
}

export enum RoomManagementCommandKind {
  LoadDetails = 'load_details',
  LoadMembers = 'load_members',
  CreateRoom = 'create_room',
  JoinRoom = 'join_room',
  KnockRoom = 'knock_room',
  LeaveRoom = 'leave_room',
  ForgetRoom = 'forget_room',
  InviteUser = 'invite_user',
  UpdateDetails = 'update_details',
  SetMemberRole = 'set_member_role',
  KickMember = 'kick_member',
  BanMember = 'ban_member',
  UnbanMember = 'unban_member',
  ReportRoom = 'report_room'
}

export interface RoomManagementCommand {
  requestId: string;
  kind: RoomManagementCommandKind;
  roomId: string | null;
  aliasOrId: string | null;
  createRequest: CreateRoomRequest | null;
  detailsPatch: RoomDetailsPatch | null;
  targetUserId: string | null;
  role: RoomMemberRole | null;
  reason: string | null;
  reportScore: number | null;
}

export interface RoomManagementPayload {
  room: ManagedRoomDetails | null;
  members: RoomMember[];
  acknowledged: boolean;
}

export enum AsyncOperationPhase {
  Busy = 'busy',
  Succeeded = 'succeeded',
  Failed = 'failed',
  Cancelled = 'cancelled'
}

export interface RoomManagementOperation {
  requestId: string;
  scope: string;
  kind: RoomManagementCommandKind;
  phase: AsyncOperationPhase;
  retryable: boolean;
  error: DomainError | null;
}

export enum RoomManagementPhase {
  Empty = 'empty',
  Ready = 'ready',
  Offline = 'offline',
  Error = 'error'
}

export interface RoomManagementSnapshot {
  phase: RoomManagementPhase;
  selectedRoomId: string | null;
  room: ManagedRoomDetails | null;
  members: RoomMember[];
  operations: RoomManagementOperation[];
  error: DomainError | null;
}

export enum SearchDomain {
  Rooms = 'rooms',
  Users = 'users',
  Messages = 'messages'
}

export interface SearchRequest {
  query: string;
  domain: SearchDomain;
  roomId: string | null;
  offset: number;
  limit: number;
}

export interface RoomSearchResult {
  roomId: string;
  name: string;
  alias: string | null;
  topic: string | null;
  avatarUrl: string | null;
  memberCount: number;
  membership: RoomMembershipState;
}

export interface UserSearchResult {
  userId: string;
  displayName: string | null;
  avatarUrl: string | null;
}

export interface MessageSearchResult {
  eventId: string;
  roomId: string;
  senderId: string;
  body: string;
  timestampMs: number;
}

export interface SearchPage {
  rooms: RoomSearchResult[];
  users: UserSearchResult[];
  messages: MessageSearchResult[];
  nextOffset: number | null;
}

export enum SearchPhase {
  Idle = 'idle',
  Searching = 'searching',
  Ready = 'ready',
  Empty = 'empty',
  Offline = 'offline',
  Error = 'error'
}

export interface SearchSnapshot {
  phase: SearchPhase;
  query: string;
  domain: SearchDomain;
  roomId: string | null;
  rooms: RoomSearchResult[];
  users: UserSearchResult[];
  messages: MessageSearchResult[];
  nextOffset: number | null;
  isLoadingMore: boolean;
  error: DomainError | null;
}

export interface SpaceSummary {
  roomId: string;
  name: string;
  avatarUrl: string | null;
  childCount: number;
  isJoined: boolean;
}

export interface SpacePage {
  spaces: SpaceSummary[];
  activeSpaceId: string | null;
}

export enum SpacesPhase {
  Loading = 'loading',
  Ready = 'ready',
  Empty = 'empty',
  Switching = 'switching',
  Offline = 'offline',
  Error = 'error'
}

export interface SpacesSnapshot {
  phase: SpacesPhase;
  spaces: SpaceSummary[];
  activeSpaceId: string | null;
  pendingSpaceId: string | null;
  error: DomainError | null;
  retryable: boolean;
}
