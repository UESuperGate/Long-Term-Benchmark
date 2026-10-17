import {
  DomainError,
  DomainErrorCode,
  DomainFailure,
  DomainResult
} from '../core/DomainResult';
import { StateObserver } from '../core/ObservableState';
import {
  RootNavigationPhase,
  RootNavigationState
} from '../appnav/RootNavigationState';
import { RootNavigationStateMachine } from '../appnav/RootNavigationStateMachine';
import {
  PasswordLoginCoordinator,
  PasswordLoginInput
} from '../features/login/PasswordLoginCoordinator';
import { MatrixSessionHandle } from '../matrix/api/MatrixAuthentication';
import {
  RoomListFilter,
  RoomListObserver,
  RoomListSnapshot
} from '../matrix/api/RoomModels';
import { RoomListSubscription } from '../matrix/api/RoomListService';
import {
  TextContent,
  TimelineContentKind,
  TimelineObserver,
  TimelineSendRequest,
  TimelineSnapshot
} from '../matrix/api/TimelineModels';
import { TimelineSubscription } from '../matrix/api/TimelineService';
import { RoomListController } from '../rooms/RoomListController';
import { TimelineController } from '../timeline/TimelineController';
import {
  AppShellState,
  AppShellStateObserver,
  AppShellTransportState,
  ComposerState
} from './AppShellModels';

export interface AppShellTimelineFactory {
  create(roomId: string, sessionHandle: MatrixSessionHandle): TimelineController | null;
}

/** A ready transport must be backed by the production Matrix bridge. */
export interface AppShellTransport {
  roomList: RoomListController;
  timelineFactory: AppShellTimelineFactory;
  currentUserId: string;
}

export interface AppShellRuntime {
  nowMs(): number;
  nextTransactionId(): string;
}

export class DefaultAppShellRuntime implements AppShellRuntime {
  private sequence: number = 0;

  nowMs(): number {
    return Date.now();
  }

  nextTransactionId(): string {
    this.sequence += 1;
    return `ohos-${Date.now()}-${this.sequence}`;
  }
}

class RootObserver implements StateObserver<RootNavigationState> {
  private readonly callback: (state: RootNavigationState) => void;

  constructor(callback: (state: RootNavigationState) => void) {
    this.callback = callback;
  }

  onStateChanged(state: RootNavigationState): void {
    this.callback(state);
  }
}

class RoomsObserver implements RoomListObserver {
  private readonly callback: (state: RoomListSnapshot) => void;

  constructor(callback: (state: RoomListSnapshot) => void) {
    this.callback = callback;
  }

  onRoomListChanged(snapshot: RoomListSnapshot): void {
    this.callback(snapshot);
  }
}

class ShellTimelineObserver implements TimelineObserver {
  private readonly generation: number;
  private readonly callback: (generation: number, state: TimelineSnapshot) => void;

  constructor(generation: number, callback: (generation: number, state: TimelineSnapshot) => void) {
    this.generation = generation;
    this.callback = callback;
  }

  onTimelineChanged(snapshot: TimelineSnapshot): void {
    this.callback(this.generation, snapshot);
  }
}

/**
 * Production shell orchestration. It never creates domain data and cannot turn
 * a missing Matrix transport into a successful login, room load, or send.
 */
export class AppShellCoordinator {
  private readonly rootNavigation: RootNavigationStateMachine;
  private readonly passwordLogin: PasswordLoginCoordinator | null;
  private readonly transport: AppShellTransport | null;
  private readonly runtime: AppShellRuntime;
  private readonly unavailableMessage: string;
  private state: AppShellState;
  private readonly observers: Map<number, AppShellStateObserver> = new Map<number, AppShellStateObserver>();
  private nextObserverId: number = 1;
  private started: boolean = false;
  private rootObserverId: number = 0;
  private roomSubscription: RoomListSubscription | null = null;
  private timelineSubscription: TimelineSubscription | null = null;
  private timelineController: TimelineController | null = null;
  private timelineGeneration: number = 0;
  private activeSessionId: string = '';

  constructor(
    rootNavigation: RootNavigationStateMachine,
    passwordLogin: PasswordLoginCoordinator | null,
    transport: AppShellTransport | null,
    runtime: AppShellRuntime = new DefaultAppShellRuntime(),
    unavailableMessage: string = 'Matrix transport is unavailable'
  ) {
    this.rootNavigation = rootNavigation;
    this.passwordLogin = passwordLogin;
    this.transport = transport;
    this.runtime = runtime;
    this.unavailableMessage = unavailableMessage;
    const transportState = transport === null ? AppShellTransportState.Unavailable : AppShellTransportState.Ready;
    this.state = new AppShellState(
      rootNavigation.getState(),
      transportState,
      transport === null ? unavailableMessage : '',
      null,
      null,
      null,
      new ComposerState(),
      null
    );
    this.rootObserverId = this.rootNavigation.subscribe(new RootObserver((root: RootNavigationState) => {
      this.handleRootState(root);
    }));
  }

  static unavailable(message: string = 'Production composition is not installed'): AppShellCoordinator {
    return new AppShellCoordinator(new RootNavigationStateMachine(), null, null, new DefaultAppShellRuntime(), message);
  }

  getState(): AppShellState {
    return this.state;
  }

  subscribe(observer: AppShellStateObserver): number {
    const id = this.nextObserverId++;
    this.observers.set(id, observer);
    observer.onAppShellStateChanged(this.state);
    return id;
  }

  unsubscribe(observerId: number): void {
    this.observers.delete(observerId);
  }

  async start(): Promise<void> {
    if (this.started) {
      return;
    }
    this.started = true;
    await this.activateRoot(this.rootNavigation.getState());
  }

  dispose(): void {
    this.started = false;
    this.rootNavigation.unsubscribe(this.rootObserverId);
    this.closeRoomSubscription();
    this.closeTimeline();
    this.observers.clear();
  }

  async login(input: PasswordLoginInput): Promise<DomainResult<boolean>> {
    if (this.passwordLogin === null) {
      return this.failUnavailable<boolean>('Password login transport is unavailable');
    }
    await this.passwordLogin.submit(input);
    const root = this.rootNavigation.getState();
    if (root.phase === RootNavigationPhase.LoggedIn) {
      return DomainResult.succeed<boolean>(true);
    }
    const error = root.error === null ? this.unavailable('Password login did not create a session') : root.error;
    return DomainResult.fail<boolean>(error);
  }

  async setRoomFilter(filter: RoomListFilter): Promise<DomainResult<RoomListSnapshot>> {
    if (!this.isLoggedIn() || this.transport === null) {
      return this.failUnavailable<RoomListSnapshot>('Room filtering requires an active Matrix session');
    }
    this.closeTimeline();
    this.replaceState(this.state.root, null, null, null, new ComposerState(), null);
    const result = await this.transport.roomList.updateFilter(filter);
    this.captureFailure(result.error);
    return result;
  }

  async refreshRooms(): Promise<DomainResult<RoomListSnapshot>> {
    if (!this.isLoggedIn() || this.transport === null) {
      return this.failUnavailable<RoomListSnapshot>('Room refresh requires an active Matrix session');
    }
    const result = await this.transport.roomList.refresh();
    this.captureFailure(result.error);
    return result;
  }

  async selectRoom(roomId: string): Promise<DomainResult<TimelineSnapshot>> {
    if (!this.isLoggedIn() || this.transport === null || this.state.root.sessionHandle === null) {
      return this.failUnavailable<TimelineSnapshot>('Opening a room requires an active Matrix transport');
    }
    const selected = this.transport.roomList.selectRoom(roomId);
    if (!selected.success) {
      this.captureFailure(selected.error);
      return DomainResult.fail<TimelineSnapshot>(selected.error === null ?
        this.unavailable('Room selection failed') : selected.error);
    }

    this.closeTimeline();
    const generation = this.timelineGeneration;
    const timeline = this.transport.timelineFactory.create(roomId, this.state.root.sessionHandle);
    if (timeline === null) {
      return this.failUnavailable<TimelineSnapshot>('Timeline transport is unavailable for this room');
    }
    this.timelineController = timeline;
    this.timelineSubscription = timeline.subscribe(new ShellTimelineObserver(
      generation,
      (observedGeneration: number, snapshot: TimelineSnapshot) => {
        this.acceptTimeline(observedGeneration, snapshot);
      }
    ));
    this.replaceState(
      this.state.root,
      this.transport.roomList.getSnapshot(),
      timeline.getSnapshot(),
      roomId,
      new ComposerState(),
      null
    );
    const result = await timeline.start();
    if (generation !== this.timelineGeneration) {
      return DomainResult.fail<TimelineSnapshot>(new DomainFailure(
        DomainErrorCode.Cancelled,
        'Timeline request was superseded by a newer room selection',
        true
      ));
    }
    this.captureFailure(result.error);
    return result;
  }

  setComposerDraft(draft: string): void {
    this.replaceState(
      this.state.root,
      this.state.roomList,
      this.state.timeline,
      this.state.activeRoomId,
      new ComposerState(draft, false, null),
      this.state.operationError
    );
  }

  async sendMessage(): Promise<DomainResult<TimelineSnapshot>> {
    const body = this.state.composer.draft.trim();
    if (body.length === 0) {
      return this.failComposer(new DomainFailure(DomainErrorCode.InvalidInput, 'Message is empty', false));
    }
    if (!this.isLoggedIn() || this.transport === null || this.timelineController === null) {
      return this.failComposer(this.unavailable('Message sending requires an active room transport'));
    }
    const content: TextContent = {
      kind: TimelineContentKind.Text,
      body: body,
      formattedBody: null
    };
    const request: TimelineSendRequest = {
      transactionId: this.runtime.nextTransactionId(),
      content: content,
      replyToEventId: null
    };
    this.replaceState(
      this.state.root,
      this.state.roomList,
      this.state.timeline,
      this.state.activeRoomId,
      new ComposerState(this.state.composer.draft, true, null),
      null
    );
    const generation = this.timelineGeneration;
    const result = await this.timelineController.send(request, this.transport.currentUserId, this.runtime.nowMs());
    if (generation !== this.timelineGeneration) {
      return DomainResult.fail<TimelineSnapshot>(new DomainFailure(
        DomainErrorCode.Cancelled,
        'Message send completed after the room changed',
        true
      ));
    }
    if (!result.success) {
      const error = result.error === null ? this.unavailable('Message send failed') : result.error;
      this.replaceState(
        this.state.root,
        this.state.roomList,
        this.timelineController.getSnapshot(),
        this.state.activeRoomId,
        new ComposerState(this.state.composer.draft, false, error),
        error
      );
      return DomainResult.fail<TimelineSnapshot>(error);
    }
    this.replaceState(
      this.state.root,
      this.state.roomList,
      this.timelineController.getSnapshot(),
      this.state.activeRoomId,
      new ComposerState(),
      null
    );
    return result;
  }

  private handleRootState(root: RootNavigationState): void {
    this.replaceState(
      root,
      root.phase === RootNavigationPhase.LoggedIn ? this.state.roomList : null,
      root.phase === RootNavigationPhase.LoggedIn ? this.state.timeline : null,
      root.phase === RootNavigationPhase.LoggedIn ? this.state.activeRoomId : null,
      root.phase === RootNavigationPhase.LoggedIn ? this.state.composer : new ComposerState(),
      root.error
    );
    if (this.started) {
      this.activateRoot(root);
    }
  }

  private async activateRoot(root: RootNavigationState): Promise<void> {
    if (root.phase !== RootNavigationPhase.LoggedIn || root.session === null) {
      this.activeSessionId = '';
      this.closeRoomSubscription();
      this.closeTimeline();
      return;
    }
    if (this.transport === null) {
      this.captureFailure(this.unavailable('Matrix transport is unavailable for the authenticated session'));
      return;
    }
    if (this.activeSessionId === root.session.sessionId && this.roomSubscription !== null) {
      return;
    }
    this.activeSessionId = root.session.sessionId;
    this.closeRoomSubscription();
    this.closeTimeline();
    this.roomSubscription = this.transport.roomList.subscribe(new RoomsObserver((snapshot: RoomListSnapshot) => {
      if (this.isLoggedIn()) {
        this.replaceState(
          this.state.root,
          snapshot,
          this.state.timeline,
          this.state.activeRoomId,
          this.state.composer,
          this.state.operationError
        );
      }
    }));
    const result = await this.transport.roomList.start();
    this.captureFailure(result.error);
  }

  private acceptTimeline(generation: number, snapshot: TimelineSnapshot): void {
    if (generation !== this.timelineGeneration || snapshot.roomId !== this.state.activeRoomId) {
      return;
    }
    this.replaceState(
      this.state.root,
      this.state.roomList,
      snapshot,
      this.state.activeRoomId,
      this.state.composer,
      this.state.operationError
    );
  }

  private closeRoomSubscription(): void {
    if (this.roomSubscription !== null) {
      this.roomSubscription.close();
      this.roomSubscription = null;
    }
  }

  private closeTimeline(): void {
    this.timelineGeneration += 1;
    if (this.timelineSubscription !== null) {
      this.timelineSubscription.close();
      this.timelineSubscription = null;
    }
    this.timelineController = null;
  }

  private isLoggedIn(): boolean {
    return this.state.root.phase === RootNavigationPhase.LoggedIn;
  }

  private captureFailure(error: DomainError | null): void {
    if (error !== null) {
      this.replaceState(
        this.state.root,
        this.state.roomList,
        this.state.timeline,
        this.state.activeRoomId,
        this.state.composer,
        error
      );
    }
  }

  private failUnavailable<T>(message: string): DomainResult<T> {
    const error = this.unavailable(message);
    this.captureFailure(error);
    return DomainResult.fail<T>(error);
  }

  private failComposer(error: DomainError): DomainResult<TimelineSnapshot> {
    this.replaceState(
      this.state.root,
      this.state.roomList,
      this.state.timeline,
      this.state.activeRoomId,
      new ComposerState(this.state.composer.draft, false, error),
      error
    );
    return DomainResult.fail<TimelineSnapshot>(error);
  }

  private unavailable(message: string): DomainFailure {
    return new DomainFailure(DomainErrorCode.NativeBridgeUnavailable, message, true);
  }

  private replaceState(
    root: RootNavigationState,
    roomList: RoomListSnapshot | null,
    timeline: TimelineSnapshot | null,
    activeRoomId: string | null,
    composer: ComposerState,
    operationError: DomainError | null
  ): void {
    this.state = new AppShellState(
      root,
      this.transport === null ? AppShellTransportState.Unavailable : AppShellTransportState.Ready,
      this.transport === null ? this.unavailableMessage : '',
      roomList,
      timeline,
      activeRoomId,
      composer,
      operationError
    );
    this.observers.forEach((observer: AppShellStateObserver) => observer.onAppShellStateChanged(this.state));
  }
}
