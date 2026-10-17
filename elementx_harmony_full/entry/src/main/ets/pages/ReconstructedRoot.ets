import { RootNavigationPhase } from '../appnav/RootNavigationState';
import { AppShellCoordinator } from '../appshell/AppShellCoordinator';
import { AppShellRegistry } from '../appshell/AppShellRegistry';
import {
  AppShellState,
  AppShellStateObserver,
  AppShellTransportState
} from '../appshell/AppShellModels';
import {
  RoomListPhase,
  RoomSummary
} from '../matrix/api/RoomModels';
import {
  LocalSendState,
  TextContent,
  TimelineContentKind,
  TimelineEvent,
  TimelinePhase
} from '../matrix/api/TimelineModels';
import { RoomListFilters } from '../rooms/RoomListFilters';

function timelineEventLabel(event: TimelineEvent): string {
  switch (event.content.kind) {
    case TimelineContentKind.Text:
      return (event.content as TextContent).body;
    case TimelineContentKind.Image:
      return 'Image';
    case TimelineContentKind.Video:
      return 'Video';
    case TimelineContentKind.Audio:
      return 'Audio';
    case TimelineContentKind.File:
      return 'File';
    case TimelineContentKind.Gallery:
      return 'Gallery';
    case TimelineContentKind.Poll:
      return 'Poll';
    case TimelineContentKind.Call:
      return 'Call';
    case TimelineContentKind.Location:
      return 'Location';
    case TimelineContentKind.State:
      return 'Room update';
    case TimelineContentKind.UnableToDecrypt:
      return 'Unable to decrypt message';
    case TimelineContentKind.Redacted:
      return 'Message removed';
    default:
      return 'Unsupported event';
  }
}

function sendStateLabel(state: LocalSendState | null): string {
  if (state === null || state === LocalSendState.Sent) {
    return '';
  }
  return state;
}

class RootShellObserver implements AppShellStateObserver {
  private readonly callback: (state: AppShellState) => void;

  constructor(callback: (state: AppShellState) => void) {
    this.callback = callback;
  }

  onAppShellStateChanged(state: AppShellState): void {
    this.callback(state);
  }
}

@Entry
@Component
struct ReconstructedRoot {
  private coordinator: AppShellCoordinator = AppShellRegistry.resolve();
  private observerId: number = 0;
  @State private shell: AppShellState = this.coordinator.getState();
  @State private homeserver: string = 'matrix.org';
  @State private username: string = '';
  @State private password: string = '';

  build() {
    Column() {
      if (this.shell.root.phase === RootNavigationPhase.LoggedIn) {
        this.LoggedInShell()
      } else {
        this.AuthenticationScreen()
      }
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F5F7F8')
    .onAppear(() => {
      this.observerId = this.coordinator.subscribe(new RootShellObserver((state: AppShellState) => {
        this.shell = state;
      }));
      this.coordinator.start();
    })
    .onDisAppear(() => {
      if (this.observerId !== 0) {
        this.coordinator.unsubscribe(this.observerId);
        this.observerId = 0;
      }
    })
  }

  @Builder
  AuthenticationScreen() {
    Column({ space: 18 }) {
      Blank()
      Text('Element')
        .fontSize(38)
        .fontWeight(FontWeight.Bold)
        .fontColor('#087A67')
      Text('Sign in to your Matrix account')
        .fontSize(18)
        .fontColor('#3A424A')
      TextInput({ text: this.homeserver, placeholder: 'Homeserver' })
        .id('login_homeserver')
        .width('88%')
        .height(48)
        .onChange((value: string) => this.homeserver = value)
      TextInput({ text: this.username, placeholder: 'Username' })
        .id('login_username')
        .width('88%')
        .height(48)
        .onChange((value: string) => this.username = value)
      TextInput({ text: this.password, placeholder: 'Password' })
        .id('login_password')
        .type(InputType.Password)
        .width('88%')
        .height(48)
        .onChange((value: string) => this.password = value)
      if (this.shell.root.phase === RootNavigationPhase.Authenticating) {
        LoadingProgress()
          .width(32)
          .height(32)
        Text('Signing in...')
          .fontColor('#4C5661')
      } else {
        Button('Sign in')
          .id('login_submit')
          .width('88%')
          .height(48)
          .backgroundColor('#087A67')
          .onClick(() => {
            this.coordinator.login({
              homeserver: this.homeserver,
              username: this.username,
              password: this.password,
              deviceDisplayName: 'Element X OpenHarmony'
            });
          })
      }
      if (this.shell.root.error !== null) {
        Text(this.shell.root.error.message)
          .id('login_operation_error')
          .width('88%')
          .fontSize(14)
          .fontColor('#B3261E')
      } else if (this.shell.operationError !== null) {
        Text(this.shell.operationError.message)
          .id('login_error')
          .width('88%')
          .fontSize(14)
          .fontColor('#B3261E')
      }
      if (this.shell.transportState === AppShellTransportState.Unavailable) {
        Text(this.shell.transportMessage)
          .id('auth_transport_unavailable')
          .width('88%')
          .fontSize(13)
          .fontColor('#6B4F00')
      }
      Blank()
    }
    .width('100%')
    .height('100%')
    .alignItems(HorizontalAlign.Center)
  }

  @Builder
  LoggedInShell() {
    Column() {
      Row() {
        Text('Element')
          .fontSize(22)
          .fontWeight(FontWeight.Bold)
          .fontColor('#087A67')
        Blank()
        if (this.shell.root.session !== null) {
          Text(this.shell.root.session.userId)
            .fontSize(13)
            .fontColor('#4C5661')
        }
      }
      .width('100%')
      .height(56)
      .padding({ left: 16, right: 16 })
      .backgroundColor('#FFFFFF')

      if (this.shell.transportState === AppShellTransportState.Unavailable) {
        Row() {
          Text(this.shell.transportMessage)
            .id('shell_transport_unavailable')
            .fontSize(13)
            .fontColor('#6B4F00')
        }
        .width('100%')
        .padding(10)
        .backgroundColor('#FFF4CE')
      }

      Row() {
        this.RoomPane()
        this.TimelinePane()
      }
      .width('100%')
      .layoutWeight(1)
      .alignItems(VerticalAlign.Top)
    }
    .width('100%')
    .height('100%')
  }

  @Builder
  RoomPane() {
    Column() {
      Scroll() {
        Row({ space: 6 }) {
          Button('All')
            .id('filter_all')
            .fontSize(12)
            .onClick(() => this.coordinator.setRoomFilter(RoomListFilters.all()))
          Button('Unread')
            .id('filter_unread')
            .fontSize(12)
            .onClick(() => this.coordinator.setRoomFilter(RoomListFilters.unread()))
          Button('Favorites')
            .id('filter_favorites')
            .fontSize(12)
            .onClick(() => this.coordinator.setRoomFilter(RoomListFilters.favorite()))
          Button('Invites')
            .id('filter_invites')
            .fontSize(12)
            .onClick(() => this.coordinator.setRoomFilter(RoomListFilters.invite()))
        }
        .padding({ left: 10, right: 10, top: 10, bottom: 8 })
      }
      .scrollable(ScrollDirection.Horizontal)
      .width('100%')

      if (this.shell.roomList === null || this.shell.roomList.phase === RoomListPhase.Loading) {
        LoadingProgress()
          .id('rooms_loading')
          .margin({ top: 32 })
      } else if (this.shell.roomList.phase === RoomListPhase.Error ||
        this.shell.roomList.phase === RoomListPhase.Offline) {
        Text(this.shell.roomList.error === null ? 'Rooms unavailable' : this.shell.roomList.error.message)
          .id('rooms_error')
          .fontSize(14)
          .fontColor('#B3261E')
          .padding(16)
        Button('Retry')
          .id('rooms_retry')
          .onClick(() => this.coordinator.refreshRooms())
      } else if (this.shell.roomList.phase === RoomListPhase.Empty) {
        Text('No rooms')
          .id('rooms_empty')
          .fontColor('#68717A')
          .margin({ top: 32 })
      } else {
        List() {
          ForEach(this.shell.roomList.rooms, (room: RoomSummary) => {
            ListItem() {
              Row() {
                Column({ space: 4 }) {
                  Text(room.displayName)
                    .fontSize(15)
                    .fontWeight(FontWeight.Medium)
                    .maxLines(1)
                    .textOverflow({ overflow: TextOverflow.Ellipsis })
                  Text(room.latestEventPreview === null ? '' : room.latestEventPreview)
                    .fontSize(12)
                    .fontColor('#68717A')
                    .maxLines(1)
                    .textOverflow({ overflow: TextOverflow.Ellipsis })
                }
                .alignItems(HorizontalAlign.Start)
                .layoutWeight(1)
                if (room.unreadNotificationCount > 0) {
                  Text(`${room.unreadNotificationCount}`)
                    .fontSize(12)
                    .fontColor('#087A67')
                }
              }
              .width('100%')
              .height(64)
              .padding({ left: 12, right: 12 })
              .backgroundColor(this.shell.activeRoomId === room.roomId ? '#DCEFEA' : '#FFFFFF')
              .onClick(() => this.coordinator.selectRoom(room.roomId))
            }
          }, (room: RoomSummary) => room.roomId)
        }
        .id('room_list')
        .width('100%')
        .layoutWeight(1)
      }
    }
    .width('34%')
    .height('100%')
    .backgroundColor('#FFFFFF')
    .border({ width: { right: 1 }, color: '#D9DEE3' })
  }

  @Builder
  TimelinePane() {
    Column() {
      if (this.shell.activeRoomId === null || this.shell.timeline === null) {
        Column({ space: 8 }) {
          Text('Select a room')
            .id('timeline_unselected')
            .fontSize(20)
            .fontWeight(FontWeight.Medium)
          Text('Messages will appear here when the Matrix timeline transport is ready.')
            .fontSize(13)
            .fontColor('#68717A')
        }
        .layoutWeight(1)
        .justifyContent(FlexAlign.Center)
      } else {
        Row() {
          Text(this.shell.activeRoomId)
            .fontSize(16)
            .fontWeight(FontWeight.Medium)
            .maxLines(1)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
        }
        .width('100%')
        .height(48)
        .padding({ left: 14, right: 14 })
        .border({ width: { bottom: 1 }, color: '#D9DEE3' })

        if (this.shell.timeline.phase === TimelinePhase.Loading) {
          LoadingProgress()
            .id('timeline_loading')
            .layoutWeight(1)
        } else if (this.shell.timeline.phase === TimelinePhase.Error ||
          this.shell.timeline.phase === TimelinePhase.Offline) {
          Text(this.shell.timeline.error === null ? 'Timeline unavailable' : this.shell.timeline.error.message)
            .id('timeline_error')
            .layoutWeight(1)
            .fontColor('#B3261E')
            .padding(20)
        } else if (this.shell.timeline.phase === TimelinePhase.Empty) {
          Text('No messages yet')
            .id('timeline_empty')
            .layoutWeight(1)
            .fontColor('#68717A')
            .padding(20)
        } else {
          List({ space: 6 }) {
            ForEach(this.shell.timeline.items, (event: TimelineEvent) => {
              ListItem() {
                Column({ space: 4 }) {
                  Text(event.senderDisplayName === null ? event.senderId : event.senderDisplayName)
                    .fontSize(12)
                    .fontWeight(FontWeight.Medium)
                    .fontColor('#47515B')
                  Text(timelineEventLabel(event))
                    .fontSize(15)
                    .fontColor('#20262C')
                  if (sendStateLabel(event.localSendState).length > 0) {
                    Text(sendStateLabel(event.localSendState))
                      .fontSize(11)
                      .fontColor(event.localSendState === LocalSendState.Failed ? '#B3261E' : '#68717A')
                  }
                }
                .width('100%')
                .alignItems(HorizontalAlign.Start)
                .padding({ left: 14, right: 14, top: 8, bottom: 8 })
              }
            }, (event: TimelineEvent) => event.stableId)
          }
          .id('timeline_list')
          .width('100%')
          .layoutWeight(1)
        }

        Row({ space: 8 }) {
          TextInput({ text: this.shell.composer.draft, placeholder: 'Message' })
            .id('composer_input')
            .layoutWeight(1)
            .height(44)
            .enabled(!this.shell.composer.isSending)
            .onChange((value: string) => this.coordinator.setComposerDraft(value))
          Button('Send')
            .id('composer_send')
            .height(44)
            .enabled(!this.shell.composer.isSending)
            .backgroundColor('#087A67')
            .onClick(() => this.coordinator.sendMessage())
        }
        .width('100%')
        .padding({ left: 12, right: 12, top: 8, bottom: 8 })
        if (this.shell.composer.error !== null) {
          Text(this.shell.composer.error.message)
            .id('composer_error')
            .width('100%')
            .fontSize(12)
            .fontColor('#B3261E')
            .padding({ left: 12, right: 12, bottom: 8 })
        }
      }
    }
    .width('66%')
    .height('100%')
  }
}
