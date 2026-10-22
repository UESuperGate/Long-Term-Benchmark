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

export class SpaceChildrenPage {
  children: SpaceRoom[];
  nextCursor: string | undefined;

  constructor(children: SpaceRoom[], nextCursor: string | undefined = undefined) {
    this.children = children;
    this.nextCursor = nextCursor;
  }
}

export interface SpaceChildrenSource {
  loadChildren(spaceId: string, cursor?: string): Promise<SpaceChildrenPage>;
}

export interface SpaceJoinSource {
  joinRoom(roomId: string): Promise<boolean>;
}

export class SpacesGateway {
  private childrenSource?: SpaceChildrenSource;
  private joinSource?: SpaceJoinSource;

  constructor(childrenSource?: SpaceChildrenSource, joinSource?: SpaceJoinSource) {
    this.childrenSource = childrenSource;
    this.joinSource = joinSource;
  }

  async loadChildren(spaceId: string, cursor?: string): Promise<SpaceChildrenPage> {
    if (this.childrenSource !== undefined) {
      return this.childrenSource.loadChildren(spaceId, cursor);
    }
    // Standalone sample data; a session supplies the hierarchy source above.
    return cursor === undefined ? new SpaceChildrenPage([
      new SpaceRoom('!a', 'Design', ''),
      new SpaceRoom('!b', 'Engineering', ''),
      new SpaceRoom('!admin', 'Operations', 'joined', false, true),
      new SpaceRoom('!dm', 'Direct message', 'joined', true, false)
    ], 'next') : new SpaceChildrenPage([
      new SpaceRoom('!b', 'Engineering', ''), new SpaceRoom('!c', 'Research', '')
    ]);
  }

  failNextJoin: boolean = false;
  failNextLeave: boolean = false;
  lastJoinedRoomId: string = '';
  lastAcceptedInviteId: string = '';
  lastLeftRoomIds: string[] = [];

  async joinRoom(roomId: string): Promise<boolean> {
    if (this.failNextJoin) {
      this.failNextJoin = false;
      return false;
    }
    if (this.joinSource !== undefined) {
      const joined = await this.joinSource.joinRoom(roomId);
      if (!joined) return false;
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
  private childrenGeneration: number = 0;
  private nextCursor: string | undefined = undefined;

  constructor(gateway: SpacesGateway) {
    this.gateway = gateway;
  }

  async openSpace(spaceId: string): Promise<void> {
    const generation = ++this.childrenGeneration;
    this.selectedSpaceId = spaceId;
    this.surface = SpaceSurface.Space;
    this.childrenState = AsyncOperationState.Loading;
    this.children = [];
    this.nextCursor = undefined;
    this.hasMoreToLoad = true;
    this.paginationState = AsyncOperationState.Idle;
    try {
      const page = await this.gateway.loadChildren(spaceId);
      if (generation !== this.childrenGeneration) return;
      this.mergeChildren(page);
      this.childrenState = AsyncOperationState.Success;
    } catch {
      if (generation === this.childrenGeneration) this.childrenState = AsyncOperationState.Failure;
    }
  }

  async loadMore(): Promise<void> {
    if (!this.hasMoreToLoad || this.childrenState !== AsyncOperationState.Success ||
      this.paginationState === AsyncOperationState.Loading) {
      return;
    }
    const generation = this.childrenGeneration;
    this.paginationState = AsyncOperationState.Loading;
    try {
      const page = await this.gateway.loadChildren(this.selectedSpaceId, this.nextCursor);
      if (generation !== this.childrenGeneration) return;
      this.mergeChildren(page);
      this.paginationState = AsyncOperationState.Idle;
    } catch {
      if (generation === this.childrenGeneration) this.paginationState = AsyncOperationState.Failure;
    }
  }

  private mergeChildren(page: SpaceChildrenPage): void {
    page.children.forEach((room: SpaceRoom) => {
      if (!this.children.some((existing: SpaceRoom) => existing.roomId === room.roomId)) {
        this.children.push(room);
      }
    });
    this.nextCursor = page.nextCursor;
    this.hasMoreToLoad = page.nextCursor !== undefined;
  }

  async joinChild(roomId: string): Promise<boolean> {
    const currentAction = this.actionFor(roomId);
    const attempts = currentAction === undefined ? 1 : currentAction.attempts + 1;
    this.setJoinAction(roomId, AsyncOperationState.Loading, attempts);
    const succeeded = await this.gateway.joinRoom(roomId);
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
      this.seenInviteIds = this.seenInviteIds.filter((id: string) => id !== spaceId);
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
