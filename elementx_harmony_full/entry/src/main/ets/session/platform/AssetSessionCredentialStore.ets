import asset from '@ohos.security.asset';
import util from '@ohos.util';
import { DomainErrorCode, DomainResult } from '../../core/DomainResult';
import {
  PlatformFailure,
  PlatformFailureKind,
  platformCodeOf,
  platformSdkError
} from '../../platform/errors/PlatformFailure';
import { SessionCredentialSecret } from '../SessionModels';
import { SessionCredentialLookup, SessionCredentialStore } from '../SessionStores';

interface CredentialEnvelope {
  schemaVersion: number;
  sessionId: string;
  accessToken: string;
  refreshToken: string | null;
  databasePassphrase: string | null;
}

/** Abstracted so secure-store behavior can be tested without weakening production storage. */
export interface SecureAssetBackend {
  read(alias: string): Promise<Uint8Array | null>;
  write(alias: string, secret: Uint8Array): Promise<void>;
  remove(alias: string): Promise<void>;
}

export class OpenHarmonySecureAssetBackend implements SecureAssetBackend {
  async read(alias: string): Promise<Uint8Array | null> {
    const query = new Map<asset.Tag, asset.Value>();
    query.set(asset.Tag.ALIAS, this.encode(alias));
    query.set(asset.Tag.RETURN_TYPE, asset.ReturnType.ALL);
    query.set(asset.Tag.RETURN_LIMIT, 1);
    try {
      const results = await asset.query(query);
      if (results.length === 0) {
        return null;
      }
      const value = results[0].get(asset.Tag.SECRET);
      return value instanceof Uint8Array ? value : null;
    } catch (error) {
      const failure = error as Error;
      if (platformCodeOf(failure) === 24000002) {
        return null;
      }
      throw platformSdkError('asset.query', failure);
    }
  }

  async write(alias: string, secret: Uint8Array): Promise<void> {
    const attributes = new Map<asset.Tag, asset.Value>();
    attributes.set(asset.Tag.ALIAS, this.encode(alias));
    attributes.set(asset.Tag.SECRET, secret);
    attributes.set(asset.Tag.ACCESSIBILITY, asset.Accessibility.DEVICE_FIRST_UNLOCKED);
    attributes.set(asset.Tag.AUTH_TYPE, asset.AuthType.NONE);
    attributes.set(asset.Tag.SYNC_TYPE, asset.SyncType.NEVER);
    attributes.set(asset.Tag.CONFLICT_RESOLUTION, asset.ConflictResolution.OVERWRITE);
    try {
      await asset.add(attributes);
    } catch (error) {
      throw platformSdkError('asset.add', error as Error);
    }
  }

  async remove(alias: string): Promise<void> {
    const query = new Map<asset.Tag, asset.Value>();
    query.set(asset.Tag.ALIAS, this.encode(alias));
    try {
      await asset.remove(query);
    } catch (error) {
      const failure = error as Error;
      if (platformCodeOf(failure) !== 24000002) {
        throw platformSdkError('asset.remove', failure);
      }
    }
  }

  private encode(value: string): Uint8Array {
    return new util.TextEncoder().encode(value);
  }
}

/**
 * Stores credentials only in AssetStore. Capability or access failures are returned
 * to the caller; this class deliberately has no Preferences fallback.
 */
export class AssetSessionCredentialStore implements SessionCredentialStore {
  private static readonly ALIAS_PREFIX: string = 'elementx.session.v1/';
  private static readonly MAX_ALIAS_BYTES: number = 256;
  private readonly backend: SecureAssetBackend;
  private readonly encoder: util.TextEncoder = new util.TextEncoder();
  private readonly decoder: util.TextDecoder = new util.TextDecoder('utf-8', { fatal: true });

  constructor(backend: SecureAssetBackend = new OpenHarmonySecureAssetBackend()) {
    this.backend = backend;
  }

  async get(sessionId: string): Promise<DomainResult<SessionCredentialLookup>> {
    const aliasResult = this.aliasFor(sessionId);
    if (!aliasResult.success || aliasResult.value === null) {
      return DomainResult.fail<SessionCredentialLookup>(aliasResult.error as PlatformFailure);
    }
    try {
      const bytes = await this.backend.read(aliasResult.value);
      if (bytes === null) {
        return DomainResult.succeed<SessionCredentialLookup>({ found: false, credential: null });
      }
      const decoded = this.decodeCredential(bytes, sessionId);
      if (decoded === null) {
        return DomainResult.fail<SessionCredentialLookup>(new PlatformFailure(
          DomainErrorCode.StorageReadFailed,
          PlatformFailureKind.InvalidData,
          'session_credential.decode',
          'Secure session credential is malformed or belongs to another session',
          false
        ));
      }
      return DomainResult.succeed<SessionCredentialLookup>({ found: true, credential: decoded });
    } catch (error) {
      const failure = error as Error;
      return DomainResult.fail<SessionCredentialLookup>(new PlatformFailure(
        DomainErrorCode.StorageReadFailed,
        this.secureStoreFailureKind(failure),
        'session_credential.read',
        'Secure credential storage is unavailable or denied',
        true,
        platformCodeOf(failure)
      ));
    }
  }

  async save(credential: SessionCredentialSecret): Promise<DomainResult<boolean>> {
    if (credential.sessionId.length === 0 || credential.accessToken.length === 0) {
      return DomainResult.fail<boolean>(new PlatformFailure(
        DomainErrorCode.InvalidInput,
        PlatformFailureKind.InvalidData,
        'session_credential.validate',
        'Session id and access token are required',
        false
      ));
    }
    const aliasResult = this.aliasFor(credential.sessionId);
    if (!aliasResult.success || aliasResult.value === null) {
      return DomainResult.fail<boolean>(aliasResult.error as PlatformFailure);
    }
    const envelope: CredentialEnvelope = {
      schemaVersion: 1,
      sessionId: credential.sessionId,
      accessToken: credential.accessToken,
      refreshToken: credential.refreshToken,
      databasePassphrase: credential.databasePassphrase
    };
    try {
      await this.backend.write(aliasResult.value, this.encoder.encode(JSON.stringify(envelope)));
      return DomainResult.succeed<boolean>(true);
    } catch (error) {
      const failure = error as Error;
      return DomainResult.fail<boolean>(new PlatformFailure(
        DomainErrorCode.StorageWriteFailed,
        this.secureStoreFailureKind(failure),
        'session_credential.write',
        'Secure credential storage is unavailable or denied; no plaintext fallback was used',
        false,
        platformCodeOf(failure)
      ));
    }
  }

  async remove(sessionId: string): Promise<DomainResult<boolean>> {
    const aliasResult = this.aliasFor(sessionId);
    if (!aliasResult.success || aliasResult.value === null) {
      return DomainResult.fail<boolean>(aliasResult.error as PlatformFailure);
    }
    try {
      await this.backend.remove(aliasResult.value);
      return DomainResult.succeed<boolean>(true);
    } catch (error) {
      const failure = error as Error;
      return DomainResult.fail<boolean>(new PlatformFailure(
        DomainErrorCode.StorageDeleteFailed,
        this.secureStoreFailureKind(failure),
        'session_credential.remove',
        'Unable to remove secure session credentials',
        true,
        platformCodeOf(failure)
      ));
    }
  }

  private aliasFor(sessionId: string): DomainResult<string> {
    if (sessionId.length === 0) {
      return DomainResult.fail<string>(new PlatformFailure(
        DomainErrorCode.InvalidInput,
        PlatformFailureKind.InvalidData,
        'session_credential.alias',
        'Session id is empty',
        false
      ));
    }
    const alias = AssetSessionCredentialStore.ALIAS_PREFIX + encodeURIComponent(sessionId);
    if (this.encoder.encode(alias).length > AssetSessionCredentialStore.MAX_ALIAS_BYTES) {
      return DomainResult.fail<string>(new PlatformFailure(
        DomainErrorCode.InvalidInput,
        PlatformFailureKind.InvalidData,
        'session_credential.alias',
        'Session id is too long for secure credential storage',
        false
      ));
    }
    return DomainResult.succeed<string>(alias);
  }

  private decodeCredential(bytes: Uint8Array, expectedSessionId: string): SessionCredentialSecret | null {
    const parsed = JSON.parse(this.decoder.decode(bytes)) as CredentialEnvelope;
    if (parsed.schemaVersion !== 1 || parsed.sessionId !== expectedSessionId ||
      typeof parsed.accessToken !== 'string' || parsed.accessToken.length === 0 ||
      !(parsed.refreshToken === null || typeof parsed.refreshToken === 'string') ||
      !(parsed.databasePassphrase === null || typeof parsed.databasePassphrase === 'string')) {
      return null;
    }
    return {
      sessionId: parsed.sessionId,
      accessToken: parsed.accessToken,
      refreshToken: parsed.refreshToken,
      databasePassphrase: parsed.databasePassphrase
    };
  }

  private secureStoreFailureKind(error: Error): PlatformFailureKind {
    const code = platformCodeOf(error);
    if (code === 201 || code === 24000004 || code === 24000005) {
      return PlatformFailureKind.PermissionDenied;
    }
    if (code === 801 || code === 24000001 || code === 24000017) {
      return PlatformFailureKind.CapabilityUnavailable;
    }
    return PlatformFailureKind.WriteFailed;
  }
}
