import { DomainResult } from '../../core/DomainResult';

export const MATRIX_AUTHENTICATION_CONTRACT_VERSION: string = '1';

export interface MatrixHomeserverDetails {
  canonicalUrl: string;
  serverName: string;
  supportsPasswordLogin: boolean;
  supportsOidcLogin: boolean;
}

export interface PasswordLoginRequest {
  username: string;
  password: string;
  deviceDisplayName: string;
}

/** Opaque runtime identity. It deliberately exposes neither token nor SDK client internals. */
export interface MatrixSessionHandle {
  sessionId: string;
  runtimeId: string;
}

/**
 * Ephemeral authentication output. The coordinator must split this into public
 * metadata and protected credentials before persistence.
 */
export interface MatrixAuthenticatedSession {
  sessionId: string;
  userId: string;
  deviceId: string;
  homeserverUrl: string;
  accessToken: string;
  refreshToken: string | null;
  databasePassphrase: string | null;
  loginTimestampMs: number;
  handle: MatrixSessionHandle;
}

export interface MatrixSessionRestoreRequest {
  sessionId: string;
  userId: string;
  deviceId: string;
  homeserverUrl: string;
  accessToken: string;
  refreshToken: string | null;
  databasePassphrase: string | null;
}

/**
 * Authentication boundary implemented by the future Matrix Rust native bridge.
 * Implementations must report failures through DomainResult and never substitute
 * fixture sessions, rooms, users, or tokens.
 */
export interface MatrixAuthenticationService {
  resolveHomeserver(serverNameOrUrl: string): Promise<DomainResult<MatrixHomeserverDetails>>;
  loginWithPassword(
    homeserver: MatrixHomeserverDetails,
    request: PasswordLoginRequest
  ): Promise<DomainResult<MatrixAuthenticatedSession>>;
  restoreSession(request: MatrixSessionRestoreRequest): Promise<DomainResult<MatrixSessionHandle>>;
  releaseSession(handle: MatrixSessionHandle): Promise<DomainResult<boolean>>;
}
