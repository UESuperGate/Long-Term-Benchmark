import { NavigationState, RoomNavigationGateway, RoomUpgradePresenter } from '../features/RoomUpgradeFeature';

@Entry
@Component
struct Index {
  private presenter: RoomUpgradePresenter = new RoomUpgradePresenter(new RoomNavigationGateway());
  @State private roomName: string = 'Product planning';
  @State private roomId: string = '!old:example.org';
  @State private history: string[] = ['Earlier message'];
  @State private isTombstoned: boolean = true;
  @State private hasPredecessor: boolean = false;
  @State private navigationState: NavigationState = NavigationState.Idle;
  @State private sameRoomNoticeVisible: boolean = false;

  build() {
    Column() {
      Column({ space: 4 }) {
        Text(this.isTombstoned ? `${this.roomName} - replaced` : this.roomName)
          .fontSize(24)
          .fontWeight(FontWeight.Bold)
        Text(this.roomId)
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
          Button(`Product planning - ${this.presenter.roomListPreview(this.presenter.oldRoom)}`)
            .id('room_list_tombstoned_room')
            .width('100%')
            .onClick(() => {
              this.presenter.selectOldRoom();
              this.refresh();
            })
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
              Button('Open predecessor room')
                .id('open_predecessor_room')
                .onClick(() => {
                  this.presenter.openPredecessorRoom();
                  this.refresh();
                })
            }
            .padding(14)
            .width('100%')
            .backgroundColor('#E8F3EE')
            .borderRadius(6)
          }

          Text('Timeline')
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .width('100%')
          ForEach(this.history, (message: string) => {
            Text(message)
              .padding(14)
              .width('100%')
              .backgroundColor('#FFFFFF')
              .borderRadius(6)
          })

          if (this.isTombstoned) {
            Column({ space: 8 }) {
              Text('This room has been replaced and is read-only.')
                .id('successor_room_banner')
                .width('100%')
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
    this.navigationState = this.presenter.navigationState;
    this.sameRoomNoticeVisible = this.presenter.sameRoomNoticeVisible;
  }
}
