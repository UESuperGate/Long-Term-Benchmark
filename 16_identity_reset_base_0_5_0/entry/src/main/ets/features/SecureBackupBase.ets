export enum BackupState {
  Disabled = 'disabled',
  Enabled = 'enabled',
  Recovering = 'recovering'
}

export class SecureBackupBasePresenter {
  backupState: BackupState = BackupState.Disabled;
  recoveryKey: string = '';

  enableBackup(): void {
    this.backupState = BackupState.Enabled;
  }

  recoverWithKey(value: string): void {
    this.recoveryKey = value.trim();
    if (this.recoveryKey.length > 0) {
      this.backupState = BackupState.Recovering;
    }
  }
}
