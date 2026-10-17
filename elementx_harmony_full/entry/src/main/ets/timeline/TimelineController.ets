import {
  DomainErrorCode,
  DomainFailure,
  DomainResult,
  unexpectedFailure
} from '../core/DomainResult';
import {
  LocalSendState,
  PaginationDirection,
  TimelineEventInput,
  TimelineObserver,
  TimelinePage,
  TimelineSendRequest,
  TimelineSnapshot
} from '../matrix/api/TimelineModels';
import {
  TimelineDataSource,
  TimelineService,
  TimelineSubscription
} from '../matrix/api/TimelineService';
import { TimelineReducer } from './TimelineReducer';

class ControllerTimelineSubscription implements TimelineSubscription {
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

export class TimelineController implements TimelineService {
  private readonly roomId: string;
  private readonly source: TimelineDataSource;
  private readonly reducer: TimelineReducer;
  private readonly observers: Map<number, TimelineObserver> = new Map<number, TimelineObserver>();
  private nextObserverId: number = 1;

  constructor(roomId: string, source: TimelineDataSource) {
    this.roomId = roomId;
    this.source = source;
    this.reducer = new TimelineReducer(roomId);
  }

  getSnapshot(): TimelineSnapshot {
    return this.reducer.getSnapshot();
  }

  subscribe(observer: TimelineObserver): TimelineSubscription {
    const id = this.nextObserverId++;
    this.observers.set(id, observer);
    observer.onTimelineChanged(this.getSnapshot());
    return new ControllerTimelineSubscription(id, (subscriptionId: number) => {
      this.observers.delete(subscriptionId);
    });
  }

  async start(): Promise<DomainResult<TimelineSnapshot>> {
    this.publish(this.reducer.beginLoading());
    const result = await this.source.loadInitial(this.roomId);
    return this.completePage(result);
  }

  receive(events: TimelineEventInput[]): DomainResult<TimelineSnapshot> {
    const result = this.reducer.merge(events);
    if (result.success && result.value !== null) {
      this.publish(result.value);
    }
    return result;
  }

  async paginate(direction: PaginationDirection): Promise<DomainResult<TimelineSnapshot>> {
    const pagination = direction === PaginationDirection.Backwards ?
      this.getSnapshot().backwardPagination : this.getSnapshot().forwardPagination;
    if (pagination.isPaginating || !pagination.hasMore) {
      return DomainResult.succeed<TimelineSnapshot>(this.getSnapshot());
    }
    this.publish(this.reducer.beginPagination(direction));
    const result = await this.source.paginate(this.roomId, direction);
    if (!result.success || result.value === null) {
      const error = result.error === null ? unexpectedFailure('timeline pagination') : result.error;
      this.publish(this.reducer.failPagination(direction, error));
      return DomainResult.fail<TimelineSnapshot>(error);
    }
    const merged = this.reducer.merge(result.value.events);
    if (!merged.success) {
      const error = merged.error === null ? unexpectedFailure('timeline merge') : merged.error;
      this.publish(this.reducer.failPagination(direction, error));
      return DomainResult.fail<TimelineSnapshot>(error);
    }
    const snapshot = this.reducer.finishPagination(direction, result.value.hasMore);
    this.publish(snapshot);
    return DomainResult.succeed<TimelineSnapshot>(snapshot);
  }

  async send(
    request: TimelineSendRequest,
    senderId: string,
    timestampMs: number
  ): Promise<DomainResult<TimelineSnapshot>> {
    const queued = this.reducer.enqueueLocal(
      request.transactionId,
      senderId,
      timestampMs,
      request.content,
      request.replyToEventId
    );
    if (!queued.success || queued.value === null) {
      return queued;
    }
    this.publish(queued.value);
    const sending = this.reducer.updateSendState(request.transactionId, LocalSendState.Sending, null, null);
    if (sending.value !== null) {
      this.publish(sending.value);
    }
    const result = await this.source.send(this.roomId, request);
    if (!result.success) {
      const error = result.error === null ? unexpectedFailure('timeline send') : result.error;
      const failed = this.reducer.updateSendState(request.transactionId, LocalSendState.Failed, null, error);
      if (failed.value !== null) {
        this.publish(failed.value);
      }
      return DomainResult.fail<TimelineSnapshot>(error);
    }
    if (result.value === null) {
      const error = unexpectedFailure('timeline send acknowledgement');
      const failed = this.reducer.updateSendState(request.transactionId, LocalSendState.Failed, null, error);
      if (failed.value !== null) {
        this.publish(failed.value);
      }
      return DomainResult.fail<TimelineSnapshot>(error);
    }
    return this.acknowledgeSent(request.transactionId, result.value, timestampMs, timestampMs);
  }

  async retry(transactionId: string): Promise<DomainResult<TimelineSnapshot>> {
    const sending = this.reducer.updateSendState(transactionId, LocalSendState.Sending, null, null);
    if (!sending.success || sending.value === null) {
      return sending;
    }
    this.publish(sending.value);
    const result = await this.source.retry(this.roomId, transactionId);
    if (!result.success) {
      const error = result.error === null ? unexpectedFailure('timeline retry') : result.error;
      const failed = this.reducer.updateSendState(transactionId, LocalSendState.Failed, null, error);
      if (failed.value !== null) {
        this.publish(failed.value);
      }
      return DomainResult.fail<TimelineSnapshot>(error);
    }
    if (result.value === null) {
      const error = unexpectedFailure('timeline retry acknowledgement');
      const failed = this.reducer.updateSendState(transactionId, LocalSendState.Failed, null, error);
      if (failed.value !== null) {
        this.publish(failed.value);
      }
      return DomainResult.fail<TimelineSnapshot>(error);
    }
    const timestampMs = Date.now();
    return this.acknowledgeSent(transactionId, result.value, timestampMs, timestampMs);
  }

  async cancel(transactionId: string): Promise<DomainResult<TimelineSnapshot>> {
    const result = await this.source.cancel(this.roomId, transactionId);
    if (!result.success) {
      return DomainResult.fail<TimelineSnapshot>(
        result.error === null ? unexpectedFailure('timeline cancel') : result.error
      );
    }
    const cancelled = this.reducer.updateSendState(transactionId, LocalSendState.Cancelled, null, null);
    if (cancelled.success && cancelled.value !== null) {
      this.publish(cancelled.value);
    }
    return cancelled;
  }

  acknowledgeSent(
    transactionId: string,
    eventId: string,
    timestampMs: number,
    order: number
  ): DomainResult<TimelineSnapshot> {
    const result = this.reducer.acknowledgeSent(transactionId, eventId, timestampMs, order);
    if (result.success && result.value !== null) {
      this.publish(result.value);
    }
    return result;
  }

  setOffline(isOffline: boolean): void {
    this.publish(this.reducer.setOffline(isOffline));
  }

  private completePage(result: DomainResult<TimelinePage>): DomainResult<TimelineSnapshot> {
    if (!result.success || result.value === null) {
      const error = result.error === null ? unexpectedFailure('timeline load') : result.error;
      this.publish(this.reducer.fail(error, error.code === DomainErrorCode.NetworkUnavailable));
      return DomainResult.fail<TimelineSnapshot>(error);
    }
    const merged = this.reducer.merge(result.value.events);
    if (!merged.success || merged.value === null) {
      const error = merged.error === null ? new DomainFailure(
        DomainErrorCode.ServiceUnavailable,
        'Timeline returned invalid events',
        true
      ) : merged.error;
      this.publish(this.reducer.fail(error, false));
      return DomainResult.fail<TimelineSnapshot>(error);
    }
    this.reducer.finishPagination(result.value.direction, result.value.hasMore);
    const snapshot = this.getSnapshot();
    this.publish(snapshot);
    return DomainResult.succeed<TimelineSnapshot>(snapshot);
  }

  private publish(snapshot: TimelineSnapshot): void {
    this.observers.forEach((observer: TimelineObserver) => observer.onTimelineChanged(snapshot));
  }
}
