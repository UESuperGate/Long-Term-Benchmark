import { MountedSitePickerPageOwner, SitePickerPageRuntime } from './SitePickerPageOwner';

@Entry
@Component
struct Index {
  private owner: MountedSitePickerPageOwner = SitePickerPageRuntime.createOwner();
  @State summary: string = 'Loading';

  aboutToAppear(): void {
    this.owner.waitUntilReady().then(() => {
      this.summary = JSON.stringify(this.owner.currentState());
    });
  }

  build() {
    Column({ space: 16 }) {
      Text('WordPress Site Picker').fontSize(28).fontWeight(FontWeight.Bold)
      Text(this.summary).fontSize(14)
    }.width('100%').height('100%').padding(24)
  }
}
