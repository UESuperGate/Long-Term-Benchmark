export class RoomDetailsGateway {
  leaveCalls: number = 0;

  leaveRoom(): boolean {
    this.leaveCalls += 1;
    return true;
  }
}

export class RoomDetailsPresenter {
  readonly gateway: RoomDetailsGateway;
  roomName: string = 'Community support';
  memberCount: number = 128;
  leaveSucceeded: boolean = false;

  constructor(gateway: RoomDetailsGateway) {
    this.gateway = gateway;
  }

  leaveRoom(): void {
    this.leaveSucceeded = this.gateway.leaveRoom();
  }
}
