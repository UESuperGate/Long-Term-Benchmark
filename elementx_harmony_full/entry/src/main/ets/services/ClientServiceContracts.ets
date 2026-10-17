import {
  AsyncDataState,
  HomeserverCapabilitiesState,
  LoggedInRuntimeState,
  MatrixClientRuntime,
  NetworkStatus,
  ResolvedIntentKind,
  RootNavState,
  SessionStoreRecord,
  SessionVerificationStatus,
  SyncRuntimeState
} from '../model/ClientRuntimeModels';

export interface SessionStoreContract {
  getLatestSession(): SessionStoreRecord | null;
  getAllSessions(): SessionStoreRecord[];
  setLatestSession(sessionId: string): void;
  clearLatestSession(): void;
}

export interface MatrixSessionCacheContract {
  getOrNull(sessionId: string): MatrixClientRuntime | null;
  getOrRestore(sessionId: string): MatrixClientRuntime | null;
  put(client: MatrixClientRuntime): void;
  removeAll(): void;
}

export interface SyncServiceContract {
  startSync(): SyncRuntimeState;
  stopSync(): SyncRuntimeState;
  currentState(): SyncRuntimeState;
}

export interface PushServiceContract {
  registerPusher(sessionId: string): AsyncDataState;
}

export interface SessionVerificationServiceContract {
  currentStatus(sessionId: string): SessionVerificationStatus;
}

export interface EncryptionServiceContract {
  currentState(sessionId: string): LoggedInRuntimeState;
}

export interface NetworkMonitorContract {
  currentConnectivity(): NetworkStatus;
}

export interface IntentResolverContract {
  resolve(action: string, data: string): ResolvedIntentKind;
}

export interface HomeserverCapabilitiesContract {
  refresh(sessionId: string): HomeserverCapabilitiesState;
}

export interface RootNavStateFactoryContract {
  create(): RootNavState;
  saveIntoSavedState(): string;
  restoreFromSavedState(serializedState: string): RootNavState;
}
