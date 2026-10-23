import { StickerManagementPageOwner } from '../feature/StickerManagementStore';

@Entry
@Component
struct Index {
  private readonly owner: StickerManagementPageOwner = new StickerManagementPageOwner();
  @State private revision: number = 0;

  aboutToAppear(): void {
    this.owner.appear();
    this.refresh();
  }

  private refresh(): void { this.revision += 1; }

  build() {
    Column({ space: 14 }) {
      Text('Sticker Management').fontSize(24).fontWeight(FontWeight.Bold)
      Text('Available').fontSize(16).fontWeight(FontWeight.Medium)
      ForEach([
        ...this.owner.state().availableOfficialIds,
        ...this.owner.state().availableOtherIds
      ], (id: string) => {
        Row({ space: 8 }) {
          Text(id).layoutWeight(1)
          Button('Install').id(`install-${id}`).onClick(() => {
            this.owner.installPack(id);
            this.refresh();
          })
        }.width('100%')
      })
      Text('Installed').fontSize(16).fontWeight(FontWeight.Medium)
      ForEach(this.owner.state().installedPackIds, (id: string, index: number) => {
        Row({ space: 8 }) {
          Checkbox({ name: id, group: 'packs' })
            .select(this.owner.state().selectedPackIds.includes(id))
            .onChange(() => {
              this.owner.toggleSelection(id);
              this.refresh();
            })
          Text(id).layoutWeight(1)
          Button('Move').id(`move-${id}`).enabled(index < this.owner.state().installedPackIds.length - 1).onClick(() => {
            this.owner.movePack(index, index + 1);
            this.refresh();
          })
          Button('Drop').id(`drop-${id}`).enabled(index < this.owner.state().installedPackIds.length - 1).onClick(() => {
            this.owner.completeDrag(index, index + 1);
            this.refresh();
          })
        }.width('100%')
      })
      Row({ space: 8 }) {
        Button('Select all').id('select-all').onClick(() => {
          this.owner.toggleSelectAll();
          this.refresh();
        })
        Button('Exit select').id('exit-select').onClick(() => {
          this.owner.setMultiSelectEnabled(false);
          this.refresh();
        })
        Button('Delete selected')
          .id('delete-selected')
          .enabled(this.owner.state().selectedPackIds.length > 0)
          .onClick(() => {
            this.owner.requestUninstall(this.owner.state().selectedPackIds);
            this.refresh();
          })
      }
      if (this.owner.state().prompt !== null) {
        Text(`Delete ${this.owner.state().prompt} packs?`)
        Row({ space: 12 }) {
          Button('Cancel').id('delete-cancel').onClick(() => {
            this.owner.cancelUninstall();
            this.refresh();
          })
          Button('Delete').id('delete-confirm').onClick(() => {
            this.owner.confirmUninstall();
            this.refresh();
          })
        }
      }
    }
    .width('100%')
    .height('100%')
    .padding(24)
  }
}

