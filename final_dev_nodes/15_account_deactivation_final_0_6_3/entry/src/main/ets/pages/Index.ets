import { AccountDeactivationPresenter, DeactivationAction, DemoAccountService } from '../features/AccountDeactivationFeature';

@Entry
@Component
struct Index {
  private service: DemoAccountService = new DemoAccountService();
  private presenter: AccountDeactivationPresenter = new AccountDeactivationPresenter(this.service, this.service);
  @State private screen: string = 'settings';
  @State private canDeactivate: boolean = false;
  @State private password: string = '';
  @State private eraseData: boolean = false;
  @State private action: DeactivationAction = DeactivationAction.Uninitialized;
  @State private errorMessage: string = '';

  aboutToAppear(): void {
    this.presenter.loadCapability().then(() => this.refresh());
  }

  build() {
    Column() {
      Column({ space: 4 }) {
        Text(this.screen === 'settings' ? 'Settings' : 'Deactivate account').fontSize(24).fontWeight(FontWeight.Bold)
        Text(this.screen === 'settings' ? 'Account and application preferences' : 'This action permanently disables your account').fontSize(13).fontColor('#64748B')
      }
      .alignItems(HorizontalAlign.Start)
      .padding(20)
      .width('100%')
      .backgroundColor('#FFFFFF')
      if (this.screen === 'settings') {
        Column({ space: 12 }) {
          Button('Notifications').width('100%')
          Button('Chat backup').width('100%')
          Button('Sign out').width('100%')
          if (this.canDeactivate) {
            Button('Deactivate account')
              .id('deactivate_account_entry')
              .width('100%')
              .fontColor('#B42318')
              .onClick(() => this.screen = 'deactivation')
          }
        }
        .padding(20)
        .width('100%')
      } else {
        Column({ space: 14 }) {
          Text('Your account cannot be recovered after deactivation.').fontColor('#B42318')
          Row() {
            Text('Erase all messages')
            Blank()
            Toggle({ type: ToggleType.Switch, isOn: this.eraseData })
              .enabled(this.action !== DeactivationAction.Loading)
              .onChange((value: boolean) => {
                this.presenter.setEraseData(value);
                this.refresh();
              })
          }
          TextInput({ text: this.password, placeholder: 'Confirm password' })
            .id('deactivation_password')
            .type(InputType.Password)
            .enabled(this.action !== DeactivationAction.Loading)
            .onChange((value: string) => {
              this.presenter.setPassword(value);
              this.refresh();
            })
          Button(this.action === DeactivationAction.Loading ? 'Deactivating...' : 'Deactivate account')
            .id('deactivate_submit')
            .enabled(this.presenter.submitEnabled())
            .width('100%')
            .fontColor('#B42318')
            .onClick(() => this.submitDeactivation(false))
          if (this.action === DeactivationAction.Confirming) {
            Text('Are you sure you want to deactivate this account?').fontWeight(FontWeight.Medium)
            Row({ space: 10 }) {
              Button('Cancel').onClick(() => {
                this.presenter.closeDialogs();
                this.refresh();
              })
              Button('Confirm deactivation').onClick(() => this.submitDeactivation(false))
            }
          }
          if (this.action === DeactivationAction.Failure) {
            Text(this.errorMessage).fontColor('#B42318')
            Row({ space: 10 }) {
              Button('Close').onClick(() => {
                this.presenter.closeDialogs();
                this.refresh();
              })
              Button('Retry').onClick(() => this.submitDeactivation(true))
            }
          }
          if (this.action === DeactivationAction.Success) {
            Text('Account deactivated').fontColor('#0F766E').fontWeight(FontWeight.Bold)
          }
        }
        .padding(20)
        .width('100%')
      }
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }

  private refresh(): void {
    this.canDeactivate = this.presenter.canDeactivateAccount;
    this.password = this.presenter.password;
    this.eraseData = this.presenter.eraseData;
    this.action = this.presenter.action;
    this.errorMessage = this.presenter.errorMessage;
  }

  private submitDeactivation(isRetry: boolean): void {
    const pending: Promise<void> = this.presenter.deactivateAccount(isRetry);
    this.refresh();
    pending.then(() => this.refresh());
  }
}
