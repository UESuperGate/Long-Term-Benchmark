import { LegacyPagesPageOwner, LegacyPagesPageRuntime } from './PagesPageOwner';

@Entry
@Component
struct Index {
  private owner: LegacyPagesPageOwner = LegacyPagesPageRuntime.createOwner();
  @State surface: string = 'legacy_pages';

  aboutToAppear(): void {
    this.owner.aboutToAppear();
    this.surface = this.owner.store().surface;
  }

  build() {
    Column({ space: 16 }) {
      Text('Pages').fontSize(24).fontWeight(FontWeight.Bold)
      Text('Legacy pages list').fontSize(16)
      List() {
        ListItem() { Text('No pages loaded') }
      }.layoutWeight(1).width('100%')
    }.width('100%').height('100%').padding(20)
  }
}
