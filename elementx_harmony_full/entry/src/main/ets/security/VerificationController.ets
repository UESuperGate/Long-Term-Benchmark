import { DomainErrorCode, DomainFailure, DomainResult, unexpectedFailure } from '../core/DomainResult';
import {
  VerificationSnapshot,
  VerificationUpdate
} from '../matrix/api/SecurityModels';
import {
  SecuritySubscription,
  VerificationDataSource,
  VerificationObserver,
  VerificationService
} from '../matrix/api/SecurityServices';
import { VerificationReducer } from './VerificationReducer';

class VerificationSubscription implements SecuritySubscription {
  readonly subscriptionId: number;
  private readonly onClose: (subscriptionId: number) => void;
  private closed: boolean = false;

  constructor(subscriptionId: number, onClose: (subscriptionId: number) => void) {
    this.subscriptionId = subscriptionId;
    this.onClose = onClose;
  }

  close(): void {
    if (!this.closed) {
      this.closed = true;
      this.onClose(this.subscriptionId);
    }
  }
}

export class VerificationController implements VerificationService {
  private readonly source: VerificationDataSource;
  private readonly reducer: VerificationReducer = new VerificationReducer();
  private readonly observers: Map<number, VerificationObserver> = new Map<number, VerificationObserver>();
  private nextObserverId: number = 1;

  constructor(source: VerificationDataSource) {
    this.source = source;
  }

  getSnapshot(): VerificationSnapshot {
    return this.reducer.getSnapshot();
  }

  subscribe(observer: VerificationObserver): SecuritySubscription {
    const id = this.nextObserverId++;
    this.observers.set(id, observer);
    observer.onVerificationChanged(this.getSnapshot());
    return new VerificationSubscription(id, (subscriptionId: number) => this.observers.delete(subscriptionId));
  }

  async requestCurrentSession(attemptId: string): Promise<DomainResult<VerificationSnapshot>> {
    return this.beginRequest(attemptId, null, this.source.requestCurrentSession(attemptId));
  }

  async requestUser(attemptId: string, userId: string): Promise<DomainResult<VerificationSnapshot>> {
    return this.beginRequest(attemptId, userId, this.source.requestUser(attemptId, userId));
  }

  receive(update: VerificationUpdate): DomainResult<VerificationSnapshot> {
    const result = this.reducer.receive(update);
    if (result.success && result.value !== null) {
      this.publish(result.value);
    }
    return result;
  }

  async accept(): Promise<DomainResult<VerificationSnapshot>> {
    return this.runForActive('accept verification', (attemptId: string) => this.source.accept(attemptId), false);
  }

  async approve(): Promise<DomainResult<VerificationSnapshot>> {
    this.publish(this.reducer.beginApproving());
    return this.runForActive('approve verification', (attemptId: string) => this.source.approve(attemptId), false);
  }

  async decline(): Promise<DomainResult<VerificationSnapshot>> {
    return this.runForActive('decline verification', (attemptId: string) => this.source.decline(attemptId), true);
  }

  async cancel(): Promise<DomainResult<VerificationSnapshot>> {
    return this.runForActive('cancel verification', (attemptId: string) => this.source.cancel(attemptId), true);
  }

  private async beginRequest(
    attemptId: string,
    userId: string | null,
    pending: Promise<DomainResult<boolean>>
  ): Promise<DomainResult<VerificationSnapshot>> {
    if (attemptId.length === 0) {
      return DomainResult.fail<VerificationSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Verification attempt ID must not be empty',
        false
      ));
    }
    this.publish(this.reducer.begin(attemptId, userId));
    const result = await pending;
    if (this.getSnapshot().attemptId !== attemptId) {
      return DomainResult.fail<VerificationSnapshot>(new DomainFailure(
        DomainErrorCode.Cancelled,
        'Verification request was superseded',
        false
      ));
    }
    if (!result.success) {
      const error = result.error === null ? unexpectedFailure('verification request') : result.error;
      this.publish(this.reducer.fail(error, error.code === DomainErrorCode.NetworkUnavailable));
      return DomainResult.fail<VerificationSnapshot>(error);
    }
    const snapshot = this.reducer.waitForAcceptance();
    this.publish(snapshot);
    return DomainResult.succeed<VerificationSnapshot>(snapshot);
  }

  private async runForActive(
    operation: string,
    action: (attemptId: string) => Promise<DomainResult<boolean>>,
    cancelOnSuccess: boolean
  ): Promise<DomainResult<VerificationSnapshot>> {
    const attemptId = this.getSnapshot().attemptId;
    if (attemptId === null) {
      return DomainResult.fail<VerificationSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'No verification attempt is active',
        false
      ));
    }
    const result = await action(attemptId);
    if (this.getSnapshot().attemptId !== attemptId) {
      return DomainResult.fail<VerificationSnapshot>(new DomainFailure(
        DomainErrorCode.Cancelled,
        'Verification action belongs to a stale attempt',
        false
      ));
    }
    if (!result.success) {
      const error = result.error === null ? unexpectedFailure(operation) : result.error;
      this.publish(this.reducer.fail(error, error.code === DomainErrorCode.NetworkUnavailable));
      return DomainResult.fail<VerificationSnapshot>(error);
    }
    const snapshot = cancelOnSuccess ? this.reducer.cancel(null) : this.getSnapshot();
    this.publish(snapshot);
    return DomainResult.succeed<VerificationSnapshot>(snapshot);
  }

  private publish(snapshot: VerificationSnapshot): void {
    this.observers.forEach((observer: VerificationObserver) => observer.onVerificationChanged(snapshot));
  }
}
