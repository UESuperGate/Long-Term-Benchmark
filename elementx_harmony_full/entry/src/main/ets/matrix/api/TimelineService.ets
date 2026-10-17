import { DomainResult } from '../../core/DomainResult';
import {
  PaginationDirection,
  TimelineEventInput,
  TimelineObserver,
  TimelinePage,
  TimelineSendRequest,
  TimelineSnapshot
} from './TimelineModels';

export interface TimelineSubscription {
  subscriptionId: number;
  close(): void;
}

/** Production boundary to be backed by a room-scoped Matrix Rust timeline handle. */
export interface TimelineDataSource {
  loadInitial(roomId: string): Promise<DomainResult<TimelinePage>>;
  paginate(roomId: string, direction: PaginationDirection): Promise<DomainResult<TimelinePage>>;
  send(roomId: string, request: TimelineSendRequest): Promise<DomainResult<string>>;
  retry(roomId: string, transactionId: string): Promise<DomainResult<string>>;
  cancel(roomId: string, transactionId: string): Promise<DomainResult<boolean>>;
}

export interface TimelineService {
  getSnapshot(): TimelineSnapshot;
  subscribe(observer: TimelineObserver): TimelineSubscription;
  start(): Promise<DomainResult<TimelineSnapshot>>;
  receive(events: TimelineEventInput[]): DomainResult<TimelineSnapshot>;
  paginate(direction: PaginationDirection): Promise<DomainResult<TimelineSnapshot>>;
  send(request: TimelineSendRequest, senderId: string, timestampMs: number): Promise<DomainResult<TimelineSnapshot>>;
  retry(transactionId: string): Promise<DomainResult<TimelineSnapshot>>;
  cancel(transactionId: string): Promise<DomainResult<TimelineSnapshot>>;
  acknowledgeSent(transactionId: string, eventId: string, timestampMs: number, order: number): DomainResult<TimelineSnapshot>;
  setOffline(isOffline: boolean): void;
}
