import { describe, expect, it } from '@ohos/hypium';
import { SessionLoginType } from '../main/ets/session/SessionModels';
import type { SessionMetadata, SessionCredentialSecret } from '../main/ets/session/SessionModels';
import type { StringPreferences } from '../main/ets/platform/storage/StringPreferences';
import { PreferencesSessionMetadataStore } from '../main/ets/session/platform/PreferencesSessionMetadataStore';
import { AssetSessionCredentialStore } from '../main/ets/session/platform/AssetSessionCredentialStore';
import type { SecureAssetBackend } from '../main/ets/session/platform/AssetSessionCredentialStore';
import {
  AppIntentKind,
  TypedIntentRouter
} from '../main/ets/platform/intents/TypedIntentRouter';
import type { AppIntent, IntentQueuePersistence } from '../main/ets/platform/intents/TypedIntentRouter';
import {
  NetworkConnectivityService,
  NetworkConnectivityStatus,
  NetworkTransport
} from '../main/ets/platform/network/NetworkConnectivity';
import type {
  NetworkBackendSubscription,
  NetworkConnectivityBackend,
  NetworkConnectivitySnapshot,
  NetworkSnapshotListener
} from '../main/ets/platform/network/NetworkConnectivity';
import {
  RuntimePermissionController,
  RuntimePermissionState
} from '../main/ets/platform/permissions/RuntimePermissions';
import type {
  PermissionHistory,
  PermissionRequestDecision,
  RuntimePermissionBackend
} from '../main/ets/platform/permissions/RuntimePermissions';
import { PushRegistrationPhase } from '../main/ets/platform/notifications/NotificationPushContracts';
import type { PushRegistrationSnapshot } from '../main/ets/platform/notifications/NotificationPushContracts';
import { PreferencesPushRegistrationStore } from '../main/ets/platform/notifications/PreferencesPushRegistrationStore';
import { OwnedMediaDescriptor } from '../main/ets/platform/media/OwnedMediaDescriptor';
import type { MediaDescriptorBackend } from '../main/ets/platform/media/OwnedMediaDescriptor';
import {
  ApplicationLifecyclePhase,
  ApplicationLifecycleState,
  BackgroundNetworkRequirement,
  BackgroundWorkScheduler
} from '../main/ets/platform/lifecycle/LifecycleAndBackgroundWork';
import type {
  BackgroundWorkRequest,
  BackgroundWorkSchedulerBackend
} from '../main/ets/platform/lifecycle/LifecycleAndBackgroundWork';

interface SessionMetadataWithSecrets extends SessionMetadata {
  accessToken: string;
  databasePassphrase: string;
}

class CodedTestError extends Error {
  readonly code: number;

  constructor(message: string, code: number) {
    super(message);
    this.code = code;
  }
}

class MemoryStringPreferences implements StringPreferences {
  readonly values: Map<string, string> = new Map<string, string>();
  failRead: boolean = false;
  failWrite: boolean = false;

  async get(key: string, defaultValue: string): Promise<string> {
    if (this.failRead) {
      throw new Error('read failed');
    }
    const value = this.values.get(key);
    return value === undefined ? defaultValue : value;
  }

  async put(key: string, value: string): Promise<void> {
    if (this.failWrite) {
      throw new Error('write failed');
    }
    this.values.set(key, value);
  }

  async remove(key: string): Promise<void> {
    this.values.delete(key);
  }

  firstValue(): string {
    let result = '';
    this.values.forEach((value: string) => {
      result = value;
    });
    return result;
  }
}

class MemorySecureAssetBackend implements SecureAssetBackend {
  readonly values: Map<string, Uint8Array> = new Map<string, Uint8Array>();
  failWrites: boolean = false;

  async read(alias: string): Promise<Uint8Array | null> {
    const value = this.values.get(alias);
    return value === undefined ? null : value;
  }

  async write(alias: string, secret: Uint8Array): Promise<void> {
    if (this.failWrites) {
      throw new CodedTestError('secure capability unavailable', 24000017);
    }
    this.values.set(alias, secret);
  }

  async remove(alias: string): Promise<void> {
    this.values.delete(alias);
  }
}

class MemoryIntentPersistence implements IntentQueuePersistence {
  intents: AppIntent[] = [];
  saveCount: number = 0;

  async load(): Promise<AppIntent[]> {
    return this.intents.slice();
  }

  async save(intents: AppIntent[]): Promise<void> {
    this.intents = intents.slice();
    this.saveCount += 1;
  }
}

class FakeNetworkSubscription implements NetworkBackendSubscription {
  closed: boolean = false;

  async close(): Promise<void> {
    this.closed = true;
  }
}

class FakeNetworkBackend implements NetworkConnectivityBackend {
  listener: NetworkSnapshotListener | null = null;
  subscription: FakeNetworkSubscription = new FakeNetworkSubscription();
  snapshotValue: NetworkConnectivitySnapshot = {
    status: NetworkConnectivityStatus.Connected,
    blocked: false,
    metered: false,
    hasInternetCapability: true,
    validated: true,
    airGapped: false,
    transports: [NetworkTransport.Wifi],
    updatedAtMs: 10
  };

  async readSnapshot(): Promise<NetworkConnectivitySnapshot> {
    return this.snapshotValue;
  }

  async subscribe(listener: NetworkSnapshotListener): Promise<NetworkBackendSubscription> {
    this.listener = listener;
    return this.subscription;
  }
}

class MemoryPermissionHistory implements PermissionHistory {
  asked: boolean = false;
  permanentlyDenied: boolean = false;

  async wasAsked(permission: string): Promise<boolean> {
    return this.asked;
  }

  async wasDeniedPermanently(permission: string): Promise<boolean> {
    return this.permanentlyDenied;
  }

  async record(permission: string, asked: boolean, permanentlyDenied: boolean): Promise<void> {
    this.asked = asked;
    this.permanentlyDenied = permanentlyDenied;
  }
}

class FakePermissionBackend implements RuntimePermissionBackend {
  granted: boolean = false;
  decision: PermissionRequestDecision = {
    granted: false,
    dialogShown: true,
    requestAllowed: true
  };

  async isGranted(permission: string): Promise<boolean> {
    return this.granted;
  }

  async request(permission: string): Promise<PermissionRequestDecision> {
    return this.decision;
  }
}

class FakeDescriptorBackend implements MediaDescriptorBackend {
  nextDescriptor: number = 41;
  readonly closed: number[] = [];

  async openReadOnly(uri: string): Promise<number> {
    return this.nextDescriptor;
  }

  async duplicate(fd: number): Promise<number> {
    this.nextDescriptor += 1;
    return this.nextDescriptor;
  }

  async close(fd: number): Promise<void> {
    this.closed.push(fd);
  }
}

class FakeBackgroundBackend implements BackgroundWorkSchedulerBackend {
  scheduled: BackgroundWorkRequest | null = null;
  cancelled: BackgroundWorkRequest | null = null;

  async schedule(request: BackgroundWorkRequest): Promise<void> {
    this.scheduled = request;
  }

  async cancel(request: BackgroundWorkRequest): Promise<void> {
    this.cancelled = request;
  }
}

function metadata(
  sessionId: string = '@alice:example.org',
  lastUsageIndex: number = 1
): SessionMetadata {
  return {
    sessionId: sessionId,
    userId: sessionId,
    deviceId: 'DEVICE',
    homeserverUrl: 'https://matrix.example.org',
    loginType: SessionLoginType.Password,
    loginTimestampMs: 100,
    isTokenValid: true,
    position: lastUsageIndex,
    lastUsageIndex: lastUsageIndex,
    userDisplayName: 'Alice',
    userAvatarUrl: null
  };
}

function credential(): SessionCredentialSecret {
  return {
    sessionId: '@alice:example.org',
    accessToken: 'access-secret',
    refreshToken: 'refresh-secret',
    databasePassphrase: 'database-secret'
  };
}

function intent(id: string, roomId: string = '!room:example.org'): AppIntent {
  return {
    id: id,
    kind: AppIntentKind.OpenRoom,
    receivedAtMs: 100,
    uri: null,
    sessionId: '@alice:example.org',
    roomId: roomId,
    eventId: null,
    action: null
  };
}

export default function platformFoundationTest(): void {
  describe('platformFoundation', () => {
    it('persists metadata ordering without leaking credential fields', 0, async () => {
      const preferences = new MemoryStringPreferences();
      const store = new PreferencesSessionMetadataStore(preferences);
      const unsafe: SessionMetadataWithSecrets = {
        sessionId: '@alice:example.org',
        userId: '@alice:example.org',
        deviceId: 'DEVICE',
        homeserverUrl: 'https://matrix.example.org',
        loginType: SessionLoginType.Password,
        loginTimestampMs: 100,
        isTokenValid: true,
        position: 1,
        lastUsageIndex: 1,
        userDisplayName: 'Alice',
        userAvatarUrl: null,
        accessToken: 'must-not-enter-preferences',
        databasePassphrase: 'must-not-enter-preferences-either'
      };

      expect((await store.save(unsafe)).success).assertTrue();
      expect((await store.save(metadata('@bob:example.org', 2))).success).assertTrue();
      const latest = await store.getLatest();

      expect(latest.value?.metadata?.sessionId).assertEqual('@bob:example.org');
      expect(preferences.firstValue().includes('must-not-enter-preferences')).assertFalse();
      expect(preferences.firstValue().includes('accessToken')).assertFalse();
      expect(preferences.firstValue().includes('databasePassphrase')).assertFalse();
    });

    it('fails closed when secure AssetStore is unavailable', 0, async () => {
      const backend = new MemorySecureAssetBackend();
      backend.failWrites = true;
      const store = new AssetSessionCredentialStore(backend);

      const result = await store.save(credential());

      expect(result.success).assertFalse();
      expect(backend.values.size).assertEqual(0);
      expect(result.error?.retryable).assertFalse();
    });

    it('round trips all credential fields only through the secure backend', 0, async () => {
      const backend = new MemorySecureAssetBackend();
      const store = new AssetSessionCredentialStore(backend);

      expect((await store.save(credential())).success).assertTrue();
      const loaded = await store.get('@alice:example.org');

      expect(loaded.value?.credential?.accessToken).assertEqual('access-secret');
      expect(loaded.value?.credential?.refreshToken).assertEqual('refresh-secret');
      expect(loaded.value?.credential?.databasePassphrase).assertEqual('database-secret');
      expect(backend.values.size).assertEqual(1);
    });

    it('routes intents FIFO, deduplicates ids and persists consumption', 0, async () => {
      const persistence = new MemoryIntentPersistence();
      const router = new TypedIntentRouter(persistence, 4);
      expect((await router.initialize()).success).assertTrue();

      expect((await router.enqueue(intent('one'))).value).assertTrue();
      expect((await router.enqueue(intent('one'))).value).assertFalse();
      expect((await router.enqueue(intent('two'))).value).assertTrue();
      expect(router.peek().value?.id).assertEqual('one');
      expect((await router.consume('one')).value).assertTrue();
      expect(router.peek().value?.id).assertEqual('two');
      expect(persistence.intents.length).assertEqual(1);
    });

    it('serializes concurrent intent writes without dropping either intent', 0, async () => {
      const persistence = new MemoryIntentPersistence();
      const router = new TypedIntentRouter(persistence, 4);
      await router.initialize();

      await Promise.all([router.enqueue(intent('one')), router.enqueue(intent('two'))]);

      expect(router.snapshot().value?.length).assertEqual(2);
      expect(router.snapshot().value?.[0].id).assertEqual('one');
      expect(router.snapshot().value?.[1].id).assertEqual('two');
    });

    it('rejects an incomplete typed intent', 0, async () => {
      const router = new TypedIntentRouter(new MemoryIntentPersistence());
      await router.initialize();
      const result = await router.enqueue(intent('broken', ''));
      expect(result.success).assertFalse();
    });

    it('exposes network snapshot and closes subscriptions', 0, async () => {
      const backend = new FakeNetworkBackend();
      const service = new NetworkConnectivityService(backend);
      const snapshot = await service.snapshot();
      expect(snapshot.value?.status).assertEqual(NetworkConnectivityStatus.Connected);

      const subscription = await service.subscribe((value: NetworkConnectivitySnapshot): void => {
        expect(value.validated).assertTrue();
      });
      expect((await subscription.value?.close())?.success).assertTrue();
      expect(backend.subscription.closed).assertTrue();
    });

    it('tracks first ask and permanent permission denial', 0, async () => {
      const backend = new FakePermissionBackend();
      const history = new MemoryPermissionHistory();
      const controller = new RuntimePermissionController(backend, history);
      expect((await controller.state('ohos.permission.CAMERA')).value)
        .assertEqual(RuntimePermissionState.NotRequested);

      backend.decision = { granted: false, dialogShown: false, requestAllowed: false };
      expect((await controller.request('ohos.permission.CAMERA')).value)
        .assertEqual(RuntimePermissionState.DeniedPermanently);
      expect((await controller.state('ohos.permission.CAMERA')).value)
        .assertEqual(RuntimePermissionState.DeniedPermanently);
    });

    it('owns and closes each media descriptor exactly once', 0, async () => {
      const backend = new FakeDescriptorBackend();
      const opened = await OwnedMediaDescriptor.open('file:///data/media/photo.jpg', backend);
      const descriptor = opened.value;
      expect(descriptor?.borrow().value).assertEqual(41);
      const duplicate = await descriptor?.duplicate();

      expect((await descriptor?.close())?.value).assertTrue();
      expect((await descriptor?.close())?.value).assertFalse();
      expect((await duplicate?.value?.close())?.value).assertTrue();
      expect(backend.closed.length).assertEqual(2);
      expect(descriptor?.borrow().success).assertFalse();
    });

    it('publishes lifecycle changes and delegates constrained background work', 0, async () => {
      const lifecycle = new ApplicationLifecycleState(1);
      let observed = ApplicationLifecyclePhase.Inactive;
      const subscription = lifecycle.subscribe((snapshot): void => {
        observed = snapshot.phase;
      });
      lifecycle.updatePhase(ApplicationLifecyclePhase.Foreground, 2);
      expect(observed).assertEqual(ApplicationLifecyclePhase.Foreground);
      subscription.close();

      const backend = new FakeBackgroundBackend();
      const scheduler = new BackgroundWorkScheduler(backend);
      const request: BackgroundWorkRequest = {
        id: 7,
        uniqueName: 'notification-sync',
        network: BackgroundNetworkRequirement.Any,
        requiresCharging: false,
        persisted: true,
        repeatIntervalMs: null
      };
      expect((await scheduler.schedule(request)).success).assertTrue();
      expect(backend.scheduled?.uniqueName).assertEqual('notification-sync');
    });

    it('persists non-secret push state without provider token fields', 0, async () => {
      const preferences = new MemoryStringPreferences();
      const store = new PreferencesPushRegistrationStore(preferences);
      const snapshot: PushRegistrationSnapshot = {
        sessionId: '@alice:example.org',
        providerName: 'openharmony',
        phase: PushRegistrationPhase.Registered,
        notificationsEnabledForDevice: true,
        ignoreRegistrationError: false,
        lastAttemptAtMs: 100,
        lastErrorCode: null
      };
      expect((await store.save(snapshot)).success).assertTrue();
      expect((await store.get(snapshot.sessionId)).value?.phase)
        .assertEqual(PushRegistrationPhase.Registered);
      expect(preferences.firstValue().includes('pushToken')).assertFalse();
      expect(preferences.firstValue().includes('registrationToken')).assertFalse();
    });

  });
}
