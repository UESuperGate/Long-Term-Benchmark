import { HomeRoom, HomeRoomsPresenter } from '../features/HomeRoomsFeature';

@Entry
@Component
struct Index {
  private presenter: HomeRoomsPresenter = new HomeRoomsPresenter();
  @State private selectedRoomId: string = '';

  build() {
    Column() {
      Column({ space: 4 }) {
        Text('Element X Home')
          .fontSize(24)
          .fontWeight(FontWeight.Bold)
        Text('Android v25.08.4 behavior: flat joined-room list')
          .fontSize(13)
          .fontColor('#64748B')
      }
      .alignItems(HorizontalAlign.Start)
      .padding(20)
      .width('100%')
      .backgroundColor('#FFFFFF')
      Column({ space: 12 }) {
        ForEach(this.presenter.rooms, (room: HomeRoom) => {
          Button(room.name)
            .width('100%')
            .onClick(() => {
              this.presenter.openRoom(room.roomId);
              this.selectedRoomId = this.presenter.selectedRoomId;
            })
        })
        Text(this.selectedRoomId.length > 0 ? `Opened ${this.selectedRoomId}` : 'Choose a room')
      }
      .padding(20)
      .width('100%')
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }
}
