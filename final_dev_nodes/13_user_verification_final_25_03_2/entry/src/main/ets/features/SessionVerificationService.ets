export class VerificationEvent {
  readonly kind: string;
  readonly sas: string[];
  constructor(kind: string, sas: string[] = []) { this.kind = kind; this.sas = sas.slice(); }
}
export enum SessionVerifiedStatus { Unknown = 'unknown', NotVerified = 'not_verified', Verified = 'verified' }

// Session-owned SDK boundary, corresponding to Android SessionVerificationService.
export interface SessionSdkPort {
  subscribeVerifiedStatus(listener: (status: SessionVerifiedStatus) => void): () => void;
  subscribe(listener: (event: VerificationEvent) => void): () => void;
  requestCurrentSessionVerification(): Promise<void>;
  startVerification(): Promise<void>;
  approveVerification(): Promise<void>;
  declineVerification(): Promise<void>;
  cancelVerification(): Promise<void>;
  resetVerification(cancelPending: boolean): Promise<void>;
  isVerified(userId: string): boolean;
  setListener(listener: ((requestId: string) => void) | undefined): void;
  acknowledgeVerificationRequest(requestId: string): Promise<void>;
  acceptVerificationRequest(): Promise<void>;
}
export class SessionVerificationService {
  private port: SessionSdkPort | undefined = undefined;
  private detach: (() => void) | undefined = undefined;
  private listeners: Array<(event: VerificationEvent) => void> = [];
  private generation: number = 0;
  private flow: number = 0;
  private detachStatus: (() => void) | undefined = undefined;
  private status: SessionVerifiedStatus = SessionVerifiedStatus.Unknown;
  private statusListeners: Array<(status: SessionVerifiedStatus) => void> = [];
  get sessionVerifiedStatus(): SessionVerifiedStatus { return this.status; }
  get needsSessionVerification(): boolean { return this.status === SessionVerifiedStatus.NotVerified; }
  subscribeVerifiedStatus(listener: (status: SessionVerifiedStatus) => void): () => void {
    this.statusListeners.push(listener); listener(this.status);
    return () => { this.statusListeners = this.statusListeners.filter(item => item !== listener); };
  }
  get available(): boolean { return this.port !== undefined; }
  connect(port: SessionSdkPort): void {
    this.disconnect(); this.port = port; this.listen();
  }
  private listen(): void {
    this.detach?.();
    const generation = this.generation;
    const flow = ++this.flow;
    this.detachStatus?.();
    this.detachStatus = this.sdk().subscribeVerifiedStatus(status => {
      if (generation !== this.generation || flow !== this.flow) return;
      this.status = status; this.statusListeners.slice().forEach(listener => listener(status));
      this.listeners.slice().forEach(listener => listener(new VerificationEvent('verified_status_changed')));
    });
    this.detach = this.sdk().subscribe(event => {
      if (generation !== this.generation || flow !== this.flow) return;
      this.listeners.slice().forEach(listener => listener(event));
    });
  }
  disconnect(): void {
    this.generation += 1; this.flow += 1;
    this.detachStatus?.(); this.detachStatus = undefined;
    this.port?.setListener(undefined);
    this.status = SessionVerifiedStatus.Unknown;
    this.statusListeners.slice().forEach(listener => listener(this.status));
    this.detach?.(); this.detach = undefined; this.port = undefined;
    this.listeners.slice().forEach(listener => listener(new VerificationEvent('canceled')));
  }
  subscribe(listener: (event: VerificationEvent) => void): () => void {
    this.listeners.push(listener);
    return () => { this.listeners = this.listeners.filter(item => item !== listener); };
  }
  protected sdk(): SessionSdkPort {
    if (!this.port) throw new Error('Session verification SDK is not connected');
    return this.port;
  }
  protected async operation(action: (port: SessionSdkPort) => Promise<void>): Promise<void> {
    const generation = this.generation;
    const flow = this.flow;
    await action(this.sdk());
    if (generation !== this.generation || flow !== this.flow) throw new Error('Stale verification session operation');
  }
  async requestCurrentSessionVerification(): Promise<void> { await this.operation(port => port.requestCurrentSessionVerification()); }
  async startVerification(): Promise<void> { await this.operation(port => port.startVerification()); }
  async approveVerification(): Promise<void> { await this.operation(port => port.approveVerification()); }
  async declineVerification(): Promise<void> { await this.operation(port => port.declineVerification()); }
  async cancelVerification(): Promise<void> { await this.operation(port => port.cancelVerification()); }
  async resetVerification(cancelPending: boolean): Promise<void> {
    this.listen(); await this.operation(port => port.resetVerification(cancelPending));
  }
  setListener(listener: ((requestId: string) => void) | undefined): void {
    const generation = this.generation;
    this.sdk().setListener(listener ? (requestId: string) => {
      if (generation === this.generation) listener(requestId);
    } : undefined);
  }
  async acknowledgeVerificationRequest(requestId: string): Promise<void> {
    await this.operation(port => port.acknowledgeVerificationRequest(requestId));
  }
  async acceptVerificationRequest(): Promise<void> { await this.operation(port => port.acceptVerificationRequest()); }
  isVerified(userId: string): boolean { return this.port?.isVerified(userId) === true; }
}

const sessionVerificationService = new SessionVerificationService();
export function getSessionVerificationService(): SessionVerificationService { return sessionVerificationService; }
