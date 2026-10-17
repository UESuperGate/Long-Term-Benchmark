import { DomainErrorCode, DomainFailure, DomainResult, unexpectedFailure } from '../core/DomainResult';
import { PersistableSession, StoredSessionLookup } from './SessionModels';
import {
  SessionCredentialLookup,
  SessionCredentialStore,
  SessionMetadataLookup,
  SessionMetadataStore
} from './SessionStores';

/** Coordinates two stores without ever writing credentials to the metadata store. */
export class SessionPersistence {
  private readonly metadataStore: SessionMetadataStore;
  private readonly credentialStore: SessionCredentialStore;

  constructor(metadataStore: SessionMetadataStore, credentialStore: SessionCredentialStore) {
    this.metadataStore = metadataStore;
    this.credentialStore = credentialStore;
  }

  async save(session: PersistableSession): Promise<DomainResult<boolean>> {
    if (session.metadata.sessionId.length === 0 ||
      session.metadata.sessionId !== session.credential.sessionId) {
      return DomainResult.fail<boolean>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Session metadata and credential identities do not match',
        false
      ));
    }
    try {
      const credentialResult = await this.credentialStore.save(session.credential);
      if (!credentialResult.success) {
        return DomainResult.fail<boolean>(
          credentialResult.error === null ? unexpectedFailure('Session credential write') : credentialResult.error
        );
      }
      const metadataResult = await this.metadataStore.save(session.metadata);
      if (!metadataResult.success) {
        await this.credentialStore.remove(session.metadata.sessionId);
        return DomainResult.fail<boolean>(
          metadataResult.error === null ? unexpectedFailure('Session metadata write') : metadataResult.error
        );
      }
      return DomainResult.succeed<boolean>(true);
    } catch (error) {
      await this.bestEffortRemoveCredential(session.metadata.sessionId);
      return DomainResult.fail<boolean>(unexpectedFailure('Session persistence'));
    }
  }

  async loadLatest(): Promise<DomainResult<StoredSessionLookup>> {
    try {
      const metadataResult = await this.metadataStore.getLatest();
      if (!metadataResult.success || metadataResult.value === null) {
        return DomainResult.fail<StoredSessionLookup>(
          metadataResult.error === null ? unexpectedFailure('Session metadata read') : metadataResult.error
        );
      }
      const metadataLookup: SessionMetadataLookup = metadataResult.value;
      if (!metadataLookup.found || metadataLookup.metadata === null) {
        return DomainResult.succeed<StoredSessionLookup>({ found: false, session: null });
      }
      const credentialResult = await this.credentialStore.get(metadataLookup.metadata.sessionId);
      if (!credentialResult.success || credentialResult.value === null) {
        return DomainResult.fail<StoredSessionLookup>(
          credentialResult.error === null ? unexpectedFailure('Session credential read') : credentialResult.error
        );
      }
      const credentialLookup: SessionCredentialLookup = credentialResult.value;
      if (!credentialLookup.found || credentialLookup.credential === null) {
        return DomainResult.fail<StoredSessionLookup>(new DomainFailure(
          DomainErrorCode.CredentialMissing,
          'Secure credentials are missing for the latest session',
          false
        ));
      }
      if (metadataLookup.metadata.sessionId !== credentialLookup.credential.sessionId) {
        return DomainResult.fail<StoredSessionLookup>(new DomainFailure(
          DomainErrorCode.StorageReadFailed,
          'Stored session identities do not match',
          false
        ));
      }
      return DomainResult.succeed<StoredSessionLookup>({
        found: true,
        session: {
          metadata: metadataLookup.metadata,
          credential: credentialLookup.credential
        }
      });
    } catch (error) {
      return DomainResult.fail<StoredSessionLookup>(unexpectedFailure('Session restoration read'));
    }
  }

  async markTokenInvalid(sessionId: string): Promise<DomainResult<boolean>> {
    try {
      return await this.metadataStore.setTokenValidity(sessionId, false);
    } catch (error) {
      return DomainResult.fail<boolean>(unexpectedFailure('Token validity update'));
    }
  }

  async remove(sessionId: string): Promise<DomainResult<boolean>> {
    try {
      const credentialResult = await this.credentialStore.remove(sessionId);
      if (!credentialResult.success) {
        return credentialResult;
      }
      const metadataResult = await this.metadataStore.remove(sessionId);
      if (!metadataResult.success) {
        return metadataResult;
      }
      return DomainResult.succeed<boolean>(true);
    } catch (error) {
      return DomainResult.fail<boolean>(unexpectedFailure('Session removal'));
    }
  }

  private async bestEffortRemoveCredential(sessionId: string): Promise<void> {
    try {
      await this.credentialStore.remove(sessionId);
    } catch (error) {
      // The original persistence failure remains the user-facing error.
    }
  }
}
