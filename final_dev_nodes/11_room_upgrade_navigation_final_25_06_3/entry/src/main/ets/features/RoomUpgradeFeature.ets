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

export interface RoomInfoSource {
  requestRoomInfo(roomId: string): Promise<RoomSnapshot | undefined>;
}

export class DemoRoomInfoSource implements RoomInfoSource {
  async requestRoomInfo(roomId: string): Promise<RoomSnapshot | undefined> {
    if (roomId === '!old:example.org') {
      return new RoomSnapshot(roomId, 'Product planning', ['Earlier message'], new SuccessorRoom('!new:example.org'));
    }
    if (roomId === '!new:example.org') {
      return new RoomSnapshot(roomId, 'Product planning v2', ['Welcome to the replacement room'], undefined,
        new PredecessorRoom('!old:example.org', '$last:example.org'));
    }
    return undefined;
  }
}

export class RoomNavigationGateway {
  private roomInfoSource?: RoomInfoSource;

  constructor(roomInfoSource?: RoomInfoSource) {
    this.roomInfoSource = roomInfoSource;
  }

  async requestRoomInfo(roomId: string): Promise<RoomSnapshot | undefined> {
    return this.roomInfoSource?.requestRoomInfo(roomId);
  }

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
    ['Earlier message']
  );
  readonly replacementRoom: RoomSnapshot = new RoomSnapshot(
    '!new:example.org',
    'Product planning v2',
    ['Welcome to the replacement room']
  );
  currentRoom: RoomSnapshot;
  navigationState: NavigationState = NavigationState.Idle;
  sameRoomNoticeVisible: boolean = false;
  private rooms: Map<string, RoomSnapshot> = new Map();
  private roomInfoGenerations: Map<string, number> = new Map();

  constructor(gateway: RoomNavigationGateway) {
    this.gateway = gateway;
    this.currentRoom = this.oldRoom;
    this.rooms.set(this.oldRoom.roomId, this.oldRoom);
    this.rooms.set(this.replacementRoom.roomId, this.replacementRoom);
  }

  async observeTimelineRoomInfo(roomId: string = this.currentRoom.roomId): Promise<void> {
    const generation = (this.roomInfoGenerations.get(roomId) ?? 0) + 1;
    this.roomInfoGenerations.set(roomId, generation);
    const info = await this.gateway.requestRoomInfo(roomId);
    if (info === undefined || info.roomId !== roomId || this.roomInfoGenerations.get(roomId) !== generation) return;
    let room = this.rooms.get(roomId);
    if (room === undefined) {
      room = new RoomSnapshot(roomId, info.name, []);
      this.rooms.set(roomId, room);
    }
    room.name = info.name;
    room.history = info.history.slice();
    room.successorRoom = info.successorRoom === undefined ? undefined :
      new SuccessorRoom(info.successorRoom.roomId, info.successorRoom.reason);
    room.predecessorRoom = info.predecessorRoom === undefined ? undefined :
      new PredecessorRoom(info.predecessorRoom.roomId, info.predecessorRoom.lastEventId);
  }

  selectRoom(roomId: string): boolean {
    const room = this.rooms.get(roomId);
    if (room === undefined) return false;
    this.currentRoom = room;
    this.navigationState = NavigationState.Idle;
    return true;
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
    this.selectRoom(this.oldRoom.roomId);
  }

  selectReplacementRoom(): void {
    this.selectRoom(this.replacementRoom.roomId);
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
      const room = this.rooms.get(roomId);
      // Navigation may target a room whose data has not arrived yet.
      if (room !== undefined) this.currentRoom = room;
    }
  }
}
