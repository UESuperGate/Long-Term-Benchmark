export enum VerificationRequestType {
  CurrentSession = 'current_session',
  User = 'user'
}

export enum VerificationStep {
  Initial = 'initial',
  AwaitingOtherDeviceResponse = 'awaiting_other_device_response',
  Ready = 'ready',
  Verifying = 'verifying',
  Canceled = 'canceled',
  Completed = 'completed',
  Exit = 'exit'
}

export enum ReplyState {
  Uninitialized = 'uninitialized',
  Loading = 'loading'
}

export enum IdentityState {
  Unknown = 'unknown',
  Unverified = 'unverified',
  Verified = 'verified',
  VerificationViolation = 'verification_violation'
}

export class VerificationRequest {
  type: VerificationRequestType;
  userId: string;

  constructor(type: VerificationRequestType, userId: string) {
    this.type = type;
    this.userId = userId;
  }
}

export class VerificationGateway {
  requestUserCalls: number = 0;
  requestCurrentSessionCalls: number = 0;
  startCalls: number = 0;
  approveCalls: number = 0;
  declineCalls: number = 0;
  cancelCalls: number = 0;
  resetCalls: number = 0;
  lastRequestedUserId: string = '';
  lastResetCancelPending: boolean = true;

  requestUserVerification(userId: string): void {
    this.requestUserCalls += 1;
    this.lastRequestedUserId = userId;
  }

  requestCurrentSessionVerification(): void {
    this.requestCurrentSessionCalls += 1;
  }

  startVerification(): void {
    this.startCalls += 1;
  }

  approveVerification(): void {
    this.approveCalls += 1;
  }

  declineVerification(): void {
    this.declineCalls += 1;
  }

  cancelVerification(): void {
    this.cancelCalls += 1;
  }

  resetVerification(cancelPending: boolean): void {
    this.resetCalls += 1;
    this.lastResetCancelPending = cancelPending;
  }
}

export class IdentityStateStore {
  userId: string;
  identityState: IdentityState;

  constructor(userId: string, identityState: IdentityState) {
    this.userId = userId;
    this.identityState = identityState;
  }

  markVerified(userId: string): void {
    if (userId === this.userId) {
      this.identityState = IdentityState.Verified;
    }
  }

  get warningVisible(): boolean {
    return this.identityState === IdentityState.VerificationViolation;
  }
}

export class UserVerificationPresenter {
  readonly request: VerificationRequest;
  readonly gateway: VerificationGateway;
  readonly identityStore: IdentityStateStore;
  step: VerificationStep = VerificationStep.Initial;
  replyState: ReplyState = ReplyState.Uninitialized;
  sas: string[] = [];

  constructor(request: VerificationRequest, gateway: VerificationGateway, identityStore: IdentityStateStore) {
    this.request = request;
    this.gateway = gateway;
    this.identityStore = identityStore;
  }

  requestVerification(): void {
    if (this.step !== VerificationStep.Initial) {
      return;
    }
    if (this.request.type === VerificationRequestType.User) {
      this.gateway.requestUserVerification(this.request.userId);
    } else {
      this.gateway.requestCurrentSessionVerification();
    }
    this.step = VerificationStep.AwaitingOtherDeviceResponse;
  }

  remoteAcceptedRequest(): void {
    if (this.step === VerificationStep.AwaitingOtherDeviceResponse) {
      this.step = VerificationStep.Ready;
    }
  }

  startSasVerification(): void {
    if (this.step !== VerificationStep.Ready) {
      return;
    }
    this.gateway.startVerification();
    this.step = VerificationStep.AwaitingOtherDeviceResponse;
  }

  receiveChallenge(sas: string[]): void {
    this.sas = sas.slice();
    this.replyState = ReplyState.Uninitialized;
    this.step = VerificationStep.Verifying;
  }

  acceptChallenge(): void {
    if (this.step !== VerificationStep.Verifying || this.replyState !== ReplyState.Uninitialized) {
      return;
    }
    this.gateway.approveVerification();
    this.replyState = ReplyState.Loading;
  }

  declineChallenge(): void {
    if (this.step !== VerificationStep.Verifying || this.replyState !== ReplyState.Uninitialized) {
      return;
    }
    this.gateway.declineVerification();
    this.replyState = ReplyState.Loading;
  }

  verificationFinished(): void {
    if (this.step === VerificationStep.Verifying) {
      this.step = VerificationStep.Completed;
      this.identityStore.markVerified(this.request.userId);
    }
  }

  cancel(): void {
    if (this.step === VerificationStep.Initial || this.step === VerificationStep.Completed ||
      this.step === VerificationStep.Canceled) {
      this.step = VerificationStep.Exit;
      return;
    }
    this.gateway.cancelVerification();
    this.step = VerificationStep.Canceled;
  }

  remoteCanceled(): void {
    this.step = VerificationStep.Canceled;
  }

  verificationFailed(): void {
    this.step = VerificationStep.Canceled;
  }

  reset(): void {
    if (this.step === VerificationStep.Canceled) {
      this.gateway.resetVerification(false);
      this.replyState = ReplyState.Uninitialized;
      this.sas = [];
      this.step = VerificationStep.Initial;
    }
  }
}
