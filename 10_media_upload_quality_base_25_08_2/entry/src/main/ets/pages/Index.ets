import { AttachmentGateway, AttachmentPresenter, AttachmentSendState } from '../features/AttachmentFeature';

@Entry
@Component
struct Index {
  private presenter: AttachmentPresenter = new AttachmentPresenter(new AttachmentGateway());
  @State private caption: string = '';
  @State private sendState: AttachmentSendState = AttachmentSendState.Idle;

  build() {
    Column() {
      Column({ space: 4 }) {
        Text('Attachment preview')
          .fontSize(24)
          .fontWeight(FontWeight.Bold)
        Text('Android v25.08.2 behavior: send original media')
          .fontSize(13)
          .fontColor('#64748B')
      }
      .alignItems(HorizontalAlign.Start)
      .padding(20)
      .width('100%')
      .backgroundColor('#FFFFFF')
      Column({ space: 12 }) {
        Text('video-demo.mp4')
          .fontSize(20)
          .fontWeight(FontWeight.Bold)
          .width('100%')
        TextInput({ text: this.caption, placeholder: 'Caption' })
          .id('attachment_caption')
          .onChange((value: string) => {
            this.presenter.setCaption(value);
            this.caption = value;
          })
        Button('Send original')
          .id('attachment_send')
          .onClick(() => {
            this.presenter.send();
            this.sendState = this.presenter.sendState;
          })
        Text(`Send state: ${this.sendState}`)
      }
      .padding(20)
      .width('100%')
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }
}
