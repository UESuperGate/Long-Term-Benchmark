import { RoomDetailsGateway, RoomDetailsPresenter } from '../features/RoomDetailsFeature';

@Entry
@Component
struct Index {
  private presenter: RoomDetailsPresenter = new RoomDetailsPresenter(new RoomDetailsGateway());
  @State private statusText: string = 'Room details';

  build() {
    Column() {
      Column({ space: 4 }) {
        Text('Community support')
          .fontSize(24)
          .fontWeight(FontWeight.Bold)
        Text('128 members')
          .fontSize(13)
          .fontColor('#64748B')
      }
      .alignItems(HorizontalAlign.Start)
      .padding(20)
      .width('100%')
      .backgroundColor('#FFFFFF')

      Column({ space: 12 }) {
        Button('Notifications')
          .width('100%')
        Button('Members')
          .width('100%')
        Button('Leave room')
          .id('leave_room')
          .width('100%')
          .onClick(() => {
            this.presenter.leaveRoom();
            this.statusText = this.presenter.leaveSucceeded ? 'Left room' : 'Unable to leave room';
          })
        Text(this.statusText)
          .fontSize(13)
          .fontColor('#64748B')
          .width('100%')
      }
      .padding(20)
      .width('100%')
      .layoutWeight(1)
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }
}
