import common from '@ohos.app.ability.common';
import { DomainErrorCode, DomainResult } from '../../core/DomainResult';
import { PlatformFailure, PlatformFailureKind } from '../errors/PlatformFailure';
import { OpenHarmonyStringPreferences } from '../storage/StringPreferences';
import type { StringPreferences } from '../storage/StringPreferences';
import { PushRegistrationPhase } from './NotificationPushContracts';
import type {
  PushRegistrationSnapshot,
  PushRegistrationStore
} from './NotificationPushContracts';

interface PushRegistrationEnvelope {
  schemaVersion: number;
  registrations: PushRegistrationSnapshot[];
}

/** Persists non-secret push registration state. Provider tokens are intentionally absent. */
export class PreferencesPushRegistrationStore implements PushRegistrationStore {
  private static readonly STORE_NAME: string = 'elementx_push_registration_v1';
  private static readonly KEY: string = 'registrations';
  private readonly preferences: StringPreferences;

  constructor(preferencesStore: StringPreferences) {
    this.preferences = preferencesStore;
  }

  static async create(context: common.Context): Promise<PreferencesPushRegistrationStore> {
    const store = await OpenHarmonyStringPreferences.create(
      context,
      PreferencesPushRegistrationStore.STORE_NAME
    );
    return new PreferencesPushRegistrationStore(store);
  }

  async get(sessionId: string): Promise<DomainResult<PushRegistrationSnapshot>> {
    try {
      const registrations = await this.readAll();
      for (let index = 0; index < registrations.length; index++) {
        if (registrations[index].sessionId === sessionId) {
          return DomainResult.succeed<PushRegistrationSnapshot>(registrations[index]);
        }
      }
      return DomainResult.succeed<PushRegistrationSnapshot>(this.empty(sessionId));
    } catch (error) {
      return this.failure<PushRegistrationSnapshot>(
        DomainErrorCode.StorageReadFailed,
        PlatformFailureKind.ReadFailed,
        'push_registration.read'
      );
    }
  }

  async save(snapshot: PushRegistrationSnapshot): Promise<DomainResult<boolean>> {
    if (!this.isValid(snapshot)) {
      return this.failure<boolean>(
        DomainErrorCode.InvalidInput,
        PlatformFailureKind.InvalidData,
        'push_registration.validate'
      );
    }
    try {
      const registrations = await this.readAll();
      let replaced = false;
      for (let index = 0; index < registrations.length; index++) {
        if (registrations[index].sessionId === snapshot.sessionId) {
          registrations[index] = snapshot;
          replaced = true;
          break;
        }
      }
      if (!replaced) {
        registrations.push(snapshot);
      }
      await this.writeAll(registrations);
      return DomainResult.succeed<boolean>(true);
    } catch (error) {
      return this.failure<boolean>(
        DomainErrorCode.StorageWriteFailed,
        PlatformFailureKind.WriteFailed,
        'push_registration.write'
      );
    }
  }

  async reset(sessionId: string): Promise<DomainResult<boolean>> {
    try {
      const registrations = await this.readAll();
      const retained = registrations.filter(
        (snapshot: PushRegistrationSnapshot) => snapshot.sessionId !== sessionId
      );
      await this.writeAll(retained);
      return DomainResult.succeed<boolean>(true);
    } catch (error) {
      return this.failure<boolean>(
        DomainErrorCode.StorageDeleteFailed,
        PlatformFailureKind.DeleteFailed,
        'push_registration.reset'
      );
    }
  }

  private async readAll(): Promise<PushRegistrationSnapshot[]> {
    const raw = await this.preferences.get(PreferencesPushRegistrationStore.KEY, '');
    if (raw.length === 0) {
      return [];
    }
    const envelope = JSON.parse(raw) as PushRegistrationEnvelope;
    if (envelope.schemaVersion !== 1 || !Array.isArray(envelope.registrations)) {
      throw new Error('Unsupported push registration schema');
    }
    for (let index = 0; index < envelope.registrations.length; index++) {
      if (!this.isValid(envelope.registrations[index])) {
        throw new Error('Malformed push registration state');
      }
    }
    return envelope.registrations;
  }

  private async writeAll(registrations: PushRegistrationSnapshot[]): Promise<void> {
    const envelope: PushRegistrationEnvelope = { schemaVersion: 1, registrations: registrations };
    const serialized = JSON.stringify(envelope);
    if (serialized.includes('"pushToken"') || serialized.includes('"registrationToken"')) {
      throw new Error('Push token rejected from ordinary preferences');
    }
    await this.preferences.put(PreferencesPushRegistrationStore.KEY, serialized);
  }

  private empty(sessionId: string): PushRegistrationSnapshot {
    return {
      sessionId: sessionId,
      providerName: null,
      phase: PushRegistrationPhase.Unregistered,
      notificationsEnabledForDevice: true,
      ignoreRegistrationError: false,
      lastAttemptAtMs: null,
      lastErrorCode: null
    };
  }

  private isValid(snapshot: PushRegistrationSnapshot): boolean {
    return snapshot !== null && typeof snapshot === 'object' && snapshot.sessionId.length > 0 &&
      (snapshot.phase === PushRegistrationPhase.Unregistered ||
        snapshot.phase === PushRegistrationPhase.Registering ||
        snapshot.phase === PushRegistrationPhase.Registered ||
        snapshot.phase === PushRegistrationPhase.Failed);
  }

  private failure<T>(
    code: DomainErrorCode,
    kind: PlatformFailureKind,
    operation: string
  ): DomainResult<T> {
    return DomainResult.fail<T>(new PlatformFailure(
      code,
      kind,
      operation,
      `Push registration ${operation} failed`,
      code !== DomainErrorCode.InvalidInput
    ));
  }
}
