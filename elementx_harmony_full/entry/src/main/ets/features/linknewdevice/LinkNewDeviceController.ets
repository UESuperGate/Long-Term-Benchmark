import {
  DomainErrorCode,
  DomainFailure,
  DomainResult,
  unexpectedFailure
} from '../../core/DomainResult';
import {
  LinkAttemptMode,
  LinkErrorCode,
  LinkNewDeviceObserver,
  LinkNewDeviceSnapshot,
  LinkNewDeviceSubscription,
  LinkSdkStep,
  LinkSdkStepKind,
  LinkSupportState,
  OwnerVerificationMethod
} from './LinkNewDeviceModels';
import { LinkNewDeviceReducer } from './LinkNewDeviceReducer';
import { LinkNewDeviceDataSource, LinkNewDeviceService } from './LinkNewDeviceService';

class ControllerLinkSubscription implements LinkNewDeviceSubscription {
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

export class LinkNewDeviceController implements LinkNewDeviceService {
  private readonly source: LinkNewDeviceDataSource;
  private readonly reducer: LinkNewDeviceReducer = new LinkNewDeviceReducer();
  private readonly observers: Map<number, LinkNewDeviceObserver> = new Map<number, LinkNewDeviceObserver>();
  private nextObserverId: number = 1;
  private nextAttemptId: number = 1;
  private supportGeneration: number = 0;
  private ownerGeneration: number = 0;

  constructor(source: LinkNewDeviceDataSource) {
    this.source = source;
  }

  getSnapshot(): LinkNewDeviceSnapshot {
    return this.reducer.getSnapshot();
  }

  subscribe(observer: LinkNewDeviceObserver): LinkNewDeviceSubscription {
    const id = this.nextObserverId++;
    this.observers.set(id, observer);
    observer.onLinkNewDeviceChanged(this.getSnapshot());
    return new ControllerLinkSubscription(id, (subscriptionId: number) => this.observers.delete(subscriptionId));
  }

  async loadSupport(): Promise<DomainResult<LinkNewDeviceSnapshot>> {
    const generation = ++this.supportGeneration;
    this.publish(this.reducer.beginSupportLoad());
    const result = await this.source.canLinkNewDevice();
    if (generation !== this.supportGeneration) {
      return this.stale('Link support result was superseded');
    }
    if (!result.success || result.value === null) {
      const error = result.error === null ? unexpectedFailure('link support check') : result.error;
      this.publish(this.reducer.failSupport(error));
      return DomainResult.fail<LinkNewDeviceSnapshot>(error);
    }
    return this.publishSuccess(this.reducer.setSupported(result.value));
  }

  async verifyOwner(method: OwnerVerificationMethod): Promise<DomainResult<LinkNewDeviceSnapshot>> {
    if (this.getSnapshot().support !== LinkSupportState.Supported) {
      return DomainResult.fail<LinkNewDeviceSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Link-new-device support must be confirmed before owner verification',
        false
      ));
    }
    const generation = ++this.ownerGeneration;
    this.publish(this.reducer.beginOwnerVerification());
    const result = await this.source.verifyOwner(method);
    if (generation !== this.ownerGeneration) {
      return this.stale('Owner verification result was superseded');
    }
    const error = result.error === null && !result.success ? unexpectedFailure('owner verification') : result.error;
    const snapshot = this.reducer.finishOwnerVerification(result.success && result.value === true, method, error);
    this.publish(snapshot);
    if (!result.success || result.value !== true) {
      return DomainResult.fail<LinkNewDeviceSnapshot>(
        error === null ? new DomainFailure(DomainErrorCode.AuthenticationRejected, 'Owner verification failed', true) : error
      );
    }
    return DomainResult.succeed<LinkNewDeviceSnapshot>(snapshot);
  }

  async verifyOwnerAndStart(
    method: OwnerVerificationMethod,
    mode: LinkAttemptMode,
    nowMs: number,
    timeoutMs: number
  ): Promise<DomainResult<LinkNewDeviceSnapshot>> {
    const verified = await this.verifyOwner(method);
    if (!verified.success) {
      return verified;
    }
    return this.startAttempt(mode, nowMs, timeoutMs);
  }

  async startAttempt(
    mode: LinkAttemptMode,
    nowMs: number,
    timeoutMs: number
  ): Promise<DomainResult<LinkNewDeviceSnapshot>> {
    const attemptId = `link-attempt-${this.nextAttemptId++}`;
    const started = this.reducer.startAttempt(attemptId, mode, nowMs, timeoutMs);
    if (!started.success || started.value === null) {
      return started;
    }
    this.publish(started.value);
    const result = await this.source.createHandler(attemptId, mode);
    if (this.getSnapshot().attemptId !== attemptId) {
      return this.stale('Link handler creation belongs to a stale attempt');
    }
    if (!result.success) {
      const error = result.error === null ? unexpectedFailure('create link handler') : result.error;
      const failed = this.reducer.receiveSdkStep({
        attemptId: attemptId,
        kind: LinkSdkStepKind.Error,
        qrCodeData: null,
        checkCodeDigits: [],
        errorCode: LinkErrorCode.Unknown,
        error: error
      });
      if (failed.value !== null) {
        this.publish(failed.value);
      }
      return DomainResult.fail<LinkNewDeviceSnapshot>(error);
    }
    return DomainResult.succeed<LinkNewDeviceSnapshot>(this.getSnapshot());
  }

  async scanQrCode(payload: string): Promise<DomainResult<LinkNewDeviceSnapshot>> {
    const attemptId = this.getSnapshot().attemptId;
    if (attemptId === null || payload.length === 0) {
      return DomainResult.fail<LinkNewDeviceSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'An active attempt and non-empty QR payload are required',
        false
      ));
    }
    const begun = this.reducer.beginScan();
    if (!begun.success || begun.value === null) {
      return begun;
    }
    this.publish(begun.value);
    const result = await this.source.scanQrCode(attemptId, payload);
    if (this.getSnapshot().attemptId !== attemptId) {
      return this.stale('QR scan result belongs to a stale attempt');
    }
    if (!result.success) {
      const error = result.error === null ? unexpectedFailure('scan QR code') : result.error;
      const failed = this.reducer.receiveSdkStep({
        attemptId: attemptId,
        kind: LinkSdkStepKind.InvalidQrCode,
        qrCodeData: null,
        checkCodeDigits: [],
        errorCode: LinkErrorCode.InvalidQrCode,
        error: error
      });
      if (failed.value !== null) {
        this.publish(failed.value);
      }
      return DomainResult.fail<LinkNewDeviceSnapshot>(error);
    }
    return DomainResult.succeed<LinkNewDeviceSnapshot>(this.getSnapshot());
  }

  tryAgain(): DomainResult<LinkNewDeviceSnapshot> {
    const result = this.reducer.tryAgain();
    if (result.success && result.value !== null) {
      this.publish(result.value);
    }
    return result;
  }

  async submitCheckCode(code: number): Promise<DomainResult<LinkNewDeviceSnapshot>> {
    const attemptId = this.getSnapshot().attemptId;
    if (attemptId === null || code < 0 || code > 255) {
      return DomainResult.fail<LinkNewDeviceSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Check code must be an unsigned byte for an active attempt',
        false
      ));
    }
    const result = await this.source.submitCheckCode(attemptId, code);
    if (this.getSnapshot().attemptId !== attemptId) {
      return this.stale('Check-code result belongs to a stale attempt');
    }
    if (!result.success) {
      const error = result.error === null ? unexpectedFailure('submit check code') : result.error;
      this.publish(this.reducer.markCheckCodeSent(false));
      return DomainResult.fail<LinkNewDeviceSnapshot>(error);
    }
    return this.publishSuccess(this.reducer.markCheckCodeSent(result.value === true));
  }

  receiveSdkStep(step: LinkSdkStep): DomainResult<LinkNewDeviceSnapshot> {
    const result = this.reducer.receiveSdkStep(step);
    if (result.success && result.value !== null) {
      this.publish(result.value);
    }
    return result;
  }

  tick(attemptId: string, nowMs: number): DomainResult<LinkNewDeviceSnapshot> {
    const result = this.reducer.tick(attemptId, nowMs);
    if (result.success && result.value !== null) {
      this.publish(result.value);
    }
    return result;
  }

  async retry(
    mode: LinkAttemptMode,
    nowMs: number,
    timeoutMs: number,
    requireOwnerVerification: boolean
  ): Promise<DomainResult<LinkNewDeviceSnapshot>> {
    const previousAttemptId = this.getSnapshot().attemptId;
    if (previousAttemptId !== null) {
      const cancelled = await this.source.cancel(previousAttemptId);
      if (!cancelled.success) {
        const error = cancelled.error === null ? unexpectedFailure('cancel previous link attempt') : cancelled.error;
        this.publish(this.reducer.markCancelled(error));
        return DomainResult.fail<LinkNewDeviceSnapshot>(error);
      }
    }
    if (requireOwnerVerification) {
      ++this.ownerGeneration;
      return this.publishSuccess(this.reducer.requireOwnerVerification());
    }
    return this.startAttempt(mode, nowMs, timeoutMs);
  }

  async cancel(): Promise<DomainResult<LinkNewDeviceSnapshot>> {
    ++this.ownerGeneration;
    const attemptId = this.getSnapshot().attemptId;
    if (attemptId === null) {
      return this.publishSuccess(this.reducer.ownerCancelled());
    }
    const result = await this.source.cancel(attemptId);
    if (this.getSnapshot().attemptId !== attemptId) {
      return this.stale('Link cancellation belongs to a stale attempt');
    }
    if (!result.success) {
      const error = result.error === null ? unexpectedFailure('cancel link attempt') : result.error;
      this.publish(this.reducer.markCancelled(error));
      return DomainResult.fail<LinkNewDeviceSnapshot>(error);
    }
    return this.publishSuccess(this.reducer.markCancelled(null));
  }

  resetCompleted(): LinkNewDeviceSnapshot {
    const snapshot = this.reducer.resetCompleted();
    this.publish(snapshot);
    return snapshot;
  }

  private stale(message: string): DomainResult<LinkNewDeviceSnapshot> {
    return DomainResult.fail<LinkNewDeviceSnapshot>(new DomainFailure(
      DomainErrorCode.Cancelled,
      message,
      false
    ));
  }

  private publishSuccess(snapshot: LinkNewDeviceSnapshot): DomainResult<LinkNewDeviceSnapshot> {
    this.publish(snapshot);
    return DomainResult.succeed<LinkNewDeviceSnapshot>(snapshot);
  }

  private publish(snapshot: LinkNewDeviceSnapshot): void {
    this.observers.forEach((observer: LinkNewDeviceObserver) => observer.onLinkNewDeviceChanged(snapshot));
  }
}
