export class NotificationSettingsPresenter {
  notificationsEnabled: boolean = true;
  callNotificationsEnabled: boolean = true;
  mentionsEnabled: boolean = true;

  setNotificationsEnabled(enabled: boolean): void {
    this.notificationsEnabled = enabled;
  }

  setCallNotificationsEnabled(enabled: boolean): void {
    this.callNotificationsEnabled = enabled;
  }

  setMentionsEnabled(enabled: boolean): void {
    this.mentionsEnabled = enabled;
  }
}
