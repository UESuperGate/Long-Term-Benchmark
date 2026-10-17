const ADDRESS_DEBOUNCE_MS: number = 300;
const ADDRESS_RESOLVE_TIMEOUT_MS: number = 10000;

export enum RoomAddressState {
  Unknown = 'unknown',
  Invalid = 'invalid',
  Resolving = 'resolving',
  RoomNotFound = 'room_not_found',
  RoomFound = 'room_found'
}

export interface ResolvedRoomAlias {
  roomId: string;
  servers: string[];
}

export interface RoomAliasResolver {
  resolveRoomAlias(alias: string): Promise<ResolvedRoomAlias | undefined>;
}

export interface CreateRoomNavigator {
  dismissJoinRoomByAddress(): void;
  openRoom(roomIdOrAlias: string, serverNames: string[]): void;
}

function delay(milliseconds: number): Promise<void> {
  return new Promise<void>((resolve: () => void) => {
    setTimeout(resolve, milliseconds);
  });
}

export class DemoRoomAliasResolver implements RoomAliasResolver {
  async resolveRoomAlias(alias: string): Promise<ResolvedRoomAlias | undefined> {
    await delay(120);
    if (alias.includes('missing')) {
      return undefined;
    }
    if (alias.includes('error')) {
      throw new Error('Room directory is unavailable');
    }
    const localPart: string = alias.substring(1, alias.indexOf(':'));
    const server: string = alias.substring(alias.indexOf(':') + 1);
    return { roomId: `!${localPart}:${server}`, servers: [server] };
  }
}

export class JoinRoomNavigator implements CreateRoomNavigator {
  addressFlowVisible: boolean = false;
  openedRoomId: string = '';
  openedServers: string[] = [];
  openRoomCount: number = 0;

  showJoinRoomByAddress(): void {
    this.addressFlowVisible = true;
  }

  dismissJoinRoomByAddress(): void {
    this.addressFlowVisible = false;
  }

  openRoom(roomIdOrAlias: string, serverNames: string[]): void {
    this.openedRoomId = roomIdOrAlias;
    this.openedServers = serverNames.slice();
    this.openRoomCount += 1;
  }
}

export class JoinRoomByAddressPresenter {
  address: string = '';
  addressState: RoomAddressState = RoomAddressState.Unknown;
  validationRequested: boolean = false;
  resolvedRoom: ResolvedRoomAlias | undefined = undefined;
  private updateToken: number = 0;
  private resolver: RoomAliasResolver;
  private navigator: CreateRoomNavigator;

  constructor(resolver: RoomAliasResolver, navigator: CreateRoomNavigator) {
    this.resolver = resolver;
    this.navigator = navigator;
  }

  async updateAddress(value: string): Promise<void> {
    this.address = value.trim();
    this.addressState = RoomAddressState.Unknown;
    this.validationRequested = false;
    this.resolvedRoom = undefined;
    this.updateToken += 1;
    const token: number = this.updateToken;
    await delay(ADDRESS_DEBOUNCE_MS);
    if (token !== this.updateToken) {
      return;
    }
    if (!this.isValidRoomAlias(this.address)) {
      this.addressState = RoomAddressState.Invalid;
      return;
    }
    this.addressState = RoomAddressState.Resolving;
    const resolved: ResolvedRoomAlias | undefined = await this.resolveWithTimeout(this.address);
    if (token !== this.updateToken) {
      return;
    }
    if (resolved === undefined) {
      this.addressState = RoomAddressState.RoomNotFound;
      return;
    }
    this.resolvedRoom = resolved;
    this.addressState = RoomAddressState.RoomFound;
    if (this.validationRequested) {
      this.navigateToResolvedRoom();
    }
  }

  continue(): void {
    if (this.addressState === RoomAddressState.RoomFound) {
      this.navigateToResolvedRoom();
      return;
    }
    this.validationRequested = true;
  }

  dismiss(): void {
    this.updateToken += 1;
    this.navigator.dismissJoinRoomByAddress();
  }

  visibleAddressState(): RoomAddressState {
    if (this.validationRequested || this.addressState === RoomAddressState.RoomFound) {
      return this.addressState;
    }
    return RoomAddressState.Unknown;
  }

  private isValidRoomAlias(value: string): boolean {
    return /^#[^:\s]+:[^:\s]+$/.test(value);
  }

  private async resolveWithTimeout(alias: string): Promise<ResolvedRoomAlias | undefined> {
    return new Promise<ResolvedRoomAlias | undefined>((resolve: (value: ResolvedRoomAlias | undefined) => void) => {
      let settled: boolean = false;
      setTimeout(() => {
        if (!settled) {
          settled = true;
          resolve(undefined);
        }
      }, ADDRESS_RESOLVE_TIMEOUT_MS);
      this.resolver.resolveRoomAlias(alias).then((result: ResolvedRoomAlias | undefined) => {
        if (!settled) {
          settled = true;
          resolve(result);
        }
      }).catch(() => {
        if (!settled) {
          settled = true;
          resolve(undefined);
        }
      });
    });
  }

  private navigateToResolvedRoom(): void {
    if (this.resolvedRoom === undefined) {
      return;
    }
    this.navigator.dismissJoinRoomByAddress();
    this.navigator.openRoom(this.resolvedRoom.roomId, this.resolvedRoom.servers);
  }
}
