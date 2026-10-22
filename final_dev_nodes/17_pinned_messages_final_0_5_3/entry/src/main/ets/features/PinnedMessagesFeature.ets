import preferences from '@ohos.data.preferences';
import common from '@ohos.app.ability.common';
import { PinnedMessage, PinnedTimelinePort, PinnedRoomPort, RoomSession } from './MatrixRoomServices';
export { PinnedMessage, PinnedTimelinePort, PinnedRoomPort } from './MatrixRoomServices';

export enum PinnedMessagesListState {
  Idle = 'idle', Loading = 'loading', Empty = 'empty', Filled = 'filled', Failed = 'failed'
}

export class PinnedMessagesRepository {
  private static readonly STORE_NAME: string = 'element_x_pinned_messages';
  private static readonly PINNED_KEY: string = 'room_design_pinned_events';
  private timeline: PinnedTimelinePort | undefined = undefined;
  private unsubscribe: (() => void) | undefined = undefined;
  private generation: number = 0;
  private writes: Promise<void> = Promise.resolve();
  private rejectFirst: ((error: Error) => void) | undefined = undefined;

  readonly room: PinnedRoomPort | undefined;

  constructor(room: PinnedRoomPort | undefined) {
    this.room = room;
  }

  async openPinnedTimeline(context: common.Context, onItems: (items: PinnedMessage[]) => void): Promise<PinnedMessage[]> {
    if (this.room === undefined) {
      throw new Error('Pinned timeline SDK service unavailable');
    }
    this.close();
    const generation: number = this.generation;
    const timeline: PinnedTimelinePort = await this.room.pinnedEventsTimeline();
    if (generation !== this.generation) {
      timeline.close();
      throw new Error('Pinned timeline request cancelled');
    }
    this.timeline = timeline;
    return new Promise<PinnedMessage[]>((resolve, reject) => {
      let first: boolean = true;
      this.rejectFirst = (error: Error): void => {
        if (first) {
          first = false;
          reject(error);
        }
      };
      this.unsubscribe = timeline.subscribeItems((items: PinnedMessage[]) => {
        const snapshot: PinnedMessage[] = this.copy(items);
        // Only SDK item flow can change the authoritative list or its cache.
        this.writes = this.writes.then(async (): Promise<void> => {
          if (generation !== this.generation) {
            return;
          }
          await this.persistPinnedState(context, snapshot);
          if (generation !== this.generation) {
            return;
          }
          onItems(this.copy(snapshot));
          if (first) {
            first = false;
            this.rejectFirst = undefined;
            resolve(this.copy(snapshot));
          }
        }).catch((error: Error): void => {
          if (first) {
            first = false;
            this.rejectFirst = undefined;
            reject(error);
          }
        });
      });
    });
  }

  async unpinEvent(eventId: string): Promise<boolean> {
    if (this.timeline === undefined) {
      throw new Error('No active SDK pinned timeline');
    }
    return this.timeline.unpinEvent(eventId);
  }

  async persistPinnedState(context: common.Context, messages: PinnedMessage[]): Promise<void> {
    const store = await preferences.getPreferences(context, PinnedMessagesRepository.STORE_NAME);
    await store.put(PinnedMessagesRepository.PINNED_KEY, JSON.stringify(messages));
    await store.flush();
  }

  close(): void {
    this.generation += 1;
    const unsubscribe: (() => void) | undefined = this.unsubscribe;
    const timeline: PinnedTimelinePort | undefined = this.timeline;
    this.unsubscribe = undefined;
    this.timeline = undefined;
    this.rejectFirst?.(new Error('Pinned item subscription cancelled'));
    this.rejectFirst = undefined;
    try {
      unsubscribe?.();
    } finally {
      timeline?.close();
    }
  }

  private copy(items: PinnedMessage[]): PinnedMessage[] {
    return items.map((item: PinnedMessage) => new PinnedMessage(item.eventId, item.sender, item.body));
  }
}

export class RoomTimelineModel {
  items: PinnedMessage[] = [];
  focusedEventId: string = '';
  focusedIndex: number = -1;
  private generation: number = 0;

  readonly room: PinnedRoomPort | undefined;

  constructor(room: PinnedRoomPort | undefined) {
    this.room = room;
  }

  async load(): Promise<void> {
    await this.loadAround(undefined);
  }

  async focusOnEvent(eventId: string): Promise<void> {
    await this.loadAround(eventId);
  }

  private async loadAround(eventId: string | undefined): Promise<void> {
    if (this.room === undefined) {
      throw new Error('Room timeline SDK service unavailable');
    }
    const generation: number = ++this.generation;
    const items: PinnedMessage[] = await this.room.loadTimeline(eventId);
    if (generation !== this.generation) {
      throw new Error('Room timeline navigation cancelled');
    }
    const index: number = eventId === undefined ? -1 : items.findIndex((item: PinnedMessage) => item.eventId === eventId);
    if (eventId !== undefined && index < 0) {
      throw new Error('Focused event was not returned by the room timeline');
    }
    this.items = items.map((item: PinnedMessage) => new PinnedMessage(item.eventId, item.sender, item.body));
    this.focusedEventId = eventId === undefined ? '' : eventId;
    this.focusedIndex = index;
  }

  dispose(): void {
    this.generation += 1;
  }
}

// Owned by the room page, not recreated by its pinned-list child.
export class PinnedEventsTimelineProvider {
  private operation: Promise<PinnedMessage[]> | undefined = undefined;
  private listeners: ((items: PinnedMessage[]) => void)[] = [];
  private items: PinnedMessage[] | undefined = undefined;
  private disposed: boolean = false;
  readonly repository: PinnedMessagesRepository;

  constructor(repository: PinnedMessagesRepository) {
    this.repository = repository;
  }

  start(context: common.Context): Promise<PinnedMessage[]> {
    if (this.disposed) {
      return Promise.reject(new Error('Room pinned provider disposed'));
    }
    if (this.operation !== undefined) {
      return this.operation;
    }
    this.operation = this.repository.openPinnedTimeline(context, (items: PinnedMessage[]) => {
      if (!this.disposed) {
        this.items = items;
        this.listeners.forEach((listener: (items: PinnedMessage[]) => void) => listener(items));
      }
    });
    // Keep a failed state retryable; never manufacture an empty success.
    this.operation.catch(() => {
      this.operation = undefined;
    });
    return this.operation;
  }

  subscribe(listener: (items: PinnedMessage[]) => void): () => void {
    this.listeners.push(listener);
    if (this.items !== undefined) {
      listener(this.items);
    }
    return (): void => {
      this.listeners = this.listeners.filter((value: (items: PinnedMessage[]) => void) => value !== listener);
    };
  }

  dispose(): void {
    this.disposed = true;
    this.listeners = [];
    this.repository.close();
  }
}

export class PinnedMessagesListPresenter {
  listState: PinnedMessagesListState = PinnedMessagesListState.Idle;
  pinnedMessages: PinnedMessage[] = [];
  canPinUnpin: boolean = false;
  errorMessage: string = '';
  retryEnabled: boolean = false;
  private listeners: (() => void)[] = [];
  private unsubscribeSync: (() => void) | undefined = undefined;
  private permissionGeneration: number = 0;
  private generation: number = 0;
  private disposed: boolean = false;
  private unsubscribeItems: (() => void) | undefined = undefined;

  readonly repository: PinnedMessagesRepository;
  readonly parent: RoomTimelineModel;
  readonly provider: PinnedEventsTimelineProvider;

  constructor(repository: PinnedMessagesRepository, parent: RoomTimelineModel) {
    this.repository = repository;
    this.parent = parent;
    this.provider = new PinnedEventsTimelineProvider(repository);
  }

  startRoom(context: common.Context): void {
    // Original MessagesFlowNode starts this room-scoped service before child UI.
    this.provider.start(context).catch(() => {
      // The list exposes Failed when opened; room timeline remains usable.
    });
  }

  subscribe(listener: () => void): () => void {
    this.listeners.push(listener);
    return (): void => {
      this.listeners = this.listeners.filter((value: () => void) => value !== listener);
    };
  }

  private publish(): void {
    this.listeners.forEach((listener: () => void) => listener());
  }

  private async refreshPermission(): Promise<void> {
    const generation: number = ++this.permissionGeneration;
    let allowed: boolean = false;
    try {
      allowed = this.repository.room !== undefined && await this.repository.room.canPinUnpin();
    } catch (error) {
      allowed = false;
    }
    if (!this.disposed && generation === this.permissionGeneration) {
      this.canPinUnpin = allowed;
      this.publish();
    }
  }

  async openPinnedMessages(context: common.Context, beforeResult?: () => Promise<void>): Promise<void> {
    if (this.disposed) {
      return;
    }
    const generation: number = ++this.generation;
    this.listState = PinnedMessagesListState.Loading;
    this.errorMessage = '';
    this.retryEnabled = false;
    this.publish();
    this.unsubscribeSync?.();
    this.unsubscribeSync = this.repository.room?.subscribeSync(() => {
      this.refreshPermission();
    });
    this.refreshPermission();
    let pendingItems: PinnedMessage[] = [];
    let frameReady: boolean = false;
    try {
      this.unsubscribeItems?.();
      this.unsubscribeItems = this.provider.subscribe((items: PinnedMessage[]) => {
        pendingItems = items;
        if (frameReady && generation === this.generation && !this.disposed) {
          this.applyItems(items);
        }
      });
      await this.provider.start(context);
      if (beforeResult !== undefined) {
        await beforeResult();
      }
      frameReady = true;
      if (generation === this.generation && !this.disposed) {
        this.applyItems(pendingItems);
      }
    } catch (error) {
      if (generation === this.generation && !this.disposed) {
        this.listState = PinnedMessagesListState.Failed;
        this.errorMessage = this.repository.room === undefined ?
          'Pinned timeline SDK service unavailable' : 'Unable to load pinned timeline';
        this.retryEnabled = true;
        this.publish();
      }
    }
  }

  private applyItems(items: PinnedMessage[]): void {
    this.pinnedMessages = items;
    this.listState = items.length === 0 ? PinnedMessagesListState.Empty : PinnedMessagesListState.Filled;
    this.publish();
  }

  async retry(context: common.Context): Promise<void> {
    await this.openPinnedMessages(context);
  }

  availableActions(): string[] {
    return this.canPinUnpin ? ['view_in_timeline', 'unpin'] : ['view_in_timeline'];
  }

  async viewInTimeline(eventId: string): Promise<void> {
    await this.parent.focusOnEvent(eventId);
  }

  async unpin(_context: common.Context, eventId: string): Promise<boolean> {
    if (this.disposed || !this.canPinUnpin) {
      return false;
    }
    const generation: number = this.generation;
    this.errorMessage = '';
    try {
      const changed: boolean = await this.repository.unpinEvent(eventId);
      // The SDK item subscription, not this acknowledgement, updates the list.
      if (generation === this.generation && !this.disposed) {
        this.retryEnabled = false;
        this.publish();
      }
      return changed;
    } catch (error) {
      if (generation === this.generation && !this.disposed) {
        this.errorMessage = 'Unable to unpin this message';
        this.retryEnabled = true;
        this.publish();
      }
      return false;
    }
  }

  dismissError(): void {
    this.errorMessage = '';
    this.publish();
  }

  dispose(): void {
    this.disposed = true;
    this.generation += 1;
    this.permissionGeneration += 1;
    this.unsubscribeSync?.();
    this.unsubscribeItems?.();
    this.provider.dispose();
    this.parent.dispose();
    this.listeners = [];
  }
}

export class PinnedMessagesSession {
  static configureRoom(room: PinnedRoomPort | undefined): void {
    RoomSession.configureRoom(room);
  }

  static createPresenter(): PinnedMessagesListPresenter {
    const room: PinnedRoomPort | undefined = RoomSession.createService();
    return new PinnedMessagesListPresenter(new PinnedMessagesRepository(room), new RoomTimelineModel(room));
  }
}
