import {
  DomainErrorCode,
  DomainFailure,
  DomainResult,
  unexpectedFailure
} from '../core/DomainResult';
import {
  SecuritySnapshot,
  UtdKeyRequest,
  UtdKeyRequestState
} from '../matrix/api/SecurityModels';
import {
  SecurityDataSource,
  SecurityObserver,
  SecurityService,
  SecuritySubscription
} from '../matrix/api/SecurityServices';
import { SecurityReducer } from './SecurityReducer';

class ControllerSecuritySubscription implements SecuritySubscription {
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

export class SecurityController implements SecurityService {
  private readonly source: SecurityDataSource;
  private readonly reducer: SecurityReducer = new SecurityReducer();
  private readonly observers: Map<number, SecurityObserver> = new Map<number, SecurityObserver>();
  private nextObserverId: number = 1;
  private generation: number = 0;
  private nextRequestId: number = 1;

  constructor(source: SecurityDataSource) {
    this.source = source;
  }

  getSnapshot(): SecuritySnapshot {
    return this.reducer.getSnapshot();
  }

  subscribe(observer: SecurityObserver): SecuritySubscription {
    const id = this.nextObserverId++;
    this.observers.set(id, observer);
    observer.onSecurityChanged(this.getSnapshot());
    return new ControllerSecuritySubscription(id, (subscriptionId: number) => this.observers.delete(subscriptionId));
  }

  async start(): Promise<DomainResult<SecuritySnapshot>> {
    const generation = ++this.generation;
    this.publish(this.reducer.beginLoading());
    const result = await this.source.loadState();
    if (generation !== this.generation) {
      return DomainResult.fail<SecuritySnapshot>(new DomainFailure(
        DomainErrorCode.Cancelled,
        'Security state load superseded by a newer request',
        true
      ));
    }
    if (!result.success || result.value === null) {
      const error = result.error === null ? unexpectedFailure('security state load') : result.error;
      this.publish(this.reducer.fail(error, error.code === DomainErrorCode.NetworkUnavailable));
      return DomainResult.fail<SecuritySnapshot>(error);
    }
    return this.publishSuccess(this.reducer.replace(result.value));
  }

  async requestRoomKey(
    roomId: string,
    eventId: string,
    sessionId: string | null
  ): Promise<DomainResult<SecuritySnapshot>> {
    if (roomId.length === 0 || eventId.length === 0) {
      return DomainResult.fail<SecuritySnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'A room and event are required for a room-key request',
        false
      ));
    }
    const request: UtdKeyRequest = {
      requestId: `key-request-${this.nextRequestId++}`,
      roomId: roomId,
      eventId: eventId,
      sessionId: sessionId,
      state: UtdKeyRequestState.Requesting,
      error: null
    };
    this.publish(this.reducer.beginKeyRequest(request));
    const result = await this.source.requestRoomKey(request);
    if (!result.success) {
      const error = result.error === null ? unexpectedFailure('room-key request') : result.error;
      this.publish(this.reducer.updateKeyRequest(request.requestId, UtdKeyRequestState.Failed, error));
      return DomainResult.fail<SecuritySnapshot>(error);
    }
    return this.publishSuccess(this.reducer.updateKeyRequest(request.requestId, UtdKeyRequestState.Waiting, null));
  }

  async cancelRoomKeyRequest(requestId: string): Promise<DomainResult<SecuritySnapshot>> {
    const result = await this.source.cancelRoomKeyRequest(requestId);
    if (!result.success) {
      return DomainResult.fail<SecuritySnapshot>(
        result.error === null ? unexpectedFailure('cancel room-key request') : result.error
      );
    }
    return this.publishSuccess(this.reducer.updateKeyRequest(requestId, UtdKeyRequestState.Cancelled, null));
  }

  receiveRoomKeyRequestState(
    requestId: string,
    state: UtdKeyRequestState
  ): DomainResult<SecuritySnapshot> {
    const known = this.getSnapshot().keyRequests.some((request: UtdKeyRequest) => request.requestId === requestId);
    if (!known) {
      return DomainResult.fail<SecuritySnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        `Cannot update unknown room-key request ${requestId}`,
        false
      ));
    }
    return this.publishSuccess(this.reducer.updateKeyRequest(requestId, state, null));
  }

  async enableBackups(): Promise<DomainResult<SecuritySnapshot>> {
    this.publish(this.reducer.beginBackups());
    const result = await this.source.enableBackups();
    if (!result.success) {
      const error = result.error === null ? unexpectedFailure('enable backups') : result.error;
      this.publish(this.reducer.failBackups(error));
      return DomainResult.fail<SecuritySnapshot>(error);
    }
    return this.publishSuccess(this.reducer.finishBackups());
  }

  async enableRecovery(waitForBackupsToUpload: boolean): Promise<DomainResult<SecuritySnapshot>> {
    this.publish(this.reducer.beginEnableRecovery());
    const result = await this.source.enableRecovery(waitForBackupsToUpload);
    if (!result.success) {
      const error = result.error === null ? unexpectedFailure('enable recovery') : result.error;
      this.publish(this.reducer.failRecovery(error));
      return DomainResult.fail<SecuritySnapshot>(error);
    }
    return this.publishSuccess(this.reducer.finishEnableRecovery());
  }

  async recover(recoveryKeyOrPassphrase: string): Promise<DomainResult<SecuritySnapshot>> {
    if (recoveryKeyOrPassphrase.length === 0) {
      return DomainResult.fail<SecuritySnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Recovery input must not be empty',
        false
      ));
    }
    this.publish(this.reducer.beginRecovery());
    const result = await this.source.recover(recoveryKeyOrPassphrase);
    if (!result.success) {
      const error = result.error === null ? unexpectedFailure('recovery') : result.error;
      this.publish(this.reducer.failRecovery(error));
      return DomainResult.fail<SecuritySnapshot>(error);
    }
    return this.publishSuccess(this.reducer.finishRecovery());
  }

  async disableRecovery(): Promise<DomainResult<SecuritySnapshot>> {
    this.publish(this.reducer.beginDisableRecovery());
    const result = await this.source.disableRecovery();
    if (!result.success) {
      const error = result.error === null ? unexpectedFailure('disable recovery') : result.error;
      this.publish(this.reducer.failRecovery(error));
      return DomainResult.fail<SecuritySnapshot>(error);
    }
    return this.publishSuccess(this.reducer.finishDisableRecovery());
  }

  setOffline(isOffline: boolean): void {
    this.publish(this.reducer.setOffline(isOffline));
  }

  private publishSuccess(snapshot: SecuritySnapshot): DomainResult<SecuritySnapshot> {
    this.publish(snapshot);
    return DomainResult.succeed<SecuritySnapshot>(snapshot);
  }

  private publish(snapshot: SecuritySnapshot): void {
    this.observers.forEach((observer: SecurityObserver) => observer.onSecurityChanged(snapshot));
  }
}
