import { RoomGateway, RoomPresenter } from '../features/RoomFeature';

@Entry
@Component
struct Index {
  private presenter: RoomPresenter = new RoomPresenter(new RoomGateway());
  @State private history: string[] = ['Earlier message'];
  @State private composerText: string = '';
  @State private statusText: string = 'Room is writable';
  @State private roomName: string = 'Product planning';
  @State private roomId: string = '!old:example.org';
  @State private roomPreview: string = 'Earlier message';

  async aboutToAppear(): Promise<void> {
    if (await this.presenter.observeRoomInfo(this.presenter.room.roomId)) {
      this.roomName = this.presenter.room.name;
      this.roomId = this.presenter.room.roomId;
      this.roomPreview = this.presenter.room.lastMessage;
      this.history = this.presenter.history.slice();
    }
  }

  build() {
    Column() {
      Column({ space: 4 }) {
        Text(this.roomName)
          .fontSize(24)
          .fontWeight(FontWeight.Bold)
        Text('Element X room timeline')
          .fontSize(13)
          .fontColor('#64748B')
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
          Button(this.roomName + ' - ' + this.roomPreview)
            .id('room_list_old_room')
            .width('100%')
            .onClick(() => this.presenter.openRoom())
          Button('Product planning v2 - Welcome to the replacement room')
            .id('room_list_replacement_room')
            .width('100%')
            .onClick(() => {
              this.presenter.selectRoom('!new:example.org').then((selected: boolean) => {
                if (selected) this.refreshRoom();
              })
            })

          Divider()
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

  private refreshRoom(): void {
    this.roomName = this.presenter.room.name;
    this.roomId = this.presenter.room.roomId;
    this.roomPreview = this.presenter.room.lastMessage;
    this.history = this.presenter.history.slice();
  }
}
