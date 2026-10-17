import { RootNavigationStateMachine } from '../../appnav/RootNavigationStateMachine';
import {
  DomainErrorCode,
  DomainFailure,
  DomainResult
} from '../../core/DomainResult';
import {
  NativeBridgeError,
  NativeBridgeErrorCode,
  NativeDataOperationResult,
  NativeMatrixBridge
} from '../../nativebridge/Index';
import {
  PaginationDirection,
  RedactedContent,
  StateContent,
  TextContent,
  TimelineContent,
  TimelineContentKind,
  TimelineEventInput,
  TimelinePage,
  TimelineRelation,
  TimelineRelationKind,
  TimelineSendRequest,
  UnableToDecryptCause,
  UnableToDecryptContent
} from '../api/TimelineModels';
import { TimelineDataSource } from '../api/TimelineService';

interface MatrixRelationContent {
  rel_type?: string;
  event_id?: string;
  key?: string;
  mInReplyTo?: MatrixReplyContent;
}

interface MatrixReplyContent {
  event_id?: string;
}

interface MatrixTimelineContent {
  body?: string;
  formatted_body?: string;
  msgtype?: string;
  reason?: string;
  name?: string;
  topic?: string;
  membership?: string;
  session_id?: string;
  mRelatesTo?: MatrixRelationContent;
}

interface MatrixUnsignedContent {
  transaction_id?: string;
  redacted_because?: Object;
}

interface MatrixRawTimelineEvent {
  event_id?: string;
  sender?: string;
  type?: string;
  state_key?: string;
  redacts?: string;
  origin_server_ts?: number;
  content?: MatrixTimelineContent;
  unsigned?: MatrixUnsignedContent;
}

interface NativeTimelineEnvelope {
  events: MatrixRawTimelineEvent[];
  end: string | null;
}

interface NativeSendEnvelope {
  eventId: string;
}

/** Room-scoped Matrix SDK timeline transport used by the production shell. */
export class NativeTimelineDataSource implements TimelineDataSource {
  private readonly bridge: NativeMatrixBridge;
  private readonly rootNavigation: RootNavigationStateMachine;
  private backwardToken: string | null = null;
  private readonly pendingRequests: Map<string, TimelineSendRequest> = new Map<string, TimelineSendRequest>();

  constructor(bridge: NativeMatrixBridge, rootNavigation: RootNavigationStateMachine) {
    this.bridge = bridge;
    this.rootNavigation = rootNavigation;
  }

  async loadInitial(roomId: string): Promise<DomainResult<TimelinePage>> {
    this.backwardToken = null;
    return this.load(roomId, null);
  }

  async paginate(roomId: string, direction: PaginationDirection): Promise<DomainResult<TimelinePage>> {
    if (direction === PaginationDirection.Forwards) {
      return DomainResult.succeed<TimelinePage>({ events: [], direction: direction, hasMore: false });
    }
    if (this.backwardToken === null) {
      return DomainResult.succeed<TimelinePage>({ events: [], direction: direction, hasMore: false });
    }
    return this.load(roomId, this.backwardToken);
  }

  async send(roomId: string, request: TimelineSendRequest): Promise<DomainResult<string>> {
    if (request.content.kind !== TimelineContentKind.Text) {
      return DomainResult.fail<string>(new DomainFailure(
        DomainErrorCode.ServiceUnavailable,
        'The native production transport currently supports text messages only',
        false
      ));
    }
    this.pendingRequests.set(request.transactionId, request);
    return this.sendRequest(roomId, request);
  }

  async retry(roomId: string, transactionId: string): Promise<DomainResult<string>> {
    const request = this.pendingRequests.get(transactionId);
    if (request === undefined) {
      return DomainResult.fail<string>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        `Unknown timeline transaction ${transactionId}`,
        false
      ));
    }
    return this.sendRequest(roomId, request);
  }

  async cancel(_roomId: string, transactionId: string): Promise<DomainResult<boolean>> {
    this.pendingRequests.delete(transactionId);
    return DomainResult.succeed<boolean>(true);
  }

  private async load(roomId: string, token: string | null): Promise<DomainResult<TimelinePage>> {
    const handle = this.currentHandle();
    if (handle === null) {
      return DomainResult.fail<TimelinePage>(this.missingSession());
    }
    try {
      const result = await this.bridge.loadTimeline(handle, roomId, token);
      if (!result.ok || result.value === null) {
        return DomainResult.fail<TimelinePage>(this.nativeFailure(result, 'Native timeline load failed'));
      }
      const envelope = JSON.parse(result.value) as NativeTimelineEnvelope;
      if (!Array.isArray(envelope.events)) {
        return DomainResult.fail<TimelinePage>(this.malformed('Native timeline response is malformed'));
      }
      const events: TimelineEventInput[] = [];
      envelope.events.forEach((event: MatrixRawTimelineEvent) => {
        const mapped = this.mapEvent(event);
        if (mapped !== null) {
          events.push(mapped);
        }
      });
      this.backwardToken = typeof envelope.end === 'string' && envelope.end.length > 0 ? envelope.end : null;
      return DomainResult.succeed<TimelinePage>({
        events: events,
        direction: PaginationDirection.Backwards,
        hasMore: this.backwardToken !== null
      });
    } catch (error) {
      return DomainResult.fail<TimelinePage>(new DomainFailure(
        DomainErrorCode.NetworkUnavailable,
        'Matrix timeline could not reach the homeserver',
        true
      ));
    }
  }

  private async sendRequest(roomId: string, request: TimelineSendRequest): Promise<DomainResult<string>> {
    const handle = this.currentHandle();
    if (handle === null) {
      return DomainResult.fail<string>(this.missingSession());
    }
    const content = request.content as TextContent;
    try {
      const result = await this.bridge.sendText(handle, roomId, content.body, request.transactionId);
      if (!result.ok || result.value === null) {
        return DomainResult.fail<string>(this.nativeFailure(result, 'Native message send failed'));
      }
      const envelope = JSON.parse(result.value) as NativeSendEnvelope;
      if (typeof envelope.eventId !== 'string' || envelope.eventId.length === 0) {
        return DomainResult.fail<string>(this.malformed('Native send response is malformed'));
      }
      this.pendingRequests.delete(request.transactionId);
      return DomainResult.succeed<string>(envelope.eventId);
    } catch (error) {
      return DomainResult.fail<string>(new DomainFailure(
        DomainErrorCode.NetworkUnavailable,
        'Matrix message send could not reach the homeserver',
        true
      ));
    }
  }

  private mapEvent(event: MatrixRawTimelineEvent): TimelineEventInput | null {
    const eventId = event.event_id ?? '';
    const transactionId = event.unsigned?.transaction_id ?? null;
    const senderId = event.sender ?? '';
    if ((eventId.length === 0 && transactionId === null) || senderId.length === 0) {
      return null;
    }
    const timestamp = event.origin_server_ts ?? 0;
    return {
      eventId: eventId.length === 0 ? null : eventId,
      transactionId: transactionId,
      senderId: senderId,
      senderDisplayName: null,
      timestampMs: timestamp,
      order: timestamp,
      isOwn: senderId === (this.rootNavigation.getState().session?.userId ?? ''),
      content: this.mapContent(event),
      relation: this.mapRelation(event)
    };
  }

  private mapContent(event: MatrixRawTimelineEvent): TimelineContent {
    if (event.unsigned?.redacted_because !== undefined) {
      const content: RedactedContent = { kind: TimelineContentKind.Redacted, reason: null };
      return content;
    }
    if (event.type === 'm.room.message') {
      const content: TextContent = {
        kind: TimelineContentKind.Text,
        body: event.content?.body ?? '',
        formattedBody: event.content?.formatted_body ?? null
      };
      return content;
    }
    if (event.type === 'm.room.encrypted') {
      const content: UnableToDecryptContent = {
        kind: TimelineContentKind.UnableToDecrypt,
        sessionId: event.content?.session_id ?? null,
        cause: UnableToDecryptCause.Unknown
      };
      return content;
    }
    const summary = event.content?.name ?? event.content?.topic ?? event.content?.membership ??
      event.content?.body ?? event.type ?? 'Matrix state event';
    const content: StateContent = {
      kind: TimelineContentKind.State,
      eventType: event.type ?? 'm.room.unknown',
      stateKey: event.state_key ?? '',
      summary: summary
    };
    return content;
  }

  private mapRelation(event: MatrixRawTimelineEvent): TimelineRelation | null {
    if (event.type === 'm.room.redaction' && event.redacts !== undefined) {
      return { kind: TimelineRelationKind.Redaction, targetEventId: event.redacts, key: null };
    }
    const relation = event.content?.mRelatesTo;
    if (relation === undefined) {
      return null;
    }
    if (relation.mInReplyTo?.event_id !== undefined) {
      return { kind: TimelineRelationKind.Reply, targetEventId: relation.mInReplyTo.event_id, key: null };
    }
    if (relation.event_id === undefined) {
      return null;
    }
    if (relation.rel_type === 'm.replace') {
      return { kind: TimelineRelationKind.Replacement, targetEventId: relation.event_id, key: null };
    }
    if (relation.rel_type === 'm.annotation') {
      return { kind: TimelineRelationKind.Reaction, targetEventId: relation.event_id, key: relation.key ?? null };
    }
    return null;
  }

  private currentHandle(): number | null {
    const sessionHandle = this.rootNavigation.getState().sessionHandle;
    if (sessionHandle === null || !sessionHandle.runtimeId.startsWith('native:')) {
      return null;
    }
    const handle = Number(sessionHandle.runtimeId.substring('native:'.length));
    return Number.isSafeInteger(handle) && handle > 0 ? handle : null;
  }

  private missingSession(): DomainFailure {
    return new DomainFailure(
      DomainErrorCode.SessionMissing,
      'An authenticated Matrix SDK client is required for the timeline',
      false
    );
  }

  private malformed(message: string): DomainFailure {
    return new DomainFailure(DomainErrorCode.Unknown, message, false);
  }

  private nativeFailure(result: NativeDataOperationResult, fallback: string): DomainFailure {
    const error: NativeBridgeError | null = result.error;
    const network = error !== null && (error.code === NativeBridgeErrorCode.TimelineFailed ||
      error.code === NativeBridgeErrorCode.SendFailed || error.code === NativeBridgeErrorCode.SyncFailed);
    return new DomainFailure(
      network ? DomainErrorCode.NetworkUnavailable : DomainErrorCode.ServiceUnavailable,
      error === null ? fallback : error.message,
      error === null ? true : error.retryable
    );
  }
}
