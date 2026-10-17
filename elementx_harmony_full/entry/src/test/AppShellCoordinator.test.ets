import {
  AppShellRuntime,
  AppShellTimelineFactory,
  AppShellTransport,
  AppShellCoordinator
} from '../main/ets/appshell/AppShellCoordinator';
import { AppShellTransportState } from '../main/ets/appshell/AppShellModels';
import { AuthenticationSource, RootNavigationPhase } from '../main/ets/appnav/RootNavigationState';
import { RootNavigationStateMachine } from '../main/ets/appnav/RootNavigationStateMachine';
import {
  DomainErrorCode,
  DomainFailure,
  DomainResult
} from '../main/ets/core/DomainResult';
import { MatrixSessionHandle } from '../main/ets/matrix/api/MatrixAuthentication';
import {
  RoomCategory,
  RoomListFilter,
  RoomListPage,
  RoomMembership,
  RoomSummary
} from '../main/ets/matrix/api/RoomModels';
import { RoomListDataSource } from '../main/ets/matrix/api/RoomListService';
import {
  LocalSendState,
  PaginationDirection,
  TextContent,
  TimelineContentKind,
  TimelineEventInput,
  TimelinePage,
  TimelineSendRequest
} from '../main/ets/matrix/api/TimelineModels';
import { TimelineDataSource } from '../main/ets/matrix/api/TimelineService';
import { RoomListController } from '../main/ets/rooms/RoomListController';
import { SessionLoginType, SessionMetadata } from '../main/ets/session/SessionModels';
import { TimelineController } from '../main/ets/timeline/TimelineController';

function check(condition: boolean, message: string): void {
  if (!condition) {
    throw new Error(message);
  }
}

function room(roomId: string, timestampMs: number): RoomSummary {
  return {
    roomId: roomId,
    displayName: roomId,
    canonicalAlias: null,
    avatarUrl: null,
    membership: RoomMembership.Joined,
    category: RoomCategory.Group,
    isFavorite: false,
    isDirect: false,
    isMarkedUnread: false,
    unreadNotificationCount: 0,
    unreadMentionCount: 0,
    activeMembersCount: 2,
    latestEventTimestampMs: timestampMs,
    latestEventPreview: null
  };
}

function text(body: string): TextContent {
  return {
    kind: TimelineContentKind.Text,
    body: body,
    formattedBody: null
  };
}

function remoteEvent(roomId: string, body: string): TimelineEventInput {
  return {
    eventId: `$${roomId}`,
    transactionId: null,
    senderId: '@alice:example.org',
    senderDisplayName: 'Alice',
    timestampMs: 10,
    order: 10,
    isOwn: false,
    content: text(body),
    relation: null
  };
}

class StaticRoomSource implements RoomListDataSource {
  private readonly rooms: RoomSummary[];

  constructor(rooms: RoomSummary[]) {
    this.rooms = rooms;
  }

  async loadInitial(pageSize: number, filter: RoomListFilter): Promise<DomainResult<RoomListPage>> {
    return DomainResult.succeed<RoomListPage>({
      rooms: this.rooms.slice(0, pageSize),
      totalCount: this.rooms.length,
      hasMore: this.rooms.length > pageSize
    });
  }

  async loadMore(offset: number, pageSize: number, filter: RoomListFilter): Promise<DomainResult<RoomListPage>> {
    return DomainResult.succeed<RoomListPage>({
      rooms: this.rooms.slice(offset, offset + pageSize),
      totalCount: this.rooms.length,
      hasMore: offset + pageSize < this.rooms.length
    });
  }

  async refresh(filter: RoomListFilter): Promise<DomainResult<RoomListPage>> {
    return this.loadInitial(this.rooms.length, filter);
  }

  async subscribeVisibleRooms(roomIds: string[]): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(true);
  }
}

class ControlledTimelineSource implements TimelineDataSource {
  readonly roomId: string;
  readonly failLoad: boolean;
  readonly failSend: boolean;

  constructor(roomId: string, failLoad: boolean = false, failSend: boolean = false) {
    this.roomId = roomId;
    this.failLoad = failLoad;
    this.failSend = failSend;
  }

  async loadInitial(roomId: string): Promise<DomainResult<TimelinePage>> {
    if (this.failLoad) {
      return DomainResult.fail<TimelinePage>(new DomainFailure(
        DomainErrorCode.NetworkUnavailable,
        'timeline offline',
        true
      ));
    }
    return DomainResult.succeed<TimelinePage>({
      events: [remoteEvent(this.roomId, `message-${this.roomId}`)],
      direction: PaginationDirection.Backwards,
      hasMore: false
    });
  }

  async paginate(roomId: string, direction: PaginationDirection): Promise<DomainResult<TimelinePage>> {
    return DomainResult.succeed<TimelinePage>({
      events: [],
      direction: direction,
      hasMore: false
    });
  }

  async send(roomId: string, request: TimelineSendRequest): Promise<DomainResult<string>> {
    if (this.failSend) {
      return DomainResult.fail<string>(new DomainFailure(
        DomainErrorCode.ServiceUnavailable,
        'send rejected',
        true
      ));
    }
    return DomainResult.succeed<string>(`$sent-${request.transactionId}`);
  }

  async retry(roomId: string, transactionId: string): Promise<DomainResult<string>> {
    return this.failSend ? DomainResult.fail<string>(new DomainFailure(
      DomainErrorCode.ServiceUnavailable,
      'retry rejected',
      true
    )) : DomainResult.succeed<string>(`$retried-${transactionId}`);
  }

  async cancel(roomId: string, transactionId: string): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(true);
  }
}

class CapturingTimelineFactory implements AppShellTimelineFactory {
  readonly controllers: Map<string, TimelineController> = new Map<string, TimelineController>();
  failRoomId: string = '';
  failSendRoomId: string = '';

  create(roomId: string, sessionHandle: MatrixSessionHandle): TimelineController | null {
    const controller = new TimelineController(
      roomId,
      new ControlledTimelineSource(roomId, roomId === this.failRoomId, roomId === this.failSendRoomId)
    );
    this.controllers.set(roomId, controller);
    return controller;
  }
}

class FixedRuntime implements AppShellRuntime {
  private transaction: number = 0;

  nowMs(): number {
    return 100;
  }

  nextTransactionId(): string {
    this.transaction += 1;
    return `txn-${this.transaction}`;
  }
}

function loggedInRoot(): RootNavigationStateMachine {
  const root = new RootNavigationStateMachine();
  const attemptId = root.beginAuthentication(AuthenticationSource.Password);
  const metadata: SessionMetadata = {
    sessionId: '@me:example.org',
    userId: '@me:example.org',
    deviceId: 'DEVICE',
    homeserverUrl: 'https://example.org',
    loginType: SessionLoginType.Password,
    loginTimestampMs: 1,
    isTokenValid: true,
    position: 1,
    lastUsageIndex: 1,
    userDisplayName: null,
    userAvatarUrl: null
  };
  root.completeAuthentication(attemptId, metadata, {
    sessionId: metadata.sessionId,
    runtimeId: 'runtime-1'
  });
  return root;
}

function createShell(factory: CapturingTimelineFactory): AppShellCoordinator {
  const transport: AppShellTransport = {
    roomList: new RoomListController(new StaticRoomSource([room('!one', 20), room('!two', 10), room('!offline', 5)])),
    timelineFactory: factory,
    currentUserId: '@me:example.org'
  };
  return new AppShellCoordinator(loggedInRoot(), null, transport, new FixedRuntime());
}

async function testSelectionAndStaleTimelineIsolation(): Promise<void> {
  const factory = new CapturingTimelineFactory();
  const shell = createShell(factory);
  await shell.start();
  check((await shell.selectRoom('!one')).success, 'first room should open');
  check((await shell.selectRoom('!two')).success, 'second room should open');
  const oldTimeline = factory.controllers.get('!one');
  check(oldTimeline !== undefined, 'first controller should be captured');
  if (oldTimeline !== undefined) {
    oldTimeline.receive([remoteEvent('!one-late', 'late callback')]);
  }
  check(shell.getState().activeRoomId === '!two', 'late callback must not restore the previous room');
  check(shell.getState().timeline?.roomId === '!two', 'late callback must not replace the current timeline');
}

async function testUnknownRoomAndTimelineErrorRemainExplicit(): Promise<void> {
  const factory = new CapturingTimelineFactory();
  factory.failRoomId = '!offline';
  const shell = createShell(factory);
  await shell.start();
  const missing = await shell.selectRoom('!missing');
  check(!missing.success && missing.error?.code === DomainErrorCode.InvalidInput,
    'unknown room selection must fail');
  const offline = await shell.selectRoom('!offline');
  check(!offline.success, 'timeline load failure must propagate');
  check(shell.getState().timeline?.items.length === 0, 'failed timeline must not invent events');
  check(shell.getState().timeline?.error?.code === DomainErrorCode.NetworkUnavailable,
    'timeline state must retain the typed transport error');
}

async function testSendFailurePreservesDraftAndQueue(): Promise<void> {
  const factory = new CapturingTimelineFactory();
  factory.failSendRoomId = '!two';
  const shell = createShell(factory);
  await shell.start();
  await shell.selectRoom('!two');
  shell.setComposerDraft('  hello  ');
  const sent = await shell.sendMessage();
  check(!sent.success, 'send failure must propagate');
  check(shell.getState().composer.draft === '  hello  ', 'failed send must preserve the draft');
  check(shell.getState().timeline?.sendQueue.length === 1, 'failed send must remain in the queue');
  check(shell.getState().timeline?.sendQueue[0].state === LocalSendState.Failed,
    'failed queue entry must remain retryable');
}

function testAuthenticationStaleCompletionIsIgnored(): void {
  const root = new RootNavigationStateMachine();
  const shell = new AppShellCoordinator(root, null, null, new FixedRuntime());
  const staleAttempt = root.beginAuthentication(AuthenticationSource.Password);
  const activeAttempt = root.beginAuthentication(AuthenticationSource.Password);
  const accepted = root.completeAuthentication(staleAttempt, {
    sessionId: '@stale:example.org',
    userId: '@stale:example.org',
    deviceId: 'OLD',
    homeserverUrl: 'https://example.org',
    loginType: SessionLoginType.Password,
    loginTimestampMs: 1,
    isTokenValid: true,
    position: 1,
    lastUsageIndex: 1,
    userDisplayName: null,
    userAvatarUrl: null
  }, {
    sessionId: '@stale:example.org',
    runtimeId: 'old-runtime'
  });
  check(!accepted, 'stale authentication completion must be rejected');
  check(shell.getState().root.phase === RootNavigationPhase.Authenticating,
    'shell must retain the active authentication attempt');
  check(shell.getState().root.attemptId === activeAttempt, 'shell must expose the newest attempt');
}

async function testMissingTransportFailsClosed(): Promise<void> {
  const shell = new AppShellCoordinator(loggedInRoot(), null, null, new FixedRuntime());
  await shell.start();
  check(shell.getState().transportState === AppShellTransportState.Unavailable,
    'missing composition must be visible');
  shell.setComposerDraft('hello');
  const result = await shell.sendMessage();
  check(!result.success && result.error?.code === DomainErrorCode.NativeBridgeUnavailable,
    'missing transport must never report a fake send success');
}

export async function runAppShellCoordinatorTests(): Promise<string[]> {
  const passed: string[] = [];
  await testSelectionAndStaleTimelineIsolation();
  passed.push('room selection and stale timeline isolation');
  await testUnknownRoomAndTimelineErrorRemainExplicit();
  passed.push('selection and timeline errors remain explicit');
  await testSendFailurePreservesDraftAndQueue();
  passed.push('send failure preserves draft and queue');
  testAuthenticationStaleCompletionIsIgnored();
  passed.push('stale authentication completion is ignored');
  await testMissingTransportFailsClosed();
  passed.push('missing transport fails closed');
  return passed;
}
