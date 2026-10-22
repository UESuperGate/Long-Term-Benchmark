import http from '@ohos.net.http';
import { RoomAliasDirectory, RoomAliasResolution } from './ChatFeature';

interface DirectoryResponse {
  room_id: string;
  servers: string[];
}

// Only the system HTTP leaf is platform-specific. Preserve the directory's
// server list rather than deriving it from the alias or the demo session.
export class HttpRoomAliasDirectory implements RoomAliasDirectory {
  async resolveAlias(alias: string): Promise<RoomAliasResolution | undefined> {
    const match: RegExpMatchArray | null = alias.match(/^#[^:\s]+:([^\s/?#@]+)$/);
    if (match === null) {
      return undefined;
    }
    const request: http.HttpRequest = http.createHttp();
    try {
      const response: http.HttpResponse = await request.request(
        'https://' + match[1] + '/_matrix/client/v3/directory/room/' + encodeURIComponent(alias), {
          method: http.RequestMethod.GET, expectDataType: http.HttpDataType.STRING,
          connectTimeout: 10000, readTimeout: 10000, usingCache: false
        });
      if (response.responseCode === 404) {
        return undefined;
      }
      if (response.responseCode !== 200) {
        throw new Error('Room directory request failed: ' + response.responseCode);
      }
      const resolved: DirectoryResponse = JSON.parse(response.result as string) as DirectoryResponse;
      if (resolved === null || typeof resolved.room_id !== 'string' || resolved.room_id.length === 0 ||
        !Array.isArray(resolved.servers) || !resolved.servers.every((server: string) => typeof server === 'string')) {
        throw new Error('Invalid room directory response');
      }
      return { roomId: resolved.room_id, servers: resolved.servers.slice() };
    } finally {
      request.destroy();
    }
  }
}
