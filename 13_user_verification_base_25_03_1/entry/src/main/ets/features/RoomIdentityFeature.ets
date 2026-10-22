// Task-boundary port of the v25.03.1 MatrixRoom identity/member streams.
export enum IdentityState {
  Verified = 'verified',
  Pinned = 'pinned',
  PinViolation = 'pin_violation',
  VerificationViolation = 'verification_violation'
}

export class RoomMember {
  userId: string;
  displayName: string;
  membership: string;
  powerLevel: number;

  constructor(userId: string, displayName: string, membership: string = 'join', powerLevel: number = 0) {
    this.userId = userId;
    this.displayName = displayName;
    this.membership = membership;
    this.powerLevel = powerLevel;
  }
}

export class IdentityChange {
  userId: string;
  identityState: IdentityState;

  constructor(userId: string, identityState: IdentityState) {
    this.userId = userId;
    this.identityState = identityState;
  }
}

export interface EncryptionService {
  withdrawVerification(userId: string): Promise<void>;
  pinUserIdentity(userId: string): Promise<void>;
}

export class RoomIdentityDataSource {
  isEncrypted: boolean = false;
  members: RoomMember[] = [];
  identities: IdentityChange[] = [];
  currentUserId: string = '';
  verificationAvailable: boolean = false;
  private listeners: Array<() => void> = [];
  private encryptionService: EncryptionService | undefined = undefined;

  subscribe(listener: () => void): () => void {
    this.listeners.push(listener);
    listener();
    return () => { this.listeners = this.listeners.filter(item => item !== listener); };
  }

  private publish(): void {
    this.listeners.forEach(listener => listener());
  }

  receiveSession(currentUserId: string, verificationAvailable: boolean): void {
    this.currentUserId = currentUserId;
    this.verificationAvailable = verificationAvailable;
    this.publish();
  }

  receiveRoomSync(isEncrypted: boolean, members: RoomMember[]): void {
    // Matrix encryption is sticky, as in the Android room observation flow.
    this.isEncrypted = this.isEncrypted || isEncrypted;
    this.members = members.map(member => new RoomMember(member.userId, member.displayName,
      member.membership, member.powerLevel));
    this.publish();
  }

  receiveIdentityChanges(identities: IdentityChange[]): void {
    this.identities = identities.map(identity => new IdentityChange(identity.userId, identity.identityState));
    this.publish();
  }

  connectEncryptionService(service: EncryptionService): void {
    this.encryptionService = service;
  }

  async withdrawVerification(userId: string): Promise<void> {
    if (!this.encryptionService) throw new Error('Matrix encryption service is not connected');
    await this.encryptionService.withdrawVerification(userId);
    // Identity changes arrive through the SDK stream, never optimistic UI mutation.
  }

  async pinUserIdentity(userId: string): Promise<void> {
    if (!this.encryptionService) throw new Error('Matrix encryption service is not connected');
    await this.encryptionService.pinUserIdentity(userId);
  }

  visibleMembers(query: string = ''): RoomMember[] {
    const search = query.toLocaleLowerCase();
    return this.members.filter(member => ['join', 'invite', 'ban'].includes(member.membership) &&
      (member.userId.toLocaleLowerCase().includes(search) || member.displayName.toLocaleLowerCase().includes(search)))
      .sort((left, right) => {
        const groups: string[] = ['join', 'invite', 'ban'];
        const groupOrder = groups.indexOf(left.membership) - groups.indexOf(right.membership);
        if (groupOrder !== 0) return groupOrder;
        if (left.membership === 'ban') return left.userId.localeCompare(right.userId);
        if (left.powerLevel !== right.powerLevel) return right.powerLevel - left.powerLevel;
        return left.displayName.localeCompare(right.displayName);
      });
  }
}

export class TimelineIdentityPresenter {
  readonly room: RoomIdentityDataSource;

  constructor(room: RoomIdentityDataSource) { this.room = room; }

  get violation(): IdentityChange | undefined {
    if (!this.room.isEncrypted) return undefined;
    return this.room.identities.find(identity => identity.identityState === IdentityState.PinViolation ||
      identity.identityState === IdentityState.VerificationViolation);
  }

  get displayName(): string {
    const userId = this.violation?.userId || '';
    return this.room.members.find(member => member.userId === userId)?.displayName || userId;
  }

  async acknowledge(): Promise<void> {
    const violation = this.violation;
    if (!violation) return;
    if (violation.identityState === IdentityState.VerificationViolation) {
      await this.room.withdrawVerification(violation.userId);
    } else {
      await this.room.pinUserIdentity(violation.userId);
    }
  }
}

const roomIdentityDataSource = new RoomIdentityDataSource();

export function getRoomIdentityDataSource(): RoomIdentityDataSource {
  return roomIdentityDataSource;
}
