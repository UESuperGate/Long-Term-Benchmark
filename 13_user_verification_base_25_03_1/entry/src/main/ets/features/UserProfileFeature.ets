export class UserProfileGateway {
  dmStarts: number = 0;
  blocked: boolean = false;

  startDirectMessage(): void {
    this.dmStarts += 1;
  }

  setBlocked(blocked: boolean): void {
    this.blocked = blocked;
  }
}

export class UserProfilePresenter {
  readonly gateway: UserProfileGateway;
  readonly userId: string = '@alice:example.org';
  readonly displayName: string = 'Alice';
  blocked: boolean = false;

  constructor(gateway: UserProfileGateway) {
    this.gateway = gateway;
  }

  startDirectMessage(): void {
    this.gateway.startDirectMessage();
  }

  toggleBlocked(): void {
    this.blocked = !this.blocked;
    this.gateway.setBlocked(this.blocked);
  }
}
