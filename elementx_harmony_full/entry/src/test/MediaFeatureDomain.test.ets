import { DomainErrorCode, DomainFailure, DomainResult } from '../main/ets/core/DomainResult';
import { ActiveCallController } from '../main/ets/features/call/ActiveCallController';
import { LiveLocationController } from '../main/ets/features/location/LiveLocationController';
import { UserStatusController } from '../main/ets/features/userstatus/UserStatusController';
import { MediaGalleryController } from '../main/ets/media/MediaGalleryController';
import { MediaRepositoryController } from '../main/ets/media/MediaRepositoryController';
import {
  CallActionState,
  CallParticipant,
  RoomCallInput,
  RoomCallPhase
} from '../main/ets/matrix/api/CallModels';
import { RoomCallDataSource } from '../main/ets/matrix/api/CallService';
import {
  GeoPoint,
  LiveLocationBootstrap,
  LiveLocationNotificationRoute,
  LiveLocationPhase,
  LiveLocationShare,
  LiveLocationState,
  LocationPermissionState
} from '../main/ets/matrix/api/LocationModels';
import {
  LiveLocationDataSource,
  LiveLocationNotificationRouter
} from '../main/ets/matrix/api/LocationService';
import {
  CachedMedia,
  GalleryMode,
  GalleryPage,
  GalleryPhase,
  MediaItem,
  MediaKind,
  MediaTransferState,
  UploadedMedia
} from '../main/ets/matrix/api/MediaModels';
import {
  DownloadRequest,
  MediaGalleryDataSource,
  MediaProgressObserver,
  MediaRepositoryDataSource,
  ThumbnailRequest,
  UploadRequest
} from '../main/ets/matrix/api/MediaRepository';
import {
  DisplayedStatus,
  DisplayedStatusKind,
  ProfileMutationKind,
  ProfilePhase,
  UserProfile,
  UserStatus
} from '../main/ets/matrix/api/ProfileModels';
import { ProfileEdit, UserProfileDataSource } from '../main/ets/matrix/api/ProfileService';

function check(condition: boolean, message: string): void {
  if (!condition) {
    throw new Error(message);
  }
}

function media(
  mediaId: string,
  kind: MediaKind,
  timestampMs: number,
  redacted: boolean = false,
  shareAllowed: boolean = true
): MediaItem {
  return {
    mediaId: mediaId,
    eventId: `$${mediaId}`,
    roomId: '!room:example.org',
    senderId: '@member:example.org',
    timestampMs: timestampMs,
    kind: kind,
    fileName: `${mediaId}.bin`,
    mimeType: kind === MediaKind.Image ? 'image/jpeg' : 'application/octet-stream',
    sizeBytes: 100,
    width: kind === MediaKind.Image ? 100 : null,
    height: kind === MediaKind.Image ? 100 : null,
    durationMs: null,
    source: {
      contentUri: `mxc://example.org/${mediaId}`,
      thumbnailUri: null,
      encrypted: {
        algorithm: 'm.megolm.v1.aes-sha2',
        metadataReference: `secure-metadata-${mediaId}`,
        sha256: `sha-${mediaId}`,
        version: 'v2'
      }
    },
    caption: null,
    redacted: redacted,
    shareAllowed: shareAllowed
  };
}

class MediaSource implements MediaRepositoryDataSource {
  failDownload: boolean = false;
  cancelled: string[] = [];
  evicted: string[] = [];

  async loadThumbnail(request: ThumbnailRequest, observer: MediaProgressObserver): Promise<DomainResult<CachedMedia>> {
    observer.onProgress({ operationId: request.operationId, transferredBytes: 20, totalBytes: 100 });
    return DomainResult.succeed<CachedMedia>({
      cacheEntryId: `thumbnail-${request.media.mediaId}`,
      validatedMimeType: 'image/jpeg',
      sizeBytes: 100
    });
  }

  async download(request: DownloadRequest, observer: MediaProgressObserver): Promise<DomainResult<CachedMedia>> {
    observer.onProgress({ operationId: request.operationId, transferredBytes: 50, totalBytes: 100 });
    if (this.failDownload) {
      return DomainResult.fail<CachedMedia>(new DomainFailure(
        DomainErrorCode.NetworkUnavailable,
        'offline',
        true
      ));
    }
    return DomainResult.succeed<CachedMedia>({
      cacheEntryId: `cache-${request.media.mediaId}`,
      validatedMimeType: request.media.mimeType,
      sizeBytes: 100
    });
  }

  async upload(request: UploadRequest, observer: MediaProgressObserver): Promise<DomainResult<UploadedMedia>> {
    observer.onProgress({ operationId: request.operationId, transferredBytes: 100, totalBytes: 100 });
    return DomainResult.succeed<UploadedMedia>({
      contentUri: `mxc://example.org/${request.operationId}`,
      encryptedMetadataReference: request.encrypt ? 'secure-upload-metadata' : null
    });
  }

  async cancel(operationId: string): Promise<DomainResult<boolean>> {
    this.cancelled.push(operationId);
    return DomainResult.succeed<boolean>(true);
  }

  async evict(cacheEntryId: string): Promise<DomainResult<boolean>> {
    this.evicted.push(cacheEntryId);
    return DomainResult.succeed<boolean>(true);
  }
}

class DeferredMediaSource extends MediaSource {
  resolvers: Array<(result: DomainResult<CachedMedia>) => void> = [];

  async download(request: DownloadRequest, observer: MediaProgressObserver): Promise<DomainResult<CachedMedia>> {
    observer.onProgress({ operationId: request.operationId, transferredBytes: 10, totalBytes: 100 });
    return new Promise<DomainResult<CachedMedia>>((resolve: (result: DomainResult<CachedMedia>) => void) => {
      this.resolvers.push(resolve);
    });
  }

  complete(index: number, cacheEntryId: string): void {
    this.resolvers[index](DomainResult.succeed<CachedMedia>({
      cacheEntryId: cacheEntryId,
      validatedMimeType: 'image/jpeg',
      sizeBytes: 100
    }));
  }
}

class GallerySource implements MediaGalleryDataSource {
  items: MediaItem[] = [];
  failure: DomainFailure | null = null;

  async load(roomId: string): Promise<DomainResult<GalleryPage>> {
    if (this.failure !== null) {
      return DomainResult.fail<GalleryPage>(this.failure);
    }
    return DomainResult.succeed<GalleryPage>({ items: this.items.slice(), hasMore: false });
  }

  async loadMore(roomId: string): Promise<DomainResult<GalleryPage>> {
    return DomainResult.succeed<GalleryPage>({ items: [], hasMore: false });
  }
}

function point(timestampMs: number): GeoPoint {
  return {
    latitude: 51.5,
    longitude: -0.12,
    accuracyMeters: 8,
    timestampMs: timestampMs
  };
}

class LocationSource implements LiveLocationDataSource {
  permission: LocationPermissionState = LocationPermissionState.Denied;
  disclaimerAccepted: boolean = false;
  shares: LiveLocationShare[] = [];
  nextId: number = 1;

  async load(): Promise<DomainResult<LiveLocationBootstrap>> {
    return DomainResult.succeed<LiveLocationBootstrap>({
      permission: this.permission,
      disclaimerAccepted: this.disclaimerAccepted,
      locationServiceAvailable: true,
      shares: this.shares.slice()
    });
  }

  async requestPermission(): Promise<DomainResult<LocationPermissionState>> {
    this.permission = LocationPermissionState.Granted;
    return DomainResult.succeed<LocationPermissionState>(this.permission);
  }

  async persistDisclaimerAccepted(): Promise<DomainResult<boolean>> {
    this.disclaimerAccepted = true;
    return DomainResult.succeed<boolean>(true);
  }

  async start(roomId: string, durationMs: number, location: GeoPoint): Promise<DomainResult<LiveLocationShare>> {
    const share: LiveLocationShare = {
      sessionId: `location-${this.nextId++}`,
      roomId: roomId,
      userId: '@me:example.org',
      description: null,
      lastPoint: location,
      startedAtMs: location.timestampMs,
      expiresAtMs: location.timestampMs + durationMs,
      state: LiveLocationState.Live,
      error: null
    };
    this.shares.push(share);
    return DomainResult.succeed<LiveLocationShare>(share);
  }

  async update(sessionId: string, location: GeoPoint): Promise<DomainResult<LiveLocationShare>> {
    const share = this.shares.find((candidate: LiveLocationShare) => candidate.sessionId === sessionId);
    if (share === undefined) {
      return DomainResult.fail<LiveLocationShare>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'missing share',
        false
      ));
    }
    share.lastPoint = location;
    return DomainResult.succeed<LiveLocationShare>(share);
  }

  async stop(sessionId: string): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(sessionId.length > 0);
  }
}

class NotificationRouter implements LiveLocationNotificationRouter {
  shown: string[] = [];
  removed: string[] = [];
  routed: LiveLocationNotificationRoute[] = [];

  async showOrUpdate(share: LiveLocationShare): Promise<DomainResult<boolean>> {
    this.shown.push(share.sessionId);
    return DomainResult.succeed<boolean>(true);
  }

  async remove(sessionId: string): Promise<DomainResult<boolean>> {
    this.removed.push(sessionId);
    return DomainResult.succeed<boolean>(true);
  }

  resolve(route: LiveLocationNotificationRoute): DomainResult<boolean> {
    this.routed.push(route);
    return DomainResult.succeed<boolean>(true);
  }
}

class CallSource implements RoomCallDataSource {
  input: RoomCallInput;
  joinFailure: DomainFailure | null = null;

  constructor(input: RoomCallInput) {
    this.input = input;
  }

  async load(roomId: string): Promise<DomainResult<RoomCallInput>> {
    return DomainResult.succeed<RoomCallInput>(this.input);
  }

  async join(roomId: string, callId: string): Promise<DomainResult<boolean>> {
    if (this.joinFailure !== null) {
      return DomainResult.fail<boolean>(this.joinFailure);
    }
    return DomainResult.succeed<boolean>(roomId.length > 0 && callId.length > 0);
  }

  async decline(roomId: string, callId: string): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(roomId.length > 0 && callId.length > 0);
  }
}

function displayed(status: UserStatus | null): DisplayedStatus {
  return status === null ? {
    kind: DisplayedStatusKind.None,
    status: null,
    callJoinedAtSeconds: null
  } : {
    kind: DisplayedStatusKind.UserSet,
    status: status,
    callJoinedAtSeconds: null
  };
}

function profile(status: UserStatus | null = null): UserProfile {
  return {
    userId: '@me:example.org',
    displayName: 'Me',
    avatarUrl: null,
    rawStatus: status,
    displayedStatus: displayed(status)
  };
}

class ProfileSource implements UserProfileDataSource {
  current: UserProfile = profile();
  failNextStatus: boolean = false;
  lastAvatarHandle: string | null = null;

  async loadProfile(): Promise<DomainResult<UserProfile>> {
    return DomainResult.succeed<UserProfile>(this.current);
  }

  async editProfile(edit: ProfileEdit): Promise<DomainResult<UserProfile>> {
    this.lastAvatarHandle = edit.avatarSourceHandle;
    this.current.displayName = edit.displayName;
    this.current.avatarUrl = edit.removeAvatar ? null : this.current.avatarUrl;
    return DomainResult.succeed<UserProfile>(this.current);
  }

  async setUserStatus(status: UserStatus): Promise<DomainResult<UserProfile>> {
    if (this.failNextStatus) {
      this.failNextStatus = false;
      return DomainResult.fail<UserProfile>(new DomainFailure(
        DomainErrorCode.NetworkUnavailable,
        'offline',
        true
      ));
    }
    this.current.rawStatus = status;
    this.current.displayedStatus = displayed(status);
    return DomainResult.succeed<UserProfile>(this.current);
  }

  async clearUserStatus(): Promise<DomainResult<UserProfile>> {
    this.current.rawStatus = null;
    this.current.displayedStatus = displayed(null);
    return DomainResult.succeed<UserProfile>(this.current);
  }
}

async function testMediaTransferProgressRetryAndSecretIsolation(): Promise<void> {
  const source = new MediaSource();
  const controller = new MediaRepositoryController(source);
  const item = media('encrypted-image', MediaKind.Image, 10);
  source.failDownload = true;
  const failed = await controller.download({ operationId: 'download-1', media: item });
  check(!failed.success, 'offline media download must fail');
  check(controller.getOperation('download-1')?.state === MediaTransferState.Failed,
    'failed media operation must remain retryable');
  source.failDownload = false;
  check((await controller.retry('download-1')).success, 'media retry should succeed');
  check(controller.getOperation('download-1')?.progress === 1, 'completed download must expose full progress');
  check(controller.getOperation('download-1')?.cacheEntryId === 'cache-encrypted-image',
    'completed download must expose an opaque cache entry');

  const secretHandle = 'private-source-file-handle';
  const upload = await controller.upload({
    operationId: 'upload-1',
    roomId: '!room:example.org',
    sourceHandle: secretHandle,
    fileName: 'photo.jpg',
    mimeType: 'image/jpeg',
    encrypt: true
  });
  check(upload.success, 'encrypted media upload should succeed');
  check(upload.value?.encryptedMetadataReference === 'secure-upload-metadata',
    'upload should return only an opaque encrypted metadata reference');
  check(JSON.stringify(controller.getOperations()).indexOf(secretHandle) < 0,
    'protected source handles must never enter observable media state');

  const deferredSource = new DeferredMediaSource();
  const deferred = new MediaRepositoryController(deferredSource);
  const firstAttempt = deferred.download({ operationId: 'download-race', media: item });
  check((await deferred.cancel('download-race')).success, 'active download should cancel');
  const retryAttempt = deferred.retry('download-race');
  deferredSource.complete(0, 'stale-cache');
  const staleResult = await firstAttempt;
  check(!staleResult.success && staleResult.error?.code === DomainErrorCode.Cancelled,
    'completion from the cancelled attempt must be rejected');
  check(deferred.getOperation('download-race')?.state === MediaTransferState.Running,
    'stale completion must not replace the running retry');
  deferredSource.complete(1, 'fresh-cache');
  check((await retryAttempt).success, 'fresh retry completion should succeed');
  check(deferred.getOperation('download-race')?.cacheEntryId === 'fresh-cache',
    'retry must retain only the current attempt cache entry');
}

async function testGalleryAggregationValidationRedactionAndNavigation(): Promise<void> {
  const source = new GallerySource();
  const invalid = media('invalid', MediaKind.Image, 40);
  invalid.source.contentUri = '';
  source.items = [
    media('newest', MediaKind.Image, 30),
    media('redacted', MediaKind.Video, 20, true),
    invalid,
    media('file', MediaKind.File, 10, false, false)
  ];
  const controller = new MediaGalleryController('!room:example.org', source);
  check((await controller.start('newest')).success, 'gallery should aggregate valid timeline media');
  check(controller.getSnapshot().items.length === 2, 'redacted and invalid media must be omitted');
  check(controller.getSnapshot().omittedInvalidCount === 2, 'gallery must report omitted invalid media');
  check(controller.moveNext().success, 'viewer should move to the next media item');
  check(controller.getSnapshot().selectedMediaId === 'file', 'next must select the adjacent stable item');
  check(controller.shareSelection().length === 0, 'non-shareable selection must omit share action');
  check(controller.movePrevious().success, 'viewer should move to previous media');
  check(controller.shareSelection()[0] === 'newest', 'shareable media must produce its media ID only');
  controller.redact('$newest');
  check(controller.getSnapshot().selectedMediaId === 'file', 'redaction must repair viewer selection');
  controller.setMode(GalleryMode.Images);
  check(controller.getSnapshot().phase === GalleryPhase.Empty, 'filtered empty gallery must be explicit');
}

async function testLiveLocationGatesMultiRoomTimeoutAndStaleTimer(): Promise<void> {
  const source = new LocationSource();
  const notifications = new NotificationRouter();
  const controller = new LiveLocationController(source, notifications);
  check((await controller.start()).success, 'live location bootstrap should load');
  check(!(await controller.startShare(point(1000))).success, 'location cannot start before gates pass');
  check((await controller.requestPermission()).success, 'location permission should be requested explicitly');
  check((await controller.acceptDisclaimer()).success, 'location disclaimer acceptance should persist');
  check(controller.selectDuration('!one:example.org', 60 * 1000).success, 'first room duration should select');
  check((await controller.startShare(point(1000))).success, 'first room share should start');
  const firstId = controller.getSnapshot().shares[0].sessionId;
  check(controller.selectDuration('!two:example.org', 60 * 1000).success, 'second room duration should select');
  check((await controller.startShare(point(2000))).success, 'second room share should start independently');
  check(controller.getSnapshot().shares.length === 2, 'multiple rooms must retain independent shares');
  const secondId = controller.getSnapshot().shares[1].sessionId;
  check((await controller.updateShare(secondId, point(3000))).success,
    'active share should accept a real location update');
  check(controller.getSnapshot().shares[1].lastPoint?.timestampMs === 3000,
    'location update must replace only the matching share point');
  check(controller.routeNotification({ roomId: '!one:example.org', sessionId: firstId }).success,
    'notification route must resolve exact room and session');
  check((await controller.tick(firstId, 61000)).success, 'matching timer should stop expired share');
  check(controller.getSnapshot().shares[0].state === LiveLocationState.TimedOut,
    'expired share must enter explicit timed-out state');
  check(!(await controller.tick(firstId, 999999)).success, 'stale timer must not mutate completed share');
  check(controller.getSnapshot().shares[1].state === LiveLocationState.Live,
    'first room timeout must not stop another room');
  check((await controller.stopShare(secondId)).success, 'second room share should stop manually');
  check(controller.getSnapshot().shares[1].state === LiveLocationState.Stopped,
    'manual stop must remain distinct from timeout');
}

async function testCallStateParticipantAndActionGates(): Promise<void> {
  const participants: CallParticipant[] = [{
    sessionId: 'SESSION',
    userId: '@me:example.org',
    deviceId: 'DEVICE',
    displayName: 'Me',
    avatarUrl: null,
    joinedAtMs: 100
  }];
  const input: RoomCallInput = {
    roomId: '!room:example.org',
    callId: 'call-1',
    available: true,
    hasActiveCall: true,
    canCall: true,
    isDirectMessage: false,
    isAudioCall: false,
    currentSessionId: 'SESSION',
    localCallRoomId: null,
    participants: participants
  };
  const source = new CallSource(input);
  const controller = new ActiveCallController(input.roomId, source);
  check((await controller.start()).success, 'active call state should load');
  check(controller.getSnapshot().phase === RoomCallPhase.Ongoing, 'active timeline call must be ongoing');
  check(controller.getSnapshot().isUserInCall, 'session participant must be detected');
  check(!controller.getSnapshot().isUserLocallyInCall, 'remote participation differs from local call state');
  check((await controller.join()).success, 'allowed call should join');
  check(controller.getSnapshot().action === CallActionState.Joined, 'join success must be explicit');
  check(!(await controller.decline()).success, 'locally joined call cannot be declined');

  const blockedInput: RoomCallInput = {
    roomId: input.roomId,
    callId: 'call-2',
    available: true,
    hasActiveCall: true,
    canCall: false,
    isDirectMessage: true,
    isAudioCall: true,
    currentSessionId: 'SESSION',
    localCallRoomId: null,
    participants: []
  };
  check(controller.receive(blockedInput).success, 'new active call state should replace old call');
  check(!controller.getSnapshot().canJoinCall, 'permission gate must disable join action');
  check(!(await controller.join()).success, 'blocked join must not reach datasource');
  check((await controller.decline()).success, 'unjoined call can be declined');
  check(controller.getSnapshot().action === CallActionState.Declined, 'decline success must be explicit');
}

async function testProfileStatusPersistencePropagationAndRecovery(): Promise<void> {
  const source = new ProfileSource();
  const controller = new UserStatusController(source);
  check((await controller.start()).success, 'profile should load');
  controller.openCustomInput();
  check(controller.updateCustom('F', 'Focus time').success, 'custom status should edit in local UI state');
  source.failNextStatus = true;
  const desired: UserStatus = { emoji: 'F', text: 'Focus time' };
  check(!(await controller.setStatus(desired)).success, 'offline status write must fail');
  check(controller.getSnapshot().phase === ProfilePhase.Offline, 'offline status write must remain explicit');
  check(controller.getSnapshot().profile?.rawStatus === null, 'failed write must preserve stable profile');
  check(controller.getSnapshot().pendingMutation === ProfileMutationKind.SetStatus,
    'failed write must retain retry intent');
  check((await controller.retryLastMutation()).success, 'failed status write should retry');
  check(controller.getSnapshot().profile?.rawStatus?.text === 'Focus time', 'successful retry must persist status');
  check(controller.getSnapshot().timelinePresentation.text === 'Focus time',
    'user status must propagate to timeline presentation');
  check(controller.receiveActiveCall(true, 123).success, 'active call status should override displayed status');
  check(controller.getSnapshot().timelinePresentation.kind === DisplayedStatusKind.InCall,
    'timeline must display automatic in-call status');
  check(controller.getSnapshot().activeCallPresentation.kind === DisplayedStatusKind.InCall,
    'active-call surface must receive the same status');
  check(controller.receiveActiveCall(false, null).success, 'leaving call should restore manual status');
  check(controller.getSnapshot().timelinePresentation.text === 'Focus time',
    'manual status must return after call ends');
  check((await controller.editProfile({
    displayName: 'Updated',
    avatarSourceHandle: 'private-avatar-handle',
    removeAvatar: false
  })).success, 'profile edit should persist through datasource');
  check(JSON.stringify(controller.getSnapshot()).indexOf('private-avatar-handle') < 0,
    'avatar source handle must not enter ordinary profile state');
  check((await controller.clearStatus()).success, 'status should clear');
  check(!controller.getSnapshot().timelinePresentation.visible, 'cleared status must leave timeline');
}

async function testExplicitOfflineStatesDoNotInventEntities(): Promise<void> {
  const gallerySource = new GallerySource();
  gallerySource.failure = new DomainFailure(DomainErrorCode.NetworkUnavailable, 'offline', true);
  const gallery = new MediaGalleryController('!room:example.org', gallerySource);
  check(!(await gallery.start()).success, 'offline gallery must fail');
  check(gallery.getSnapshot().phase === GalleryPhase.Offline, 'gallery must expose offline state');
  check(gallery.getSnapshot().items.length === 0, 'offline gallery must not invent media');

  const callInput: RoomCallInput = {
    roomId: '!room:example.org',
    callId: null,
    available: false,
    hasActiveCall: false,
    canCall: false,
    isDirectMessage: false,
    isAudioCall: false,
    currentSessionId: 'SESSION',
    localCallRoomId: null,
    participants: []
  };
  const call = new ActiveCallController(callInput.roomId, new CallSource(callInput));
  await call.start();
  check(call.getSnapshot().phase === RoomCallPhase.Unavailable, 'unavailable call service must be explicit');
  check(call.getSnapshot().participants.length === 0, 'unavailable call state must not invent participants');
}

export async function runMediaFeatureDomainTests(): Promise<string[]> {
  const passed: string[] = [];
  await testMediaTransferProgressRetryAndSecretIsolation();
  passed.push('media progress, retry, encrypted metadata isolation');
  await testGalleryAggregationValidationRedactionAndNavigation();
  passed.push('gallery validation, navigation, redaction, share omission');
  await testLiveLocationGatesMultiRoomTimeoutAndStaleTimer();
  passed.push('live location gates, multi-room timeout, stale timer');
  await testCallStateParticipantAndActionGates();
  passed.push('call timeline state, participant state, action gates');
  await testProfileStatusPersistencePropagationAndRecovery();
  passed.push('profile status persistence, propagation, failure recovery');
  await testExplicitOfflineStatesDoNotInventEntities();
  passed.push('explicit offline states without fixtures');
  return passed;
}
