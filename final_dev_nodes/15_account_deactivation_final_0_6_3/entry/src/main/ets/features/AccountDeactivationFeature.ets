export enum DeactivationAction {
  Uninitialized = 'uninitialized',
  Confirming = 'confirming',
  Loading = 'loading',
  Success = 'success',
  Failure = 'failure'
}

export interface AccountCapabilityService {
  canDeactivateAccount(): Promise<boolean>;
}

export interface AccountDeactivationService {
  deactivateAccount(password: string, eraseData: boolean): Promise<void>;
}

export class DemoAccountService implements AccountCapabilityService, AccountDeactivationService {
  requestCount: number = 0;
  lastPassword: string = '';
  lastEraseData: boolean = false;

  async canDeactivateAccount(): Promise<boolean> {
    return true;
  }

  async deactivateAccount(password: string, eraseData: boolean): Promise<void> {
    this.requestCount += 1;
    this.lastPassword = password;
    this.lastEraseData = eraseData;
    if (password !== 'secret') {
      throw new Error('The password was rejected');
    }
  }
}

export class AccountDeactivationPresenter {
  canDeactivateAccount: boolean = false;
  password: string = '';
  eraseData: boolean = false;
  action: DeactivationAction = DeactivationAction.Uninitialized;
  errorMessage: string = '';
  private capability: AccountCapabilityService;
  private service: AccountDeactivationService;

  constructor(capability: AccountCapabilityService, service: AccountDeactivationService) {
    this.capability = capability;
    this.service = service;
  }

  async loadCapability(): Promise<void> {
    this.canDeactivateAccount = await this.capability.canDeactivateAccount();
  }

  submitEnabled(): boolean {
    return this.action === DeactivationAction.Uninitialized && this.password.length > 0;
  }

  setPassword(value: string): void {
    this.password = value.replace(/\n/g, '');
  }

  setEraseData(value: boolean): void {
    this.eraseData = value;
  }

  async deactivateAccount(isRetry: boolean): Promise<void> {
    if (this.action !== DeactivationAction.Confirming && !isRetry) {
      this.action = DeactivationAction.Confirming;
      return;
    }
    this.action = DeactivationAction.Loading;
    this.errorMessage = '';
    try {
      await this.service.deactivateAccount(this.password, this.eraseData);
      this.action = DeactivationAction.Success;
    } catch (error) {
      this.errorMessage = 'Account deactivation failed. Check your password and retry.';
      this.action = DeactivationAction.Failure;
    }
  }

  closeDialogs(): void {
    this.action = DeactivationAction.Uninitialized;
    this.errorMessage = '';
  }
}
