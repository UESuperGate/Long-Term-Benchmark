import { PageRow } from '../features/PagesController';
import { PagesPageOwner, PagesPageRuntime } from './PagesPageOwner';

@Entry
@Component
struct Index {
  private owner: PagesPageOwner = PagesPageRuntime.createOwner();
  @State rows: PageRow[] = [];
  @State selectedTab: string = 'published';
  @State query: string = '';
  @State searchActive: boolean = false;
  @State feedback: string = '';
  @State menuPageId: number = 0;
  @State menuActions: string[] = [];
  @State confirmationPageId: number = 0;

  aboutToAppear(): void {
    this.owner.aboutToAppear();
    this.owner.waitUntilReady().then(() => this.sync());
  }

  private sync(): void {
    const store = this.owner.store();
    this.rows = store.rows;
    this.selectedTab = store.selectedTab;
    this.query = store.query;
    this.searchActive = store.searchActive;
    this.feedback = store.feedback;
    this.menuPageId = store.menu.pageId === undefined ? 0 : store.menu.pageId;
    this.menuActions = store.menu.actions.slice();
    this.confirmationPageId = store.pendingTrash === undefined ? 0 : store.pendingTrash;
  }

  build() {
    Column() {
      Row({ space: 8 }) {
        Text('Pages').fontSize(24).fontWeight(FontWeight.Bold).layoutWeight(1)
        Button(this.owner.store().authorSelection === 'everyone' ? 'Everyone' : 'Me').onClick(() => {
          const selection = this.owner.store().authorSelection === 'everyone' ? 'me' : 'everyone';
          this.owner.selectAuthor(selection).then(() => this.sync());
        })
        Button('Refresh').onClick(() => { this.owner.refresh().then(() => this.sync()); })
        Button(this.searchActive ? 'Close' : 'Search').onClick(() => {
          if (this.searchActive) this.owner.closeSearch().then(() => this.sync());
          else { this.owner.openSearch(); this.sync(); }
        })
      }.width('100%').padding(16)
      if (this.feedback.length > 0) {
        Row({ space: 8 }) {
          Text(this.feedback).fontColor('#B3261E').layoutWeight(1)
          Button('Retry').onClick(() => { this.owner.retryRefresh().then(() => this.sync()); })
        }.width('100%').padding({ left: 16, right: 16 })
      }
      if (this.searchActive) {
        TextInput({ text: this.query, placeholder: 'Search pages' }).onChange((value: string) => {
          this.query = value;
          this.owner.updateSearch(value, 250).then(() => this.sync());
        }).margin({ left: 16, right: 16, bottom: 8 })
      }
      Tabs({ index: 0 }) {
        ForEach(this.owner.store().tabs, (tab: string) => {
          TabContent() {
            List() {
              ForEach(this.rows, (row: PageRow) => {
                ListItem() {
                  Column() {
                    Row({ space: 12 }) {
                      Text(row.page.title).fontSize(17).layoutWeight(1).margin({ left: row.indent * 16 })
                      Text(row.page.status).fontSize(13).fontColor('#5B6B73')
                      Button('Menu').onClick(() => { this.owner.openMenu(row.page.id); this.sync(); })
                    }.width('100%').padding(16)
                    if (this.menuPageId === row.page.id) {
                      Row({ space: 8 }) {
                        ForEach(this.menuActions, (action: string) => {
                          if (action === 'trash') {
                            Button('Trash').onClick(() => { this.owner.chooseTrash(row.page.id); this.sync(); })
                          } else {
                            Button(action)
                          }
                        })
                      }.width('100%').padding({ left: 16, right: 16, bottom: 12 })
                    }
                  }.width('100%')
                }
              }, (row: PageRow) => row.page.id.toString())
            }.width('100%').height('100%')
          }.tabBar(tab)
        })
      }.layoutWeight(1).barMode(BarMode.Scrollable)
      if (this.confirmationPageId !== 0) {
        Row({ space: 12 }) {
          Text('Move this page to trash?').layoutWeight(1)
          Button('Confirm').onClick(() => { this.owner.confirmTrash().then(() => this.sync()); })
        }.width('100%').padding(16)
      }
    }.width('100%').height('100%')
  }
}
