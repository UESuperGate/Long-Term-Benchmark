import { DomainErrorCode, DomainFailure, DomainResult } from '../core/DomainResult';
import { MatrixAuthenticatedSession } from '../matrix/api/MatrixAuthentication';

export enum SessionLoginType {
  Password = 'password',
  Oidc = 'oidc',
  Sso = 'sso',
  Direct = 'direct',
  Qr = 'qr',
  Unknown = 'unknown'
}

/** Safe for ordinary database storage and UI observation. Contains no secret. */
export interface SessionMetadata {
  sessionId: string;
  userId: string;
  deviceId: string;
  homeserverUrl: string;
  loginType: SessionLoginType;
  loginTimestampMs: number;
  isTokenValid: boolean;
  position: number;
  lastUsageIndex: number;
  userDisplayName: string | null;
  userAvatarUrl: string | null;
}

/** Must be stored only by a platform-backed secure credential implementation. */
export interface SessionCredentialSecret {
  sessionId: string;
  accessToken: string;
  refreshToken: string | null;
  databasePassphrase: string | null;
}

/** Transient value used only at the persistence boundary. */
export interface PersistableSession {
  metadata: SessionMetadata;
  credential: SessionCredentialSecret;
}

export interface StoredSessionLookup {
  found: boolean;
  session: PersistableSession | null;
}

export function toPersistablePasswordSession(
  authenticated: MatrixAuthenticatedSession,
  position: number,
  lastUsageIndex: number
): DomainResult<PersistableSession> {
  if (authenticated.sessionId.length === 0 || authenticated.sessionId !== authenticated.userId) {
    return DomainResult.fail<PersistableSession>(new DomainFailure(
      DomainErrorCode.InvalidInput,
      'Authenticated session identity is inconsistent',
      false
    ));
  }
  if (authenticated.accessToken.length === 0) {
    return DomainResult.fail<PersistableSession>(new DomainFailure(
      DomainErrorCode.InvalidInput,
      'Authenticated session has no access token',
      false
    ));
  }
  const metadata: SessionMetadata = {
    sessionId: authenticated.sessionId,
    userId: authenticated.userId,
    deviceId: authenticated.deviceId,
    homeserverUrl: authenticated.homeserverUrl,
    loginType: SessionLoginType.Password,
    loginTimestampMs: authenticated.loginTimestampMs,
    isTokenValid: true,
    position: position,
    lastUsageIndex: lastUsageIndex,
    userDisplayName: null,
    userAvatarUrl: null
  };
  const credential: SessionCredentialSecret = {
    sessionId: authenticated.sessionId,
    accessToken: authenticated.accessToken,
    refreshToken: authenticated.refreshToken,
    databasePassphrase: authenticated.databasePassphrase
  };
  const session: PersistableSession = {
    metadata: metadata,
    credential: credential
  };
  return DomainResult.succeed<PersistableSession>(session);
}
