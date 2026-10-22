import { DemoRoomInfoSource, NavigationState, RoomNavigationGateway, RoomUpgradePresenter } from '../features/RoomUpgradeFeature';

@Entry
@Component
struct Index {
  private presenter: RoomUpgradePresenter = new RoomUpgradePresenter(new RoomNavigationGateway(new DemoRoomInfoSource()));
  @State private roomName: string = 'Product planning';
  @State private roomId: string = '!old:example.org';
  @State private history: string[] = ['Earlier message'];
  @State private isTombstoned: boolean = false;
  @State private hasPredecessor: boolean = false;
  @State private predecessorRoomId: string = '';
  @State private successorRoomId: string = '';
  @State private oldRoomPreview: string = 'Earlier message';
  @State private oldRoomTombstoned: boolean = false;
  @State private navigationState: NavigationState = NavigationState.Idle;
  @State private sameRoomNoticeVisible: boolean = false;

  aboutToAppear(): void {
    this.refresh();
    this.presenter.observeTimelineRoomInfo().then(() => this.refresh());
  }

  build() {
    Column() {
      Column({ space: 4 }) {
        Text(this.isTombstoned ? `${this.roomName} - replaced` : this.roomName)
          .fontSize(24)
          .fontWeight(FontWeight.Bold)
        Text(this.roomId)
          .id('current_room_id')
          .fontSize(13)
          .fontColor('#64748B')
      }
      .alignItems(HorizontalAlign.Start)
      .padding(20)
      .width('100%')
      .backgroundColor('#FFFFFF')

      Scroll() {
        Column({ space: 12 }) {
          Text('Rooms')
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .width('100%')
          Row({ space: 8 }) {
            Stack({ alignContent: Alignment.BottomEnd }) {
              Text(this.presenter.oldRoom.name.slice(0, 1))
                .width(48).height(48).textAlign(TextAlign.Center)
                .backgroundColor('#D8EEE7').borderRadius(24)
              if (this.oldRoomTombstoned) {
                Text('Replaced')
                  .id('room_avatar_tombstone_mark')
                  .fontSize(10).padding(2).backgroundColor('#FFFFFF')
              }
            }
            Button(`Product planning - ${this.oldRoomPreview}`)
            .id('room_list_tombstoned_room')
            .layoutWeight(1)
            .onClick(() => {
              this.presenter.selectOldRoom();
              this.refresh();
            })
          }
          .width('100%')
          Button(`Product planning v2 - ${this.presenter.roomListPreview(this.presenter.replacementRoom)}`)
            .id('room_list_replacement_room')
            .width('100%')
            .onClick(() => {
              this.presenter.selectReplacementRoom();
              this.refresh();
            })

          Divider()
          if (this.hasPredecessor) {
            Column({ space: 8 }) {
              Text('This room replaces an earlier room.')
                .width('100%')
              Text(this.predecessorRoomId).id('predecessor_room_id')
              Button('Open predecessor room')
                .id('open_predecessor_room')
                .onClick(() => {
                  this.presenter.openPredecessorRoom();
                  this.refresh();
                })
            }
            .id('predecessor_room_banner')
            .padding(14)
            .width('100%')
            .backgroundColor('#E8F3EE')
            .borderRadius(6)
          }

          Text(`This is the beginning of ${this.roomName}.`)
            .id('room_beginning_content')
            .width('100%')

          Text('Timeline')
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .width('100%')
          Column({ space: 8 }) {
            ForEach(this.history, (message: string, index: number) => {
              Text(message)
              .id(`history_message_${index}`)
              .padding(14)
              .width('100%')
              .backgroundColor('#FFFFFF')
              .borderRadius(6)
            })
          }
          .id('room_history')
          .width('100%')

          if (this.isTombstoned) {
            Column({ space: 8 }) {
              Text('This room has been replaced and is read-only.')
                .id('successor_room_banner')
                .width('100%')
              Text(this.successorRoomId).id('successor_room_id')
              Button('Open replacement room')
                .id('open_successor_room')
                .onClick(() => {
                  this.presenter.openSuccessorRoom();
                  this.refresh();
                })
            }
            .padding(14)
            .width('100%')
            .backgroundColor('#FFF4D6')
            .borderRadius(6)
          } else {
            TextInput({ placeholder: 'Write a message' })
              .id('message_composer')
          }

          if (this.sameRoomNoticeVisible) {
            Text('Already viewing this room')
              .id('same_room_notice')
              .fontColor('#B42318')
          } else if (this.navigationState === NavigationState.Failure) {
            Text('Unable to open room. Timeline remains available.')
              .id('navigation_failure')
              .fontColor('#B42318')
          }
        }
        .padding(20)
        .width('100%')
      }
      .layoutWeight(1)
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }

  private refresh(): void {
    this.roomName = this.presenter.currentRoom.name;
    this.roomId = this.presenter.currentRoom.roomId;
    this.history = this.presenter.currentRoom.history.slice();
    this.isTombstoned = this.presenter.isTombstoned;
    this.hasPredecessor = this.presenter.currentRoom.predecessorRoom !== undefined;
    this.predecessorRoomId = this.presenter.currentRoom.predecessorRoom?.roomId ?? '';
    this.successorRoomId = this.presenter.currentRoom.successorRoom?.roomId ?? '';
    this.oldRoomPreview = this.presenter.roomListPreview(this.presenter.oldRoom);
    this.oldRoomTombstoned = this.presenter.oldRoom.successorRoom !== undefined;
    this.navigationState = this.presenter.navigationState;
    this.sameRoomNoticeVisible = this.presenter.sameRoomNoticeVisible;
  }
}
