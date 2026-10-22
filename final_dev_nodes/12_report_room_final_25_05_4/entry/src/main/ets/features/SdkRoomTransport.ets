import http from '@ohos.net.http';
import { RoomResponse, RoomSession, RoomTransport } from './RoomClient';

interface MatrixHeaders { Authorization: string; 'Content-Type': string; }

export class SdkRoomTransport implements RoomTransport {
  private readonly session: RoomSession;

  constructor(session: RoomSession) { this.session = session; }

  async request(method: string, path: string, body?: string): Promise<RoomResponse> {
    if (!path.startsWith('/_matrix/') || path.includes('://') || (method !== 'GET' && method !== 'POST')) {
      throw new Error('Invalid Matrix request');
    }
    const connection = http.createHttp();
    const headers: MatrixHeaders = { Authorization: 'Bearer ' + this.session.accessToken, 'Content-Type': 'application/json' };
    const options: http.HttpRequestOptions = {
      method: method === 'POST' ? http.RequestMethod.POST : http.RequestMethod.GET,
      header: headers,
      expectDataType: http.HttpDataType.STRING,
      usingCache: false,
      connectTimeout: 15000,
      readTimeout: 30000
    };
    if (body !== undefined) options.extraData = body;
    try {
      const response = await connection.request(this.session.homeserver + path, options);
      if (typeof response.result !== 'string') throw new Error('Expected a Matrix JSON response');
      const result: RoomResponse = { status: response.responseCode, body: response.result };
      return result;
    } finally {
      connection.destroy();
    }
  }
}
