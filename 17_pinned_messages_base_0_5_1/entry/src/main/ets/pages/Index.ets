import { PinnedBannerMessage, PinnedMessagesBannerPresenter } from '../features/PinnedMessagesBase';

@Entry
@Component
struct Index {
  private presenter: PinnedMessagesBannerPresenter = new PinnedMessagesBannerPresenter();
  @State private currentPinned: PinnedBannerMessage | null = this.presenter.current();

  build() {
    Column() {
      Row() {
        Column({ space: 2 }) {
          Text('Design team')
            .fontSize(22)
            .fontWeight(FontWeight.Bold)
          Text('12 members')
            .fontSize(13)
            .fontColor('#64748B')
        }
        .alignItems(HorizontalAlign.Start)
        Blank()
        Text('Room')
          .fontSize(13)
          .fontColor('#64748B')
      }
      .padding(20)
      .width('100%')
      .backgroundColor('#FFFFFF')

      if (this.currentPinned !== null) {
        Row({ space: 12 }) {
          Text('Pinned')
            .fontSize(13)
            .fontWeight(FontWeight.Medium)
            .fontColor('#067A68')
          Text(this.currentPinned?.body ?? '')
            .layoutWeight(1)
            .maxLines(1)
          Button('Next')
            .onClick(() => {
              this.presenter.moveToNext();
              this.currentPinned = this.presenter.current();
            })
            .id('pinned_banner_next')
        }
        .padding(14)
        .width('100%')
        .backgroundColor('#E9F8F4')
        .id('pinned_messages_banner')
      }

      Column({ space: 14 }) {
        Text('Alice')
          .fontSize(13)
          .fontColor('#64748B')
          .width('100%')
        Text('The room timeline remains available, but this version has no pinned-message collection screen.')
          .fontSize(16)
          .lineHeight(23)
          .width('100%')
        Text('Bob')
          .fontSize(13)
          .fontColor('#64748B')
          .width('100%')
        Text('Use the banner to cycle through known pins.')
          .fontSize(16)
          .width('100%')
      }
      .padding(20)
      .layoutWeight(1)
      .alignItems(HorizontalAlign.Start)
      .width('100%')
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }
}
