import { describe, expect, it } from '@ohos/hypium';
import {
  DomainErrorCode,
  DomainFailure,
  DomainResult
} from '../main/ets/core/DomainResult';
import {
  MatrixAuthenticatedSession,
  MatrixAuthenticationService,
  MatrixHomeserverDetails,
  MatrixSessionHandle,
  MatrixSessionRestoreRequest,
  PasswordLoginRequest
} from '../main/ets/matrix/api/MatrixAuthentication';
import { RootNavigationPhase } from '../main/ets/appnav/RootNavigationState';
import { RootNavigationStateMachine } from '../main/ets/appnav/RootNavigationStateMachine';
import { RootSessionCoordinator } from '../main/ets/appnav/RootSessionCoordinator';
import { PasswordLoginCoordinator, PasswordLoginInput } from '../main/ets/features/login/PasswordLoginCoordinator';
import {
  SessionCredentialSecret,
  SessionMetadata
} from '../main/ets/session/SessionModels';
import { SessionPersistence } from '../main/ets/session/SessionPersistence';
import {
  SessionCredentialLookup,
  SessionCredentialStore,
  SessionMetadataLookup,
  SessionMetadataStore
} from '../main/ets/session/SessionStores';

class MemoryMetadataStore implements SessionMetadataStore {
  metadata: SessionMetadata | null = null;
  failSave: boolean = false;

  async getLatest(): Promise<DomainResult<SessionMetadataLookup>> {
    return DomainResult.succeed<SessionMetadataLookup>({
      found: this.metadata !== null,
      metadata: this.metadata
    });
  }

  async getById(sessionId: string): Promise<DomainResult<SessionMetadataLookup>> {
    const found = this.metadata !== null && this.metadata.sessionId === sessionId;
    return DomainResult.succeed<SessionMetadataLookup>({
      found: found,
      metadata: found ? this.metadata : null
    });
  }

  async save(metadata: SessionMetadata): Promise<DomainResult<boolean>> {
    if (this.failSave) {
      return DomainResult.fail<boolean>(new DomainFailure(
        DomainErrorCode.StorageWriteFailed,
        'metadata write failed',
        true
      ));
    }
    this.metadata = metadata;
    return DomainResult.succeed<boolean>(true);
  }

  async setTokenValidity(sessionId: string, isValid: boolean): Promise<DomainResult<boolean>> {
    if (this.metadata === null || this.metadata.sessionId !== sessionId) {
      return DomainResult.fail<boolean>(new DomainFailure(
        DomainErrorCode.SessionMissing,
        'session missing',
        false
      ));
    }
    const previous = this.metadata;
    this.metadata = {
      sessionId: previous.sessionId,
      userId: previous.userId,
      deviceId: previous.deviceId,
      homeserverUrl: previous.homeserverUrl,
      loginType: previous.loginType,
      loginTimestampMs: previous.loginTimestampMs,
      isTokenValid: isValid,
      position: previous.position,
      lastUsageIndex: previous.lastUsageIndex,
      userDisplayName: previous.userDisplayName,
      userAvatarUrl: previous.userAvatarUrl
    };
    return DomainResult.succeed<boolean>(true);
  }

  async remove(sessionId: string): Promise<DomainResult<boolean>> {
    if (this.metadata !== null && this.metadata.sessionId === sessionId) {
      this.metadata = null;
    }
    return DomainResult.succeed<boolean>(true);
  }
}

class MemoryCredentialStore implements SessionCredentialStore {
  credential: SessionCredentialSecret | null = null;

  async get(sessionId: string): Promise<DomainResult<SessionCredentialLookup>> {
    const found = this.credential !== null && this.credential.sessionId === sessionId;
    return DomainResult.succeed<SessionCredentialLookup>({
      found: found,
      credential: found ? this.credential : null
    });
  }

  async save(credential: SessionCredentialSecret): Promise<DomainResult<boolean>> {
    this.credential = credential;
    return DomainResult.succeed<boolean>(true);
  }

  async remove(sessionId: string): Promise<DomainResult<boolean>> {
    if (this.credential !== null && this.credential.sessionId === sessionId) {
      this.credential = null;
    }
    return DomainResult.succeed<boolean>(true);
  }
}

class TestAuthenticationService implements MatrixAuthenticationService {
  resolveFailure: DomainFailure | null = null;
  restoreFailure: DomainFailure | null = null;
  released: boolean = false;

  async resolveHomeserver(serverNameOrUrl: string): Promise<DomainResult<MatrixHomeserverDetails>> {
    if (this.resolveFailure !== null) {
      return DomainResult.fail<MatrixHomeserverDetails>(this.resolveFailure);
    }
    return DomainResult.succeed<MatrixHomeserverDetails>({
      canonicalUrl: serverNameOrUrl,
      serverName: 'example.org',
      supportsPasswordLogin: true,
      supportsOidcLogin: false
    });
  }

  async loginWithPassword(
    homeserver: MatrixHomeserverDetails,
    request: PasswordLoginRequest
  ): Promise<DomainResult<MatrixAuthenticatedSession>> {
    const handle: MatrixSessionHandle = { sessionId: '@alice:example.org', runtimeId: 'runtime-1' };
    return DomainResult.succeed<MatrixAuthenticatedSession>({
      sessionId: '@alice:example.org',
      userId: '@alice:example.org',
      deviceId: 'DEVICE',
      homeserverUrl: homeserver.canonicalUrl,
      accessToken: 'secret-token',
      refreshToken: 'secret-refresh-token',
      databasePassphrase: 'secret-database-passphrase',
      loginTimestampMs: 100,
      handle: handle
    });
  }

  async restoreSession(request: MatrixSessionRestoreRequest): Promise<DomainResult<MatrixSessionHandle>> {
    if (this.restoreFailure !== null) {
      return DomainResult.fail<MatrixSessionHandle>(this.restoreFailure);
    }
    return DomainResult.succeed<MatrixSessionHandle>({
      sessionId: request.sessionId,
      runtimeId: 'restored-runtime'
    });
  }

  async releaseSession(handle: MatrixSessionHandle): Promise<DomainResult<boolean>> {
    this.released = true;
    return DomainResult.succeed<boolean>(true);
  }
}

export default function productionSliceTest(): void {
  describe('productionSlice', () => {
    it('persists secrets separately and enters logged in state', 0, async () => {
      const metadataStore = new MemoryMetadataStore();
      const credentialStore = new MemoryCredentialStore();
      const persistence = new SessionPersistence(metadataStore, credentialStore);
      const navigation = new RootNavigationStateMachine();
      const coordinator = new PasswordLoginCoordinator(
        new TestAuthenticationService(),
        persistence,
        navigation
      );
      const input: PasswordLoginInput = {
        homeserver: 'https://matrix.example.org',
        username: 'alice',
        password: 'password-not-retained-in-state',
        deviceDisplayName: 'Element X Harmony'
      };

      await coordinator.submit(input);

      expect(navigation.getState().phase).assertEqual(RootNavigationPhase.LoggedIn);
      expect(metadataStore.metadata?.userId).assertEqual('@alice:example.org');
      expect(credentialStore.credential?.accessToken).assertEqual('secret-token');
      expect(JSON.stringify(metadataStore.metadata).includes('secret-token')).assertFalse();
      expect(JSON.stringify(navigation.getState()).includes(input.password)).assertFalse();
    });

    it('rolls back credentials and exposes metadata storage failure', 0, async () => {
      const metadataStore = new MemoryMetadataStore();
      metadataStore.failSave = true;
      const credentialStore = new MemoryCredentialStore();
      const authentication = new TestAuthenticationService();
      const navigation = new RootNavigationStateMachine();
      const coordinator = new PasswordLoginCoordinator(
        authentication,
        new SessionPersistence(metadataStore, credentialStore),
        navigation
      );

      await coordinator.submit({
        homeserver: 'https://matrix.example.org',
        username: 'alice',
        password: 'password',
        deviceDisplayName: 'Element X Harmony'
      });

      expect(navigation.getState().phase).assertEqual(RootNavigationPhase.Error);
      expect(navigation.getState().error?.code).assertEqual(DomainErrorCode.StorageWriteFailed);
      expect(credentialStore.credential).assertNull();
      expect(authentication.released).assertTrue();
    });

    it('restores a persisted session through the Matrix boundary', 0, async () => {
      const metadataStore = new MemoryMetadataStore();
      const credentialStore = new MemoryCredentialStore();
      const persistence = new SessionPersistence(metadataStore, credentialStore);
      const authentication = new TestAuthenticationService();
      const firstNavigation = new RootNavigationStateMachine();
      const login = new PasswordLoginCoordinator(authentication, persistence, firstNavigation);
      await login.submit({
        homeserver: 'https://matrix.example.org',
        username: 'alice',
        password: 'password',
        deviceDisplayName: 'Element X Harmony'
      });
      const restoredNavigation = new RootNavigationStateMachine();
      const root = new RootSessionCoordinator(authentication, persistence, restoredNavigation);

      await root.restoreLatestSession();

      expect(restoredNavigation.getState().phase).assertEqual(RootNavigationPhase.LoggedIn);
      expect(restoredNavigation.getState().sessionHandle?.runtimeId).assertEqual('restored-runtime');
    });

    it('routes an invalid restored token to signed out without fallback', 0, async () => {
      const metadataStore = new MemoryMetadataStore();
      const credentialStore = new MemoryCredentialStore();
      const persistence = new SessionPersistence(metadataStore, credentialStore);
      const authentication = new TestAuthenticationService();
      const loginNavigation = new RootNavigationStateMachine();
      await new PasswordLoginCoordinator(authentication, persistence, loginNavigation).submit({
        homeserver: 'https://matrix.example.org',
        username: 'alice',
        password: 'password',
        deviceDisplayName: 'Element X Harmony'
      });
      authentication.restoreFailure = new DomainFailure(
        DomainErrorCode.InvalidToken,
        'token rejected',
        false
      );
      const restoredNavigation = new RootNavigationStateMachine();

      await new RootSessionCoordinator(authentication, persistence, restoredNavigation).restoreLatestSession();

      expect(restoredNavigation.getState().phase).assertEqual(RootNavigationPhase.SignedOut);
      expect(restoredNavigation.getState().signedOutSessionId).assertEqual('@alice:example.org');
      expect(metadataStore.metadata?.isTokenValid).assertFalse();
    });

    it('exposes a homeserver network failure instead of creating a fallback session', 0, async () => {
      const metadataStore = new MemoryMetadataStore();
      const credentialStore = new MemoryCredentialStore();
      const authentication = new TestAuthenticationService();
      authentication.resolveFailure = new DomainFailure(
        DomainErrorCode.NetworkUnavailable,
        'network unavailable',
        true
      );
      const navigation = new RootNavigationStateMachine();

      await new PasswordLoginCoordinator(
        authentication,
        new SessionPersistence(metadataStore, credentialStore),
        navigation
      ).submit({
        homeserver: 'https://matrix.example.org',
        username: 'alice',
        password: 'password',
        deviceDisplayName: 'Element X Harmony'
      });

      expect(navigation.getState().phase).assertEqual(RootNavigationPhase.Error);
      expect(navigation.getState().error?.code).assertEqual(DomainErrorCode.NetworkUnavailable);
      expect(metadataStore.metadata).assertNull();
      expect(credentialStore.credential).assertNull();
    });

    it('exposes a missing secure credential as a restoration error', 0, async () => {
      const metadataStore = new MemoryMetadataStore();
      const credentialStore = new MemoryCredentialStore();
      const persistence = new SessionPersistence(metadataStore, credentialStore);
      const authentication = new TestAuthenticationService();
      await new PasswordLoginCoordinator(
        authentication,
        persistence,
        new RootNavigationStateMachine()
      ).submit({
        homeserver: 'https://matrix.example.org',
        username: 'alice',
        password: 'password',
        deviceDisplayName: 'Element X Harmony'
      });
      credentialStore.credential = null;
      const navigation = new RootNavigationStateMachine();

      await new RootSessionCoordinator(authentication, persistence, navigation).restoreLatestSession();

      expect(navigation.getState().phase).assertEqual(RootNavigationPhase.Error);
      expect(navigation.getState().error?.code).assertEqual(DomainErrorCode.CredentialMissing);
    });
  });
}
