import {
  DomainError,
  DomainErrorCode,
  DomainFailure,
  DomainResult,
  unexpectedFailure
} from '../../core/DomainResult';
import {
  CallActionState,
  CallParticipant,
  RoomCallInput,
  RoomCallPhase,
  RoomCallSnapshot
} from '../../matrix/api/CallModels';
import { RoomCallDataSource } from '../../matrix/api/CallService';

export class ActiveCallController {
  private readonly roomId: string;
  private readonly source: RoomCallDataSource;
  private currentSessionId: string = '';
  private snapshot: RoomCallSnapshot;

  constructor(roomId: string, source: RoomCallDataSource) {
    this.roomId = roomId;
    this.source = source;
    this.snapshot = {
      roomId: roomId,
      callId: null,
      phase: RoomCallPhase.Loading,
      action: CallActionState.Idle,
      participants: [],
      canStartCall: false,
      canJoinCall: false,
      isDirectMessage: false,
      isAudioCall: false,
      isUserInCall: false,
      isUserLocallyInCall: false,
      error: null
    };
  }

  getSnapshot(): RoomCallSnapshot {
    return {
      roomId: this.snapshot.roomId,
      callId: this.snapshot.callId,
      phase: this.snapshot.phase,
      action: this.snapshot.action,
      participants: this.snapshot.participants.slice(),
      canStartCall: this.snapshot.canStartCall,
      canJoinCall: this.snapshot.canJoinCall,
      isDirectMessage: this.snapshot.isDirectMessage,
      isAudioCall: this.snapshot.isAudioCall,
      isUserInCall: this.snapshot.isUserInCall,
      isUserLocallyInCall: this.snapshot.isUserLocallyInCall,
      error: this.snapshot.error
    };
  }

  async start(): Promise<DomainResult<RoomCallSnapshot>> {
    this.snapshot.phase = RoomCallPhase.Loading;
    const result = await this.source.load(this.roomId);
    if (!result.success || result.value === null) {
      return this.fail(result.error, 'call state load');
    }
    return this.receive(result.value);
  }

  receive(input: RoomCallInput): DomainResult<RoomCallSnapshot> {
    if (input.roomId !== this.roomId) {
      return DomainResult.fail<RoomCallSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Call update belongs to another room',
        false
      ));
    }
    this.currentSessionId = input.currentSessionId;
    this.snapshot.callId = input.callId;
    this.snapshot.participants = this.uniqueParticipants(input.participants);
    this.snapshot.isDirectMessage = input.isDirectMessage;
    this.snapshot.isAudioCall = input.isAudioCall;
    this.snapshot.isUserInCall = this.snapshot.participants.some((participant: CallParticipant) =>
      participant.sessionId === input.currentSessionId);
    this.snapshot.isUserLocallyInCall = input.localCallRoomId === this.roomId;
    this.snapshot.canStartCall = input.available && !input.hasActiveCall && input.canCall;
    this.snapshot.canJoinCall = input.available && input.hasActiveCall && input.canCall &&
      (input.localCallRoomId === null || input.localCallRoomId === this.roomId);
    this.snapshot.phase = !input.available ? RoomCallPhase.Unavailable :
      input.hasActiveCall ? RoomCallPhase.Ongoing : RoomCallPhase.StandBy;
    if (this.snapshot.action !== CallActionState.Joining && this.snapshot.action !== CallActionState.Declining) {
      this.snapshot.action = this.snapshot.isUserLocallyInCall ? CallActionState.Joined : CallActionState.Idle;
    }
    this.snapshot.error = null;
    return DomainResult.succeed<RoomCallSnapshot>(this.getSnapshot());
  }

  async join(): Promise<DomainResult<RoomCallSnapshot>> {
    if (!this.snapshot.canJoinCall || this.snapshot.callId === null) {
      return DomainResult.fail<RoomCallSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Call join action is not allowed',
        true
      ));
    }
    const callId = this.snapshot.callId;
    this.snapshot.action = CallActionState.Joining;
    this.snapshot.error = null;
    const result = await this.source.join(this.roomId, callId);
    if (this.snapshot.callId !== callId || this.snapshot.phase !== RoomCallPhase.Ongoing) {
      return DomainResult.fail<RoomCallSnapshot>(new DomainFailure(
        DomainErrorCode.Cancelled,
        'Stale call join result was ignored',
        false
      ));
    }
    if (!result.success || result.value !== true) {
      return this.failAction(result.error, 'call join');
    }
    this.snapshot.action = CallActionState.Joined;
    this.snapshot.isUserLocallyInCall = true;
    this.snapshot.error = null;
    return DomainResult.succeed<RoomCallSnapshot>(this.getSnapshot());
  }

  async decline(): Promise<DomainResult<RoomCallSnapshot>> {
    if (this.snapshot.phase !== RoomCallPhase.Ongoing || this.snapshot.callId === null ||
      this.snapshot.isUserLocallyInCall) {
      return DomainResult.fail<RoomCallSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Call decline action is not allowed',
        true
      ));
    }
    const callId = this.snapshot.callId;
    this.snapshot.action = CallActionState.Declining;
    const result = await this.source.decline(this.roomId, callId);
    if (this.snapshot.callId !== callId) {
      return DomainResult.fail<RoomCallSnapshot>(new DomainFailure(
        DomainErrorCode.Cancelled,
        'Stale call decline result was ignored',
        false
      ));
    }
    if (!result.success || result.value !== true) {
      return this.failAction(result.error, 'call decline');
    }
    this.snapshot.action = CallActionState.Declined;
    this.snapshot.error = null;
    return DomainResult.succeed<RoomCallSnapshot>(this.getSnapshot());
  }

  private uniqueParticipants(participants: CallParticipant[]): CallParticipant[] {
    const unique: CallParticipant[] = [];
    participants.forEach((participant: CallParticipant) => {
      const index = unique.findIndex((candidate: CallParticipant) =>
        candidate.userId === participant.userId && candidate.deviceId === participant.deviceId);
      if (index >= 0) {
        unique[index] = participant;
      } else {
        unique.push(participant);
      }
    });
    return unique.sort((left: CallParticipant, right: CallParticipant) => left.joinedAtMs - right.joinedAtMs);
  }

  private failAction(error: DomainError | null, operation: string): DomainResult<RoomCallSnapshot> {
    const failure = error === null ? unexpectedFailure(operation) : error;
    this.snapshot.action = CallActionState.Failed;
    this.snapshot.error = failure;
    return DomainResult.fail<RoomCallSnapshot>(failure);
  }

  private fail(error: DomainError | null, operation: string): DomainResult<RoomCallSnapshot> {
    const failure = error === null ? unexpectedFailure(operation) : error;
    this.snapshot.phase = failure.code === DomainErrorCode.NetworkUnavailable ?
      RoomCallPhase.Offline : RoomCallPhase.Error;
    this.snapshot.error = failure;
    return DomainResult.fail<RoomCallSnapshot>(failure);
  }
}
