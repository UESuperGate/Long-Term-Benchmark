import {
  DomainErrorCode,
  DomainFailure,
  DomainResult
} from '../main/ets/core/DomainResult';
import {
  RoomCategory,
  RoomListFilter,
  RoomListPage,
  RoomListPhase,
  RoomMembership,
  RoomSummary
} from '../main/ets/matrix/api/RoomModels';
import { RoomListDataSource } from '../main/ets/matrix/api/RoomListService';
import {
  CallContent,
  CallKind,
  GalleryContent,
  LocalSendState,
  LocationContent,
  PaginationDirection,
  TextContent,
  TimelineContentKind,
  TimelineEventInput,
  TimelinePage,
  TimelineRelationKind,
  TimelineSendRequest
} from '../main/ets/matrix/api/TimelineModels';
import { TimelineDataSource } from '../main/ets/matrix/api/TimelineService';
import { RoomListController } from '../main/ets/rooms/RoomListController';
import { RoomListFilters } from '../main/ets/rooms/RoomListFilters';
import { RoomListReducer } from '../main/ets/rooms/RoomListReducer';
import { TimelineController } from '../main/ets/timeline/TimelineController';
import { TimelineReducer } from '../main/ets/timeline/TimelineReducer';

function check(condition: boolean, message: string): void {
  if (!condition) {
    throw new Error(message);
  }
}

function room(roomId: string, timestampMs: number, favorite: boolean, unread: number): RoomSummary {
  return {
    roomId: roomId,
    displayName: roomId,
    canonicalAlias: null,
    avatarUrl: null,
    membership: RoomMembership.Joined,
    category: RoomCategory.Group,
    isFavorite: favorite,
    isDirect: false,
    isMarkedUnread: false,
    unreadNotificationCount: unread,
    unreadMentionCount: 0,
    activeMembersCount: 3,
    latestEventTimestampMs: timestampMs,
    latestEventPreview: null
  };
}

function text(body: string): TextContent {
  return { kind: TimelineContentKind.Text, body: body, formattedBody: null };
}

function event(
  eventId: string,
  timestampMs: number,
  content: TextContent | GalleryContent | CallContent | LocationContent,
  relationKind: TimelineRelationKind = TimelineRelationKind.None,
  targetEventId: string = '',
  relationKey: string | null = null,
  senderId: string = '@alice:example.org'
): TimelineEventInput {
  return {
    eventId: eventId,
    transactionId: null,
    senderId: senderId,
    senderDisplayName: 'Alice',
    timestampMs: timestampMs,
    order: timestampMs,
    isOwn: senderId === '@me:example.org',
    content: content,
    relation: relationKind === TimelineRelationKind.None ? null : {
      kind: relationKind,
      targetEventId: targetEventId,
      key: relationKey
    }
  };
}

class FailingRoomSource implements RoomListDataSource {
  async loadInitial(pageSize: number, filter: RoomListFilter): Promise<DomainResult<RoomListPage>> {
    return DomainResult.fail<RoomListPage>(new DomainFailure(
      DomainErrorCode.NetworkUnavailable,
      'offline',
      true
    ));
  }

  async loadMore(offset: number, pageSize: number, filter: RoomListFilter): Promise<DomainResult<RoomListPage>> {
    return this.loadInitial(pageSize, filter);
  }

  async refresh(filter: RoomListFilter): Promise<DomainResult<RoomListPage>> {
    return this.loadInitial(20, filter);
  }

  async subscribeVisibleRooms(roomIds: string[]): Promise<DomainResult<boolean>> {
    return DomainResult.fail<boolean>(new DomainFailure(
      DomainErrorCode.NetworkUnavailable,
      'offline',
      true
    ));
  }
}

class FailingTimelineSource implements TimelineDataSource {
  async loadInitial(roomId: string): Promise<DomainResult<TimelinePage>> {
    return DomainResult.fail<TimelinePage>(new DomainFailure(
      DomainErrorCode.NetworkUnavailable,
      'offline',
      true
    ));
  }

  async paginate(roomId: string, direction: PaginationDirection): Promise<DomainResult<TimelinePage>> {
    return this.loadInitial(roomId);
  }

  async send(roomId: string, request: TimelineSendRequest): Promise<DomainResult<string>> {
    return DomainResult.fail<string>(new DomainFailure(
      DomainErrorCode.ServiceUnavailable,
      'send failed',
      true
    ));
  }

  async retry(roomId: string, transactionId: string): Promise<DomainResult<string>> {
    return this.send(roomId, {
      transactionId: transactionId,
      content: text('retry'),
      replyToEventId: null
    });
  }

  async cancel(roomId: string, transactionId: string): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(true);
  }
}

function testRoomFilteringSelectionAndOrdering(): void {
  const reducer = new RoomListReducer(RoomListFilters.all([
    RoomListFilters.favorite(),
    RoomListFilters.unread()
  ]));
  const snapshot = reducer.replace({
    rooms: [room('older', 10, true, 2), room('newer', 20, true, 1), room('not-favorite', 30, false, 2)],
    totalCount: 3,
    hasMore: false
  });
  check(snapshot.phase === RoomListPhase.Ready, 'matching rooms should make room list ready');
  check(snapshot.rooms.length === 2, 'all filter must require favorite and unread');
  check(snapshot.rooms[0].roomId === 'newer', 'room list must be ordered by latest event');
  check(reducer.select('newer'), 'known room must be selectable');
  check(!reducer.select('missing'), 'unknown room must not be selectable');
}

async function testFailuresStayExplicitAndEmpty(): Promise<void> {
  const rooms = new RoomListController(new FailingRoomSource());
  const roomResult = await rooms.start();
  check(!roomResult.success, 'room loading failure must propagate');
  check(rooms.getSnapshot().phase === RoomListPhase.Offline, 'network room failure must enter offline state');
  check(rooms.getSnapshot().rooms.length === 0, 'room failure must not generate fixture rooms');

  const timeline = new TimelineController('!room:example.org', new FailingTimelineSource());
  const timelineResult = await timeline.start();
  check(!timelineResult.success, 'timeline loading failure must propagate');
  check(timeline.getSnapshot().items.length === 0, 'timeline failure must not generate fixture events');
}

function testGalleryCallAndLocationPaths(): void {
  const reducer = new TimelineReducer('!room:example.org');
  const gallery: GalleryContent = {
    kind: TimelineContentKind.Gallery,
    caption: 'Trip',
    items: [
      {
        sourceUrl: 'mxc://example.org/image',
        fileName: 'image.jpg',
        mimeType: 'image/jpeg',
        sizeBytes: 10,
        width: 100,
        height: 100,
        durationMs: null,
        thumbnailUrl: null
      },
      {
        sourceUrl: 'mxc://example.org/video',
        fileName: 'video.mp4',
        mimeType: 'video/mp4',
        sizeBytes: 20,
        width: 100,
        height: 100,
        durationMs: 500,
        thumbnailUrl: 'mxc://example.org/thumb'
      }
    ]
  };
  const call: CallContent = {
    kind: TimelineContentKind.Call,
    callKind: CallKind.Notification,
    callId: 'call-1',
    isVideo: true,
    isActive: true
  };
  const location: LocationContent = {
    kind: TimelineContentKind.Location,
    body: 'Shared location',
    geoUri: 'geo:51.5008,0.1247;u=35',
    description: 'London',
    zoomLevel: 15,
    isLive: false,
    expiresAtMs: null
  };
  const result = reducer.merge([
    event('$location', 30, location),
    event('$gallery', 10, gallery),
    event('$call', 20, call)
  ]);
  check(result.success, 'gallery/call/location batch must be accepted');
  const items = reducer.getSnapshot().items;
  check(items.length === 3, 'all benchmark content paths must remain visible');
  check(items[0].content.kind === TimelineContentKind.Gallery, 'timeline ordering must be deterministic');
  check(items[1].content.kind === TimelineContentKind.Call, 'call event must retain typed content');
  check(items[2].content.kind === TimelineContentKind.Location, 'location event must retain typed content');
}

function testRelationsAndStableIdentity(): void {
  const reducer = new TimelineReducer('!room:example.org');
  const pendingReaction = event(
    '$reaction',
    15,
    text('reaction relation'),
    TimelineRelationKind.Reaction,
    '$message',
    '👍',
    '@me:example.org'
  );
  check(reducer.merge([pendingReaction]).success, 'relation may arrive before paginated target');
  check(reducer.getSnapshot().items.length === 0, 'reaction relation must not render as a message');
  check(reducer.merge([event('$message', 10, text('original'))]).success, 'target event must merge');
  const stableId = reducer.getSnapshot().items[0].stableId;
  check(reducer.getSnapshot().items[0].reactions[0].count === 1, 'pending reaction must attach to target');

  const replacement = event(
    '$edit',
    20,
    text('edited'),
    TimelineRelationKind.Replacement,
    '$message'
  );
  check(reducer.merge([replacement]).success, 'same-sender replacement must apply');
  check(reducer.getSnapshot().items[0].stableId === stableId, 'replacement must preserve stable identity');
  check(reducer.getSnapshot().items[0].isEdited, 'replacement must mark target edited');

  const redaction = event(
    '$redaction',
    30,
    text('redaction relation'),
    TimelineRelationKind.Redaction,
    '$message'
  );
  check(reducer.merge([redaction]).success, 'redaction must apply');
  check(reducer.getSnapshot().items[0].content.kind === TimelineContentKind.Redacted, 'target must become redacted');
  check(reducer.getSnapshot().items[0].stableId === stableId, 'redaction must preserve stable identity');
}

function testPaginationAndLocalEchoIdentity(): void {
  const reducer = new TimelineReducer('!room:example.org');
  check(reducer.merge([event('$new', 20, text('new'))]).success, 'live event must merge');
  check(reducer.merge([event('$old', 10, text('old')), event('$new', 20, text('new duplicate'))]).success,
    'backward page must deduplicate overlap');
  check(reducer.getSnapshot().items.length === 2, 'pagination overlap must not duplicate events');
  check(reducer.getSnapshot().items[0].eventId === '$old', 'backward page must prepend in stable order');

  check(reducer.enqueueLocal('txn-1', '@me:example.org', 30, text('local'), null).success,
    'local echo must enter send queue');
  const localStableId = reducer.getSnapshot().items[2].stableId;
  check(reducer.acknowledgeSent('txn-1', '$sent', 31, 31).success, 'sent acknowledgement must apply');
  const sent = reducer.getSnapshot().items.find((item) => item.eventId === '$sent');
  check(sent !== undefined && sent.stableId === localStableId, 'remote acknowledgement must preserve local identity');
  check(sent !== undefined && sent.localSendState === LocalSendState.Sent, 'acknowledgement must mark local event sent');
}

function testValidationIsAtomic(): void {
  const reducer = new TimelineReducer('!room:example.org');
  const invalidGallery: GalleryContent = {
    kind: TimelineContentKind.Gallery,
    caption: null,
    items: []
  };
  const result = reducer.merge([
    event('$valid', 10, text('valid')),
    event('$invalid', 20, invalidGallery)
  ]);
  check(!result.success, 'invalid gallery must fail validation');
  check(reducer.getSnapshot().items.length === 0, 'invalid batch must not partially mutate timeline');
}

async function testSendFailureRemainsInQueue(): Promise<void> {
  const controller = new TimelineController('!room:example.org', new FailingTimelineSource());
  const result = await controller.send({
    transactionId: 'txn-failed',
    content: text('message'),
    replyToEventId: null
  }, '@me:example.org', 100);
  check(!result.success, 'send service failure must propagate');
  const snapshot = controller.getSnapshot();
  check(snapshot.items.length === 1, 'failed local echo must remain visible for retry');
  check(snapshot.sendQueue[0].state === LocalSendState.Failed, 'send queue must expose failed state');
  check(snapshot.sendQueue[0].error?.code === DomainErrorCode.ServiceUnavailable,
    'send queue must retain typed failure');
}

export async function runRoomTimelineDomainTests(): Promise<string[]> {
  const passed: string[] = [];
  testRoomFilteringSelectionAndOrdering();
  passed.push('room filtering, selection, ordering');
  await testFailuresStayExplicitAndEmpty();
  passed.push('explicit empty failure states');
  testGalleryCallAndLocationPaths();
  passed.push('gallery, call, location event paths');
  testRelationsAndStableIdentity();
  passed.push('replacement, reaction, redaction identity');
  testPaginationAndLocalEchoIdentity();
  passed.push('pagination and local echo identity');
  testValidationIsAtomic();
  passed.push('atomic validation');
  await testSendFailureRemainsInQueue();
  passed.push('send queue failure propagation');
  return passed;
}
