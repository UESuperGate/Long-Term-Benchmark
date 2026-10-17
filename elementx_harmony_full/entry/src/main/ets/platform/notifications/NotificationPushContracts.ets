import { DomainResult } from '../../core/DomainResult';

export enum NotificationAuthorizationState {
  Enabled = 'enabled',
  Disabled = 'disabled'
}

export interface NotificationAuthorizationService {
  state(): Promise<DomainResult<NotificationAuthorizationState>>;
  request(): Promise<DomainResult<NotificationAuthorizationState>>;
}

export enum PushRegistrationPhase {
  Unregistered = 'unregistered',
  Registering = 'registering',
  Registered = 'registered',
  Failed = 'failed'
}

/** Contains no push token. Tokens must remain inside the provider-specific secure boundary. */
export interface PushRegistrationSnapshot {
  sessionId: string;
  providerName: string | null;
  phase: PushRegistrationPhase;
  notificationsEnabledForDevice: boolean;
  ignoreRegistrationError: boolean;
  lastAttemptAtMs: number | null;
  lastErrorCode: string | null;
}

export interface PushRegistrationStore {
  get(sessionId: string): Promise<DomainResult<PushRegistrationSnapshot>>;
  save(snapshot: PushRegistrationSnapshot): Promise<DomainResult<boolean>>;
  reset(sessionId: string): Promise<DomainResult<boolean>>;
}

export interface PushProviderRegistrationRequest {
  sessionId: string;
  providerName: string;
  appId: string;
  deviceId: string;
}

/** Push provider implementations keep raw provider tokens out of observable app state. */
export interface PushRegistrationService {
  register(request: PushProviderRegistrationRequest): Promise<DomainResult<boolean>>;
  unregister(sessionId: string): Promise<DomainResult<boolean>>;
}
