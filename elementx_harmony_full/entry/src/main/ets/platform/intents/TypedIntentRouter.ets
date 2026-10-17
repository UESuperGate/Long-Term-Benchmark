import common from '@ohos.app.ability.common';
import { DomainErrorCode, DomainResult } from '../../core/DomainResult';
import { PlatformFailure, PlatformFailureKind } from '../errors/PlatformFailure';
import { OpenHarmonyStringPreferences, StringPreferences } from '../storage/StringPreferences';

export enum AppIntentKind {
  OpenRoom = 'open_room',
  OpenThread = 'open_thread',
  ShareMedia = 'share_media',
  NotificationAction = 'notification_action',
  ExternalUri = 'external_uri'
}

export interface AppIntent {
  id: string;
  kind: AppIntentKind;
  receivedAtMs: number;
  uri: string | null;
  sessionId: string | null;
  roomId: string | null;
  eventId: string | null;
  action: string | null;
}

interface IntentEnvelope {
  schemaVersion: number;
  intents: AppIntent[];
}

export interface IntentQueuePersistence {
  load(): Promise<AppIntent[]>;
  save(intents: AppIntent[]): Promise<void>;
}

export interface IntentQueueSubscription {
  close(): void;
}

export type IntentQueueListener = (pending: AppIntent[]) => void;

class IntentQueueSubscriptionImpl implements IntentQueueSubscription {
  private closed: boolean = false;
  private readonly closeAction: () => void;

  constructor(closeAction: () => void) {
    this.closeAction = closeAction;
  }

  close(): void {
    if (this.closed) {
      return;
    }
    this.closed = true;
    this.closeAction();
  }
}

export class PreferencesIntentQueuePersistence implements IntentQueuePersistence {
  private static readonly STORE_NAME: string = 'elementx_intent_queue_v1';
  private static readonly QUEUE_KEY: string = 'pending_intents';
  private readonly preferences: StringPreferences;

  constructor(preferencesStore: StringPreferences) {
    this.preferences = preferencesStore;
  }

  static async create(context: common.Context): Promise<PreferencesIntentQueuePersistence> {
    const store = await OpenHarmonyStringPreferences.create(
      context,
      PreferencesIntentQueuePersistence.STORE_NAME
    );
    return new PreferencesIntentQueuePersistence(store);
  }

  async load(): Promise<AppIntent[]> {
    const raw = await this.preferences.get(PreferencesIntentQueuePersistence.QUEUE_KEY, '');
    if (raw.length === 0) {
      return [];
    }
    const envelope = JSON.parse(raw) as IntentEnvelope;
    if (envelope.schemaVersion !== 1 || !Array.isArray(envelope.intents)) {
      throw new Error('Unsupported intent queue schema');
    }
    return envelope.intents;
  }

  async save(intents: AppIntent[]): Promise<void> {
    const envelope: IntentEnvelope = { schemaVersion: 1, intents: intents };
    await this.preferences.put(
      PreferencesIntentQueuePersistence.QUEUE_KEY,
      JSON.stringify(envelope)
    );
  }
}

/** Persistent FIFO router. An intent remains pending until its matching id is consumed. */
export class TypedIntentRouter {
  private readonly persistence: IntentQueuePersistence;
  private readonly maximumPending: number;
  private readonly listeners: IntentQueueListener[] = [];
  private pending: AppIntent[] = [];
  private initialized: boolean = false;
  private operationTail: Promise<void> = Promise.resolve();

  constructor(persistence: IntentQueuePersistence, maximumPending: number = 64) {
    this.persistence = persistence;
    this.maximumPending = maximumPending;
  }

  async initialize(): Promise<DomainResult<boolean>> {
    return await this.serialize<boolean>((): Promise<DomainResult<boolean>> => this.initializeUnlocked());
  }

  private async initializeUnlocked(): Promise<DomainResult<boolean>> {
    try {
      const loaded = await this.persistence.load();
      const validated: AppIntent[] = [];
      for (let index = 0; index < loaded.length; index++) {
        if (!this.isValid(loaded[index])) {
          return this.failure<boolean>(
            DomainErrorCode.StorageReadFailed,
            PlatformFailureKind.InvalidData,
            'intent_queue.initialize',
            'Persisted intent queue contains an invalid intent',
            false
          );
        }
        if (!this.containsId(validated, loaded[index].id)) {
          validated.push(this.copy(loaded[index]));
        }
      }
      this.pending = validated.slice(Math.max(0, validated.length - this.maximumPending));
      this.initialized = true;
      this.notifyListeners();
      return DomainResult.succeed<boolean>(true);
    } catch (error) {
      return this.failure<boolean>(
        DomainErrorCode.StorageReadFailed,
        PlatformFailureKind.ReadFailed,
        'intent_queue.initialize',
        'Unable to restore pending intents',
        true
      );
    }
  }

  async enqueue(intent: AppIntent): Promise<DomainResult<boolean>> {
    return await this.serialize<boolean>((): Promise<DomainResult<boolean>> => this.enqueueUnlocked(intent));
  }

  private async enqueueUnlocked(intent: AppIntent): Promise<DomainResult<boolean>> {
    const ready = this.requireInitialized<boolean>('intent_queue.enqueue');
    if (ready !== null) {
      return ready;
    }
    if (!this.isValid(intent)) {
      return this.failure<boolean>(
        DomainErrorCode.InvalidInput,
        PlatformFailureKind.InvalidData,
        'intent_queue.enqueue',
        'Intent is incomplete for its declared kind',
        false
      );
    }
    if (this.containsId(this.pending, intent.id)) {
      return DomainResult.succeed<boolean>(false);
    }
    const updated = this.pending.slice();
    updated.push(this.copy(intent));
    if (updated.length > this.maximumPending) {
      updated.splice(0, updated.length - this.maximumPending);
    }
    return await this.persistAndPublish(updated, true);
  }

  peek(): DomainResult<AppIntent | null> {
    const ready = this.requireInitialized<AppIntent | null>('intent_queue.peek');
    if (ready !== null) {
      return ready;
    }
    return DomainResult.succeed<AppIntent | null>(
      this.pending.length === 0 ? null : this.copy(this.pending[0])
    );
  }

  snapshot(): DomainResult<AppIntent[]> {
    const ready = this.requireInitialized<AppIntent[]>('intent_queue.snapshot');
    if (ready !== null) {
      return ready;
    }
    return DomainResult.succeed<AppIntent[]>(this.copyList(this.pending));
  }

  async consume(id: string): Promise<DomainResult<boolean>> {
    return await this.serialize<boolean>((): Promise<DomainResult<boolean>> => this.consumeUnlocked(id));
  }

  private async consumeUnlocked(id: string): Promise<DomainResult<boolean>> {
    const ready = this.requireInitialized<boolean>('intent_queue.consume');
    if (ready !== null) {
      return ready;
    }
    const updated: AppIntent[] = [];
    let removed = false;
    this.pending.forEach((intent: AppIntent) => {
      if (intent.id === id) {
        removed = true;
      } else {
        updated.push(intent);
      }
    });
    if (!removed) {
      return DomainResult.succeed<boolean>(false);
    }
    return await this.persistAndPublish(updated, true);
  }

  subscribe(listener: IntentQueueListener): IntentQueueSubscription {
    this.listeners.push(listener);
    if (this.initialized) {
      listener(this.copyList(this.pending));
    }
    return new IntentQueueSubscriptionImpl((): void => {
      const index = this.listeners.indexOf(listener);
      if (index >= 0) {
        this.listeners.splice(index, 1);
      }
    });
  }

  private async persistAndPublish(updated: AppIntent[], result: boolean): Promise<DomainResult<boolean>> {
    try {
      await this.persistence.save(this.copyList(updated));
      this.pending = updated;
      this.notifyListeners();
      return DomainResult.succeed<boolean>(result);
    } catch (error) {
      return this.failure<boolean>(
        DomainErrorCode.StorageWriteFailed,
        PlatformFailureKind.WriteFailed,
        'intent_queue.persist',
        'Unable to persist pending intents',
        true
      );
    }
  }

  private isValid(intent: AppIntent): boolean {
    if (intent === null || typeof intent !== 'object' || intent.id.length === 0 ||
      typeof intent.receivedAtMs !== 'number') {
      return false;
    }
    if (intent.kind === AppIntentKind.OpenRoom) {
      return intent.roomId !== null && intent.roomId.length > 0;
    }
    if (intent.kind === AppIntentKind.OpenThread) {
      return intent.roomId !== null && intent.roomId.length > 0 &&
        intent.eventId !== null && intent.eventId.length > 0;
    }
    if (intent.kind === AppIntentKind.ShareMedia || intent.kind === AppIntentKind.ExternalUri) {
      return intent.uri !== null && intent.uri.length > 0;
    }
    if (intent.kind === AppIntentKind.NotificationAction) {
      return intent.action !== null && intent.action.length > 0;
    }
    return false;
  }

  private containsId(intents: AppIntent[], id: string): boolean {
    for (let index = 0; index < intents.length; index++) {
      if (intents[index].id === id) {
        return true;
      }
    }
    return false;
  }

  private copy(intent: AppIntent): AppIntent {
    return {
      id: intent.id,
      kind: intent.kind,
      receivedAtMs: intent.receivedAtMs,
      uri: intent.uri,
      sessionId: intent.sessionId,
      roomId: intent.roomId,
      eventId: intent.eventId,
      action: intent.action
    };
  }

  private copyList(intents: AppIntent[]): AppIntent[] {
    return intents.map((intent: AppIntent) => this.copy(intent));
  }

  private notifyListeners(): void {
    const snapshot = this.copyList(this.pending);
    this.listeners.forEach((listener: IntentQueueListener) => listener(snapshot));
  }

  private async serialize<T>(operation: () => Promise<DomainResult<T>>): Promise<DomainResult<T>> {
    const previous = this.operationTail;
    let release: () => void = (): void => {};
    this.operationTail = new Promise<void>((resolve: () => void): void => {
      release = resolve;
    });
    await previous;
    try {
      return await operation();
    } finally {
      release();
    }
  }

  private requireInitialized<T>(operation: string): DomainResult<T> | null {
    if (this.initialized) {
      return null;
    }
    return this.failure<T>(
      DomainErrorCode.ServiceUnavailable,
      PlatformFailureKind.CapabilityUnavailable,
      operation,
      'Intent router has not been initialized',
      true
    );
  }

  private failure<T>(
    code: DomainErrorCode,
    kind: PlatformFailureKind,
    operation: string,
    message: string,
    retryable: boolean
  ): DomainResult<T> {
    return DomainResult.fail<T>(new PlatformFailure(code, kind, operation, message, retryable));
  }
}
