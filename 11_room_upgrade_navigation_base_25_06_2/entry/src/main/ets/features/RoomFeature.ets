export class RoomSummary {
  roomId: string;
  name: string;
  lastMessage: string;

  constructor(roomId: string, name: string, lastMessage: string) {
    this.roomId = roomId;
    this.name = name;
    this.lastMessage = lastMessage;
  }
}

export class RoomGateway {
  lastOpenedRoomId: string = '';
  sentMessages: string[] = [];

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
  readonly room: RoomSummary = new RoomSummary('!old:example.org', 'Product planning', 'Earlier message');
  history: string[] = ['Earlier message'];

  constructor(gateway: RoomGateway) {
    this.gateway = gateway;
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
