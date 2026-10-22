import { IdentityResetFlowManager, IdentityResetPresenter, IdentityResetNavigation, IdentityResetScreen, ResetOperationState } from '../features/IdentityResetFeature';
import { IdentityResetSession, SessionIdentityResetService } from '../features/IdentityResetServices';
import webview from '@ohos.web.webview';

@CustomDialog
struct IdentityResetProgressDialog {
  controller: CustomDialogController;

  build() {
    Column({ space: 12 }) {
      LoadingProgress().width(32).height(32)
      Text('Reset in progress...')
    }
    .padding(24)
    .width(260)
    .id('identity_reset_progress')
  }
}

@Entry
@Component
struct Index {
  private service: SessionIdentityResetService = IdentityResetSession.createService();
  private manager: IdentityResetFlowManager = new IdentityResetFlowManager(this.service);
  private navigation: IdentityResetNavigation = new IdentityResetNavigation();
  private presenter: IdentityResetPresenter = new IdentityResetPresenter(this.manager, this.navigation);
  @State private screen: IdentityResetScreen = IdentityResetScreen.Root;
  @State private confirmationVisible: boolean = false;
  @State private password: string = '';
  @State private resetAction: ResetOperationState = ResetOperationState.Uninitialized;
  @State private progressVisible: boolean = false;
  @State private errorMessage: string = '';
  @State private approvalUrl: string = '';
  private unsubscribe: (() => void) | undefined = undefined;
  private hidden: boolean = false;
  private webController: webview.WebviewController = new webview.WebviewController();
  private progressDialog: CustomDialogController = new CustomDialogController({
    builder: IdentityResetProgressDialog(),
    autoCancel: false
  });

  aboutToAppear(): void {
    this.unsubscribe = this.presenter.subscribe(() => this.refresh());
  }

  aboutToDisappear(): void {
    this.progressDialog.close();
    this.unsubscribe?.();
    this.presenter.dispose();
  }

  onPageHide(): void {
    this.hidden = true;
  }

  onPageShow(): void {
    if (this.hidden && this.screen === IdentityResetScreen.Oidc) {
      this.presenter.oidcReturned();
    }
    this.hidden = false;
  }

  onBackPress(): boolean {
    if (this.screen === IdentityResetScreen.Oidc) {
      this.presenter.oidcReturned();
      return true;
    }
    return false;
  }

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
          Button('Continue').id('identity_reset_continue').width('100%').fontColor('#B42318').onClick(() => {
            this.presenter.continue();
            this.refresh();
          })
          if (this.confirmationVisible) {
            Text('Confirm identity reset?').fontWeight(FontWeight.Bold)
            Row({ space: 10 }) {
              Button('Cancel').id('identity_reset_cancel_confirmation').onClick(() => {
                this.presenter.dismissConfirmation();
                this.refresh();
              })
              Button('Reset identity').id('identity_reset_confirm').onClick(() => this.startConfirmedReset())
            }
          }
          if (this.errorMessage.length > 0) {
            Text(this.errorMessage).fontColor('#B42318')
            Button('Retry').id('identity_reset_retry').onClick(() => {
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
            .id('identity_reset_password_submit')
            .enabled(this.password.length > 0 && this.resetAction !== ResetOperationState.Loading)
            .width('100%')
            .onClick(() => this.submitPasswordReset())
          if (this.resetAction === ResetOperationState.Failure) {
            Text(this.errorMessage).fontColor('#B42318')
          }
          if (this.resetAction === ResetOperationState.Success) {
            Text('Identity reset. Waiting for session verification...').fontColor('#0F766E')
          }
        }
        if (this.screen === IdentityResetScreen.Oidc) {
          Text('Approve the reset with your identity provider.')
          Text(this.approvalUrl).fontColor('#2563EB').id('identity_reset_oidc_url')
          Web({ src: this.approvalUrl, controller: this.webController })
            .id('identity_reset_oidc_webview')
            .height(320)
            .javaScriptAccess(false)
        }
        if (this.screen === IdentityResetScreen.Complete) {
          Text('Identity reset complete').fontColor('#0F766E').fontWeight(FontWeight.Bold)
        }
        if (this.screen !== IdentityResetScreen.Complete) {
          Button('Exit reset').id('identity_reset_exit').width('100%').onClick(() => this.presenter.cancel().then(() => this.refresh()))
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
    if (this.presenter.progressVisible !== this.progressVisible) {
      if (this.presenter.progressVisible) {
        this.progressDialog.open();
      } else {
        this.progressDialog.close();
      }
    }
    this.screen = this.navigation.completed ? IdentityResetScreen.Complete : this.presenter.screen;
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
