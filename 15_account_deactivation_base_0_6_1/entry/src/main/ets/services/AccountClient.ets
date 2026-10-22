export interface AccountCapabilityService {
  canDeactivateAccount(): Promise<boolean>;
}

export interface AccountDeactivationService {
  deactivateAccount(password: string, eraseData: boolean): Promise<void>;
}

export interface AccountSession {
  schemaVersion: number;
  homeserver: string;
  userId: string;
  deviceId: string;
  accessToken: string;
  authMode: string;
  phase: string;
}

export interface AccountResponse {
  status: number;
  body: string;
}

export interface AccountTransport {
  post(homeserver: string, path: string, token: string, body: string): Promise<AccountResponse>;
  close(): void;
}

export interface AccountSessionStore {
  read(): Promise<AccountSession | null>;
  save(session: AccountSession): Promise<void>;
  clear(session: AccountSession): Promise<void>;
}

interface MatrixErrorBody {
  errcode?: string;
  error?: string;
  session?: string;
}

interface LoginResponse {
  user_id: string;
  device_id: string;
  access_token: string;
}

interface UserIdentifier {
  type: string;
  user: string;
}

interface PasswordAuth {
  type: string;
  identifier: UserIdentifier;
  password: string;
  session?: string;
}

interface LoginRequest {
  type: string;
  identifier: UserIdentifier;
  password: string;
  initial_device_display_name: string;
}

interface DeactivationRequest {
  erase: boolean;
  auth?: PasswordAuth;
}

export class AccountError extends Error {
  readonly status: number;
  readonly code: string;
  readonly uiaSession: string;

  constructor(status: number, code: string, message: string, uiaSession: string = '') {
    super(message);
    this.status = status;
    this.code = code;
    this.uiaSession = uiaSession;
  }
}

export function normalizeHomeserver(value: string): string {
  const normalized: string = value.trim().replace(/\/+$/, '');
  if (!/^https:\/\/[^\s/?#@]+(?::[0-9]+)?$/.test(normalized)) {
    throw new Error('Enter an HTTPS homeserver origin without a path');
  }
  return normalized;
}

export function validateAccountSession(session: AccountSession): AccountSession {
  if (session === null || session.schemaVersion !== 1 ||
    typeof session.homeserver !== 'string' || typeof session.userId !== 'string' ||
    typeof session.deviceId !== 'string' || typeof session.accessToken !== 'string' ||
    !session.userId.startsWith('@') || session.deviceId.length === 0 || session.deviceId === '.' ||
    session.deviceId === '..' || session.accessToken.length === 0 ||
    (session.authMode !== 'matrix' && session.authMode !== 'oidc') ||
    (session.phase !== 'active' && session.phase !== 'cleanup_pending')) {
    throw new Error('Stored account session is invalid');
  }
  normalizeHomeserver(session.homeserver);
  return session;
}

export class AccountClient implements AccountCapabilityService, AccountDeactivationService {
  private session: AccountSession | null = null;
  private transport: AccountTransport;
  private store: AccountSessionStore;
  private initialized: boolean = false;
  private closed: boolean = false;
  private operation: string = '';

  constructor(transport: AccountTransport, store: AccountSessionStore) {
    this.transport = transport;
    this.store = store;
  }

  async restore(): Promise<void> {
    if (this.initialized) {
      return;
    }
    this.begin('restore');
    try {
      const saved: AccountSession | null = await this.store.read();
      if (saved !== null) {
        this.session = validateAccountSession(saved);
        if (saved.phase === 'cleanup_pending') {
          await this.completeCleanup(saved);
        }
      }
      this.initialized = true;
    } finally {
      this.operation = '';
    }
  }

  userId(): string {
    return this.session !== null && !this.closed ? this.session.userId : '';
  }

  isBusy(): boolean {
    return this.operation.length > 0;
  }

  needsCleanup(): boolean {
    return this.session !== null && this.session.phase === 'cleanup_pending';
  }

  async canDeactivateAccount(): Promise<boolean> {
    return this.initialized && !this.closed && this.session !== null &&
      this.session.phase === 'active' && this.session.authMode === 'matrix';
  }

  async login(homeserver: string, user: string, password: string): Promise<void> {
    if (!this.initialized || this.session !== null) {
      throw new Error('Restore or clear the existing session before signing in');
    }
    const origin: string = normalizeHomeserver(homeserver);
    if (user.trim().length === 0 || password.length === 0) {
      throw new Error('User and password are required');
    }
    this.begin('login');
    try {
      const body: LoginRequest = {
        type: 'm.login.password', identifier: { type: 'm.id.user', user: user.trim() },
        password: password, initial_device_display_name: 'Element Account Settings'
      };
      const response: AccountResponse = await this.transport.post(origin, '/_matrix/client/v3/login', '', JSON.stringify(body));
      this.requireSuccess(response);
      const login: LoginResponse = JSON.parse(response.body) as LoginResponse;
      const session: AccountSession = validateAccountSession({
        schemaVersion: 1, homeserver: origin, userId: login.user_id, deviceId: login.device_id,
        accessToken: login.access_token, authMode: 'matrix', phase: 'active'
      });
      await this.store.save(session);
      this.session = session;
      this.closed = false;
    } finally {
      this.operation = '';
    }
  }

  async deactivateAccount(password: string, eraseData: boolean): Promise<void> {
    const session: AccountSession = this.activeSession();
    if (session.authMode !== 'matrix') {
      throw new Error('This authentication method does not support account deactivation');
    }
    this.begin('deactivate');
    try {
      // v0.6.3 RustMatrixClient first attempts without auth, then retries with password.
      try {
        await this.sendDeactivation(session, { erase: eraseData });
      } catch (error) {
        const challenge: string = error instanceof AccountError ? error.uiaSession : '';
        const auth: PasswordAuth = {
          type: 'm.login.password', identifier: { type: 'm.id.user', user: session.userId }, password: password
        };
        if (challenge.length > 0) {
          auth.session = challenge;
        }
        await this.sendDeactivation(session, { erase: eraseData, auth: auth });
      }
      await this.completeCleanup(session);
    } finally {
      this.operation = '';
    }
  }

  async logout(): Promise<void> {
    const session: AccountSession = this.activeSession();
    this.begin('logout');
    try {
      this.requireSuccess(await this.transport.post(session.homeserver, '/_matrix/client/v3/logout', session.accessToken, '{}'));
      await this.completeCleanup(session);
    } finally {
      this.operation = '';
    }
  }

  async retryCleanup(): Promise<void> {
    if (this.session === null || this.session.phase !== 'cleanup_pending') {
      throw new Error('No session cleanup is pending');
    }
    this.begin('cleanup');
    try {
      await this.completeCleanup(this.session);
      this.initialized = true;
    } finally {
      this.operation = '';
    }
  }

  private begin(operation: string): void {
    if (this.operation.length > 0) {
      throw new Error('An account operation is already pending');
    }
    this.operation = operation;
  }

  private activeSession(): AccountSession {
    if (!this.initialized || this.closed || this.session === null || this.session.phase !== 'active') {
      throw new Error('An active account session is required');
    }
    return this.session;
  }

  private async sendDeactivation(session: AccountSession, body: DeactivationRequest): Promise<void> {
    const response: AccountResponse = await this.transport.post(session.homeserver,
      '/_matrix/client/v3/account/deactivate', session.accessToken, JSON.stringify(body));
    this.requireSuccess(response);
  }

  private requireSuccess(response: AccountResponse): void {
    if (response.status >= 200 && response.status < 300) {
      return;
    }
    let body: MatrixErrorBody = {};
    try {
      const parsed: MatrixErrorBody | null = JSON.parse(response.body) as MatrixErrorBody | null;
      if (parsed !== null) {
        body = parsed;
      }
    } catch (_) {
      // A non-JSON proxy/server error remains an HTTP failure.
    }
    throw new AccountError(response.status, typeof body.errcode === 'string' ? body.errcode : 'M_UNKNOWN',
      typeof body.error === 'string' ? body.error : 'Account request failed',
      typeof body.session === 'string' ? body.session : '');
  }

  private async completeCleanup(session: AccountSession): Promise<void> {
    this.closed = true;
    this.transport.close();
    session.phase = 'cleanup_pending';
    // A durable tombstone prevents restoring a remotely deactivated session if local deletion fails.
    try {
      await this.store.save(session);
    } finally {
      await this.store.clear(session);
      this.session = null;
    }
  }
}
