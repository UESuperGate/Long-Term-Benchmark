import { RoomTimelineGateway, RoomTimelinePresenter, RoomSendState } from '../features/RoomTimelineFeature';

@Entry
@Component
struct Index {
  private presenter: RoomTimelinePresenter = new RoomTimelinePresenter(new RoomTimelineGateway());
  @State private events: string[] = ['$welcome', '$roadmap'];
  @State private composerText: string = '';
  @State private sendState: RoomSendState = RoomSendState.Idle;

  build() {
    Column() {
      Column({ space: 4 }) {
        Text('Element X Room')
          .fontSize(24)
          .fontWeight(FontWeight.Bold)
        Text('Android v25.08.3 behavior: one room timeline')
          .fontSize(13)
          .fontColor('#64748B')
      }
      .alignItems(HorizontalAlign.Start)
      .padding(20)
      .width('100%')
      .backgroundColor('#FFFFFF')
      Scroll() {
        Column({ space: 12 }) {
          ForEach(this.events, (event: string) => {
            Text(event)
              .padding(12)
              .width('100%')
              .backgroundColor('#FFFFFF')
          })
          TextInput({ text: this.composerText, placeholder: 'Message' })
            .id('room_composer')
            .onChange((value: string) => {
              this.presenter.setComposerText(value);
              this.composerText = value;
            })
          Button('Send to room')
            .id('room_send')
            .onClick(() => {
              this.presenter.sendMessage();
              this.refresh();
            })
          Text(`Send state: ${this.sendState}`)
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
    this.events = this.presenter.events.slice();
    this.composerText = this.presenter.composerText;
    this.sendState = this.presenter.sendState;
  }
}
