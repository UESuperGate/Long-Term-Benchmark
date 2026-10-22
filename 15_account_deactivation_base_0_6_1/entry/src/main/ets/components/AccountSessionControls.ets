import { AccountClient } from '../services/AccountClient';
import { createAccountClient } from '../services/NativeAccountClient';

@Component
export struct AccountSessionControls {
  client: AccountClient = createAccountClient(getContext(this));
  onSessionChange: () => void = () => {};
  @State private homeserver: string = '';
  @State private user: string = '';
  @State private password: string = '';
  @State private currentUser: string = '';
  @State private busy: boolean = true;
  @State private cleanupPending: boolean = false;
  @State private errorMessage: string = '';

  aboutToAppear(): void {
    this.client.restore().then(() => this.completed()).catch(() => {
      this.errorMessage = 'Unable to restore the secure account session';
      this.completed();
    });
  }

  build() {
    Column({ space: 12 }) {
      if (this.currentUser.length > 0) {
        Text(this.currentUser).id('account_session_user')
        Button('Sign out').id('account_sign_out').enabled(!this.busy).onClick(() => this.signOut())
      } else if (this.cleanupPending) {
        Text('Local session cleanup is incomplete')
        Button('Retry cleanup').enabled(!this.busy).onClick(() => this.retryCleanup())
      } else {
        TextInput({ text: this.homeserver, placeholder: 'Homeserver (https://...)' })
          .id('account_homeserver').enabled(!this.busy).onChange((value: string) => this.homeserver = value)
        TextInput({ text: this.user, placeholder: 'User ID' })
          .id('account_user').enabled(!this.busy).onChange((value: string) => this.user = value)
        TextInput({ text: this.password, placeholder: 'Password' }).type(InputType.Password)
          .id('account_password').enabled(!this.busy).onChange((value: string) => this.password = value)
        Button('Sign in').id('account_sign_in').enabled(!this.busy && this.homeserver.length > 0 &&
          this.user.length > 0 && this.password.length > 0).onClick(() => this.signIn())
      }
      if (this.busy) {
        LoadingProgress().width(24).height(24)
      }
      if (this.errorMessage.length > 0) {
        Text(this.errorMessage).fontColor('#B42318')
      }
    }.width('100%')
  }

  private completed(): void {
    this.busy = false;
    this.currentUser = this.client.userId();
    this.cleanupPending = this.client.needsCleanup();
    this.onSessionChange();
  }

  private signIn(): void {
    this.busy = true;
    this.errorMessage = '';
    const pending: Promise<void> = this.client.login(this.homeserver, this.user, this.password);
    this.password = '';
    pending.then(() => this.completed()).catch(() => {
      this.errorMessage = 'Sign in failed. Check the server and credentials.';
      this.completed();
    });
  }

  private signOut(): void {
    this.busy = true;
    this.errorMessage = '';
    this.client.logout().then(() => this.completed()).catch(() => {
      this.errorMessage = 'Sign out failed';
      this.completed();
    });
  }

  private retryCleanup(): void {
    this.busy = true;
    this.errorMessage = '';
    this.client.retryCleanup().then(() => this.completed()).catch(() => {
      this.errorMessage = 'Unable to clear local session data';
      this.completed();
    });
  }
}
