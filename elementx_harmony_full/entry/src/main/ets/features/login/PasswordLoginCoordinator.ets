import {
  DomainErrorCode,
  DomainFailure,
  DomainResult,
  unexpectedFailure
} from '../../core/DomainResult';
import {
  MatrixAuthenticatedSession,
  MatrixAuthenticationService,
  MatrixHomeserverDetails,
  PasswordLoginRequest
} from '../../matrix/api/MatrixAuthentication';
import { SessionPersistence } from '../../session/SessionPersistence';
import { PersistableSession, toPersistablePasswordSession } from '../../session/SessionModels';
import { AuthenticationSource } from '../../appnav/RootNavigationState';
import { RootNavigationStateMachine } from '../../appnav/RootNavigationStateMachine';

export interface PasswordLoginInput {
  homeserver: string;
  username: string;
  password: string;
  deviceDisplayName: string;
}

/** Executes the Android-equivalent set-homeserver, login, persist, navigate sequence. */
export class PasswordLoginCoordinator {
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

  async submit(input: PasswordLoginInput): Promise<void> {
    const validationError = this.validate(input);
    if (validationError !== null) {
      const validationAttempt = this.rootNavigation.beginAuthentication(AuthenticationSource.Password);
      this.rootNavigation.failAuthentication(validationAttempt, validationError);
      return;
    }
    const attemptId = this.rootNavigation.beginAuthentication(AuthenticationSource.Password);
    try {
      const homeserverResult = await this.authenticationService.resolveHomeserver(input.homeserver.trim());
      if (!homeserverResult.success || homeserverResult.value === null) {
        this.rootNavigation.failAuthentication(
          attemptId,
          homeserverResult.error === null ? unexpectedFailure('Homeserver resolution') : homeserverResult.error
        );
        return;
      }
      const request: PasswordLoginRequest = {
        username: input.username.trim(),
        password: input.password,
        deviceDisplayName: input.deviceDisplayName
      };
      const loginResult = await this.authenticationService.loginWithPassword(homeserverResult.value, request);
      if (!loginResult.success || loginResult.value === null) {
        this.rootNavigation.failAuthentication(
          attemptId,
          loginResult.error === null ? unexpectedFailure('Password login') : loginResult.error
        );
        return;
      }
      await this.persistAndComplete(attemptId, loginResult.value);
    } catch (error) {
      this.rootNavigation.failAuthentication(attemptId, unexpectedFailure('Password login'));
    }
  }

  private async persistAndComplete(attemptId: number, authenticated: MatrixAuthenticatedSession): Promise<void> {
    const persistableResult: DomainResult<PersistableSession> = toPersistablePasswordSession(
      authenticated,
      authenticated.loginTimestampMs,
      authenticated.loginTimestampMs
    );
    if (!persistableResult.success || persistableResult.value === null) {
      await this.authenticationService.releaseSession(authenticated.handle);
      this.rootNavigation.failAuthentication(
        attemptId,
        persistableResult.error === null ? unexpectedFailure('Session mapping') : persistableResult.error
      );
      return;
    }
    const persistenceResult = await this.sessionPersistence.save(persistableResult.value);
    if (!persistenceResult.success) {
      await this.authenticationService.releaseSession(authenticated.handle);
      this.rootNavigation.failAuthentication(
        attemptId,
        persistenceResult.error === null ? unexpectedFailure('Session persistence') : persistenceResult.error
      );
      return;
    }
    this.rootNavigation.completeAuthentication(
      attemptId,
      persistableResult.value.metadata,
      authenticated.handle
    );
  }

  private validate(input: PasswordLoginInput): DomainFailure | null {
    if (input.homeserver.trim().length === 0) {
      return new DomainFailure(DomainErrorCode.InvalidInput, 'Homeserver is required', false);
    }
    if (input.username.trim().length === 0) {
      return new DomainFailure(DomainErrorCode.InvalidInput, 'Username is required', false);
    }
    if (input.password.length === 0) {
      return new DomainFailure(DomainErrorCode.InvalidInput, 'Password is required', false);
    }
    return null;
  }
}
