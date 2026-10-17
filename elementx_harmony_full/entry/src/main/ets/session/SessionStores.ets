import { DomainResult } from '../core/DomainResult';
import { SessionCredentialSecret, SessionMetadata } from './SessionModels';

export interface SessionMetadataLookup {
  found: boolean;
  metadata: SessionMetadata | null;
}

export interface SessionCredentialLookup {
  found: boolean;
  credential: SessionCredentialSecret | null;
}

/** Ordinary persistence. Implementations must reject objects containing credentials. */
export interface SessionMetadataStore {
  getLatest(): Promise<DomainResult<SessionMetadataLookup>>;
  getById(sessionId: string): Promise<DomainResult<SessionMetadataLookup>>;
  save(metadata: SessionMetadata): Promise<DomainResult<boolean>>;
  setTokenValidity(sessionId: string, isValid: boolean): Promise<DomainResult<boolean>>;
  remove(sessionId: string): Promise<DomainResult<boolean>>;
}

/** Platform-secured persistence for access tokens and database passphrases. */
export interface SessionCredentialStore {
  get(sessionId: string): Promise<DomainResult<SessionCredentialLookup>>;
  save(credential: SessionCredentialSecret): Promise<DomainResult<boolean>>;
  remove(sessionId: string): Promise<DomainResult<boolean>>;
}
