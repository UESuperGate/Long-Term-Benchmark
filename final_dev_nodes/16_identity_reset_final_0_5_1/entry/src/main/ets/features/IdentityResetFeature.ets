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
  readonly available: boolean;
  startIdentityReset(): Promise<IdentityResetHandle | undefined>;
  subscribeVerification(listener: (verified: boolean) => void): () => void;
}

export type ResetStateListener = (state: ResetOperationState) => void;

export class IdentityResetFlowManager {
  handleState: ResetOperationState = ResetOperationState.Uninitialized;
  currentHandle: IdentityResetHandle | undefined = undefined;
  completionWatcherActive: boolean = false;
  resetJobActive: boolean = false;
  private service: IdentityResetService;
  private pendingHandle: Promise<IdentityResetHandle | undefined> | undefined = undefined;
  private stateListeners: ResetStateListener[] = [];
  cleanupHistory: string[] = [];
  private generation: number = 0;
  private unsubscribeVerification: (() => void) | undefined = undefined;
  verified: boolean = false;

  constructor(service: IdentityResetService) {
    this.service = service;
  }

  serviceAvailable(): boolean {
    return this.service.available;
  }

  watchVerification(listener: () => void): void {
    this.unsubscribeVerification?.();
    this.completionWatcherActive = this.service.available;
    this.unsubscribeVerification = this.service.subscribeVerification((verified: boolean) => {
      if (!this.completionWatcherActive) {
        return;
      }
      this.verified = verified;
      if (verified) {
        listener();
      }
    });
  }

  stopVerification(): void {
    this.completionWatcherActive = false;
    this.unsubscribeVerification?.();
    this.unsubscribeVerification = undefined;
  }

  subscribeHandleState(listener: ResetStateListener): () => void {
    this.stateListeners.push(listener);
    listener(this.handleState);
    return (): void => {
      const index: number = this.stateListeners.indexOf(listener);
      if (index >= 0) {
        this.stateListeners.splice(index, 1);
      }
    };
  }

  private updateHandleState(state: ResetOperationState): void {
    this.handleState = state;
    this.stateListeners.forEach((listener: ResetStateListener) => listener(state));
  }

  async getResetHandle(): Promise<IdentityResetHandle | undefined> {
    if (this.handleState === ResetOperationState.Success) {
      return this.currentHandle;
    }
    if (this.handleState === ResetOperationState.Loading && this.pendingHandle !== undefined) {
      return this.pendingHandle;
    }
    this.updateHandleState(ResetOperationState.Loading);
    this.pendingHandle = this.acquireResetHandle();
    return this.pendingHandle;
  }

  private async acquireResetHandle(): Promise<IdentityResetHandle | undefined> {
    const generation: number = this.generation;
    try {
      const handle: IdentityResetHandle | undefined = await this.service.startIdentityReset();
      if (generation !== this.generation) {
        await handle?.cancel();
        return undefined;
      }
      if (handle === undefined) {
        this.updateHandleState(ResetOperationState.Failure);
        return undefined;
      }
      this.currentHandle = handle;
      this.updateHandleState(ResetOperationState.Success);
      return handle;
    } catch (error) {
      if (generation === this.generation) {
        this.updateHandleState(ResetOperationState.Failure);
      }
      return undefined;
    } finally {
      if (generation === this.generation) {
        this.pendingHandle = undefined;
      }
    }
  }

  cleanupAfterFailure(): void {
    this.currentHandle = undefined;
    this.pendingHandle = undefined;
    this.resetJobActive = false;
    this.cleanupHistory.push('failure');
    this.updateHandleState(ResetOperationState.Uninitialized);
  }

  async cancel(reason: string = 'cancel'): Promise<void> {
    this.generation += 1;
    const handle: IdentityResetHandle | undefined = this.currentHandle;
    this.currentHandle = undefined;
    this.pendingHandle = undefined;
    this.resetJobActive = false;
    this.stopVerification();
    this.cleanupHistory.push(reason);
    this.updateHandleState(ResetOperationState.Uninitialized);
    await handle?.cancel();
  }
}

export class IdentityResetNavigation {
  completed: boolean = false;
  completionCount: number = 0;

  onDone(): void {
    if (!this.completed) {
      this.completed = true;
      this.completionCount += 1;
    }
  }
}

export class IdentityResetPresenter {
  screen: IdentityResetScreen = IdentityResetScreen.Root;
  confirmationVisible: boolean = false;
  resetAction: ResetOperationState = ResetOperationState.Uninitialized;
  password: string = '';
  errorMessage: string = '';
  approvalUrl: string = '';
  approvalSurface: string = '';
  oidcOpenCount: number = 0;
  progressVisible: boolean = false;
  completionCount: number = 0;
  manager: IdentityResetFlowManager;
  private listeners: (() => void)[] = [];
  private generation: number = 0;
  private disposed: boolean = false;
  readonly navigation: IdentityResetNavigation;

  constructor(manager: IdentityResetFlowManager,
    navigation: IdentityResetNavigation = new IdentityResetNavigation()) {
    this.manager = manager;
    this.navigation = navigation;
    this.manager.watchVerification(() => this.onSessionVerified());
  }

  subscribe(listener: () => void): () => void {
    this.listeners.push(listener);
    return (): void => {
      this.listeners = this.listeners.filter((value: () => void) => value !== listener);
    };
  }

  private publish(): void {
    this.listeners.forEach((listener: () => void) => listener());
  }

  continue(): void {
    this.confirmationVisible = true;
  }

  dismissConfirmation(): void {
    this.confirmationVisible = false;
  }

  async confirmReset(): Promise<void> {
    const generation: number = this.generation;
    if (this.disposed) {
      return;
    }
    if (!this.manager.completionWatcherActive) {
      this.manager.watchVerification(() => this.onSessionVerified());
    }
    this.confirmationVisible = false;
    this.progressVisible = true;
    this.publish();
    const handle: IdentityResetHandle | undefined = await this.manager.getResetHandle();
    if (generation !== this.generation || this.disposed) {
      return;
    }
    this.progressVisible = false;
    if (handle === undefined) {
      this.errorMessage = this.manager.serviceAvailable() ?
        'Could not start identity reset. Retry when the service is available.' :
        'Identity reset SDK service unavailable';
      this.screen = IdentityResetScreen.Root;
      this.manager.cleanupAfterFailure();
      this.publish();
      return;
    }
    if (handle.kind === ResetAuthenticationType.Password) {
      this.screen = IdentityResetScreen.Password;
      this.publish();
      return;
    }
    const oidcHandle: IdentityOidcResetHandle = handle as IdentityOidcResetHandle;
    this.approvalUrl = oidcHandle.url;
    this.approvalSurface = 'embedded_webview';
    this.oidcOpenCount += 1;
    this.screen = IdentityResetScreen.Oidc;
    this.manager.resetJobActive = true;
    this.publish();
    try {
      await oidcHandle.resetOidc();
      if (generation !== this.generation || this.disposed) {
        return;
      }
      this.resetAction = ResetOperationState.Success;
      this.progressVisible = true;
      this.onSessionVerified();
    } catch (error) {
      if (generation === this.generation && !this.disposed) {
        this.errorMessage = 'Identity reset approval failed';
        await this.cleanup('oidc_failure');
      }
    }
    this.publish();
  }

  setPassword(value: string): void {
    this.password = value;
    if (this.resetAction === ResetOperationState.Failure) {
      this.resetAction = ResetOperationState.Uninitialized;
      this.errorMessage = '';
    }
  }

  async submitPassword(): Promise<void> {
    if (this.disposed || this.password.length === 0 || this.manager.currentHandle === undefined ||
      this.resetAction === ResetOperationState.Loading) {
      return;
    }
    const generation: number = this.generation;
    const handle: IdentityPasswordResetHandle = this.manager.currentHandle as IdentityPasswordResetHandle;
    this.resetAction = ResetOperationState.Loading;
    this.progressVisible = true;
    this.publish();
    try {
      await handle.resetPassword(this.password);
      if (generation !== this.generation || this.disposed) {
        return;
      }
      this.resetAction = ResetOperationState.Success;
      this.onSessionVerified();
    } catch (error) {
      if (generation !== this.generation || this.disposed) {
        return;
      }
      this.resetAction = ResetOperationState.Failure;
      this.errorMessage = 'The password is incorrect. Edit it and retry.';
      this.progressVisible = false;
    }
    this.publish();
  }

  private onSessionVerified(): void {
    if (!this.disposed && this.manager.verified && this.resetAction === ResetOperationState.Success &&
      this.manager.completionWatcherActive) {
      this.progressVisible = false;
      this.manager.stopVerification();
      this.manager.resetJobActive = false;
      this.screen = IdentityResetScreen.Complete;
      this.completionCount += 1;
      this.navigation.onDone();
      this.publish();
    }
  }

  async cancel(): Promise<void> {
    await this.cleanup('cancel');
  }

  async oidcReturned(): Promise<void> {
    await this.cleanup('oidc_return');
  }

  async dispose(): Promise<void> {
    this.disposed = true;
    try {
      await this.cleanup('node_destroy');
    } finally {
      this.listeners = [];
    }
  }

  private async cleanup(reason: string): Promise<void> {
    this.generation += 1;
    try {
      await this.manager.cancel(reason);
    } finally {
      this.screen = IdentityResetScreen.Root;
      this.confirmationVisible = false;
      this.resetAction = ResetOperationState.Uninitialized;
      this.progressVisible = false;
      this.errorMessage = '';
      this.approvalUrl = '';
      this.approvalSurface = '';
      this.publish();
    }
  }
}
