import { RootNavigationStateMachine } from '../../appnav/RootNavigationStateMachine';
import {
  AppShellTimelineFactory,
  AppShellTransport
} from '../../appshell/AppShellCoordinator';
import { NativeMatrixBridge } from '../../nativebridge/Index';
import { RoomListController } from '../../rooms/RoomListController';
import { TimelineController } from '../../timeline/TimelineController';
import { MatrixSessionHandle } from '../api/MatrixAuthentication';
import { NativeRoomListDataSource } from './NativeRoomListDataSource';
import { NativeTimelineDataSource } from './NativeTimelineDataSource';

class NativeTimelineFactory implements AppShellTimelineFactory {
  private readonly bridge: NativeMatrixBridge;
  private readonly rootNavigation: RootNavigationStateMachine;

  constructor(bridge: NativeMatrixBridge, rootNavigation: RootNavigationStateMachine) {
    this.bridge = bridge;
    this.rootNavigation = rootNavigation;
  }

  create(roomId: string, _sessionHandle: MatrixSessionHandle): TimelineController | null {
    return new TimelineController(roomId, new NativeTimelineDataSource(this.bridge, this.rootNavigation));
  }
}

/** Production transport backed by the authenticated Matrix SDK client. */
export class NativeAppShellTransport implements AppShellTransport {
  readonly roomList: RoomListController;
  readonly timelineFactory: AppShellTimelineFactory;
  private readonly rootNavigation: RootNavigationStateMachine;

  constructor(bridge: NativeMatrixBridge, rootNavigation: RootNavigationStateMachine) {
    this.rootNavigation = rootNavigation;
    this.roomList = new RoomListController(new NativeRoomListDataSource(bridge, rootNavigation));
    this.timelineFactory = new NativeTimelineFactory(bridge, rootNavigation);
  }

  get currentUserId(): string {
    return this.rootNavigation.getState().session?.userId ?? '';
  }
}
