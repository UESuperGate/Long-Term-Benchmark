import preferences from '@ohos.data.preferences';
import common from '@ohos.app.ability.common';

export enum PinnedMessagesListState {
  Idle = 'idle',
  Loading = 'loading',
  Empty = 'empty',
  Filled = 'filled',
  Failed = 'failed'
}

class PersistedPinnedMessage {
  eventId: string;
  sender: string;
  body: string;

  constructor(eventId: string, sender: string, body: string) {
    this.eventId = eventId;
    this.sender = sender;
    this.body = body;
  }
}

export class PinnedMessage {
  eventId: string;
  sender: string;
  body: string;

  constructor(eventId: string, sender: string, body: string) {
    this.eventId = eventId;
    this.sender = sender;
    this.body = body;
  }
}

export class PinnedMessagesRepository {
  private static readonly STORE_NAME: string = 'element_x_pinned_messages';
  private static readonly PINNED_KEY: string = 'room_design_pinned_events';
  failNextLoad: boolean = false;
  failNextUnpin: boolean = false;
  lastUnpinnedEventId: string = '';

  async openPinnedTimeline(context: common.Context): Promise<PinnedMessage[]> {
    if (this.failNextLoad) {
      this.failNextLoad = false;
      throw new Error('Pinned timeline is temporarily unavailable');
    }
    const store = await preferences.getPreferences(context, PinnedMessagesRepository.STORE_NAME);
    const value = await store.get(PinnedMessagesRepository.PINNED_KEY, '');
    if (typeof value !== 'string' || value.length === 0) {
      const initial: PinnedMessage[] = [
        new PinnedMessage('$rules', 'Alice', 'Please read the room rules'),
        new PinnedMessage('$launch', 'Bob', 'Launch checklist and owner notes')
      ];
      await this.persistPinnedState(context, initial);
      return this.copy(initial);
    }
    try {
      const rows = JSON.parse(value) as PersistedPinnedMessage[];
      return rows.map((row: PersistedPinnedMessage) => new PinnedMessage(row.eventId, row.sender, row.body));
    } catch (error) {
      throw new Error('Pinned timeline cache is unreadable');
    }
  }

  async unpinEvent(context: common.Context, eventId: string, current: PinnedMessage[]): Promise<PinnedMessage[]> {
    if (this.failNextUnpin) {
      this.failNextUnpin = false;
      throw new Error('Unable to unpin this message');
    }
    this.lastUnpinnedEventId = eventId;
    const updated = current.filter((message: PinnedMessage) => message.eventId !== eventId);
    await this.persistPinnedState(context, updated);
    return this.copy(updated);
  }

  async persistPinnedState(context: common.Context, messages: PinnedMessage[]): Promise<void> {
    const rows = messages.map((message: PinnedMessage) => {
      return new PersistedPinnedMessage(message.eventId, message.sender, message.body);
    });
    const store = await preferences.getPreferences(context, PinnedMessagesRepository.STORE_NAME);
    await store.put(PinnedMessagesRepository.PINNED_KEY, JSON.stringify(rows));
    await store.flush();
  }

  private copy(messages: PinnedMessage[]): PinnedMessage[] {
    return messages.map((message: PinnedMessage) => {
      return new PinnedMessage(message.eventId, message.sender, message.body);
    });
  }
}

export class PinnedMessagesListPresenter {
  readonly repository: PinnedMessagesRepository;
  listState: PinnedMessagesListState = PinnedMessagesListState.Idle;
  pinnedMessages: PinnedMessage[] = [];
  canPinUnpin: boolean = false;
  focusedEventId: string = '';
  errorMessage: string = '';
  retryEnabled: boolean = false;

  constructor(repository: PinnedMessagesRepository) {
    this.repository = repository;
  }

  async openPinnedMessages(context: common.Context): Promise<void> {
    this.listState = PinnedMessagesListState.Loading;
    this.errorMessage = '';
    this.retryEnabled = false;
    try {
      const messages = await this.repository.openPinnedTimeline(context);
      this.pinnedMessages = messages;
      this.listState = messages.length === 0 ? PinnedMessagesListState.Empty : PinnedMessagesListState.Filled;
    } catch (error) {
      this.listState = PinnedMessagesListState.Failed;
      this.errorMessage = `${error}`;
      this.retryEnabled = true;
    }
  }

  async retry(context: common.Context): Promise<void> {
    await this.openPinnedMessages(context);
  }

  setPermission(canPinUnpin: boolean): void {
    this.canPinUnpin = canPinUnpin;
  }

  availableActions(): string[] {
    const actions: string[] = ['view_in_timeline'];
    if (this.canPinUnpin) {
      actions.push('unpin');
    }
    return actions;
  }

  viewInTimeline(eventId: string): void {
    this.focusedEventId = eventId;
  }

  async unpin(context: common.Context, eventId: string): Promise<boolean> {
    if (!this.canPinUnpin) {
      return false;
    }
    const previous = this.pinnedMessages.slice();
    this.errorMessage = '';
    try {
      this.pinnedMessages = await this.repository.unpinEvent(context, eventId, previous);
      this.listState = this.pinnedMessages.length === 0 ? PinnedMessagesListState.Empty : PinnedMessagesListState.Filled;
      this.retryEnabled = false;
      return true;
    } catch (error) {
      this.pinnedMessages = previous;
      this.listState = PinnedMessagesListState.Filled;
      this.errorMessage = `${error}`;
      this.retryEnabled = true;
      return false;
    }
  }

  dismissError(): void {
    this.errorMessage = '';
  }
}
