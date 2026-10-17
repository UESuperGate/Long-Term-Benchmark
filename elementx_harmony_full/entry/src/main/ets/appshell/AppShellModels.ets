import { DomainError } from '../core/DomainResult';
import { RootNavigationState } from '../appnav/RootNavigationState';
import { RoomListSnapshot } from '../matrix/api/RoomModels';
import { TimelineSnapshot } from '../matrix/api/TimelineModels';

export enum AppShellTransportState {
  Ready = 'ready',
  Unavailable = 'unavailable'
}

export class ComposerState {
  readonly draft: string;
  readonly isSending: boolean;
  readonly error: DomainError | null;

  constructor(draft: string = '', isSending: boolean = false, error: DomainError | null = null) {
    this.draft = draft;
    this.isSending = isSending;
    this.error = error;
  }
}

/** Single immutable presentation snapshot consumed by the ArkUI root page. */
export class AppShellState {
  readonly root: RootNavigationState;
  readonly transportState: AppShellTransportState;
  readonly transportMessage: string;
  readonly roomList: RoomListSnapshot | null;
  readonly timeline: TimelineSnapshot | null;
  readonly activeRoomId: string | null;
  readonly composer: ComposerState;
  readonly operationError: DomainError | null;

  constructor(
    root: RootNavigationState,
    transportState: AppShellTransportState,
    transportMessage: string,
    roomList: RoomListSnapshot | null,
    timeline: TimelineSnapshot | null,
    activeRoomId: string | null,
    composer: ComposerState,
    operationError: DomainError | null
  ) {
    this.root = root;
    this.transportState = transportState;
    this.transportMessage = transportMessage;
    this.roomList = roomList;
    this.timeline = timeline;
    this.activeRoomId = activeRoomId;
    this.composer = composer;
    this.operationError = operationError;
  }
}

export interface AppShellStateObserver {
  onAppShellStateChanged(state: AppShellState): void;
}
