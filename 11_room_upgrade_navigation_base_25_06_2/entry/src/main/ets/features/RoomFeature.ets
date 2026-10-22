export class SuccessorRoom {
  roomId: string;
  reason: string | null;

  constructor(roomId: string, reason: string | null = null) {
    this.roomId = roomId;
    this.reason = reason;
  }
}

export class RoomSummary {
  roomId: string;
  name: string;
  lastMessage: string;
  successorRoom: SuccessorRoom | null;

  constructor(roomId: string, name: string, lastMessage: string, successorRoom: SuccessorRoom | null = null) {
    this.roomId = roomId;
    this.name = name;
    this.lastMessage = lastMessage;
    this.successorRoom = successorRoom === null ? null : new SuccessorRoom(successorRoom.roomId, successorRoom.reason);
  }
}

export class RoomGateway {
  lastOpenedRoomId: string = '';
  sentMessages: string[] = [];
  private readonly rooms: Map<string, RoomSummary> = new Map();

  constructor(roomInfos: RoomSummary[] = [
    new RoomSummary('!old:example.org', 'Product planning', 'Earlier message'),
    new RoomSummary('!new:example.org', 'Product planning v2', 'Welcome to the replacement room')
  ]) {
    roomInfos.forEach((room: RoomSummary) => this.rooms.set(room.roomId, room));
  }

  async requestRoomInfo(roomId: string): Promise<RoomSummary | null> {
    return this.rooms.get(roomId) ?? null;
  }

  openRoom(roomId: string): void {
    this.lastOpenedRoomId = roomId;
  }

  sendMessage(message: string): boolean {
    const normalized = message.trim();
    if (normalized.length === 0) {
      return false;
    }
    this.sentMessages.push(normalized);
    return true;
  }
}

export class RoomPresenter {
  readonly gateway: RoomGateway;
  room: RoomSummary = new RoomSummary('!old:example.org', 'Product planning', 'Earlier message');
  history: string[] = ['Earlier message'];

  constructor(gateway: RoomGateway) {
    this.gateway = gateway;
  }

  async observeRoomInfo(roomId: string): Promise<boolean> {
    const info = await this.gateway.requestRoomInfo(roomId);
    if (info === null || info.roomId !== roomId) {
      return false;
    }
    this.room = new RoomSummary(info.roomId, info.name, info.lastMessage, info.successorRoom);
    this.history = [info.lastMessage];
    return true;
  }

  async selectRoom(roomId: string): Promise<boolean> {
    return this.observeRoomInfo(roomId);
  }

  openRoom(): void {
    this.gateway.openRoom(this.room.roomId);
  }

  sendMessage(message: string): boolean {
    if (!this.gateway.sendMessage(message)) {
      return false;
    }
    this.history.push(message.trim());
    return true;
  }
}
