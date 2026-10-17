import {
  DomainErrorCode,
  DomainFailure,
  DomainResult
} from '../../core/DomainResult';
import {
  MatrixAuthenticatedSession,
  MatrixAuthenticationService,
  MatrixHomeserverDetails,
  MatrixSessionHandle,
  MatrixSessionRestoreRequest,
  PasswordLoginRequest
} from '../api/MatrixAuthentication';
import {
  NativeBridgeAvailability,
  NativeClientOperationResult,
  NativeMatrixBridge
} from '../../nativebridge/Index';
import {
  MatrixClientServerApi,
  MatrixLoginResponse,
  MatrixWellKnownResult
} from '../../services/MatrixClientServerApi';

export interface MatrixPasswordApi {
  discoverHomeserver(serverName: string): Promise<MatrixWellKnownResult>;
  loginWithPassword(
    homeserverBaseUrl: string,
    username: string,
    password: string,
    deviceDisplayName: string
  ): Promise<MatrixLoginResponse>;
}

/**
 * Production authentication boundary. The native Matrix client owns runtime state,
 * while the HTTP login response is kept ephemeral until SessionPersistence splits it.
 */
export class NativeMatrixAuthenticationService implements MatrixAuthenticationService {
  private readonly bridge: NativeMatrixBridge;
  private readonly passwordApi: MatrixPasswordApi;

  constructor(
    bridge: NativeMatrixBridge,
    passwordApi: MatrixPasswordApi = new MatrixClientServerApi()
  ) {
    this.bridge = bridge;
    this.passwordApi = passwordApi;
  }

  async resolveHomeserver(serverNameOrUrl: string): Promise<DomainResult<MatrixHomeserverDetails>> {
    const normalized = serverNameOrUrl.trim();
    if (normalized.length === 0) {
      return DomainResult.fail<MatrixHomeserverDetails>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Homeserver is required',
        false
      ));
    }
    try {
      const discovery = await this.passwordApi.discoverHomeserver(normalized);
      if (!discovery.ok || discovery.homeserverBaseUrl.length === 0) {
        return DomainResult.fail<MatrixHomeserverDetails>(new DomainFailure(
          DomainErrorCode.ServiceUnavailable,
          discovery.errorMessage.length > 0 ? discovery.errorMessage : 'Homeserver discovery failed',
          true
        ));
      }
      return DomainResult.succeed<MatrixHomeserverDetails>({
        canonicalUrl: discovery.homeserverBaseUrl,
        serverName: this.serverName(discovery.homeserverBaseUrl),
        supportsPasswordLogin: true,
        supportsOidcLogin: false
      });
    } catch (error) {
      return DomainResult.fail<MatrixHomeserverDetails>(new DomainFailure(
        DomainErrorCode.NetworkUnavailable,
        'Homeserver discovery could not reach the server',
        true
      ));
    }
  }

  async loginWithPassword(
    homeserver: MatrixHomeserverDetails,
    request: PasswordLoginRequest
  ): Promise<DomainResult<MatrixAuthenticatedSession>> {
    if (request.username.trim().length === 0 || request.password.length === 0) {
      return DomainResult.fail<MatrixAuthenticatedSession>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Username and password are required',
        false
      ));
    }
    const readinessFailure = this.bridgeReadinessFailure();
    if (readinessFailure !== null) {
      return DomainResult.fail<MatrixAuthenticatedSession>(readinessFailure);
    }

    try {
      const login = await this.passwordApi.loginWithPassword(
        homeserver.canonicalUrl,
        request.username.trim(),
        request.password,
        request.deviceDisplayName
      );
      if (!login.ok || login.accessToken.length === 0 || login.userId.length === 0) {
        return DomainResult.fail<MatrixAuthenticatedSession>(new DomainFailure(
          DomainErrorCode.AuthenticationRejected,
          login.errorMessage.length > 0 ? login.errorMessage : 'Matrix password login was rejected',
          false
        ));
      }
      const nativeResult = await this.bridge.restoreClient({
        homeserverUrl: homeserver.canonicalUrl,
        userId: login.userId,
        deviceId: login.deviceId,
        accessToken: login.accessToken,
        refreshToken: null
      });
      if (!nativeResult.ok || nativeResult.client === null) {
        const message = nativeResult.error === null ?
          'Native Matrix session restoration failed' : nativeResult.error.message;
        return DomainResult.fail<MatrixAuthenticatedSession>(this.nativeFailure(message));
      }
      const handle = nativeResult.client.handle;
      return DomainResult.succeed<MatrixAuthenticatedSession>({
        sessionId: login.userId,
        userId: login.userId,
        deviceId: login.deviceId,
        homeserverUrl: homeserver.canonicalUrl,
        accessToken: login.accessToken,
        refreshToken: null,
        databasePassphrase: null,
        loginTimestampMs: Date.now(),
        handle: {
          sessionId: login.userId,
          runtimeId: this.runtimeId(handle)
        }
      });
    } catch (error) {
      return DomainResult.fail<MatrixAuthenticatedSession>(new DomainFailure(
        DomainErrorCode.NetworkUnavailable,
        'Matrix password login could not reach the server',
        true
      ));
    }
  }

  async restoreSession(request: MatrixSessionRestoreRequest): Promise<DomainResult<MatrixSessionHandle>> {
    const readinessFailure = this.bridgeReadinessFailure();
    if (readinessFailure !== null) {
      return DomainResult.fail<MatrixSessionHandle>(readinessFailure);
    }
    try {
      const nativeResult = await this.bridge.restoreClient({
        homeserverUrl: request.homeserverUrl,
        userId: request.userId,
        deviceId: request.deviceId,
        accessToken: request.accessToken,
        refreshToken: request.refreshToken
      });
      if (!nativeResult.ok || nativeResult.client === null) {
        const message = nativeResult.error === null ?
          'Native Matrix session restoration failed' : nativeResult.error.message;
        return DomainResult.fail<MatrixSessionHandle>(this.nativeFailure(message));
      }
      return DomainResult.succeed<MatrixSessionHandle>({
        sessionId: request.sessionId,
        runtimeId: this.runtimeId(nativeResult.client.handle)
      });
    } catch (error) {
      return DomainResult.fail<MatrixSessionHandle>(this.nativeFailure(
        'Native Matrix session restoration failed'
      ));
    }
  }

  async releaseSession(handle: MatrixSessionHandle): Promise<DomainResult<boolean>> {
    const nativeHandle = this.handleFromRuntimeId(handle.runtimeId);
    if (nativeHandle === null) {
      return DomainResult.fail<boolean>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Matrix runtime handle is invalid',
        false
      ));
    }
    try {
      const result = await this.bridge.releaseClient(nativeHandle);
      if (!result.ok) {
        return DomainResult.fail<boolean>(this.nativeFailure(
          result.error === null ? 'Native Matrix client release failed' : result.error.message
        ));
      }
      return DomainResult.succeed<boolean>(true);
    } catch (error) {
      return DomainResult.fail<boolean>(this.nativeFailure('Native Matrix client release failed'));
    }
  }

  private bridgeReadinessFailure(): DomainFailure | null {
    try {
      const status = this.bridge.getStatus();
      if (status.availability === NativeBridgeAvailability.Ready && status.sdkLinked) {
        return null;
      }
      return this.nativeFailure(status.message);
    } catch (error) {
      return this.nativeFailure('Native Matrix bridge status is unavailable');
    }
  }

  private nativeFailure(message: string): DomainFailure {
    return new DomainFailure(DomainErrorCode.NativeBridgeUnavailable, message, true);
  }

  private runtimeId(handle: number): string {
    return `native:${handle}`;
  }

  private handleFromRuntimeId(runtimeId: string): number | null {
    if (!runtimeId.startsWith('native:')) {
      return null;
    }
    const parsed = Number(runtimeId.substring('native:'.length));
    if (!Number.isSafeInteger(parsed) || parsed <= 0) {
      return null;
    }
    return parsed;
  }

  private serverName(url: string): string {
    const withoutScheme = url.replace(/^https?:\/\//, '');
    const slash = withoutScheme.indexOf('/');
    return slash >= 0 ? withoutScheme.substring(0, slash) : withoutScheme;
  }
}
