import { getRoomIdentityDataSource, IdentityState, RoomIdentityDataSource } from './RoomIdentityFeature';
export { SessionVerificationService, VerificationEvent, getSessionVerificationService } from './SessionVerificationService';

export { getRoomIdentityDataSource, IdentityState, RoomMember, IdentityChange,
  RoomIdentityDataSource, TimelineIdentityPresenter } from './RoomIdentityFeature';

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
  readonly userId: string;
  readonly room: RoomIdentityDataSource;
  blocked: boolean = false;

  constructor(gateway: UserProfileGateway, userId: string = '@alice:example.org',
    room: RoomIdentityDataSource = getRoomIdentityDataSource()) {
    this.gateway = gateway;
    this.userId = userId;
    this.room = room;
  }

  get displayName(): string {
    return this.room.members.find(member => member.userId === this.userId)?.displayName || this.userId;
  }

  get isCurrentUser(): boolean { return this.userId === this.room.currentUserId; }

  get isVerified(): boolean {
    return this.room.identities.some(identity => identity.userId === this.userId &&
      identity.identityState === IdentityState.Verified);
  }

  startDirectMessage(): void {
    this.gateway.startDirectMessage();
  }

  toggleBlocked(): void {
    this.blocked = !this.blocked;
    this.gateway.setBlocked(this.blocked);
  }
}
