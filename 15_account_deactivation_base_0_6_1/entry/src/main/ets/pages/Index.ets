import { PreferencesBasePresenter } from '../features/PreferencesBase';

@Entry
@Component
struct Index {
  private presenter: PreferencesBasePresenter = new PreferencesBasePresenter();
  @State private status: string = '';

  build() {
    Column() {
      Column({ space: 4 }) {
        Text('Settings').fontSize(24).fontWeight(FontWeight.Bold)
        Text('Account and application preferences').fontSize(13).fontColor('#64748B')
      }
      .alignItems(HorizontalAlign.Start)
      .padding(20)
      .width('100%')
      .backgroundColor('#FFFFFF')
      Column({ space: 12 }) {
        Button('Notifications').width('100%').onClick(() => {
          this.presenter.openNotificationSettings();
          this.status = 'Notification settings opened';
        })
        Button('Chat backup').width('100%')
        Button('Blocked users').width('100%')
        Button('Sign out').width('100%').onClick(() => {
          this.presenter.signOut();
          this.status = 'Signed out';
        })
        Text(this.status).fontColor('#64748B')
      }
      .padding(20)
      .width('100%')
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }

}
