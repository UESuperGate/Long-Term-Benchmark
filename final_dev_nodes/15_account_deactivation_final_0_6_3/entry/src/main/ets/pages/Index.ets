import { AccountDeactivationPresenter, DeactivationAction, AccountClient } from '../features/AccountDeactivationFeature';
import { createAccountClient } from '../services/NativeAccountClient';
import { AccountSessionControls } from '../components/AccountSessionControls';

@CustomDialog
struct DeactivationLoadingDialog {
  controller: CustomDialogController;

  build() {
    Column({ space: 16 }) {
      LoadingProgress().width(32).height(32)
      Text('Please wait').id('deactivation_loading_message')
    }
    .id('deactivation_loading_dialog')
    .padding(32)
    .width('100%')
  }
}

@Entry
@Component
struct Index {
  private service: AccountClient = createAccountClient(getContext(this));
  private presenter: AccountDeactivationPresenter = new AccountDeactivationPresenter(this.service, this.service);
  @State private screen: string = 'settings';
  @State private canDeactivate: boolean = false;
  @State private password: string = '';
  @State private eraseData: boolean = false;
  @State private action: DeactivationAction = DeactivationAction.Uninitialized;
  @State private submitEnabled: boolean = false;
  @State private errorMessage: string = '';
  private pageVisible: boolean = false;
  private loadingDialogOpen: boolean = false;
  private loadingDialog: CustomDialogController = new CustomDialogController({
    builder: DeactivationLoadingDialog(),
    autoCancel: false,
    isModal: true,
    onWillDismiss: () => {
      // Only operation completion or page disposal closes the progress modal.
    }
  });

  aboutToAppear(): void {
    this.pageVisible = true;
    this.presenter.loadCapability().then(() => this.refresh());
  }

  aboutToDisappear(): void {
    this.pageVisible = false;
    this.syncLoadingDialog();
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
          AccountSessionControls({ client: this.service, onSessionChange: () => {
            this.presenter.loadCapability().then(() => this.refresh());
          } })
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
              .onChange((value: boolean) => {
                this.presenter.setEraseData(value);
                this.refresh();
              })
          }
          TextInput({ text: this.password, placeholder: 'Confirm password' })
            .id('deactivation_password')
            .type(InputType.Password)
            .onChange((value: string) => {
              this.presenter.setPassword(value);
              this.refresh();
            })
          Button(this.action === DeactivationAction.Loading ? 'Deactivating...' : 'Deactivate account')
            .id('deactivate_submit')
            .enabled(this.submitEnabled)
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
            Button('Back to settings').onClick(() => {
              this.presenter.setPassword('');
              this.presenter.setEraseData(false);
              this.presenter.closeDialogs();
              this.screen = 'settings';
              this.presenter.loadCapability().then(() => this.refresh());
            })
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
    this.submitEnabled = this.presenter.submitEnabled();
    this.errorMessage = this.presenter.errorMessage;
    this.syncLoadingDialog();
  }

  private syncLoadingDialog(): void {
    const shouldOpen: boolean = this.pageVisible && this.action === DeactivationAction.Loading;
    if (shouldOpen === this.loadingDialogOpen) {
      return;
    }
    this.loadingDialogOpen = shouldOpen;
    this.getUIContext().runScopedTask(() => {
      if (shouldOpen) {
        this.loadingDialog.open();
      } else {
        this.loadingDialog.close();
      }
    });
  }

  private submitDeactivation(isRetry: boolean): void {
    const pending: Promise<void> = this.presenter.deactivateAccount(isRetry);
    this.refresh();
    pending.then(() => this.refresh());
  }
}
