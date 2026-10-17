export class PreferencesBasePresenter {
  signedOut: boolean = false;
  notificationSettingsOpen: boolean = false;

  openNotificationSettings(): void {
    this.notificationSettingsOpen = true;
  }

  signOut(): void {
    this.signedOut = true;
  }
}
