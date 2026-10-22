import { HomeRoom, HomeRoomsPresenter, HomeSurface } from '../features/HomeRoomsFeature';

@Entry
@Component
struct Index {
  private presenter: HomeRoomsPresenter = new HomeRoomsPresenter();
  @State private selectedRoomId: string = '';
  @State private surface: HomeSurface = HomeSurface.Chats;

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
      Row({ space: 8 }) {
        Button('Chats')
          .id('home_chats_tab')
          .onClick(() => {
            this.presenter.openChats();
            this.surface = this.presenter.surface;
          })
        Button('Spaces')
          .id('home_spaces_tab')
          .onClick(() => {
            this.presenter.openSpaces();
            this.surface = this.presenter.surface;
          })
      }
      .padding({ left: 20, right: 20, top: 16 })
      .width('100%')
      Column({ space: 12 }) {
        if (this.surface === HomeSurface.Chats) {
          ForEach(this.presenter.rooms, (room: HomeRoom) => {
            Button(room.name)
              .width('100%')
              .onClick(() => {
                this.presenter.openRoom(room.roomId);
                this.selectedRoomId = this.presenter.selectedRoomId;
              })
          })
          Text(this.selectedRoomId.length > 0 ? `Opened ${this.selectedRoomId}` : 'Choose a room')
        } else {
          Text('Spaces are coming soon!')
            .id('spaces_unavailable')
            .width('100%')
        }
      }
      .padding(20)
      .width('100%')
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }
}
