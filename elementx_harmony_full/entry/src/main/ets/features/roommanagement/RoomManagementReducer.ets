import { DomainError, DomainErrorCode } from '../../core/DomainResult';
import {
  AsyncOperationPhase,
  ManagedRoomDetails,
  RoomManagementCommand,
  RoomManagementCommandKind,
  RoomManagementOperation,
  RoomManagementPayload,
  RoomManagementPhase,
  RoomManagementSnapshot,
  RoomMember
} from '../../matrix/api/RoomManagementModels';

function copyRoom(room: ManagedRoomDetails | null): ManagedRoomDetails | null {
  if (room === null) {
    return null;
  }
  return {
    roomId: room.roomId,
    name: room.name,
    topic: room.topic,
    avatarUrl: room.avatarUrl,
    canonicalAlias: room.canonicalAlias,
    visibility: room.visibility,
    joinRule: room.joinRule,
    membership: room.membership,
    isEncrypted: room.isEncrypted,
    memberCount: room.memberCount
  };
}

function copyMember(member: RoomMember): RoomMember {
  return {
    userId: member.userId,
    displayName: member.displayName,
    avatarUrl: member.avatarUrl,
    membership: member.membership,
    role: member.role,
    isCurrentUser: member.isCurrentUser
  };
}

function copyOperation(operation: RoomManagementOperation): RoomManagementOperation {
  return {
    requestId: operation.requestId,
    scope: operation.scope,
    kind: operation.kind,
    phase: operation.phase,
    retryable: operation.retryable,
    error: operation.error
  };
}

export class RoomManagementReducer {
  private snapshot: RoomManagementSnapshot = {
    phase: RoomManagementPhase.Empty,
    selectedRoomId: null,
    room: null,
    members: [],
    operations: [],
    error: null
  };

  getSnapshot(): RoomManagementSnapshot {
    return {
      phase: this.snapshot.phase,
      selectedRoomId: this.snapshot.selectedRoomId,
      room: copyRoom(this.snapshot.room),
      members: this.snapshot.members.map((member: RoomMember) => copyMember(member)),
      operations: this.snapshot.operations.map(
        (operation: RoomManagementOperation) => copyOperation(operation)
      ),
      error: this.snapshot.error
    };
  }

  begin(command: RoomManagementCommand, scope: string): RoomManagementSnapshot {
    this.removeOperation(command.requestId);
    this.snapshot.operations.push({
      requestId: command.requestId,
      scope: scope,
      kind: command.kind,
      phase: AsyncOperationPhase.Busy,
      retryable: false,
      error: null
    });
    this.snapshot.error = null;
    return this.getSnapshot();
  }

  succeed(command: RoomManagementCommand, payload: RoomManagementPayload): RoomManagementSnapshot {
    this.finishOperation(command.requestId, AsyncOperationPhase.Succeeded, null, false);
    if (payload.room !== null) {
      this.snapshot.room = copyRoom(payload.room);
      this.snapshot.selectedRoomId = payload.room.roomId;
    }
    if (command.kind === RoomManagementCommandKind.LoadMembers) {
      this.snapshot.members = payload.members.map((member: RoomMember) => copyMember(member));
      this.sortMembers();
    }
    if (command.kind === RoomManagementCommandKind.ForgetRoom && payload.acknowledged) {
      this.snapshot.room = null;
      this.snapshot.selectedRoomId = null;
      this.snapshot.members = [];
    }
    this.snapshot.phase = this.snapshot.room === null ? RoomManagementPhase.Empty : RoomManagementPhase.Ready;
    this.snapshot.error = null;
    return this.getSnapshot();
  }

  fail(command: RoomManagementCommand, error: DomainError): RoomManagementSnapshot {
    this.finishOperation(command.requestId, AsyncOperationPhase.Failed, error, error.retryable);
    this.snapshot.error = error;
    this.snapshot.phase = error.code === DomainErrorCode.NetworkUnavailable ?
      RoomManagementPhase.Offline : RoomManagementPhase.Error;
    return this.getSnapshot();
  }

  cancel(command: RoomManagementCommand, error: DomainError): RoomManagementSnapshot {
    this.finishOperation(command.requestId, AsyncOperationPhase.Cancelled, error, true);
    return this.getSnapshot();
  }

  private finishOperation(
    requestId: string,
    phase: AsyncOperationPhase,
    error: DomainError | null,
    retryable: boolean
  ): void {
    const index = this.snapshot.operations.findIndex(
      (operation: RoomManagementOperation) => operation.requestId === requestId
    );
    if (index >= 0) {
      this.snapshot.operations[index].phase = phase;
      this.snapshot.operations[index].error = error;
      this.snapshot.operations[index].retryable = retryable;
    }
  }

  private removeOperation(requestId: string): void {
    const index = this.snapshot.operations.findIndex(
      (operation: RoomManagementOperation) => operation.requestId === requestId
    );
    if (index >= 0) {
      this.snapshot.operations.splice(index, 1);
    }
  }

  private sortMembers(): void {
    this.snapshot.members.sort((left: RoomMember, right: RoomMember) => {
      if (left.isCurrentUser !== right.isCurrentUser) {
        return left.isCurrentUser ? -1 : 1;
      }
      const leftName = left.displayName === null ? left.userId : left.displayName;
      const rightName = right.displayName === null ? right.userId : right.displayName;
      return leftName.localeCompare(rightName);
    });
  }
}
