import { DomainError } from '../../core/DomainResult';

export const CALL_CONTRACT_VERSION: string = '1';

export enum RoomCallPhase {
  Loading = 'loading',
  Unavailable = 'unavailable',
  StandBy = 'stand_by',
  Ongoing = 'ongoing',
  Offline = 'offline',
  Error = 'error'
}

export enum CallActionState {
  Idle = 'idle',
  Joining = 'joining',
  Joined = 'joined',
  Declining = 'declining',
  Declined = 'declined',
  Failed = 'failed'
}

export interface CallParticipant {
  sessionId: string;
  userId: string;
  deviceId: string;
  displayName: string | null;
  avatarUrl: string | null;
  joinedAtMs: number;
}

export interface RoomCallInput {
  roomId: string;
  callId: string | null;
  available: boolean;
  hasActiveCall: boolean;
  canCall: boolean;
  isDirectMessage: boolean;
  isAudioCall: boolean;
  currentSessionId: string;
  localCallRoomId: string | null;
  participants: CallParticipant[];
}

export interface RoomCallSnapshot {
  roomId: string;
  callId: string | null;
  phase: RoomCallPhase;
  action: CallActionState;
  participants: CallParticipant[];
  canStartCall: boolean;
  canJoinCall: boolean;
  isDirectMessage: boolean;
  isAudioCall: boolean;
  isUserInCall: boolean;
  isUserLocallyInCall: boolean;
  error: DomainError | null;
}
