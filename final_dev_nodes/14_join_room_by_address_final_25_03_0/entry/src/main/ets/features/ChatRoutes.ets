import { ChatNavigator } from './ChatFeature';

export class RoomRouteParams {
  roomId: string;
  serverNames: string[];
  constructor(roomId: string, serverNames: string[] = []) {
    this.roomId = roomId;
    this.serverNames = serverNames.slice();
  }
}

export interface RoutePort {
  push(url: string): Promise<void>;
  replace(url: string, params: RoomRouteParams): Promise<void>;
  returnToStart(): Promise<void>;
}

export class RouterChatNavigator implements ChatNavigator {
  private routes: RoutePort;
  constructor(routes: RoutePort) {
    this.routes = routes;
  }

  async openCreateRoom(): Promise<void> {
    await this.routes.push('pages/CreateRoom');
  }

  async openRoom(roomId: string, serverNames: string[] = []): Promise<void> {
    if (roomId.trim().length === 0) {
      throw new Error('Missing room ID');
    }
    await this.routes.replace('pages/Room', new RoomRouteParams(roomId, serverNames));
  }

  async back(): Promise<void> {
    await this.routes.returnToStart();
  }
}
