export enum IdentityResetScreen {
  Root = 'reset_root',
  Password = 'reset_password',
  Oidc = 'reset_oidc',
  Complete = 'complete'
}

export enum ResetOperationState {
  Uninitialized = 'uninitialized',
  Loading = 'loading',
  Success = 'success',
  Failure = 'failure'
}

export enum ResetAuthenticationType {
  Password = 'password',
  Oidc = 'oidc'
}

export interface IdentityResetHandle {
  kind: ResetAuthenticationType;
  cancel(): Promise<void>;
}

export interface IdentityPasswordResetHandle extends IdentityResetHandle {
  resetPassword(password: string): Promise<void>;
}

export interface IdentityOidcResetHandle extends IdentityResetHandle {
  url: string;
  resetOidc(): Promise<void>;
}

export interface IdentityResetService {
  startIdentityReset(): Promise<IdentityResetHandle | undefined>;
}

export class DemoPasswordResetHandle implements IdentityPasswordResetHandle {
  kind: ResetAuthenticationType = ResetAuthenticationType.Password;
  cancelled: boolean = false;

  async resetPassword(password: string): Promise<void> {
    if (password !== 'secret') {
      throw new Error('Password rejected');
    }
  }

  async cancel(): Promise<void> {
    this.cancelled = true;
  }
}

export class DemoOidcResetHandle implements IdentityOidcResetHandle {
  kind: ResetAuthenticationType = ResetAuthenticationType.Oidc;
  url: string = 'https://id.example/reset';
  cancelled: boolean = false;

  async resetOidc(): Promise<void> {
  }

  async cancel(): Promise<void> {
    this.cancelled = true;
  }
}

export class DemoIdentityResetService implements IdentityResetService {
  authenticationType: ResetAuthenticationType = ResetAuthenticationType.Password;
  shouldFail: boolean = false;

  async startIdentityReset(): Promise<IdentityResetHandle | undefined> {
    if (this.shouldFail) {
      throw new Error('Unable to create identity reset handle');
    }
    if (this.authenticationType === ResetAuthenticationType.Oidc) {
      return new DemoOidcResetHandle();
    }
    return new DemoPasswordResetHandle();
  }
}

export class IdentityResetFlowManager {
  handleState: ResetOperationState = ResetOperationState.Uninitialized;
  currentHandle: IdentityResetHandle | undefined = undefined;
  completionWatcherActive: boolean = false;
  resetJobActive: boolean = false;
  private service: IdentityResetService;

  constructor(service: IdentityResetService) {
    this.service = service;
  }

  async getResetHandle(): Promise<IdentityResetHandle | undefined> {
    if (this.handleState === ResetOperationState.Loading || this.handleState === ResetOperationState.Success) {
      return this.currentHandle;
    }
    this.handleState = ResetOperationState.Loading;
    try {
      const handle: IdentityResetHandle | undefined = await this.service.startIdentityReset();
      if (handle === undefined) {
        this.handleState = ResetOperationState.Failure;
        return undefined;
      }
      this.currentHandle = handle;
      this.handleState = ResetOperationState.Success;
      this.completionWatcherActive = true;
      return handle;
    } catch (error) {
      this.handleState = ResetOperationState.Failure;
      return undefined;
    }
  }

  async cancel(): Promise<void> {
    if (this.currentHandle !== undefined) {
      await this.currentHandle.cancel();
    }
    this.currentHandle = undefined;
    this.handleState = ResetOperationState.Uninitialized;
    this.resetJobActive = false;
    this.completionWatcherActive = false;
  }
}

export class IdentityResetPresenter {
  screen: IdentityResetScreen = IdentityResetScreen.Root;
  confirmationVisible: boolean = false;
  resetAction: ResetOperationState = ResetOperationState.Uninitialized;
  password: string = '';
  errorMessage: string = '';
  approvalUrl: string = '';
  progressVisible: boolean = false;
  completionCount: number = 0;
  manager: IdentityResetFlowManager;

  constructor(manager: IdentityResetFlowManager) {
    this.manager = manager;
  }

  continue(): void {
    this.confirmationVisible = true;
  }

  dismissConfirmation(): void {
    this.confirmationVisible = false;
  }

  async confirmReset(): Promise<void> {
    this.confirmationVisible = false;
    this.progressVisible = true;
    const handle: IdentityResetHandle | undefined = await this.manager.getResetHandle();
    this.progressVisible = false;
    if (handle === undefined) {
      this.errorMessage = 'Could not start identity reset. Retry when the service is available.';
      this.screen = IdentityResetScreen.Root;
      return;
    }
    if (handle.kind === ResetAuthenticationType.Password) {
      this.screen = IdentityResetScreen.Password;
      return;
    }
    const oidcHandle: IdentityOidcResetHandle = handle as IdentityOidcResetHandle;
    this.approvalUrl = oidcHandle.url;
    this.screen = IdentityResetScreen.Oidc;
    this.manager.resetJobActive = true;
    await oidcHandle.resetOidc();
    this.resetAction = ResetOperationState.Success;
    this.progressVisible = true;
  }

  setPassword(value: string): void {
    this.password = value;
    if (this.resetAction === ResetOperationState.Failure) {
      this.resetAction = ResetOperationState.Uninitialized;
      this.errorMessage = '';
    }
  }

  async submitPassword(): Promise<void> {
    if (this.password.length === 0 || this.manager.currentHandle === undefined) {
      return;
    }
    const handle: IdentityPasswordResetHandle = this.manager.currentHandle as IdentityPasswordResetHandle;
    this.resetAction = ResetOperationState.Loading;
    this.progressVisible = true;
    try {
      await handle.resetPassword(this.password);
      this.resetAction = ResetOperationState.Success;
    } catch (error) {
      this.resetAction = ResetOperationState.Failure;
      this.errorMessage = 'The password is incorrect. Edit it and retry.';
      this.progressVisible = false;
    }
  }

  sessionVerified(): void {
    if (this.resetAction === ResetOperationState.Success && this.manager.completionWatcherActive) {
      this.progressVisible = false;
      this.manager.completionWatcherActive = false;
      this.manager.resetJobActive = false;
      this.screen = IdentityResetScreen.Complete;
      this.completionCount += 1;
    }
  }

  async cancel(): Promise<void> {
    await this.manager.cancel();
    this.screen = IdentityResetScreen.Root;
    this.confirmationVisible = false;
    this.resetAction = ResetOperationState.Uninitialized;
    this.progressVisible = false;
    this.errorMessage = '';
  }
}
