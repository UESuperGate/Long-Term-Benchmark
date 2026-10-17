import { NotificationSettingsPresenter } from '../features/NotificationSettingsBase';

@Entry
@Component
struct Index {
  private presenter: NotificationSettingsPresenter = new NotificationSettingsPresenter();
  @State private notificationsEnabled: boolean = true;
  @State private callNotificationsEnabled: boolean = true;
  @State private mentionsEnabled: boolean = true;

  build() {
    Column() {
      Column({ space: 4 }) {
        Text('Notifications')
          .fontSize(24)
          .fontWeight(FontWeight.Bold)
        Text('Choose which events can notify you')
          .fontSize(13)
          .fontColor('#64748B')
      }
      .alignItems(HorizontalAlign.Start)
      .padding(20)
      .width('100%')
      .backgroundColor('#FFFFFF')

      Column({ space: 1 }) {
        this.SettingRow('All notifications', this.notificationsEnabled, (enabled: boolean) => {
          this.presenter.setNotificationsEnabled(enabled);
          this.notificationsEnabled = enabled;
        }, 'notifications_enabled')
        this.SettingRow('Incoming calls', this.callNotificationsEnabled, (enabled: boolean) => {
          this.presenter.setCallNotificationsEnabled(enabled);
          this.callNotificationsEnabled = enabled;
        }, 'call_notifications_enabled')
        this.SettingRow('Mentions and keywords', this.mentionsEnabled, (enabled: boolean) => {
          this.presenter.setMentionsEnabled(enabled);
          this.mentionsEnabled = enabled;
        }, 'mentions_enabled')
      }
      .padding({ left: 16, right: 16, top: 20 })
      .width('100%')
      Blank()
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }

  @Builder
  SettingRow(label: string, checked: boolean, onChange: (enabled: boolean) => void, controlId: string) {
    Row() {
      Text(label)
        .fontSize(16)
        .layoutWeight(1)
      Toggle({ type: ToggleType.Switch, isOn: checked })
        .onChange(onChange)
        .id(controlId)
    }
    .padding(16)
    .width('100%')
    .backgroundColor('#FFFFFF')
  }
}
