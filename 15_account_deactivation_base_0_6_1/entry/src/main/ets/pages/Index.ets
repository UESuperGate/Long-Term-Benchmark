import { PreferencesBasePresenter } from '../features/PreferencesBase';
import { AccountClient } from '../services/AccountClient';
import { createAccountClient } from '../services/NativeAccountClient';
import { AccountSessionControls } from '../components/AccountSessionControls';

@Entry
@Component
struct Index {
  private client: AccountClient = createAccountClient(getContext(this));
  private presenter: PreferencesBasePresenter = new PreferencesBasePresenter(this.client);
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
        AccountSessionControls({ client: this.client })
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
