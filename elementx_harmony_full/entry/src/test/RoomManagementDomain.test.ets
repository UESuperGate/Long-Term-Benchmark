import { DomainErrorCode, DomainFailure, DomainResult } from '../main/ets/core/DomainResult';
import { RoomManagementController } from '../main/ets/features/roommanagement/RoomManagementController';
import { SearchController } from '../main/ets/features/search/SearchController';
import { SpacesController } from '../main/ets/features/spaces/SpacesController';
import {
  CreateRoomRequest,
  ManagedRoomDetails,
  RoomJoinRule,
  RoomManagementCommand,
  RoomManagementCommandKind,
  RoomManagementPayload,
  RoomMemberRole,
  RoomMembershipState,
  RoomVisibility,
  SearchDomain,
  SearchPage,
  SearchRequest,
  SpacePage,
  SpacesPhase
} from '../main/ets/matrix/api/RoomManagementModels';
import {
  RoomManagementDataSource,
  SearchDataSource,
  SpacesDataSource
} from '../main/ets/matrix/api/RoomManagementServices';

function check(condition: boolean, message: string): void {
  if (!condition) {
    throw new Error(message);
  }
}

class DeferredResult<T> {
  readonly promise: Promise<DomainResult<T>>;
  private resolver: ((result: DomainResult<T>) => void) | null = null;

  constructor() {
    this.promise = new Promise<DomainResult<T>>((resolve: (result: DomainResult<T>) => void) => {
      this.resolver = resolve;
    });
  }

  resolve(result: DomainResult<T>): void {
    if (this.resolver === null) {
      throw new Error('Deferred result has no resolver');
    }
    this.resolver(result);
  }
}

function managedRoom(roomId: string, name: string): ManagedRoomDetails {
  return {
    roomId: roomId,
    name: name,
    topic: null,
    avatarUrl: null,
    canonicalAlias: null,
    visibility: RoomVisibility.Private,
    joinRule: RoomJoinRule.Invite,
    membership: RoomMembershipState.Joined,
    isEncrypted: true,
    memberCount: 2
  };
}

function payload(room: ManagedRoomDetails | null = null): RoomManagementPayload {
  return { room: room, members: [], acknowledged: true };
}

class RecordingRoomSource implements RoomManagementDataSource {
  readonly commands: RoomManagementCommand[] = [];
  nextFailure: DomainFailure | null = null;

  async execute(command: RoomManagementCommand): Promise<DomainResult<RoomManagementPayload>> {
    this.commands.push(command);
    if (this.nextFailure !== null) {
      const failure = this.nextFailure;
      this.nextFailure = null;
      return DomainResult.fail<RoomManagementPayload>(failure);
    }
    const roomId = command.roomId === null ?
      (command.aliasOrId === null ? '!created:example.org' : command.aliasOrId) : command.roomId;
    return DomainResult.succeed<RoomManagementPayload>(payload(managedRoom(roomId, command.kind)));
  }
}

class DeferredRoomSource implements RoomManagementDataSource {
  readonly requests: DeferredResult<RoomManagementPayload>[] = [];

  execute(command: RoomManagementCommand): Promise<DomainResult<RoomManagementPayload>> {
    const deferred = new DeferredResult<RoomManagementPayload>();
    this.requests.push(deferred);
    return deferred.promise;
  }
}

class RecordingSearchSource implements SearchDataSource {
  readonly requests: SearchRequest[] = [];
  pages: DomainResult<SearchPage>[] = [];

  async search(request: SearchRequest): Promise<DomainResult<SearchPage>> {
    this.requests.push(request);
    if (this.pages.length === 0) {
      return DomainResult.succeed<SearchPage>({ rooms: [], users: [], messages: [], nextOffset: null });
    }
    return this.pages.shift() as DomainResult<SearchPage>;
  }
}

class DeferredSearchSource implements SearchDataSource {
  readonly requests: DeferredResult<SearchPage>[] = [];

  search(request: SearchRequest): Promise<DomainResult<SearchPage>> {
    const deferred = new DeferredResult<SearchPage>();
    this.requests.push(deferred);
    return deferred.promise;
  }
}

class RecordingSpacesSource implements SpacesDataSource {
  loadResults: DomainResult<SpacePage>[] = [];
  switchResults: DomainResult<boolean>[] = [];
  readonly switched: (string | null)[] = [];

  async loadSpaces(): Promise<DomainResult<SpacePage>> {
    return this.loadResults.shift() as DomainResult<SpacePage>;
  }

  async switchSpace(spaceId: string | null): Promise<DomainResult<boolean>> {
    this.switched.push(spaceId);
    return this.switchResults.shift() as DomainResult<boolean>;
  }
}

class DeferredSpacesSource implements SpacesDataSource {
  readonly switchResult: DeferredResult<boolean> = new DeferredResult<boolean>();

  async loadSpaces(): Promise<DomainResult<SpacePage>> {
    return DomainResult.succeed<SpacePage>({
      spaces: [{ roomId: '!space:example.org', name: 'Space', avatarUrl: null, childCount: 2, isJoined: true }],
      activeSpaceId: null
    });
  }

  switchSpace(spaceId: string | null): Promise<DomainResult<boolean>> {
    return this.switchResult.promise;
  }
}

class DeferredLoadSpacesSource implements SpacesDataSource {
  readonly loads: DeferredResult<SpacePage>[] = [];

  loadSpaces(): Promise<DomainResult<SpacePage>> {
    const deferred = new DeferredResult<SpacePage>();
    this.loads.push(deferred);
    return deferred.promise;
  }

  async switchSpace(spaceId: string | null): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(true);
  }
}

class MemberRoomSource implements RoomManagementDataSource {
  async execute(command: RoomManagementCommand): Promise<DomainResult<RoomManagementPayload>> {
    return DomainResult.succeed<RoomManagementPayload>({
      room: command.kind === RoomManagementCommandKind.LoadDetails ?
        managedRoom('!room:example.org', 'Room') : null,
      members: command.kind === RoomManagementCommandKind.LoadMembers ? [{
        userId: '@zeta:example.org', displayName: 'Zeta', avatarUrl: null,
        membership: RoomMembershipState.Joined, role: RoomMemberRole.Member, isCurrentUser: false
      }, {
        userId: '@me:example.org', displayName: 'Me', avatarUrl: null,
        membership: RoomMembershipState.Joined, role: RoomMemberRole.Owner, isCurrentUser: true
      }] : [],
      acknowledged: true
    });
  }
}

function createRequest(): CreateRoomRequest {
  return {
    name: 'Project',
    topic: 'Planning',
    avatarUrl: null,
    visibility: RoomVisibility.Private,
    joinRule: RoomJoinRule.Invite,
    inviteUserIds: ['@alice:example.org'],
    parentSpaceId: null,
    isEncrypted: true
  };
}

async function testAllRoomCommandsReachProductionBoundary(): Promise<void> {
  const source = new RecordingRoomSource();
  const controller = new RoomManagementController(source);
  check((await controller.createRoom(createRequest())).success, 'create room should succeed');
  check((await controller.join('#room:example.org')).success, 'join should succeed');
  check((await controller.knock('#knock:example.org', 'request access')).success, 'knock should succeed');
  check((await controller.leave('!room:example.org')).success, 'leave should succeed');
  check((await controller.forget('!room:example.org')).success, 'forget should succeed');
  check((await controller.invite('!room:example.org', '@alice:example.org')).success, 'invite should succeed');
  check((await controller.updateDetails('!room:example.org', {
    name: 'Renamed', topic: 'Topic', avatarUrl: 'mxc://example/avatar', removeAvatar: false,
    visibility: null, joinRule: null
  })).success, 'details update should succeed');
  check((await controller.setRole('!room:example.org', '@alice:example.org', RoomMemberRole.Moderator)).success,
    'role update should succeed');
  check((await controller.kick('!room:example.org', '@alice:example.org', 'reason')).success,
    'kick should succeed');
  check((await controller.ban('!room:example.org', '@alice:example.org', 'reason')).success,
    'ban should succeed');
  check((await controller.unban('!room:example.org', '@alice:example.org')).success,
    'unban should succeed');
  check((await controller.report('!room:example.org', 'abuse', -80)).success, 'report should succeed');
  const expected: RoomManagementCommandKind[] = [
    RoomManagementCommandKind.CreateRoom,
    RoomManagementCommandKind.JoinRoom,
    RoomManagementCommandKind.KnockRoom,
    RoomManagementCommandKind.LeaveRoom,
    RoomManagementCommandKind.ForgetRoom,
    RoomManagementCommandKind.InviteUser,
    RoomManagementCommandKind.UpdateDetails,
    RoomManagementCommandKind.SetMemberRole,
    RoomManagementCommandKind.KickMember,
    RoomManagementCommandKind.BanMember,
    RoomManagementCommandKind.UnbanMember,
    RoomManagementCommandKind.ReportRoom
  ];
  check(source.commands.length === expected.length, 'every room command must reach the datasource');
  expected.forEach((kind: RoomManagementCommandKind, index: number) => {
    check(source.commands[index].kind === kind, `command ${index} must keep its kind`);
  });
}

async function testRoomDetailsAndMemberRolesLoad(): Promise<void> {
  const controller = new RoomManagementController(new MemberRoomSource());
  check((await controller.loadDetails('!room:example.org')).success, 'room details should load');
  check(controller.getSnapshot().room?.name === 'Room', 'room details should retain the server name');
  check((await controller.loadMembers('!room:example.org')).success, 'room members should load');
  check(controller.getSnapshot().members.length === 2, 'member list should retain server members');
  check(controller.getSnapshot().members[0].isCurrentUser, 'current member should sort first');
  check(controller.getSnapshot().members[0].role === RoomMemberRole.Owner, 'member role should remain typed');
}

async function testRoomStaleBusyFailureAndRetry(): Promise<void> {
  const deferred = new DeferredRoomSource();
  const controller = new RoomManagementController(deferred);
  const first = controller.loadDetails('!room:example.org');
  const second = controller.loadDetails('!room:example.org');
  deferred.requests[1].resolve(DomainResult.succeed<RoomManagementPayload>(
    payload(managedRoom('!room:example.org', 'new'))
  ));
  check((await second).success, 'latest details request should succeed');
  deferred.requests[0].resolve(DomainResult.succeed<RoomManagementPayload>(
    payload(managedRoom('!room:example.org', 'old'))
  ));
  check(!(await first).success, 'stale details request should be cancelled');
  check(controller.getSnapshot().room?.name === 'new', 'stale details must not overwrite current room');

  const busySource = new DeferredRoomSource();
  const busyController = new RoomManagementController(busySource);
  const invite = busyController.invite('!room:example.org', '@alice:example.org');
  const competing = await busyController.kick('!room:example.org', '@alice:example.org', null);
  check(!competing.success && competing.error?.code === DomainErrorCode.ServiceUnavailable,
    'same member scope must reject a concurrent mutation');
  busySource.requests[0].resolve(DomainResult.succeed<RoomManagementPayload>(payload()));
  check((await invite).success, 'original member mutation should still complete');

  const retrySource = new RecordingRoomSource();
  retrySource.nextFailure = new DomainFailure(DomainErrorCode.NetworkUnavailable, 'offline', true);
  const retryController = new RoomManagementController(retrySource);
  check(!(await retryController.join('#retry:example.org')).success, 'network failure should remain explicit');
  const operation = retryController.getSnapshot().operations[0];
  check(operation.retryable, 'failed network operation should be retryable');
  check((await retryController.retry(operation.requestId)).success, 'retry should reissue the failed command');
  check(retrySource.commands.length === 2, 'retry must cross the datasource boundary again');
}

async function testSearchDomainsPaginationAndRetry(): Promise<void> {
  const source = new RecordingSearchSource();
  source.pages = [
    DomainResult.succeed<SearchPage>({
      rooms: [{ roomId: '!room:example.org', name: 'Room', alias: null, topic: null, avatarUrl: null,
        memberCount: 3, membership: RoomMembershipState.Joined }],
      users: [], messages: [], nextOffset: 1
    }),
    DomainResult.succeed<SearchPage>({
      rooms: [{ roomId: '!second:example.org', name: 'Second', alias: null, topic: null, avatarUrl: null,
        memberCount: 2, membership: RoomMembershipState.Left }],
      users: [], messages: [], nextOffset: null
    }),
    DomainResult.fail<SearchPage>(new DomainFailure(DomainErrorCode.NetworkUnavailable, 'offline', true)),
    DomainResult.succeed<SearchPage>({
      rooms: [], users: [{ userId: '@alice:example.org', displayName: 'Alice', avatarUrl: null }],
      messages: [], nextOffset: null
    }),
    DomainResult.succeed<SearchPage>({
      rooms: [], users: [], messages: [{ eventId: '$event', roomId: '!room:example.org',
        senderId: '@alice:example.org', body: 'needle', timestampMs: 10 }], nextOffset: null
    })
  ];
  const controller = new SearchController(source, 1);
  check((await controller.search('room', SearchDomain.Rooms)).success, 'room search should succeed');
  check((await controller.loadMore()).success, 'room pagination should succeed');
  check(controller.getSnapshot().rooms.length === 2, 'pagination should append unique rooms');
  check(!(await controller.search('alice', SearchDomain.Users)).success, 'user search failure should propagate');
  check((await controller.retry()).success, 'failed user search should retry');
  check(controller.getSnapshot().users.length === 1, 'user search result should remain typed');
  check((await controller.search('needle', SearchDomain.Messages, '!room:example.org')).success,
    'message search should require and retain its room scope');
  check(controller.getSnapshot().messages[0].eventId === '$event', 'message search result should be retained');
}

async function testSearchRejectsStaleResults(): Promise<void> {
  const source = new DeferredSearchSource();
  const controller = new SearchController(source);
  const first = controller.search('old', SearchDomain.Rooms);
  const second = controller.search('new', SearchDomain.Rooms);
  source.requests[1].resolve(DomainResult.succeed<SearchPage>({
    rooms: [{ roomId: '!new:example.org', name: 'New', alias: null, topic: null, avatarUrl: null,
      memberCount: 1, membership: RoomMembershipState.Joined }],
    users: [], messages: [], nextOffset: null
  }));
  check((await second).success, 'new search should finish');
  source.requests[0].resolve(DomainResult.succeed<SearchPage>({
    rooms: [{ roomId: '!old:example.org', name: 'Old', alias: null, topic: null, avatarUrl: null,
      memberCount: 1, membership: RoomMembershipState.Joined }],
    users: [], messages: [], nextOffset: null
  }));
  const stale = await first;
  check(!stale.success && stale.error?.code === DomainErrorCode.Cancelled, 'old search should be cancelled');
  check(controller.getSnapshot().rooms[0].roomId === '!new:example.org', 'old search must not replace new results');
}

async function testSpacesListSwitchBusyAndRetry(): Promise<void> {
  const source = new RecordingSpacesSource();
  source.loadResults = [DomainResult.succeed<SpacePage>({
    spaces: [
      { roomId: '!z:example.org', name: 'Zeta', avatarUrl: null, childCount: 2, isJoined: true },
      { roomId: '!a:example.org', name: 'Alpha', avatarUrl: null, childCount: 1, isJoined: true }
    ],
    activeSpaceId: null
  })];
  source.switchResults = [
    DomainResult.fail<boolean>(new DomainFailure(DomainErrorCode.NetworkUnavailable, 'offline', true)),
    DomainResult.succeed<boolean>(true)
  ];
  const controller = new SpacesController(source);
  check((await controller.load()).success, 'spaces should load');
  check(controller.getSnapshot().spaces[0].name === 'Alpha', 'spaces should sort deterministically');
  check(!(await controller.switchSpace('!a:example.org')).success, 'switch failure should propagate');
  check(controller.getSnapshot().phase === SpacesPhase.Offline, 'network switch failure should be offline');
  check((await controller.retry()).success, 'failed space switch should retry');
  check(controller.getSnapshot().activeSpaceId === '!a:example.org', 'successful retry should select the space');

  const deferred = new DeferredSpacesSource();
  const busyController = new SpacesController(deferred);
  await busyController.load();
  const switching = busyController.switchSpace('!space:example.org');
  const busy = await busyController.switchSpace(null);
  check(!busy.success && busy.error?.code === DomainErrorCode.ServiceUnavailable,
    'concurrent space switch should expose busy failure');
  deferred.switchResult.resolve(DomainResult.succeed<boolean>(true));
  check((await switching).success, 'original space switch should complete');

  const crossSource = new DeferredSpacesSource();
  const crossController = new SpacesController(crossSource);
  await crossController.load();
  const staleSwitch = crossController.switchSpace('!space:example.org');
  await crossController.load();
  crossSource.switchResult.resolve(DomainResult.succeed<boolean>(true));
  const staleSwitchResult = await staleSwitch;
  check(!staleSwitchResult.success && staleSwitchResult.error?.code === DomainErrorCode.Cancelled,
    'a newer list load should cancel an obsolete space switch callback');

  const staleSource = new DeferredLoadSpacesSource();
  const staleController = new SpacesController(staleSource);
  const oldLoad = staleController.load();
  const newLoad = staleController.load();
  staleSource.loads[1].resolve(DomainResult.succeed<SpacePage>({
    spaces: [{ roomId: '!new:example.org', name: 'New', avatarUrl: null, childCount: 1, isJoined: true }],
    activeSpaceId: '!new:example.org'
  }));
  check((await newLoad).success, 'new space load should finish');
  staleSource.loads[0].resolve(DomainResult.succeed<SpacePage>({
    spaces: [{ roomId: '!old:example.org', name: 'Old', avatarUrl: null, childCount: 1, isJoined: true }],
    activeSpaceId: '!old:example.org'
  }));
  const oldResult = await oldLoad;
  check(!oldResult.success && oldResult.error?.code === DomainErrorCode.Cancelled,
    'stale space load should be cancelled');
  check(staleController.getSnapshot().activeSpaceId === '!new:example.org',
    'stale space load must not replace the current selection');
}

export async function runRoomManagementDomainTests(): Promise<string[]> {
  const passed: string[] = [];
  await testAllRoomCommandsReachProductionBoundary();
  passed.push('room lifecycle, details, membership, moderation and report commands');
  await testRoomDetailsAndMemberRolesLoad();
  passed.push('room details, member list and roles');
  await testRoomStaleBusyFailureAndRetry();
  passed.push('room stale callbacks, busy scopes and retry');
  await testSearchDomainsPaginationAndRetry();
  passed.push('room, user and message search with pagination and retry');
  await testSearchRejectsStaleResults();
  passed.push('search stale callback isolation');
  await testSpacesListSwitchBusyAndRetry();
  passed.push('space list, switching, busy and retry');
  return passed;
}
