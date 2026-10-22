import { IdentityResetHandle, IdentityPasswordResetHandle, IdentityOidcResetHandle,
  IdentityResetService, ResetAuthenticationType } from './IdentityResetFeature';

// Session SDK boundary. Implementations supply SDK responses, never page state.
export interface IdentityResetSdkHandle {
  kind: ResetAuthenticationType;
  cancel(): Promise<void>;
  destroy(): void;
}

export interface PasswordResetSdkHandle extends IdentityResetSdkHandle {
  resetPassword(password: string): Promise<void>;
}

export interface OidcResetSdkHandle extends IdentityResetSdkHandle {
  url: string;
  resetOidc(): Promise<void>;
}

export interface IdentityResetSdkPort {
  startIdentityReset(): Promise<IdentityResetSdkHandle | undefined>;
  subscribeVerification(listener: (verified: boolean) => void): () => void;
}

export class PasswordResetHandle implements IdentityPasswordResetHandle {
  readonly kind: ResetAuthenticationType = ResetAuthenticationType.Password;
  private closed: boolean = false;

  readonly sdkHandle: PasswordResetSdkHandle;

  constructor(sdkHandle: PasswordResetSdkHandle) {
    this.sdkHandle = sdkHandle;
  }

  async resetPassword(password: string): Promise<void> {
    if (this.closed) {
      throw new Error('Reset handle closed');
    }
    await this.sdkHandle.resetPassword(password);
  }

  async cancel(): Promise<void> {
    if (!this.closed) {
      this.closed = true;
      try {
        await this.sdkHandle.cancel();
      } finally {
        this.sdkHandle.destroy();
      }
    }
  }
}

export class OidcResetHandle implements IdentityOidcResetHandle {
  readonly kind: ResetAuthenticationType = ResetAuthenticationType.Oidc;
  readonly url: string;
  private closed: boolean = false;

  readonly sdkHandle: OidcResetSdkHandle;

  constructor(sdkHandle: OidcResetSdkHandle) {
    this.sdkHandle = sdkHandle;
    this.url = sdkHandle.url;
  }

  async resetOidc(): Promise<void> {
    if (this.closed) {
      throw new Error('Reset handle closed');
    }
    await this.sdkHandle.resetOidc();
  }

  async cancel(): Promise<void> {
    if (!this.closed) {
      this.closed = true;
      try {
        await this.sdkHandle.cancel();
      } finally {
        this.sdkHandle.destroy();
      }
    }
  }
}

export class SessionIdentityResetService implements IdentityResetService {
  readonly port: IdentityResetSdkPort | undefined;

  constructor(port: IdentityResetSdkPort | undefined) {
    this.port = port;
  }

  get available(): boolean {
    return this.port !== undefined;
  }

  async startIdentityReset(): Promise<IdentityResetHandle | undefined> {
    if (this.port === undefined) {
      throw new Error('Identity reset SDK service unavailable');
    }
    const handle: IdentityResetSdkHandle | undefined = await this.port.startIdentityReset();
    if (handle === undefined) {
      return undefined;
    }
    if (handle.kind === ResetAuthenticationType.Password) {
      return new PasswordResetHandle(handle as PasswordResetSdkHandle);
    }
    return new OidcResetHandle(handle as OidcResetSdkHandle);
  }

  subscribeVerification(listener: (verified: boolean) => void): () => void {
    if (this.port === undefined) {
      return (): void => {};
    }
    return this.port.subscribeVerification(listener);
  }
}

// Composition root: a restored session may supply its SDK port. No default fake.
export class IdentityResetSession {
  private static port: IdentityResetSdkPort | undefined = undefined;

  static configure(port: IdentityResetSdkPort | undefined): void {
    IdentityResetSession.port = port;
  }

  static createService(): SessionIdentityResetService {
    return new SessionIdentityResetService(IdentityResetSession.port);
  }
}
