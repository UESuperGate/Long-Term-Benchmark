import { AccountClient } from '../services/AccountClient';

export class PreferencesBasePresenter {
  signedOut: boolean = false;
  notificationSettingsOpen: boolean = false;
  private client: AccountClient;

  constructor(client: AccountClient) {
    this.client = client;
  }

  openNotificationSettings(): void {
    this.notificationSettingsOpen = true;
  }

  async signOut(): Promise<void> {
    await this.client.logout();
    this.signedOut = true;
  }
}
