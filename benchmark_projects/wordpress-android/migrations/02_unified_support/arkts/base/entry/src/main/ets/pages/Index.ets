import { LegacySupportPageOwner, LegacySupportPageRuntime } from './UnifiedSupportPageOwner';

@Entry
@Component
struct Index {
  private owner: LegacySupportPageOwner = LegacySupportPageRuntime.createOwner();
  aboutToAppear(): void { this.owner.aboutToAppear(); }

  build() {
    Column({ space: 12 }) {
      Text('Help & Support').fontSize(24).fontWeight(FontWeight.Bold).margin({ bottom: 12 })
      ForEach(this.owner.store().entries, (entry: string) => {
        Button(entry).width('100%')
      })
    }.width('100%').height('100%').padding(20)
  }
}
