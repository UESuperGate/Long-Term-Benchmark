import { BackupState, SecureBackupBasePresenter } from '../features/SecureBackupBase';

@Entry
@Component
struct Index {
  private presenter: SecureBackupBasePresenter = new SecureBackupBasePresenter();
  @State private recoveryKey: string = '';
  @State private backupState: BackupState = BackupState.Disabled;

  build() {
    Column() {
      Column({ space: 4 }) {
        Text('Chat backup').fontSize(24).fontWeight(FontWeight.Bold)
        Text('Protect and recover encrypted messages').fontSize(13).fontColor('#64748B')
      }
      .alignItems(HorizontalAlign.Start)
      .padding(20)
      .width('100%')
      .backgroundColor('#FFFFFF')
      Column({ space: 14 }) {
        Text(`Backup state: ${this.backupState}`).width('100%')
        Button('Enable backup').width('100%').onClick(() => {
          this.presenter.enableBackup();
          this.backupState = this.presenter.backupState;
        })
        TextInput({ text: this.recoveryKey, placeholder: 'Recovery key' })
          .onChange((value: string) => {
            this.recoveryKey = value;
          })
        Button('Recover').width('100%').enabled(this.recoveryKey.length > 0).onClick(() => {
          this.presenter.recoverWithKey(this.recoveryKey);
          this.backupState = this.presenter.backupState;
        })
      }
      .padding(20)
      .width('100%')
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }

}
