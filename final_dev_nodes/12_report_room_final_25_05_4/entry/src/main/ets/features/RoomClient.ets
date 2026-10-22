export interface RoomInfo {
  roomId: string;
  name: string;
  topic: string;
  memberCount: number;
}

export interface RoomClient {
  getRoom(roomId: string): Promise<RoomInfo | undefined>;
  leaveRoom(roomId: string): Promise<void>;
}

export interface RoomResponse {
  status: number;
  body: string;
}

export interface RoomTransport {
  request(method: string, path: string, body?: string): Promise<RoomResponse>;
}

interface JoinedRoomsResponse { joined_rooms: string[]; }
interface RoomStateContent { name?: string; topic?: string; membership?: string; }
interface RoomStateEvent { type: string; state_key: string; content: RoomStateContent; }

export function requireRoomId(roomId: string): void {
  if (!/^![^\s:]+:[^\s]+$/.test(roomId)) {
    throw new Error('A Matrix room ID is required');
  }
}

export class RoomSession {
  readonly homeserver: string;
  readonly accessToken: string;

  constructor(homeserver: string, accessToken: string) {
    const address = homeserver.trim().replace(/\/+$/, '');
    if (!/^https:\/\/[^\s/@?#]+(?:\/[^\s?#]*)?$/.test(address) &&
      !/^http:\/\/(localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$/.test(address)) {
      throw new Error('Use an HTTPS homeserver (or a local development server)');
    }
    if (!accessToken.trim() || /[\r\n]/.test(accessToken)) throw new Error('An access token is required');
    this.homeserver = address;
    this.accessToken = accessToken;
  }
}

export class MatrixRoomClient implements RoomClient {
  protected readonly transport: RoomTransport;

  constructor(transport: RoomTransport) { this.transport = transport; }

  async getRoom(roomId: string): Promise<RoomInfo | undefined> {
    requireRoomId(roomId);
    const joined = await this.transport.request('GET', '/_matrix/client/v3/joined_rooms');
    if (joined.status !== 200) throw new Error('Unable to load joined rooms');
    const membership = JSON.parse(joined.body) as JoinedRoomsResponse;
    if (!Array.isArray(membership.joined_rooms)) throw new Error('Invalid joined-room response');
    if (!membership.joined_rooms.includes(roomId)) return undefined;
    const response = await this.transport.request('GET', '/_matrix/client/v3/rooms/' + encodeURIComponent(roomId) + '/state');
    if (response.status === 404) return undefined;
    if (response.status !== 200) throw new Error('Unable to load room details');
    const events = JSON.parse(response.body) as RoomStateEvent[];
    if (!Array.isArray(events)) throw new Error('Invalid room-state response');
    const room: RoomInfo = { roomId, name: roomId, topic: '', memberCount: 0 };
    for (const event of events) {
      if (!event.content) continue;
      if (event.type === 'm.room.name' && event.state_key === '' && typeof event.content.name === 'string') room.name = event.content.name;
      if (event.type === 'm.room.topic' && event.state_key === '' && typeof event.content.topic === 'string') room.topic = event.content.topic;
      if (event.type === 'm.room.member' && event.content.membership === 'join') room.memberCount++;
    }
    return room;
  }

  async leaveRoom(roomId: string): Promise<void> {
    requireRoomId(roomId);
    const response = await this.transport.request('POST', '/_matrix/client/v3/rooms/' + encodeURIComponent(roomId) + '/leave', '{}');
    if (response.status !== 200) throw new Error('Unable to leave room');
  }
}
