export enum NavigationState {
  Idle = 'idle',
  Success = 'success',
  Failure = 'failure',
  SameRoom = 'same_room'
}

export class SuccessorRoom {
  roomId: string;
  reason?: string;

  constructor(roomId: string, reason?: string) {
    this.roomId = roomId;
    this.reason = reason;
  }
}

export class PredecessorRoom {
  roomId: string;
  lastEventId: string;

  constructor(roomId: string, lastEventId: string) {
    this.roomId = roomId;
    this.lastEventId = lastEventId;
  }
}

export class RoomSnapshot {
  roomId: string;
  name: string;
  history: string[];
  successorRoom?: SuccessorRoom;
  predecessorRoom?: PredecessorRoom;

  constructor(roomId: string, name: string, history: string[], successorRoom?: SuccessorRoom,
    predecessorRoom?: PredecessorRoom) {
    this.roomId = roomId;
    this.name = name;
    this.history = history;
    this.successorRoom = successorRoom;
    this.predecessorRoom = predecessorRoom;
  }
}

export class RoomNavigationGateway {
  failNextNavigation: boolean = false;
  navigationCount: number = 0;
  lastOpenedRoomId: string = '';

  navigateToRoom(roomId: string): boolean {
    if (this.failNextNavigation) {
      this.failNextNavigation = false;
      return false;
    }
    this.navigationCount += 1;
    this.lastOpenedRoomId = roomId;
    return true;
  }
}

export class RoomUpgradePresenter {
  readonly gateway: RoomNavigationGateway;
  readonly oldRoom: RoomSnapshot = new RoomSnapshot(
    '!old:example.org',
    'Product planning',
    ['Earlier message'],
    new SuccessorRoom('!new:example.org')
  );
  readonly replacementRoom: RoomSnapshot = new RoomSnapshot(
    '!new:example.org',
    'Product planning v2',
    ['Welcome to the replacement room'],
    undefined,
    new PredecessorRoom('!old:example.org', '$last:example.org')
  );
  currentRoom: RoomSnapshot;
  navigationState: NavigationState = NavigationState.Idle;
  sameRoomNoticeVisible: boolean = false;

  constructor(gateway: RoomNavigationGateway) {
    this.gateway = gateway;
    this.currentRoom = this.oldRoom;
  }

  get isTombstoned(): boolean {
    return this.currentRoom.successorRoom !== undefined;
  }

  get canCompose(): boolean {
    return !this.isTombstoned;
  }

  roomListPreview(room: RoomSnapshot): string {
    return room.successorRoom !== undefined ? 'This room has been replaced' : room.history[room.history.length - 1];
  }

  selectOldRoom(): void {
    this.currentRoom = this.oldRoom;
    this.navigationState = NavigationState.Idle;
  }

  selectReplacementRoom(): void {
    this.currentRoom = this.replacementRoom;
    this.navigationState = NavigationState.Idle;
  }

  openSuccessorRoom(): void {
    const successor = this.currentRoom.successorRoom;
    if (successor !== undefined) {
      this.navigateToRoom(successor.roomId);
    }
  }

  openPredecessorRoom(): void {
    const predecessor = this.currentRoom.predecessorRoom;
    if (predecessor !== undefined) {
      this.navigateToRoom(predecessor.roomId);
    }
  }

  navigateToRoom(roomId: string): void {
    this.sameRoomNoticeVisible = false;
    if (roomId === this.currentRoom.roomId) {
      this.navigationState = NavigationState.SameRoom;
      this.sameRoomNoticeVisible = true;
      return;
    }
    const succeeded = this.gateway.navigateToRoom(roomId);
    this.navigationState = succeeded ? NavigationState.Success : NavigationState.Failure;
    if (succeeded) {
      this.currentRoom = roomId === this.replacementRoom.roomId ? this.replacementRoom : this.oldRoom;
    }
  }
}
