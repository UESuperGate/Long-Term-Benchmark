export enum SpaceSurface {
  Home = 'home',
  Space = 'space',
  Leave = 'leave'
}

export enum AsyncOperationState {
  Idle = 'idle',
  Loading = 'loading',
  Success = 'success',
  Failure = 'failure'
}

export class SpaceRoom {
  roomId: string;
  name: string;
  membership: string;
  isDirect: boolean;
  isLastAdmin: boolean;

  constructor(roomId: string, name: string, membership: string, isDirect: boolean = false, isLastAdmin: boolean = false) {
    this.roomId = roomId;
    this.name = name;
    this.membership = membership;
    this.isDirect = isDirect;
    this.isLastAdmin = isLastAdmin;
  }
}

export class RoomAction {
  roomId: string;
  state: AsyncOperationState;
  attempts: number;

  constructor(roomId: string, state: AsyncOperationState, attempts: number) {
    this.roomId = roomId;
    this.state = state;
    this.attempts = attempts;
  }
}

export class SpacesGateway {
  failNextJoin: boolean = false;
  failNextLeave: boolean = false;
  lastJoinedRoomId: string = '';
  lastAcceptedInviteId: string = '';
  lastLeftRoomIds: string[] = [];

  joinRoom(roomId: string): boolean {
    if (this.failNextJoin) {
      this.failNextJoin = false;
      return false;
    }
    this.lastJoinedRoomId = roomId;
    return true;
  }

  acceptInvite(spaceId: string): boolean {
    this.lastAcceptedInviteId = spaceId;
    return true;
  }

  leaveSpace(roomIds: string[]): boolean {
    if (this.failNextLeave) {
      this.failNextLeave = false;
      return false;
    }
    this.lastLeftRoomIds = roomIds.slice();
    return true;
  }
}

export class SpacesPresenter {
  readonly gateway: SpacesGateway;
  spaces: SpaceRoom[] = [new SpaceRoom('!space', 'Product', 'joined')];
  invites: SpaceRoom[] = [new SpaceRoom('!invited', 'Community', 'invited')];
  seenInviteIds: string[] = [];
  children: SpaceRoom[] = [];
  joinActions: RoomAction[] = [];
  surface: SpaceSurface = SpaceSurface.Home;
  selectedSpaceId: string = '';
  childrenState: AsyncOperationState = AsyncOperationState.Idle;
  paginationState: AsyncOperationState = AsyncOperationState.Idle;
  hasMoreToLoad: boolean = true;
  selectedLeaveRoomIds: string[] = [];
  leaveState: AsyncOperationState = AsyncOperationState.Idle;
  leaveAttempts: number = 0;

  constructor(gateway: SpacesGateway) {
    this.gateway = gateway;
  }

  openSpace(spaceId: string): void {
    this.selectedSpaceId = spaceId;
    this.surface = SpaceSurface.Space;
    this.childrenState = AsyncOperationState.Loading;
    this.children = [
      new SpaceRoom('!a', 'Design', ''),
      new SpaceRoom('!b', 'Engineering', ''),
      new SpaceRoom('!admin', 'Operations', 'joined', false, true),
      new SpaceRoom('!dm', 'Direct message', 'joined', true, false)
    ];
    this.childrenState = AsyncOperationState.Success;
  }

  loadMore(): void {
    if (!this.hasMoreToLoad) {
      return;
    }
    this.paginationState = AsyncOperationState.Loading;
    const page: SpaceRoom[] = [new SpaceRoom('!b', 'Engineering', ''), new SpaceRoom('!c', 'Research', '')];
    page.forEach((room: SpaceRoom) => {
      if (!this.children.some((existing: SpaceRoom) => existing.roomId === room.roomId)) {
        this.children.push(room);
      }
    });
    this.hasMoreToLoad = false;
    this.paginationState = AsyncOperationState.Idle;
  }

  joinChild(roomId: string): boolean {
    const currentAction = this.actionFor(roomId);
    const attempts = currentAction === undefined ? 1 : currentAction.attempts + 1;
    this.setJoinAction(roomId, AsyncOperationState.Loading, attempts);
    const succeeded = this.gateway.joinRoom(roomId);
    if (!succeeded) {
      this.setJoinAction(roomId, AsyncOperationState.Failure, attempts);
      return false;
    }
    const room = this.children.find((child: SpaceRoom) => child.roomId === roomId);
    if (room !== undefined) {
      room.membership = 'joined';
    }
    this.removeJoinAction(roomId);
    return true;
  }

  clearJoinFailures(): void {
    this.joinActions.forEach((action: RoomAction) => {
      if (action.state === AsyncOperationState.Failure) {
        action.state = AsyncOperationState.Idle;
      }
    });
  }

  acceptInvite(spaceId: string): boolean {
    const succeeded = this.gateway.acceptInvite(spaceId);
    if (succeeded) {
      const invite = this.invites.find((item: SpaceRoom) => item.roomId === spaceId);
      if (invite !== undefined) {
        invite.membership = 'joined';
        this.spaces = this.spaces.concat(invite);
      }
      if (!this.seenInviteIds.includes(spaceId)) {
        this.seenInviteIds.push(spaceId);
      }
      this.invites = this.invites.filter((item: SpaceRoom) => item.roomId !== spaceId);
    }
    return succeeded;
  }

  openLeaveSpace(): void {
    this.surface = SpaceSurface.Leave;
    this.leaveState = AsyncOperationState.Idle;
    this.selectedLeaveRoomIds = this.leaveCandidates()
      .filter((room: SpaceRoom) => !room.isLastAdmin)
      .map((room: SpaceRoom) => room.roomId);
  }

  leaveCandidates(): SpaceRoom[] {
    return this.children.filter((room: SpaceRoom) => !room.isDirect);
  }

  deselectAllRooms(): void {
    this.selectedLeaveRoomIds = [];
  }

  selectAllRooms(): void {
    this.selectedLeaveRoomIds = this.leaveCandidates()
      .filter((room: SpaceRoom) => !room.isLastAdmin)
      .map((room: SpaceRoom) => room.roomId);
  }

  toggleRoomSelection(roomId: string): void {
    const room = this.leaveCandidates().find((candidate: SpaceRoom) => candidate.roomId === roomId);
    if (room === undefined || room.isLastAdmin) {
      return;
    }
    if (this.selectedLeaveRoomIds.includes(roomId)) {
      this.selectedLeaveRoomIds = this.selectedLeaveRoomIds.filter((selected: string) => selected !== roomId);
    } else {
      this.selectedLeaveRoomIds = this.selectedLeaveRoomIds.concat(roomId);
    }
  }

  leaveSpace(): boolean {
    this.leaveAttempts += 1;
    this.leaveState = AsyncOperationState.Loading;
    const succeeded = this.gateway.leaveSpace(this.selectedLeaveRoomIds);
    this.leaveState = succeeded ? AsyncOperationState.Success : AsyncOperationState.Failure;
    if (succeeded) {
      this.surface = SpaceSurface.Home;
      this.selectedSpaceId = '';
    }
    return succeeded;
  }

  closeLeaveError(): void {
    if (this.leaveState === AsyncOperationState.Failure) {
      this.leaveState = AsyncOperationState.Idle;
    }
  }

  actionFor(roomId: string): RoomAction | undefined {
    return this.joinActions.find((action: RoomAction) => action.roomId === roomId);
  }

  private setJoinAction(roomId: string, state: AsyncOperationState, attempts: number): void {
    const action = this.actionFor(roomId);
    if (action === undefined) {
      this.joinActions.push(new RoomAction(roomId, state, attempts));
    } else {
      action.state = state;
      action.attempts = attempts;
    }
  }

  private removeJoinAction(roomId: string): void {
    this.joinActions = this.joinActions.filter((action: RoomAction) => action.roomId !== roomId);
  }
}
