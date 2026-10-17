import { DomainError } from '../core/DomainResult';
import { MatrixSessionHandle } from '../matrix/api/MatrixAuthentication';
import { SessionMetadata } from '../session/SessionModels';

export enum RootNavigationPhase {
  SignedOut = 'signed_out',
  Authenticating = 'authenticating',
  LoggedIn = 'logged_in',
  Error = 'error'
}

export enum AuthenticationSource {
  Password = 'password',
  SessionRestore = 'session_restore'
}

export class RootNavigationState {
  readonly phase: RootNavigationPhase;
  readonly authenticationSource: AuthenticationSource | null;
  readonly attemptId: number;
  readonly session: SessionMetadata | null;
  readonly sessionHandle: MatrixSessionHandle | null;
  readonly signedOutSessionId: string;
  readonly error: DomainError | null;

  constructor(
    phase: RootNavigationPhase,
    authenticationSource: AuthenticationSource | null,
    attemptId: number,
    session: SessionMetadata | null,
    sessionHandle: MatrixSessionHandle | null,
    signedOutSessionId: string,
    error: DomainError | null
  ) {
    this.phase = phase;
    this.authenticationSource = authenticationSource;
    this.attemptId = attemptId;
    this.session = session;
    this.sessionHandle = sessionHandle;
    this.signedOutSessionId = signedOutSessionId;
    this.error = error;
  }

  static signedOut(sessionId: string = ''): RootNavigationState {
    return new RootNavigationState(
      RootNavigationPhase.SignedOut,
      null,
      0,
      null,
      null,
      sessionId,
      null
    );
  }
}
