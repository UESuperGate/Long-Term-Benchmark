import { RoomGateway, RoomPresenter } from '../features/RoomFeature';

@Entry
@Component
struct Index {
  private presenter: RoomPresenter = new RoomPresenter(new RoomGateway());
  @State private history: string[] = ['Earlier message'];
  @State private composerText: string = '';
  @State private statusText: string = 'Room is writable';

  build() {
    Column() {
      Column({ space: 4 }) {
        Text('Product planning')
          .fontSize(24)
          .fontWeight(FontWeight.Bold)
        Text('Element X room timeline')
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
          Button('Product planning - Earlier message')
            .id('room_list_old_room')
            .width('100%')
            .onClick(() => this.presenter.openRoom())

          Divider()
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

          TextInput({ text: this.composerText, placeholder: 'Write a message' })
            .id('message_composer')
            .onChange((value: string) => this.composerText = value)
          Button('Send')
            .id('send_message')
            .enabled(this.composerText.trim().length > 0)
            .onClick(() => {
              if (this.presenter.sendMessage(this.composerText)) {
                this.history = this.presenter.history.slice();
                this.composerText = '';
                this.statusText = 'Message sent';
              }
            })
          Text(this.statusText)
            .fontSize(13)
            .fontColor('#64748B')
            .width('100%')
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
}
