export class ChatPerson {
  userId: string;
  displayName: string;
  constructor(userId: string, displayName: string) {
    this.userId = userId;
    this.displayName = displayName;
  }
}

export class ChatMessage {
  id: string;
  senderId: string;
  body: string;
  constructor(id: string, senderId: string, body: string) {
    this.id = id;
    this.senderId = senderId;
    this.body = body;
  }
}

export class ChatRoom {
  roomId: string;
  name: string;
  topic: string;
  memberIds: string[];
  direct: boolean;
  messages: ChatMessage[];
  constructor(roomId: string, name: string, topic: string,
    memberIds: string[], direct: boolean, messages: ChatMessage[]) {
    this.roomId = roomId;
    this.name = name;
    this.topic = topic;
    this.memberIds = memberIds;
    this.direct = direct;
    this.messages = messages;
  }
}

export interface RoomAliasResolution {
  roomId: string;
  servers: string[];
}

export interface RoomAliasDirectory {
  resolveAlias(alias: string): Promise<RoomAliasResolution | undefined>;
}

export interface RoomGateway {
  people(): ChatPerson[];
  findDirectRoom(userId: string): Promise<string | undefined>;
  createDirectRoom(userId: string): Promise<string>;
  createRoom(name: string, topic: string, memberIds: string[]): Promise<string>;
  getRoom(roomId: string, serverNames?: string[]): Promise<ChatRoom>;
  sendMessage(roomId: string, body: string): Promise<ChatMessage>;
  resolveAlias(alias: string): Promise<RoomAliasResolution | undefined>;
}

export interface ChatNavigator {
  openCreateRoom(): Promise<void>;
  openRoom(roomId: string, serverNames?: string[]): Promise<void>;
}

export function errorMessage(error: Error): string {
  return error.message.length > 0 ? error.message : 'Unable to complete the request';
}

// Session-local demo backend. Every returned ID identifies a stored room.
export class DemoRoomGateway implements RoomGateway {
  readonly selfId: string = '@me:demo.local';
  private directory: ChatPerson[] = [
    new ChatPerson('@alice:demo.local', 'Alice'),
    new ChatPerson('@bob:demo.local', 'Bob'),
    new ChatPerson('@charlie:demo.local', 'Charlie')
  ];
  private rooms: Map<string, ChatRoom> = new Map<string, ChatRoom>();
  private sequence: number = 0;
  private messageSequence: number = 0;
  private lobbyId: string;
  private aliasDirectory: RoomAliasDirectory | undefined;

  constructor(aliasDirectory?: RoomAliasDirectory) {
    this.aliasDirectory = aliasDirectory;
    this.lobbyId = this.storeRoom('Lobby', 'Local demo room', [], false);
  }

  people(): ChatPerson[] {
    return this.directory.map((person: ChatPerson) => new ChatPerson(person.userId, person.displayName));
  }

  async findDirectRoom(userId: string): Promise<string | undefined> {
    this.requirePerson(userId);
    return this.directRoomId(userId);
  }

  async createDirectRoom(userId: string): Promise<string> {
    const person: ChatPerson = this.requirePerson(userId);
    const existing: string | undefined = this.directRoomId(userId);
    if (existing !== undefined) {
      return existing;
    }
    return this.storeRoom(person.displayName, '', [userId], true);
  }

  async createRoom(name: string, topic: string, memberIds: string[]): Promise<string> {
    const cleanName: string = name.trim();
    if (cleanName.length === 0) {
      throw new Error('Enter a room name');
    }
    const members: string[] = [];
    memberIds.forEach((id: string) => {
      this.requirePerson(id);
      if (!members.includes(id)) {
        members.push(id);
      }
    });
    return this.storeRoom(cleanName, topic.trim(), members, false);
  }

  async getRoom(roomId: string, serverNames: string[] = []): Promise<ChatRoom> {
    const room: ChatRoom = this.requireRoom(roomId);
    return new ChatRoom(room.roomId, room.name, room.topic, room.memberIds.slice(), room.direct,
      room.messages.map((message: ChatMessage) => new ChatMessage(message.id, message.senderId, message.body)));
  }

  async sendMessage(roomId: string, body: string): Promise<ChatMessage> {
    const room: ChatRoom = this.requireRoom(roomId);
    const text: string = body.trim();
    if (text.length === 0) {
      throw new Error('Enter a message');
    }
    this.messageSequence += 1;
    const message: ChatMessage = new ChatMessage('message-' + this.messageSequence, this.selfId, text);
    room.messages.push(message);
    return new ChatMessage(message.id, message.senderId, message.body);
  }

  async resolveAlias(alias: string): Promise<RoomAliasResolution | undefined> {
    if (alias === '#lobby:demo.local') {
      return { roomId: this.lobbyId, servers: [this.selfId.substring(this.selfId.indexOf(':') + 1)] };
    }
    return this.aliasDirectory === undefined ? undefined : await this.aliasDirectory.resolveAlias(alias);
  }

  private requirePerson(userId: string): ChatPerson {
    const person: ChatPerson | undefined = this.directory.find((item: ChatPerson) => item.userId === userId);
    if (person === undefined) {
      throw new Error('Person is not in this session directory');
    }
    return person;
  }

  private directRoomId(userId: string): string | undefined {
    let result: string | undefined = undefined;
    this.rooms.forEach((room: ChatRoom) => {
      if (room.direct && room.memberIds.includes(userId)) {
        result = room.roomId;
      }
    });
    return result;
  }

  private requireRoom(roomId: string): ChatRoom {
    const room: ChatRoom | undefined = this.rooms.get(roomId);
    if (room === undefined) {
      throw new Error('Room not found in this session');
    }
    return room;
  }

  private storeRoom(name: string, topic: string, members: string[], direct: boolean): string {
    this.sequence += 1;
    const roomId: string = '!local-' + this.sequence + ':demo.local';
    const memberIds: string[] = [this.selfId];
    members.forEach((id: string) => memberIds.push(id));
    this.rooms.set(roomId, new ChatRoom(roomId, name, topic, memberIds, direct, []));
    return roomId;
  }
}

export class StartDMService {
  private gateway: RoomGateway;
  constructor(gateway: RoomGateway) {
    this.gateway = gateway;
  }

  async execute(userId: string): Promise<string> {
    const existing: string | undefined = await this.gateway.findDirectRoom(userId);
    return existing === undefined ? await this.gateway.createDirectRoom(userId) : existing;
  }
}

export class StartChatPresenter {
  query: string = '';
  busy: boolean = false;
  error: string = '';
  private token: number = 0;

  private gateway: RoomGateway;
  private startDM: StartDMService;
  private navigator: ChatNavigator;
  constructor(gateway: RoomGateway, startDM: StartDMService, navigator: ChatNavigator) {
    this.gateway = gateway;
    this.startDM = startDM;
    this.navigator = navigator;
  }

  updateQuery(value: string): void {
    this.query = value.trim();
  }

  visiblePeople(): ChatPerson[] {
    const query: string = this.query.toLowerCase();
    return this.gateway.people().filter((person: ChatPerson) =>
      person.displayName.toLowerCase().includes(query) || person.userId.toLowerCase().includes(query));
  }

  async selectPerson(userId: string): Promise<void> {
    if (this.busy) {
      return;
    }
    this.busy = true;
    this.error = '';
    const token: number = ++this.token;
    try {
      const roomId: string = await this.startDM.execute(userId);
      if (token === this.token) {
        await this.navigator.openRoom(roomId);
      }
    } catch (error) {
      if (token === this.token) {
        this.error = errorMessage(error as Error);
      }
    } finally {
      if (token === this.token) {
        this.busy = false;
      }
    }
  }

  async createRoom(): Promise<void> {
    if (this.busy) {
      return;
    }
    this.busy = true;
    this.error = '';
    const token: number = ++this.token;
    try {
      await this.navigator.openCreateRoom();
    } catch (error) {
      if (token === this.token) {
        this.error = errorMessage(error as Error);
      }
    } finally {
      if (token === this.token) {
        this.busy = false;
      }
    }
  }

  cancel(): void {
    this.token += 1;
    this.busy = false;
  }
}

export class CreateRoomPresenter {
  name: string = '';
  topic: string = '';
  memberIds: string[] = [];
  busy: boolean = false;
  error: string = '';
  createdRoomId: string = '';
  private token: number = 0;

  private gateway: RoomGateway;
  private navigator: ChatNavigator;
  constructor(gateway: RoomGateway, navigator: ChatNavigator) {
    this.gateway = gateway;
    this.navigator = navigator;
  }

  people(): ChatPerson[] {
    return this.gateway.people();
  }

  setName(value: string): void {
    if (!this.busy && this.createdRoomId.length === 0) {
      this.name = value;
    }
  }

  setTopic(value: string): void {
    if (!this.busy && this.createdRoomId.length === 0) {
      this.topic = value;
    }
  }

  toggleMember(userId: string, selected: boolean): void {
    if (this.busy || this.createdRoomId.length > 0 ||
      !this.people().some((person: ChatPerson) => person.userId === userId)) {
      return;
    }
    this.memberIds = this.memberIds.filter((id: string) => id !== userId);
    if (selected) {
      this.memberIds.push(userId);
    }
  }

  async submit(): Promise<void> {
    if (this.busy) {
      return;
    }
    if (this.name.trim().length === 0) {
      this.error = 'Enter a room name';
      return;
    }
    this.busy = true;
    this.error = '';
    const token: number = ++this.token;
    try {
      if (this.createdRoomId.length === 0) {
        this.createdRoomId = await this.gateway.createRoom(this.name, this.topic, this.memberIds);
      }
      if (token === this.token) {
        await this.navigator.openRoom(this.createdRoomId);
      }
    } catch (error) {
      if (token === this.token) {
        this.error = errorMessage(error as Error);
      }
    } finally {
      if (token === this.token) {
        this.busy = false;
      }
    }
  }

  cancel(): void {
    this.token += 1;
    this.busy = false;
  }
}

export class RoomPresenter {
  room: ChatRoom | undefined = undefined;
  busy: boolean = false;
  error: string = '';

  private gateway: RoomGateway;
  constructor(gateway: RoomGateway) {
    this.gateway = gateway;
  }

  async load(roomId: string, serverNames: string[] = []): Promise<void> {
    this.room = undefined;
    this.error = '';
    try {
      this.room = await this.gateway.getRoom(roomId, serverNames.slice());
    } catch (error) {
      this.error = errorMessage(error as Error);
    }
  }

  async send(body: string): Promise<boolean> {
    if (this.busy || this.room === undefined) {
      return false;
    }
    this.busy = true;
    this.error = '';
    try {
      await this.gateway.sendMessage(this.room.roomId, body);
      this.room = await this.gateway.getRoom(this.room.roomId);
      return true;
    } catch (error) {
      this.error = errorMessage(error as Error);
      return false;
    } finally {
      this.busy = false;
    }
  }
}
