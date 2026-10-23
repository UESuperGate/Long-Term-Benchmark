import { KeyboardSticker, MediaKeyboardPageOwner } from '../feature/MediaKeyboardStore';

@Entry
@Component
struct Index {
  private readonly owner: MediaKeyboardPageOwner = new MediaKeyboardPageOwner();
  @State private revision: number = 0;

  aboutToAppear(): void {
    this.owner.appear();
    this.refresh();
  }

  private refresh(): void { this.revision += 1; }

  build() {
    Column({ space: 16 }) {
      Text('Signal Media Keyboard').fontSize(24).fontWeight(FontWeight.Bold)
      Text('Emoji, stickers, and GIFs').fontSize(14).fontColor('#5F6368')
      Row({ space: 8 }) {
        ForEach(this.owner.keyboardState().availableTabs, (tab: string) => {
          Button(tab)
            .id(`media-tab-${tab}`)
            .onClick(() => {
              this.owner.selectTab(tab);
              this.refresh();
            })
        })
      }
      Text(`Selected: ${this.owner.keyboardState().selectedTab}`).fontSize(18)
      TextInput({ placeholder: 'Message', text: this.owner.keyboardState().searchQuery })
        .onChange((value: string) => {
          this.owner.setSearch(true, value);
          this.refresh();
        })
      if (this.owner.keyboardState().selectedTab === 'GIF') {
        Row({ space: 8 }) {
          Button('Load').id('gif-load').onClick(() => {
            this.owner.loadFirstGifPage();
            this.refresh();
          })
          Button('Retry').id('gif-retry').onClick(() => {
            this.owner.retryGifLoad();
            this.refresh();
          })
          Button('More').id('gif-more').onClick(() => {
            this.owner.loadMoreGifs();
            this.refresh();
          })
        }
        Text(`${this.owner.gifState().gifs.length} GIFs`)
      }
      if (this.owner.keyboardState().selectedTab === 'STICKER') {
        Button('Sticker 7').id('sticker-7').onClick(() => {
          const sticker: KeyboardSticker = { packId: 'pack-1', packKey: 'key-1', stickerId: 7 };
          this.owner.tapSticker(sticker);
          this.refresh();
        })
      }
      if (this.owner.confirmation() !== null) {
        Row({ space: 12 }) {
          Button('Cancel').id('sticker-cancel').onClick(() => {
            this.owner.cancelStickerConfirmation();
            this.refresh();
          })
          Button('Send').id('sticker-send').onClick(() => {
            this.owner.confirmStickerSend();
            this.refresh();
          })
        }
      }
    }
    .width('100%')
    .height('100%')
    .padding(24)
    .justifyContent(FlexAlign.Center)
  }
}

