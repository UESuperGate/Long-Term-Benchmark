import { DomainErrorCode, DomainFailure, unexpectedFailure } from '../core/DomainResult';
import {
  MatrixAuthenticationService,
  MatrixSessionRestoreRequest
} from '../matrix/api/MatrixAuthentication';
import { SessionPersistence } from '../session/SessionPersistence';
import { PersistableSession, StoredSessionLookup } from '../session/SessionModels';
import { AuthenticationSource } from './RootNavigationState';
import { RootNavigationStateMachine } from './RootNavigationStateMachine';

/** Restores the latest production session and drives the root navigation state. */
export class RootSessionCoordinator {
  private readonly authenticationService: MatrixAuthenticationService;
  private readonly sessionPersistence: SessionPersistence;
  private readonly rootNavigation: RootNavigationStateMachine;

  constructor(
    authenticationService: MatrixAuthenticationService,
    sessionPersistence: SessionPersistence,
    rootNavigation: RootNavigationStateMachine
  ) {
    this.authenticationService = authenticationService;
    this.sessionPersistence = sessionPersistence;
    this.rootNavigation = rootNavigation;
  }

  async restoreLatestSession(): Promise<void> {
    const attemptId = this.rootNavigation.beginAuthentication(AuthenticationSource.SessionRestore);
    try {
      const lookupResult = await this.sessionPersistence.loadLatest();
      if (!lookupResult.success || lookupResult.value === null) {
        this.rootNavigation.failAuthentication(
          attemptId,
          lookupResult.error === null ? unexpectedFailure('Session lookup') : lookupResult.error
        );
        return;
      }
      const lookup: StoredSessionLookup = lookupResult.value;
      if (!lookup.found || lookup.session === null) {
        this.rootNavigation.finishSignedOut(attemptId);
        return;
      }
      if (!lookup.session.metadata.isTokenValid) {
        this.rootNavigation.finishSignedOut(attemptId, lookup.session.metadata.sessionId);
        return;
      }
      await this.restoreStoredSession(attemptId, lookup.session);
    } catch (error) {
      this.rootNavigation.failAuthentication(attemptId, unexpectedFailure('Session restoration'));
    }
  }

  private async restoreStoredSession(attemptId: number, session: PersistableSession): Promise<void> {
    const request: MatrixSessionRestoreRequest = {
      sessionId: session.metadata.sessionId,
      userId: session.metadata.userId,
      deviceId: session.metadata.deviceId,
      homeserverUrl: session.metadata.homeserverUrl,
      accessToken: session.credential.accessToken,
      refreshToken: session.credential.refreshToken,
      databasePassphrase: session.credential.databasePassphrase
    };
    const restoreResult = await this.authenticationService.restoreSession(request);
    if (restoreResult.success && restoreResult.value !== null) {
      this.rootNavigation.completeAuthentication(attemptId, session.metadata, restoreResult.value);
      return;
    }
    if (restoreResult.error !== null && restoreResult.error.code === DomainErrorCode.InvalidToken) {
      const invalidationResult = await this.sessionPersistence.markTokenInvalid(session.metadata.sessionId);
      if (!invalidationResult.success) {
        this.rootNavigation.failAuthentication(
          attemptId,
          invalidationResult.error === null ? unexpectedFailure('Token invalidation') : invalidationResult.error
        );
        return;
      }
      this.rootNavigation.finishSignedOut(attemptId, session.metadata.sessionId);
      return;
    }
    this.rootNavigation.failAuthentication(
      attemptId,
      restoreResult.error === null ? new DomainFailure(
        DomainErrorCode.ServiceUnavailable,
        'Matrix session restoration failed',
        true
      ) : restoreResult.error
    );
  }
}
