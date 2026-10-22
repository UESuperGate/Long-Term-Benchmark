import { MatrixRoomClient, RoomClient, RoomTransport, requireRoomId } from './RoomClient';

export interface ReportingRoomClient extends RoomClient {
  canReportRoom(): Promise<boolean>;
  reportRoom(roomId: string, reason?: string): Promise<void>;
}

interface ServerVersions { versions: string[]; }
interface ReportBody { reason?: string; }

export class MatrixReportingRoomClient extends MatrixRoomClient implements ReportingRoomClient {
  constructor(transport: RoomTransport) { super(transport); }

  async canReportRoom(): Promise<boolean> {
    try {
      const response = await this.transport.request('GET', '/_matrix/client/versions');
      if (response.status !== 200) return false;
      const data = JSON.parse(response.body) as ServerVersions;
      return Array.isArray(data.versions) && data.versions.includes('v1.13');
    } catch (error) {
      return false;
    }
  }

  async reportRoom(roomId: string, reason?: string): Promise<void> {
    requireRoomId(roomId);
    const body: ReportBody = {};
    if (reason !== undefined) body.reason = reason;
    const response = await this.transport.request('POST', '/_matrix/client/v3/rooms/' + encodeURIComponent(roomId) + '/report', JSON.stringify(body));
    if (response.status !== 200) throw new Error('Unable to report room');
  }
}
