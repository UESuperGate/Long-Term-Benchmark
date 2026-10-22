import { RoomGateway, RoomAliasResolution } from './ChatFeature';
import { RouterChatNavigator } from './ChatRoutes';
import { RoomAliasResolver, ResolvedRoomAlias, JoinRoomNavigator } from './JoinRoomByAddressFeature';

export class SessionRoomAliasResolver implements RoomAliasResolver {
  private gateway: RoomGateway;
  constructor(gateway: RoomGateway) {
    this.gateway = gateway;
  }

  async resolveRoomAlias(alias: string): Promise<ResolvedRoomAlias | undefined> {
    const resolved: RoomAliasResolution | undefined = await this.gateway.resolveAlias(alias);
    if (resolved === undefined) {
      return undefined;
    }
    return { roomId: resolved.roomId, servers: resolved.servers.slice() };
  }
}

export class RoutedJoinRoomNavigator extends JoinRoomNavigator {
  navigationError: string = '';
  navigation: Promise<void> = Promise.resolve();
  private opening: boolean = false;
  private routes: RouterChatNavigator;

  constructor(routes: RouterChatNavigator) {
    super();
    this.routes = routes;
  }

  openRoom(roomIdOrAlias: string, serverNames: string[]): void {
    if (this.opening) {
      return;
    }
    this.opening = true;
    this.navigationError = '';
    super.openRoom(roomIdOrAlias, serverNames);
    this.navigation = this.routes.openRoom(roomIdOrAlias, serverNames).catch((error: Error) => {
      this.navigationError = error.message;
      this.showJoinRoomByAddress();
    }).then(() => {
      this.opening = false;
    });
  }
}
