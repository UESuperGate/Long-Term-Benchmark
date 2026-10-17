import common from '@ohos.app.ability.common';
import { DomainErrorCode, DomainResult } from '../../core/DomainResult';
import { PlatformFailure, PlatformFailureKind, platformCodeOf } from '../../platform/errors/PlatformFailure';
import { OpenHarmonyStringPreferences } from '../../platform/storage/StringPreferences';
import type { StringPreferences } from '../../platform/storage/StringPreferences';
import { SessionLoginType } from '../SessionModels';
import type { SessionMetadata } from '../SessionModels';
import type { SessionMetadataLookup, SessionMetadataStore } from '../SessionStores';

interface MetadataEnvelope {
  schemaVersion: number;
  sessions: SessionMetadata[];
}

/** Stores only the explicitly whitelisted, non-secret session metadata fields. */
export class PreferencesSessionMetadataStore implements SessionMetadataStore {
  private static readonly STORE_NAME: string = 'elementx_session_metadata_v1';
  private static readonly SNAPSHOT_KEY: string = 'metadata_snapshot';
  private readonly preferences: StringPreferences;

  constructor(preferencesStore: StringPreferences) {
    this.preferences = preferencesStore;
  }

  static async create(context: common.Context): Promise<PreferencesSessionMetadataStore> {
    const store = await OpenHarmonyStringPreferences.create(
      context,
      PreferencesSessionMetadataStore.STORE_NAME
    );
    return new PreferencesSessionMetadataStore(store);
  }

  async getLatest(): Promise<DomainResult<SessionMetadataLookup>> {
    const allResult = await this.readAll();
    if (!allResult.success || allResult.value === null) {
      return DomainResult.fail<SessionMetadataLookup>(allResult.error as PlatformFailure);
    }
    let latest: SessionMetadata | null = null;
    allResult.value.forEach((metadata: SessionMetadata) => {
      if (latest === null || metadata.lastUsageIndex > latest.lastUsageIndex ||
        (metadata.lastUsageIndex === latest.lastUsageIndex && metadata.position > latest.position)) {
        latest = metadata;
      }
    });
    return DomainResult.succeed<SessionMetadataLookup>({
      found: latest !== null,
      metadata: latest
    });
  }

  async getById(sessionId: string): Promise<DomainResult<SessionMetadataLookup>> {
    if (sessionId.length === 0) {
      return this.invalidLookup('Session id is empty');
    }
    const allResult = await this.readAll();
    if (!allResult.success || allResult.value === null) {
      return DomainResult.fail<SessionMetadataLookup>(allResult.error as PlatformFailure);
    }
    const sessions = allResult.value;
    for (let index = 0; index < sessions.length; index++) {
      if (sessions[index].sessionId === sessionId) {
        return DomainResult.succeed<SessionMetadataLookup>({ found: true, metadata: sessions[index] });
      }
    }
    return DomainResult.succeed<SessionMetadataLookup>({ found: false, metadata: null });
  }

  async save(metadata: SessionMetadata): Promise<DomainResult<boolean>> {
    const normalized = this.normalize(metadata);
    if (normalized === null) {
      return this.invalidBoolean('Session metadata is invalid or contains an unsupported login type');
    }
    const allResult = await this.readAll();
    if (!allResult.success || allResult.value === null) {
      return DomainResult.fail<boolean>(allResult.error as PlatformFailure);
    }
    const sessions = allResult.value;
    let replaced = false;
    for (let index = 0; index < sessions.length; index++) {
      if (sessions[index].sessionId === normalized.sessionId) {
        sessions[index] = normalized;
        replaced = true;
        break;
      }
    }
    if (!replaced) {
      sessions.push(normalized);
    }
    return await this.writeAll(sessions);
  }

  async setTokenValidity(sessionId: string, isValid: boolean): Promise<DomainResult<boolean>> {
    const allResult = await this.readAll();
    if (!allResult.success || allResult.value === null) {
      return DomainResult.fail<boolean>(allResult.error as PlatformFailure);
    }
    const sessions = allResult.value;
    for (let index = 0; index < sessions.length; index++) {
      const current = sessions[index];
      if (current.sessionId === sessionId) {
        sessions[index] = this.copyWithTokenValidity(current, isValid);
        return await this.writeAll(sessions);
      }
    }
    return DomainResult.fail<boolean>(new PlatformFailure(
      DomainErrorCode.SessionMissing,
      PlatformFailureKind.InvalidData,
      'session_metadata.set_token_validity',
      'Cannot update a session that is not stored',
      false
    ));
  }

  async remove(sessionId: string): Promise<DomainResult<boolean>> {
    const allResult = await this.readAll();
    if (!allResult.success || allResult.value === null) {
      return DomainResult.fail<boolean>(allResult.error as PlatformFailure);
    }
    const retained: SessionMetadata[] = [];
    allResult.value.forEach((metadata: SessionMetadata) => {
      if (metadata.sessionId !== sessionId) {
        retained.push(metadata);
      }
    });
    return await this.writeAll(retained);
  }

  private async readAll(): Promise<DomainResult<SessionMetadata[]>> {
    try {
      const raw = await this.preferences.get(PreferencesSessionMetadataStore.SNAPSHOT_KEY, '');
      if (raw.length === 0) {
        return DomainResult.succeed<SessionMetadata[]>([]);
      }
      const parsed = JSON.parse(raw) as MetadataEnvelope;
      if (parsed.schemaVersion !== 1 || !Array.isArray(parsed.sessions)) {
        return this.invalidArray('Session metadata schema is unsupported');
      }
      const sessions: SessionMetadata[] = [];
      for (let index = 0; index < parsed.sessions.length; index++) {
        const normalized = this.normalize(parsed.sessions[index]);
        if (normalized === null) {
          return this.invalidArray('Stored session metadata is malformed');
        }
        sessions.push(normalized);
      }
      return DomainResult.succeed<SessionMetadata[]>(sessions);
    } catch (error) {
      const failure = error as Error;
      return DomainResult.fail<SessionMetadata[]>(new PlatformFailure(
        DomainErrorCode.StorageReadFailed,
        PlatformFailureKind.ReadFailed,
        'session_metadata.read',
        'Unable to read session metadata',
        true,
        platformCodeOf(failure)
      ));
    }
  }

  private async writeAll(sessions: SessionMetadata[]): Promise<DomainResult<boolean>> {
    try {
      const envelope: MetadataEnvelope = { schemaVersion: 1, sessions: sessions };
      const serialized = JSON.stringify(envelope);
      if (this.containsCredentialField(serialized)) {
        return DomainResult.fail<boolean>(new PlatformFailure(
          DomainErrorCode.StorageWriteFailed,
          PlatformFailureKind.InvalidData,
          'session_metadata.write',
          'Credential material was rejected from ordinary preferences',
          false
        ));
      }
      await this.preferences.put(PreferencesSessionMetadataStore.SNAPSHOT_KEY, serialized);
      return DomainResult.succeed<boolean>(true);
    } catch (error) {
      const failure = error as Error;
      return DomainResult.fail<boolean>(new PlatformFailure(
        DomainErrorCode.StorageWriteFailed,
        PlatformFailureKind.WriteFailed,
        'session_metadata.write',
        'Unable to write session metadata',
        true,
        platformCodeOf(failure)
      ));
    }
  }

  private normalize(value: SessionMetadata): SessionMetadata | null {
    if (value === null || typeof value !== 'object' ||
      typeof value.sessionId !== 'string' || value.sessionId.length === 0 ||
      typeof value.userId !== 'string' || value.userId.length === 0 ||
      typeof value.deviceId !== 'string' ||
      typeof value.homeserverUrl !== 'string' || value.homeserverUrl.length === 0 ||
      !this.isLoginType(value.loginType) ||
      typeof value.loginTimestampMs !== 'number' ||
      typeof value.isTokenValid !== 'boolean' ||
      typeof value.position !== 'number' ||
      typeof value.lastUsageIndex !== 'number') {
      return null;
    }
    return {
      sessionId: value.sessionId,
      userId: value.userId,
      deviceId: value.deviceId,
      homeserverUrl: value.homeserverUrl,
      loginType: value.loginType,
      loginTimestampMs: value.loginTimestampMs,
      isTokenValid: value.isTokenValid,
      position: value.position,
      lastUsageIndex: value.lastUsageIndex,
      userDisplayName: typeof value.userDisplayName === 'string' ? value.userDisplayName : null,
      userAvatarUrl: typeof value.userAvatarUrl === 'string' ? value.userAvatarUrl : null
    };
  }

  private copyWithTokenValidity(value: SessionMetadata, isValid: boolean): SessionMetadata {
    return {
      sessionId: value.sessionId,
      userId: value.userId,
      deviceId: value.deviceId,
      homeserverUrl: value.homeserverUrl,
      loginType: value.loginType,
      loginTimestampMs: value.loginTimestampMs,
      isTokenValid: isValid,
      position: value.position,
      lastUsageIndex: value.lastUsageIndex,
      userDisplayName: value.userDisplayName,
      userAvatarUrl: value.userAvatarUrl
    };
  }

  private isLoginType(value: SessionLoginType): boolean {
    return value === SessionLoginType.Password || value === SessionLoginType.Oidc ||
      value === SessionLoginType.Sso || value === SessionLoginType.Direct ||
      value === SessionLoginType.Qr || value === SessionLoginType.Unknown;
  }

  private containsCredentialField(serialized: string): boolean {
    return serialized.includes('"accessToken":') || serialized.includes('"refreshToken":') ||
      serialized.includes('"databasePassphrase":') || serialized.includes('"password":');
  }

  private invalidLookup(message: string): DomainResult<SessionMetadataLookup> {
    return DomainResult.fail<SessionMetadataLookup>(new PlatformFailure(
      DomainErrorCode.InvalidInput,
      PlatformFailureKind.InvalidData,
      'session_metadata.lookup',
      message,
      false
    ));
  }

  private invalidBoolean(message: string): DomainResult<boolean> {
    return DomainResult.fail<boolean>(new PlatformFailure(
      DomainErrorCode.InvalidInput,
      PlatformFailureKind.InvalidData,
      'session_metadata.validate',
      message,
      false
    ));
  }

  private invalidArray(message: string): DomainResult<SessionMetadata[]> {
    return DomainResult.fail<SessionMetadata[]>(new PlatformFailure(
      DomainErrorCode.StorageReadFailed,
      PlatformFailureKind.InvalidData,
      'session_metadata.decode',
      message,
      false
    ));
  }
}
