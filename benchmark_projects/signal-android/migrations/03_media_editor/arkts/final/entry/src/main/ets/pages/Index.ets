import { MediaEditorPageOwner } from '../feature/MediaEditorStore';

@Entry
@Component
struct Index {
  private readonly owner: MediaEditorPageOwner = new MediaEditorPageOwner();
  @State private revision: number = 0;
  aboutToAppear(): void { this.owner.appear(); this.refresh(); }
  private refresh(): void { this.revision += 1; }
  build() {
    Column({ space: 16 }) {
      Text('Media editor').fontSize(24).fontWeight(FontWeight.Bold)
      Text(`Focused: ${String(this.owner.state()['focusedItemId'])}`)
      Row({ space: 10 }) {
        Button('Mute').id('toggle-audio').onClick(() => { this.owner.toggleVideoMuted(); this.refresh(); })
        Button('Next media').id('next-media').onClick(() => { this.owner.setFocusedItem('video-2'); this.refresh(); })
      }
      Row({ space: 10 }) {
        Button('Move').id('reorder-media').onClick(() => { this.owner.reorderSelectedMedia(0, 1); this.refresh(); })
        Button('Close').id('close-editor').onClick(() => { this.owner.requestCloseThenCancelDiscard(); this.refresh(); })
      }
      Text(`Screen: ${String(this.owner.state()['screen'])}`)
    }.width('100%').height('100%').padding(24)
  }
}
