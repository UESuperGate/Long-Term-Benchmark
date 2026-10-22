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

export interface PinnedTimelinePort {
  subscribeItems(listener: (items: PinnedMessage[]) => void): () => void;
  unpinEvent(eventId: string): Promise<boolean>;
  close(): void;
}

export interface PinnedRoomPort {
  roomId: string;
  pinnedEventsTimeline(): Promise<PinnedTimelinePort>;
  canPinUnpin(): Promise<boolean>;
  subscribeSync(listener: () => void): () => void;
  loadTimeline(focusedEventId: string | undefined): Promise<PinnedMessage[]>;
}

// v0.5.1 already exposes these SDK operations; no collection UI/provider here.
export class MatrixRoomService implements PinnedRoomPort {
  readonly port: PinnedRoomPort;
  readonly roomId: string;

  constructor(port: PinnedRoomPort) {
    this.port = port;
    this.roomId = port.roomId;
  }

  pinnedEventsTimeline(): Promise<PinnedTimelinePort> {
    return this.port.pinnedEventsTimeline();
  }

  canPinUnpin(): Promise<boolean> {
    return this.port.canPinUnpin();
  }

  subscribeSync(listener: () => void): () => void {
    return this.port.subscribeSync(listener);
  }

  loadTimeline(focusedEventId: string | undefined): Promise<PinnedMessage[]> {
    return this.port.loadTimeline(focusedEventId);
  }
}

export class RoomSession {
  private static room: PinnedRoomPort | undefined = undefined;

  static configureRoom(room: PinnedRoomPort | undefined): void {
    RoomSession.room = room;
  }

  static createService(): MatrixRoomService | undefined {
    return RoomSession.room === undefined ? undefined : new MatrixRoomService(RoomSession.room);
  }
}
