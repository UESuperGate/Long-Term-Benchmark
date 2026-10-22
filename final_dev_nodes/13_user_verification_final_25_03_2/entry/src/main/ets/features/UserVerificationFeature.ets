import { getRoomIdentityDataSource, RoomIdentityDataSource, IdentityState } from './RoomIdentityFeature';
import { SessionVerificationService as BaseSessionVerificationService, SessionSdkPort,
  VerificationEvent } from './SessionVerificationService';
export { getRoomIdentityDataSource, IdentityState, RoomMember, IdentityChange,
  TimelineIdentityPresenter } from './RoomIdentityFeature';
export { UserProfileGateway, UserProfilePresenter } from './UserProfileFeature';

export enum VerificationRequestType { CurrentSession = 'current_session', User = 'user' }
export enum VerificationStep {
  Initial = 'initial', AwaitingOtherDeviceResponse = 'awaiting_other_device_response',
  Ready = 'ready', Verifying = 'verifying', Canceled = 'canceled', Completed = 'completed', Exit = 'exit'
}
export enum ReplyState { Uninitialized = 'uninitialized', Loading = 'loading' }

export class VerificationRequest {
  readonly type: VerificationRequestType;
  readonly userId: string;
  constructor(type: VerificationRequestType, userId: string) { this.type = type; this.userId = userId; }
}
export { VerificationEvent } from './SessionVerificationService';
export interface SessionVerificationPort extends SessionSdkPort {
  requestUserVerification(userId: string): Promise<void>;
}
export class SessionVerificationService extends BaseSessionVerificationService {
  async requestUserVerification(userId: string): Promise<void> {
    await this.operation(port => (port as SessionVerificationPort).requestUserVerification(userId));
  }
}
const sessionService = new SessionVerificationService();
export function getSessionVerificationService(): SessionVerificationService { return sessionService; }

export class VerificationGateway {
  readonly service: SessionVerificationService;
  readonly room: RoomIdentityDataSource;
  constructor(service: SessionVerificationService = getSessionVerificationService(),
    room: RoomIdentityDataSource = getRoomIdentityDataSource()) { this.service = service; this.room = room; }
  async requestUserVerification(userId: string): Promise<void> { await this.service.requestUserVerification(userId); }
  async requestCurrentSessionVerification(): Promise<void> { await this.service.requestCurrentSessionVerification(); }
  async startVerification(): Promise<void> { await this.service.startVerification(); }
  async approveVerification(): Promise<void> { await this.service.approveVerification(); }
  async declineVerification(): Promise<void> { await this.service.declineVerification(); }
  async cancelVerification(): Promise<void> { await this.service.cancelVerification(); }
  async resetVerification(cancelPending: boolean): Promise<void> { await this.service.resetVerification(cancelPending); }
  async withdrawVerification(userId: string): Promise<void> { await this.room.withdrawVerification(userId); }
}
export class IdentityStateStore {
  readonly userId: string;
  readonly room: RoomIdentityDataSource;
  constructor(userId: string, room: RoomIdentityDataSource = getRoomIdentityDataSource()) {
    this.userId = userId; this.room = room;
  }
  get identityState(): IdentityState {
    return this.room.identities.find(identity => identity.userId === this.userId)?.identityState || IdentityState.Unknown;
  }
  get warningVisible(): boolean { return this.room.isEncrypted && this.identityState === IdentityState.VerificationViolation; }
}
export class UserVerificationPresenter {
  readonly request: VerificationRequest;
  readonly gateway: VerificationGateway;
  readonly identityStore: IdentityStateStore;
  step: VerificationStep = VerificationStep.Initial;
  replyState: ReplyState = ReplyState.Uninitialized;
  sas: string[] = [];
  error: string = '';
  initializing: boolean = true;
  private waitingForSas: boolean = false;
  private sasStarted: boolean = false;
  private active: boolean = false;
  private finished: boolean = false;
  private lifecycle: number = 0;
  private detachService: (() => void) | undefined = undefined;
  private detachIdentity: (() => void) | undefined = undefined;
  private changed: () => void = () => {};
  constructor(request: VerificationRequest, gateway: VerificationGateway, identityStore: IdentityStateStore) {
    this.request = request; this.gateway = gateway; this.identityStore = identityStore;
  }
  attach(changed: () => void): void {
    if (this.active) return;
    this.active = true; this.lifecycle += 1; this.changed = changed;
    this.detachService = this.gateway.service.subscribe(event => this.receiveServiceEvent(event));
    this.detachIdentity = this.identityStore.room.subscribe(() => { this.completeIfVerified(); this.changed(); });
    const lifecycle = this.lifecycle;
    this.initializing = true;
    this.gateway.resetVerification(true).then(() => {
      if (this.active && lifecycle === this.lifecycle) { this.initializing = false; this.changed(); }
    }).catch((error: Error) => {
      if (this.active && lifecycle === this.lifecycle) {
        this.initializing = false; this.error = String(error); this.step = VerificationStep.Canceled; this.changed();
      }
    });
  }
  dispose(): void {
    this.active = false; this.lifecycle += 1; this.detachService?.(); this.detachIdentity?.(); this.changed = () => {};
  }
  private async invoke(operation: () => Promise<void>): Promise<void> {
    const lifecycle = this.lifecycle;
    try { await operation(); }
    catch (error) { if (this.active && lifecycle === this.lifecycle) { this.error = String(error); this.step = VerificationStep.Canceled; } }
    if (this.active && lifecycle === this.lifecycle) this.changed();
  }
  async requestVerification(): Promise<void> {
    if (!this.active || this.initializing || this.step !== VerificationStep.Initial) return;
    this.waitingForSas = false;
    this.step = VerificationStep.AwaitingOtherDeviceResponse; this.changed();
    await this.invoke(() => this.request.type === VerificationRequestType.User ?
      this.gateway.requestUserVerification(this.request.userId) : this.gateway.requestCurrentSessionVerification());
  }
  async startSasVerification(): Promise<void> {
    if (!this.active || this.step !== VerificationStep.Ready) return;
    this.waitingForSas = true;
    this.step = VerificationStep.AwaitingOtherDeviceResponse; this.changed();
    await this.invoke(() => this.gateway.startVerification());
  }
  async acceptChallenge(): Promise<void> {
    if (!this.active || this.step !== VerificationStep.Verifying || this.replyState !== ReplyState.Uninitialized) return;
    this.replyState = ReplyState.Loading; this.changed();
    await this.invoke(() => this.gateway.approveVerification());
  }
  async declineChallenge(): Promise<void> {
    if (!this.active || this.step !== VerificationStep.Verifying || this.replyState !== ReplyState.Uninitialized) return;
    this.replyState = ReplyState.Loading; this.changed();
    await this.invoke(() => this.gateway.declineVerification());
  }
  async cancel(): Promise<void> {
    if (!this.active) return;
    if ([VerificationStep.Initial, VerificationStep.Completed, VerificationStep.Canceled].includes(this.step)) {
      this.step = VerificationStep.Exit; this.changed(); return;
    }
    this.step = VerificationStep.Canceled; this.changed();
    await this.invoke(() => this.gateway.cancelVerification());
  }
  async reset(): Promise<void> {
    if (!this.active || this.step !== VerificationStep.Canceled) return;
    const lifecycle = ++this.lifecycle;
    this.error = '';
    await this.invoke(() => this.gateway.resetVerification(false));
    if (!this.active || lifecycle !== this.lifecycle || this.error) return;
    this.sas = []; this.sasStarted = false; this.finished = false; this.waitingForSas = false;
    this.replyState = ReplyState.Uninitialized; this.step = VerificationStep.Initial; this.changed();
  }
  receiveServiceEvent(event: VerificationEvent): void {
    if (!this.active) return;
    if (event.kind === 'accepted' && this.step === VerificationStep.AwaitingOtherDeviceResponse && !this.sasStarted && !this.waitingForSas) {
      this.step = VerificationStep.Ready;
    } else if (event.kind === 'started' && this.step === VerificationStep.AwaitingOtherDeviceResponse) {
      this.sasStarted = true;
    } else if (event.kind === 'challenge' && this.sasStarted && this.step === VerificationStep.AwaitingOtherDeviceResponse) {
      this.sas = event.sas.slice(); this.replyState = ReplyState.Uninitialized; this.step = VerificationStep.Verifying;
    } else if (event.kind === 'finished' && this.step === VerificationStep.Verifying && this.replyState === ReplyState.Loading) {
      this.finished = true; this.completeIfVerified();
    } else if (event.kind === 'failed' || event.kind === 'canceled') {
      this.finished = false; this.step = VerificationStep.Canceled;
    } else if (event.kind === 'verified_status_changed') {
      this.completeIfVerified();
    }
    this.changed();
  }
  private completeIfVerified(): void {
    if (this.active && this.finished && this.step === VerificationStep.Verifying &&
      this.gateway.service.isVerified(this.request.userId) &&
      this.identityStore.identityState === IdentityState.Verified) this.step = VerificationStep.Completed;
  }
}
