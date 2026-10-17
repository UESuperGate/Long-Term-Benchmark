import { DemoIdentityResetService, IdentityResetFlowManager, IdentityResetPresenter, IdentityResetScreen, ResetAuthenticationType, ResetOperationState } from '../features/IdentityResetFeature';

@Entry
@Component
struct Index {
  private service: DemoIdentityResetService = new DemoIdentityResetService();
  private manager: IdentityResetFlowManager = new IdentityResetFlowManager(this.service);
  private presenter: IdentityResetPresenter = new IdentityResetPresenter(this.manager);
  @State private screen: IdentityResetScreen = IdentityResetScreen.Root;
  @State private confirmationVisible: boolean = false;
  @State private password: string = '';
  @State private resetAction: ResetOperationState = ResetOperationState.Uninitialized;
  @State private progressVisible: boolean = false;
  @State private errorMessage: string = '';
  @State private approvalUrl: string = '';
  @State private useOidc: boolean = false;

  build() {
    Column() {
      Column({ space: 4 }) {
        Text('Reset cryptographic identity').fontSize(24).fontWeight(FontWeight.Bold)
        Text('Use this only when recovery is unavailable').fontSize(13).fontColor('#64748B')
      }
      .alignItems(HorizontalAlign.Start)
      .padding(20)
      .width('100%')
      .backgroundColor('#FFFFFF')
      Column({ space: 14 }) {
        if (this.screen === IdentityResetScreen.Root) {
          Text('Resetting creates a new identity. Previously encrypted messages may remain unavailable.').fontColor('#B42318')
          Row() {
            Text('Use SSO approval demo')
            Blank()
            Toggle({ type: ToggleType.Switch, isOn: this.useOidc }).onChange((value: boolean) => {
              this.useOidc = value;
              this.service.authenticationType = value ? ResetAuthenticationType.Oidc : ResetAuthenticationType.Password;
            })
          }
          Button('Continue').id('identity_reset_continue').width('100%').fontColor('#B42318').onClick(() => {
            this.presenter.continue();
            this.refresh();
          })
          if (this.confirmationVisible) {
            Text('Confirm identity reset?').fontWeight(FontWeight.Bold)
            Row({ space: 10 }) {
              Button('Cancel').onClick(() => {
                this.presenter.dismissConfirmation();
                this.refresh();
              })
              Button('Reset identity').onClick(() => this.startConfirmedReset())
            }
          }
          if (this.errorMessage.length > 0) {
            Text(this.errorMessage).fontColor('#B42318')
            Button('Retry').onClick(() => {
              this.presenter.continue();
              this.refresh();
            })
          }
        }
        if (this.screen === IdentityResetScreen.Password) {
          Text('Confirm your account password to reset identity.')
          TextInput({ text: this.password, placeholder: 'Password' })
            .id('identity_reset_password')
            .type(InputType.Password)
            .onChange((value: string) => {
              this.presenter.setPassword(value);
              this.refresh();
            })
          Button('Reset identity')
            .enabled(this.password.length > 0 && this.resetAction !== ResetOperationState.Loading)
            .width('100%')
            .onClick(() => this.submitPasswordReset())
          if (this.resetAction === ResetOperationState.Failure) {
            Text(this.errorMessage).fontColor('#B42318')
          }
          if (this.resetAction === ResetOperationState.Success) {
            Text('Identity reset. Waiting for session verification...').fontColor('#0F766E')
            Button('Session verified').onClick(() => {
              this.presenter.sessionVerified();
              this.refresh();
            })
          }
        }
        if (this.screen === IdentityResetScreen.Oidc) {
          Text('Approve the reset with your identity provider.')
          Text(this.approvalUrl).fontColor('#2563EB')
          Button('Approval completed').onClick(() => {
            this.presenter.sessionVerified();
            this.refresh();
          })
        }
        if (this.screen === IdentityResetScreen.Complete) {
          Text('Identity reset complete').fontColor('#0F766E').fontWeight(FontWeight.Bold)
        }
        if (this.progressVisible) {
          Text('Reset in progress...').fontColor('#64748B')
        }
        if (this.screen !== IdentityResetScreen.Complete) {
          Button('Exit reset').width('100%').onClick(() => this.presenter.cancel().then(() => this.refresh()))
        }
      }
      .padding(20)
      .width('100%')
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }

  private refresh(): void {
    this.screen = this.presenter.screen;
    this.confirmationVisible = this.presenter.confirmationVisible;
    this.password = this.presenter.password;
    this.resetAction = this.presenter.resetAction;
    this.progressVisible = this.presenter.progressVisible;
    this.errorMessage = this.presenter.errorMessage;
    this.approvalUrl = this.presenter.approvalUrl;
  }

  private startConfirmedReset(): void {
    const pending: Promise<void> = this.presenter.confirmReset();
    this.refresh();
    pending.then(() => this.refresh());
  }

  private submitPasswordReset(): void {
    const pending: Promise<void> = this.presenter.submitPassword();
    this.refresh();
    pending.then(() => this.refresh());
  }
}
