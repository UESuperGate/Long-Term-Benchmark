import {
  DomainErrorCode,
  DomainFailure,
  DomainResult,
  unexpectedFailure
} from '../../core/DomainResult';
import { ObservableState } from '../../core/ObservableState';
import {
  CreateRoomRequest,
  RoomDetailsPatch,
  RoomManagementCommand,
  RoomManagementCommandKind,
  RoomManagementPayload,
  RoomManagementSnapshot,
  RoomMemberRole
} from '../../matrix/api/RoomManagementModels';
import { RoomManagementDataSource } from '../../matrix/api/RoomManagementServices';
import { RoomManagementReducer } from './RoomManagementReducer';

function emptyCommand(requestId: string, kind: RoomManagementCommandKind): RoomManagementCommand {
  return {
    requestId: requestId,
    kind: kind,
    roomId: null,
    aliasOrId: null,
    createRequest: null,
    detailsPatch: null,
    targetUserId: null,
    role: null,
    reason: null,
    reportScore: null
  };
}

export class RoomManagementController {
  readonly state: ObservableState<RoomManagementSnapshot>;
  private readonly source: RoomManagementDataSource;
  private readonly reducer: RoomManagementReducer = new RoomManagementReducer();
  private readonly scopeGeneration: Map<string, number> = new Map<string, number>();
  private readonly busyScopes: Map<string, string> = new Map<string, string>();
  private readonly retryCommands: Map<string, RoomManagementCommand> = new Map<string, RoomManagementCommand>();
  private nextRequestId: number = 1;

  constructor(source: RoomManagementDataSource) {
    this.source = source;
    this.state = new ObservableState<RoomManagementSnapshot>(this.reducer.getSnapshot());
  }

  getSnapshot(): RoomManagementSnapshot {
    return this.reducer.getSnapshot();
  }

  loadDetails(roomId: string): Promise<DomainResult<RoomManagementSnapshot>> {
    const command = emptyCommand(this.requestId(), RoomManagementCommandKind.LoadDetails);
    command.roomId = roomId;
    return this.run(command, `details:${roomId}`, true);
  }

  loadMembers(roomId: string): Promise<DomainResult<RoomManagementSnapshot>> {
    const command = emptyCommand(this.requestId(), RoomManagementCommandKind.LoadMembers);
    command.roomId = roomId;
    return this.run(command, `members:${roomId}`, true);
  }

  createRoom(request: CreateRoomRequest): Promise<DomainResult<RoomManagementSnapshot>> {
    const command = emptyCommand(this.requestId(), RoomManagementCommandKind.CreateRoom);
    command.createRequest = request;
    return this.run(command, 'create-room', false);
  }

  join(aliasOrId: string): Promise<DomainResult<RoomManagementSnapshot>> {
    return this.membershipCommand(RoomManagementCommandKind.JoinRoom, aliasOrId);
  }

  knock(aliasOrId: string, reason: string | null): Promise<DomainResult<RoomManagementSnapshot>> {
    const command = emptyCommand(this.requestId(), RoomManagementCommandKind.KnockRoom);
    command.aliasOrId = aliasOrId;
    command.reason = reason;
    return this.run(command, `membership:${aliasOrId}`, false);
  }

  leave(roomId: string): Promise<DomainResult<RoomManagementSnapshot>> {
    return this.roomCommand(RoomManagementCommandKind.LeaveRoom, roomId, 'membership');
  }

  forget(roomId: string): Promise<DomainResult<RoomManagementSnapshot>> {
    return this.roomCommand(RoomManagementCommandKind.ForgetRoom, roomId, 'membership');
  }

  invite(roomId: string, userId: string): Promise<DomainResult<RoomManagementSnapshot>> {
    const command = emptyCommand(this.requestId(), RoomManagementCommandKind.InviteUser);
    command.roomId = roomId;
    command.targetUserId = userId;
    return this.run(command, `member:${roomId}:${userId}`, false);
  }

  updateDetails(roomId: string, patch: RoomDetailsPatch): Promise<DomainResult<RoomManagementSnapshot>> {
    const command = emptyCommand(this.requestId(), RoomManagementCommandKind.UpdateDetails);
    command.roomId = roomId;
    command.detailsPatch = patch;
    return this.run(command, `details-mutation:${roomId}`, false);
  }

  setRole(roomId: string, userId: string, role: RoomMemberRole): Promise<DomainResult<RoomManagementSnapshot>> {
    const command = emptyCommand(this.requestId(), RoomManagementCommandKind.SetMemberRole);
    command.roomId = roomId;
    command.targetUserId = userId;
    command.role = role;
    return this.run(command, `member:${roomId}:${userId}`, false);
  }

  kick(roomId: string, userId: string, reason: string | null): Promise<DomainResult<RoomManagementSnapshot>> {
    return this.moderationCommand(RoomManagementCommandKind.KickMember, roomId, userId, reason);
  }

  ban(roomId: string, userId: string, reason: string | null): Promise<DomainResult<RoomManagementSnapshot>> {
    return this.moderationCommand(RoomManagementCommandKind.BanMember, roomId, userId, reason);
  }

  unban(roomId: string, userId: string): Promise<DomainResult<RoomManagementSnapshot>> {
    return this.moderationCommand(RoomManagementCommandKind.UnbanMember, roomId, userId, null);
  }

  report(roomId: string, reason: string, score: number): Promise<DomainResult<RoomManagementSnapshot>> {
    const command = emptyCommand(this.requestId(), RoomManagementCommandKind.ReportRoom);
    command.roomId = roomId;
    command.reason = reason;
    command.reportScore = score;
    return this.run(command, `report:${roomId}`, false);
  }

  retry(requestId: string): Promise<DomainResult<RoomManagementSnapshot>> {
    const previous = this.retryCommands.get(requestId);
    if (previous === undefined) {
      return Promise.resolve(DomainResult.fail<RoomManagementSnapshot>(this.invalid('Unknown retry request')));
    }
    const command = this.copyForRetry(previous);
    return this.run(command, this.scopeFor(command), false);
  }

  private async run(
    command: RoomManagementCommand,
    scope: string,
    allowSupersede: boolean
  ): Promise<DomainResult<RoomManagementSnapshot>> {
    const validation = this.validate(command);
    if (validation !== null) {
      return DomainResult.fail<RoomManagementSnapshot>(validation);
    }
    if (!allowSupersede && this.busyScopes.has(scope)) {
      return DomainResult.fail<RoomManagementSnapshot>(new DomainFailure(
        DomainErrorCode.ServiceUnavailable,
        `Operation ${scope} is already in progress`,
        true
      ));
    }
    const generation = (this.scopeGeneration.get(scope) ?? 0) + 1;
    this.scopeGeneration.set(scope, generation);
    this.busyScopes.set(scope, command.requestId);
    this.publish(this.reducer.begin(command, scope));
    const result = await this.source.execute(command);
    if (this.scopeGeneration.get(scope) !== generation) {
      const cancelled = new DomainFailure(
        DomainErrorCode.Cancelled,
        `Operation ${scope} was superseded by a newer request`,
        true
      );
      this.publish(this.reducer.cancel(command, cancelled));
      return DomainResult.fail<RoomManagementSnapshot>(cancelled);
    }
    if (this.busyScopes.get(scope) === command.requestId) {
      this.busyScopes.delete(scope);
    }
    if (!result.success || result.value === null) {
      const error = result.error === null ? unexpectedFailure(command.kind) : result.error;
      this.retryCommands.set(command.requestId, command);
      this.publish(this.reducer.fail(command, error));
      return DomainResult.fail<RoomManagementSnapshot>(error);
    }
    this.retryCommands.delete(command.requestId);
    const snapshot = this.reducer.succeed(command, result.value);
    this.publish(snapshot);
    return DomainResult.succeed<RoomManagementSnapshot>(snapshot);
  }

  private membershipCommand(
    kind: RoomManagementCommandKind,
    aliasOrId: string
  ): Promise<DomainResult<RoomManagementSnapshot>> {
    const command = emptyCommand(this.requestId(), kind);
    command.aliasOrId = aliasOrId;
    return this.run(command, `membership:${aliasOrId}`, false);
  }

  private roomCommand(
    kind: RoomManagementCommandKind,
    roomId: string,
    scopePrefix: string
  ): Promise<DomainResult<RoomManagementSnapshot>> {
    const command = emptyCommand(this.requestId(), kind);
    command.roomId = roomId;
    return this.run(command, `${scopePrefix}:${roomId}`, false);
  }

  private moderationCommand(
    kind: RoomManagementCommandKind,
    roomId: string,
    userId: string,
    reason: string | null
  ): Promise<DomainResult<RoomManagementSnapshot>> {
    const command = emptyCommand(this.requestId(), kind);
    command.roomId = roomId;
    command.targetUserId = userId;
    command.reason = reason;
    return this.run(command, `member:${roomId}:${userId}`, false);
  }

  private validate(command: RoomManagementCommand): DomainFailure | null {
    if (command.kind === RoomManagementCommandKind.CreateRoom) {
      if (command.createRequest === null || command.createRequest.name.trim().length === 0) {
        return this.invalid('Room name must not be empty');
      }
      return null;
    }
    if (command.kind === RoomManagementCommandKind.JoinRoom || command.kind === RoomManagementCommandKind.KnockRoom) {
      return command.aliasOrId === null || command.aliasOrId.trim().length === 0 ?
        this.invalid('Room alias or id must not be empty') : null;
    }
    if (command.roomId === null || command.roomId.length === 0) {
      return this.invalid('Room id must not be empty');
    }
    if (command.kind === RoomManagementCommandKind.InviteUser ||
      command.kind === RoomManagementCommandKind.SetMemberRole ||
      command.kind === RoomManagementCommandKind.KickMember ||
      command.kind === RoomManagementCommandKind.BanMember ||
      command.kind === RoomManagementCommandKind.UnbanMember) {
      if (command.targetUserId === null || command.targetUserId.length === 0) {
        return this.invalid('Target user id must not be empty');
      }
    }
    if (command.kind === RoomManagementCommandKind.UpdateDetails && command.detailsPatch === null) {
      return this.invalid('Room details patch is required');
    }
    if (command.kind === RoomManagementCommandKind.SetMemberRole && command.role === null) {
      return this.invalid('Member role is required');
    }
    if (command.kind === RoomManagementCommandKind.ReportRoom &&
      (command.reason === null || command.reason.trim().length === 0 || command.reportScore === null ||
        command.reportScore < -100 || command.reportScore > 0)) {
      return this.invalid('A report reason and score from -100 through 0 are required');
    }
    return null;
  }

  private scopeFor(command: RoomManagementCommand): string {
    if (command.kind === RoomManagementCommandKind.CreateRoom) {
      return 'create-room';
    }
    if (command.kind === RoomManagementCommandKind.JoinRoom || command.kind === RoomManagementCommandKind.KnockRoom) {
      return `membership:${command.aliasOrId}`;
    }
    if (command.kind === RoomManagementCommandKind.LoadDetails) {
      return `details:${command.roomId}`;
    }
    if (command.kind === RoomManagementCommandKind.LoadMembers) {
      return `members:${command.roomId}`;
    }
    if (command.kind === RoomManagementCommandKind.UpdateDetails) {
      return `details-mutation:${command.roomId}`;
    }
    if (command.targetUserId !== null) {
      return `member:${command.roomId}:${command.targetUserId}`;
    }
    if (command.kind === RoomManagementCommandKind.ReportRoom) {
      return `report:${command.roomId}`;
    }
    return `membership:${command.roomId}`;
  }

  private copyForRetry(previous: RoomManagementCommand): RoomManagementCommand {
    return {
      requestId: this.requestId(),
      kind: previous.kind,
      roomId: previous.roomId,
      aliasOrId: previous.aliasOrId,
      createRequest: previous.createRequest,
      detailsPatch: previous.detailsPatch,
      targetUserId: previous.targetUserId,
      role: previous.role,
      reason: previous.reason,
      reportScore: previous.reportScore
    };
  }

  private requestId(): string {
    return `room-management-${this.nextRequestId++}`;
  }

  private invalid(message: string): DomainFailure {
    return new DomainFailure(DomainErrorCode.InvalidInput, message, false);
  }

  private publish(snapshot: RoomManagementSnapshot): void {
    this.state.setValue(snapshot);
  }
}
