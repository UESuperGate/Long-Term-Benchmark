import { RoomSummary, TimelineEvent } from '../model/ElementModels';
import { HomeserverCapabilitiesState, MatrixClientRuntime, SyncRuntimeState, TimelineMediaPreviewMode } from '../model/ClientRuntimeModels';
import {
  ContentScannerContract,
  ClientResult,
  CreateRoomParameters,
  EncryptionServiceContract,
  LinkNewDeviceHandlerState,
  MatrixClientContract,
  MatrixLiveEvent,
  MatrixLiveValue,
  MatrixMediaLoaderContract,
  MatrixSessionCoroutineScope,
  MatrixSessionPaths,
  MatrixSearchUserResults,
  MatrixUser,
  MediaPreviewServiceContract,
  MessageSearchServiceContract,
  NotificationServiceContract,
  NotificationSettingsServiceContract,
  PushersServiceContract,
  ResolvedRoomAlias,
  RoomDirectoryServiceContract,
  RoomInfo,
  RoomListServiceContract,
  RoomMembershipObserverContract,
  RoomMembershipUpdate,
  RoomPreview,
  SdkStoreSizes,
  SessionVerificationServiceContract,
  SpaceServiceContract,
  SyncServiceContract,
  failure,
  success,
  successVoid
} from './MatrixClientContract';

export class FixtureMatrixClientAdapter implements MatrixClientContract {
  sessionId: string;
  deviceId: string;
  sessionPaths: MatrixSessionPaths = {
    basePath: '',
    cachePath: '',
    mediaPath: '',
    cryptoStorePath: ''
  };
  private userId: string;
  private homeserver: string;
  private accessToken: string;
  private nextSyncBatch: string;
  userProfile: MatrixLiveValue<MatrixUser> = {
    current: {
      userId: '',
      displayName: '',
      avatarUrl: '',
      status: ''
    },
    version: 0
  };
  roomListService: RoomListServiceContract;
  spaceService: SpaceServiceContract;
  syncService: SyncServiceContract;
  sessionVerificationService: SessionVerificationServiceContract;
  pushersService: PushersServiceContract;
  notificationService: NotificationServiceContract;
  notificationSettingsService: NotificationSettingsServiceContract;
  encryptionService: EncryptionServiceContract;
  roomDirectoryService: RoomDirectoryServiceContract;
  private rooms: RoomSummary[];
  private timeline: TimelineEvent[];
  private ignoredUsers: string[] = [];
  ignoredUsersFlow: MatrixLiveValue<string[]> = { current: [], version: 0 };
  isMessageSearchAvailable: boolean = true;
  messageSearchService: MessageSearchServiceContract;
  mediaPreviewService: MediaPreviewServiceContract;
  matrixMediaLoader: MatrixMediaLoaderContract;
  sessionCoroutineScope: MatrixSessionCoroutineScope = { isActive: true };
  roomMembershipObserver: RoomMembershipObserverContract;
  ownBeaconInfoUpdates: MatrixLiveEvent<string> = { latest: '', sequence: 0 };
  contentScanner: ContentScannerContract | null;
  isShuttingDown: boolean = false;

  private readonly capabilities: HomeserverCapabilitiesState;
  private readonly recentRooms: string[] = [];
  private readonly recentEmojis: string[] = [':thumbsup:', ':heart:', ':eyes:'];
  private readonly accountData: string[] = [];
  private automaticCallStatusEnabled: boolean = true;
  private displayName: string;
  private avatarUrl: string = '';
  private userStatus: string = 'Away';
  private sendPublicReadReceipts: boolean = true;
  private renderReadReceipts: boolean = true;
  private timelineMediaPreviewMode: TimelineMediaPreviewMode = TimelineMediaPreviewMode.AlwaysShow;
  private sendQueuesEnabled: boolean = true;
  private sendQueueDisabledSequence: number = 0;
  private syncRuntimeState: SyncRuntimeState;

  constructor(
    runtime: MatrixClientRuntime,
    rooms: RoomSummary[],
    timeline: TimelineEvent[]
  ) {
    this.sessionId = runtime.sessionId;
    this.deviceId = runtime.deviceId;
    this.sessionPaths = {
      basePath: `session://${runtime.sessionId}`,
      cachePath: `session://${runtime.sessionId}/cache`,
      mediaPath: `session://${runtime.sessionId}/media`,
      cryptoStorePath: `session://${runtime.sessionId}/crypto`
    };
    this.userId = runtime.userId;
    this.homeserver = runtime.homeserver;
    this.accessToken = runtime.accessToken;
    this.nextSyncBatch = runtime.nextSyncBatch;
    this.ignoredUsers = runtime.ignoredUsers.slice();
    this.syncRuntimeState = runtime.syncService;
    this.capabilities = runtime.homeserverCapabilities;
    this.rooms = rooms;
    this.timeline = timeline;
    this.roomMembershipObserver = this.createRoomMembershipObserver();
    this.displayName = runtime.displayName.length > 0 ? runtime.displayName : this.displayNameFromUserId(runtime.userId);
    this.avatarUrl = runtime.avatarUrl;
    this.userStatus = runtime.userStatus;
    this.userProfile = {
      current: {
        userId: this.userId,
        displayName: this.displayName,
        avatarUrl: this.avatarUrl,
        status: this.userStatus
      },
      version: 1
    };
    this.ignoredUsersFlow = {
      current: this.ignoredUsers.slice(),
      version: 1
    };
    this.sendPublicReadReceipts = runtime.sendPublicReadReceipts;
    this.renderReadReceipts = runtime.renderReadReceipts;
    this.timelineMediaPreviewMode = runtime.timelineMediaPreviewMode;
    this.roomListService = this.createRoomListService();
    this.spaceService = this.createSpaceService();
    this.syncService = this.createSyncService();
    this.sessionVerificationService = this.createSessionVerificationService();
    this.pushersService = this.createPushersService();
    this.notificationService = this.createNotificationService();
    this.notificationSettingsService = this.createNotificationSettingsService();
    this.encryptionService = this.createEncryptionService();
    this.roomDirectoryService = this.createRoomDirectoryService();
    this.messageSearchService = this.createMessageSearchService();
    this.mediaPreviewService = this.createMediaPreviewService();
    this.matrixMediaLoader = this.createMatrixMediaLoader();
    this.contentScanner = this.createContentScanner();
  }

  getJoinedRoom(roomId: string): RoomInfo | null {
    const room = this.rooms.find((item: RoomSummary) => item.id === roomId);
    if (room === undefined) {
      return null;
    }
    return this.toRoomInfo(room, 'join');
  }

  getRoom(roomId: string): RoomInfo | null {
    return this.getJoinedRoom(roomId);
  }

  findDM(userId: string): ClientResult<string> {
    const room = this.rooms.find((item: RoomSummary) => item.isDirect && item.name.toLowerCase() === this.displayNameFromUserId(userId).toLowerCase());
    if (room === undefined) {
      return failure('No direct message room found');
    }
    return success(room.id);
  }

  getJoinedRoomIds(): ClientResult<string[]> {
    return success(this.rooms.map((item: RoomSummary) => item.id));
  }

  ignoreUser(userId: string): ClientResult<void> {
    if (!this.ignoredUsers.includes(userId)) {
      this.ignoredUsers.push(userId);
    }
    this.refreshIgnoredUsersFlow();
    return successVoid();
  }

  unignoreUser(userId: string): ClientResult<void> {
    const index = this.ignoredUsers.indexOf(userId);
    if (index >= 0) {
      this.ignoredUsers.splice(index, 1);
    }
    this.refreshIgnoredUsersFlow();
    return successVoid();
  }

  createRoom(createRoomParams: CreateRoomParameters): ClientResult<string> {
    const roomId = `!${createRoomParams.name.toLowerCase().replace(' ', '-')}:${this.homeserver}`;
    this.rooms.push({
      id: roomId,
      name: createRoomParams.name,
      topic: createRoomParams.topic,
      unreadCount: 0,
      isMarkedUnread: false,
      isFavorite: false,
      isDirect: false
    });
    this.roomMembershipObserver.updates = {
      latest: {
        roomId: roomId,
        isSpace: false,
        isUserInRoom: true,
        change: 'joined'
      },
      sequence: this.roomMembershipObserver.updates.sequence + 1
    };
    return success(roomId);
  }

  createDM(userId: string, isEncrypted: boolean): ClientResult<string> {
    const roomId = `!dm-${this.displayNameFromUserId(userId).toLowerCase()}:${this.homeserver}`;
    this.rooms.push({
      id: roomId,
      name: this.displayNameFromUserId(userId),
      topic: isEncrypted ? 'Direct message - encrypted' : 'Direct message',
      unreadCount: 0,
      isMarkedUnread: false,
      isFavorite: false,
      isDirect: true
    });
    this.roomMembershipObserver.updates = {
      latest: {
        roomId: roomId,
        isSpace: false,
        isUserInRoom: true,
        change: 'joined'
      },
      sequence: this.roomMembershipObserver.updates.sequence + 1
    };
    return success(roomId);
  }

  getProfile(userId: string): ClientResult<MatrixUser> {
    return success(this.toMatrixUser(userId));
  }

  searchUsers(searchTerm: string, limit: number): ClientResult<MatrixSearchUserResults> {
    const candidates: MatrixUser[] = [
      this.toMatrixUser('@alice:matrix.org'),
      this.toMatrixUser('@bob:matrix.org'),
      this.toMatrixUser('@dana:matrix.org')
    ];
    const normalized = searchTerm.toLowerCase();
    const results: MatrixSearchUserResults = {
      results: candidates.filter((item: MatrixUser) => item.userId.indexOf(normalized) >= 0 || item.displayName.toLowerCase().indexOf(normalized) >= 0).slice(0, limit),
      limited: candidates.length > limit
    };
    return success(results);
  }

  setDisplayName(displayName: string): ClientResult<void> {
    this.displayName = displayName;
    this.refreshUserProfile();
    return successVoid();
  }

  uploadAvatar(mimeType: string, data: ArrayBuffer): ClientResult<void> {
    this.avatarUrl = `mxc://${this.homeserver}/avatar-${mimeType.replace('/', '-')}-${data.byteLength}`;
    this.refreshUserProfile();
    return successVoid();
  }

  removeAvatar(): ClientResult<void> {
    this.avatarUrl = '';
    this.refreshUserProfile();
    return successVoid();
  }

  setUserStatus(status: string): ClientResult<void> {
    this.userStatus = status;
    this.refreshUserProfile();
    return successVoid();
  }

  clearUserStatus(): ClientResult<void> {
    this.userStatus = '';
    this.refreshUserProfile();
    return successVoid();
  }

  isUserStatusSupported(): ClientResult<boolean> {
    return success(true);
  }

  isProfilesSlidingSyncExtensionSupported(): ClientResult<boolean> {
    return success(true);
  }

  enableAutomaticCallStatus(enabled: boolean): void {
    this.automaticCallStatusEnabled = enabled;
  }

  joinRoom(roomId: string): ClientResult<RoomInfo> {
    const room = this.getJoinedRoom(roomId);
    if (room === null) {
      return failure('Room is unknown');
    }
    return success(room);
  }

  joinRoomByIdOrAlias(roomIdOrAlias: string, serverNames: string[]): ClientResult<RoomInfo> {
    const fallbackRoom: RoomInfo = {
      roomId: roomIdOrAlias,
      name: serverNames.length > 0 ? serverNames[0] : roomIdOrAlias,
      membership: 'join',
      isEncrypted: true
    };
    const room = this.getJoinedRoom(roomIdOrAlias) ?? fallbackRoom;
    return success(room);
  }

  knockRoom(roomIdOrAlias: string, message: string, serverNames: string[]): ClientResult<RoomInfo> {
    const name = message.length > 0 ? message : (serverNames.length > 0 ? serverNames[0] : roomIdOrAlias);
    const room: RoomInfo = {
      roomId: roomIdOrAlias,
      name: name,
      membership: 'knock',
      isEncrypted: true
    };
    return success(room);
  }

  getCacheSize(): number {
    return 15728640;
  }

  getDatabaseSizes(): ClientResult<SdkStoreSizes> {
    const sizes: SdkStoreSizes = {
      stateStoreBytes: 5242880,
      cryptoStoreBytes: 3145728,
      eventCacheBytes: 4194304,
      mediaCacheBytes: 3145728
    };
    return success(sizes);
  }

  clearCache(): void {
    this.isShuttingDown = true;
  }

  logout(userInitiated: boolean, ignoreSdkError: boolean): void {
    this.isShuttingDown = userInitiated || ignoreSdkError;
  }

  getUserProfile(): ClientResult<MatrixUser> {
    const user: MatrixUser = {
      userId: this.userId,
      displayName: this.displayName,
      avatarUrl: this.avatarUrl,
      status: this.userStatus
    };
    return success(user);
  }

  getAccountManagementUrl(action: string): ClientResult<string> {
    const suffix = action.length > 0 ? `/${action}` : '';
    return success(`https://${this.homeserver}/account${suffix}`);
  }

  uploadMedia(mimeType: string, data: ArrayBuffer): ClientResult<string> {
    return success(`mxc://${this.homeserver}/media-${mimeType.replace('/', '-')}-${data.byteLength}`);
  }

  getRoomInfoFlow(roomId: string): MatrixLiveValue<RoomInfo | null> {
    return {
      current: this.getJoinedRoom(roomId),
      version: this.roomMembershipObserver.updates.sequence
    };
  }

  isMe(userId: string): boolean {
    return userId === this.sessionId;
  }

  trackRecentlyVisitedRoom(roomId: string): ClientResult<void> {
    const index = this.recentRooms.indexOf(roomId);
    if (index >= 0) {
      this.recentRooms.splice(index, 1);
    }
    this.recentRooms.unshift(roomId);
    return successVoid();
  }

  getRecentlyVisitedRooms(): ClientResult<string[]> {
    return success(this.recentRooms);
  }

  resolveRoomAlias(roomAlias: string): ClientResult<ResolvedRoomAlias> {
    if (!roomAlias.startsWith('#')) {
      return failure('Invalid room alias');
    }
    const resolved: ResolvedRoomAlias = {
      roomId: `!${roomAlias.substring(1).replace(':', '-')}`,
      serverNames: [this.homeserver]
    };
    return success(resolved);
  }

  setAllSendQueuesEnabled(enabled: boolean): ClientResult<void> {
    if (this.sendQueuesEnabled !== enabled) {
      this.sendQueueDisabledSequence += 1;
    }
    this.sendQueuesEnabled = enabled;
    return successVoid();
  }

  sendQueueDisabledFlow(): MatrixLiveEvent<string> {
    const disabledRoomIds = this.disabledSendQueueRoomIds();
    return {
      latest: disabledRoomIds.length > 0 ? disabledRoomIds[0] : '',
      sequence: this.sendQueueDisabledSequence
    };
  }

  userIdServerName(): string {
    const parts = this.userId.split(':');
    if (parts.length < 2) {
      return this.homeserver;
    }
    return parts[1];
  }

  getRoomPreview(roomIdOrAlias: string, serverNames: string[]): ClientResult<RoomPreview> {
    const preview: RoomPreview = {
      roomIdOrAlias: roomIdOrAlias,
      name: serverNames.length > 0 ? serverNames[0] : roomIdOrAlias,
      topic: 'Room preview',
      canJoin: true
    };
    return success(preview);
  }

  currentSlidingSyncVersion(): ClientResult<string> {
    return success('Native');
  }

  canDeactivateAccount(): boolean {
    return this.capabilities.canDeactivateAccount;
  }

  deactivateAccount(password: string, eraseData: boolean): ClientResult<void> {
    if (password.length === 0 && eraseData) {
      return failure('Password required');
    }
    this.isShuttingDown = true;
    return successVoid();
  }

  canReportRoom(): boolean {
    return this.capabilities.canReportRoom;
  }

  isLivekitRtcSupported(): boolean {
    return this.capabilities.livekitRtcSupported;
  }

  getMaxFileUploadSize(): ClientResult<number> {
    return success(this.capabilities.maxFileUploadSizeBytes);
  }

  getRecentEmojis(): ClientResult<string[]> {
    return success(this.recentEmojis);
  }

  addRecentEmoji(emoji: string): ClientResult<void> {
    if (!this.recentEmojis.includes(emoji)) {
      this.recentEmojis.unshift(emoji);
    }
    return successVoid();
  }

  getAccountData(eventType: string): ClientResult<string> {
    const prefix = `${eventType}=`;
    const entry = this.accountData.find((item: string) => item.startsWith(prefix));
    if (entry === undefined) {
      return failure('Account data not found');
    }
    return success(entry.substring(prefix.length));
  }

  setAccountData(eventType: string, content: string): ClientResult<void> {
    const prefix = `${eventType}=`;
    const index = this.accountData.findIndex((item: string) => item.startsWith(prefix));
    const entry = `${prefix}${content}`;
    if (index >= 0) {
      this.accountData[index] = entry;
    } else {
      this.accountData.push(entry);
    }
    return successVoid();
  }

  markRoomAsFullyRead(roomId: string, eventId: string): ClientResult<void> {
    const room = this.rooms.find((item: RoomSummary) => item.id === roomId);
    if (room === undefined || eventId.length === 0) {
      return failure('Room or event is unknown');
    }
    room.unreadCount = 0;
    room.isMarkedUnread = false;
    return successVoid();
  }

  markAllRoomsAsRead(): ClientResult<void> {
    this.rooms.forEach((item: RoomSummary) => {
      item.unreadCount = 0;
      item.isMarkedUnread = false;
    });
    return successVoid();
  }

  canLinkNewDevice(): ClientResult<boolean> {
    return success(this.capabilities.canLinkNewDevice);
  }

  createLinkMobileHandler(): ClientResult<LinkNewDeviceHandlerState> {
    return success(this.createLinkHandler('mobile'));
  }

  createLinkDesktopHandler(): ClientResult<LinkNewDeviceHandlerState> {
    return success(this.createLinkHandler('desktop'));
  }

  performDatabaseVacuum(): ClientResult<void> {
    return successVoid();
  }

  resetWellKnownConfig(): ClientResult<void> {
    return successVoid();
  }

  homeserverCapabilities(): HomeserverCapabilitiesState {
    return this.capabilities;
  }

  private toRoomInfo(room: RoomSummary, membership: string): RoomInfo {
    return {
      roomId: room.id,
      name: room.name,
      membership: membership,
      isEncrypted: true
    };
  }

  private toMatrixUser(userId: string): MatrixUser {
    return {
      userId: userId,
      displayName: this.displayNameFromUserId(userId),
      avatarUrl: '',
      status: userId === this.userId ? this.userStatus : ''
    };
  }

  private createLinkHandler(mode: string): LinkNewDeviceHandlerState {
    return {
      mode: mode,
      qrCodeData: `${mode}:${this.sessionId}:${this.deviceId}`,
      expiresAtMs: 600000,
      ownerVerified: true
    };
  }

  private refreshUserProfile(): void {
    this.userProfile = {
      current: {
        userId: this.userId,
        displayName: this.displayName,
        avatarUrl: this.avatarUrl,
        status: this.userStatus
      },
      version: this.userProfile.version + 1
    };
  }

  private refreshIgnoredUsersFlow(): void {
    this.ignoredUsersFlow = {
      current: this.ignoredUsers.slice(),
      version: this.ignoredUsersFlow.version + 1
    };
  }

  private disabledSendQueueRoomIds(): string[] {
    if (this.sendQueuesEnabled) {
      return [];
    }
    return this.rooms.map((item: RoomSummary) => item.id);
  }

  private createRoomListService(): RoomListServiceContract {
    return new FixtureRoomListService(this.rooms, this.syncRuntimeState);
  }

  private createSpaceService(): SpaceServiceContract {
    return new FixtureSpaceService(this.rooms);
  }

  private createSyncService(): SyncServiceContract {
    return new FixtureSyncService(this.syncRuntimeState);
  }

  private createSessionVerificationService(): SessionVerificationServiceContract {
    return new FixtureSessionVerificationService();
  }

  private createPushersService(): PushersServiceContract {
    return new FixturePushersService();
  }

  private createNotificationService(): NotificationServiceContract {
    return new FixtureNotificationService();
  }

  private createNotificationSettingsService(): NotificationSettingsServiceContract {
    return new FixtureNotificationSettingsService();
  }

  private createEncryptionService(): EncryptionServiceContract {
    return new FixtureEncryptionService();
  }

  private createRoomDirectoryService(): RoomDirectoryServiceContract {
    return new FixtureRoomDirectoryService();
  }

  private createMessageSearchService(): MessageSearchServiceContract {
    return new FixtureMessageSearchService(this.timeline);
  }

  private createMediaPreviewService(): MediaPreviewServiceContract {
    return new FixtureMediaPreviewService(`${this.timelineMediaPreviewMode}`);
  }

  private createMatrixMediaLoader(): MatrixMediaLoaderContract {
    return new FixtureMatrixMediaLoader();
  }

  private createRoomMembershipObserver(): RoomMembershipObserverContract {
    return new FixtureRoomMembershipObserver();
  }

  private createContentScanner(): ContentScannerContract {
    return new FixtureContentScanner();
  }

  private displayNameFromUserId(userId: string): string {
    const withoutAt = userId.startsWith('@') ? userId.substring(1) : userId;
    const localpart = withoutAt.split(':')[0];
    if (localpart.length === 0) {
      return 'Alice';
    }
    return `${localpart.substring(0, 1).toUpperCase()}${localpart.substring(1)}`;
  }
}

class FixtureRoomListService implements RoomListServiceContract {
  isInitialSyncDone: boolean = true;
  allRooms: MatrixLiveValue<RoomSummary[]>;
  syncIndicator: MatrixLiveValue<string>;
  state: MatrixLiveValue<string>;
  private readonly rooms: RoomSummary[];

  constructor(rooms: RoomSummary[], syncRuntimeState: SyncRuntimeState) {
    this.rooms = rooms;
    this.allRooms = liveValue<RoomSummary[]>(rooms, 1);
    this.syncIndicator = liveValue<string>(`${syncRuntimeState.indicatorState}`, 1);
    this.state = liveValue<string>(`${syncRuntimeState.serviceState}`, 1);
  }

  createRoomList(pageSize: number, filters: string[]): MatrixLiveValue<RoomSummary[]> {
    const maxRows = pageSize > 0 ? pageSize : this.rooms.length;
    return liveValue<RoomSummary[]>(this.rooms.slice(0, maxRows), filters.length);
  }

  subscribeToVisibleRooms(roomIds: string[]): ClientResult<void> {
    return roomIds.length >= 0 ? successVoid() : failure('Invalid room list');
  }
}

class FixtureSpaceService implements SpaceServiceContract {
  topLevelSpacesFlow: MatrixLiveValue<RoomInfo[]> = liveValue<RoomInfo[]>([], 1);
  spaceFiltersFlow: MatrixLiveValue<string[]> = liveValue<string[]>([], 1);
  private readonly rooms: RoomSummary[];

  constructor(rooms: RoomSummary[]) {
    this.rooms = rooms;
  }

  joinedParents(spaceId: string): ClientResult<RoomInfo[]> {
    const parents: RoomInfo[] = [];
    return spaceId.length > 0 ? success<RoomInfo[]>(parents) : failure<RoomInfo[]>('Invalid space id');
  }

  getSpaceRoom(spaceId: string): RoomInfo | null {
    const room = this.rooms.find((item: RoomSummary) => item.id === spaceId);
    return room === undefined ? null : roomInfoFromSummary(room, 'join');
  }

  spaceRoomList(id: string): MatrixLiveValue<RoomInfo[]> {
    const room = this.getSpaceRoom(id);
    const rooms: RoomInfo[] = room === null ? [] : [room];
    return liveValue<RoomInfo[]>(rooms, 1);
  }

  editableSpaces(): ClientResult<RoomInfo[]> {
    const spaces: RoomInfo[] = [];
    return success<RoomInfo[]>(spaces);
  }

  getLeaveSpaceHandle(spaceId: string): string {
    return spaceId;
  }

  addChildToSpace(spaceId: string, childId: string): ClientResult<void> {
    return spaceId.length > 0 && childId.length > 0 ? successVoid() : failure('Invalid space child');
  }

  removeChildFromSpace(spaceId: string, childId: string): ClientResult<void> {
    return spaceId.length > 0 && childId.length > 0 ? successVoid() : failure('Invalid space child');
  }
}

class FixtureSyncService implements SyncServiceContract {
  syncState: MatrixLiveValue<string>;
  isOnline: MatrixLiveValue<boolean> = liveValue<boolean>(true, 1);

  constructor(syncRuntimeState: SyncRuntimeState) {
    this.syncState = liveValue<string>(`${syncRuntimeState.serviceState}`, 1);
  }

  startSync(): ClientResult<void> {
    return successVoid();
  }

  stopSync(): ClientResult<void> {
    return successVoid();
  }
}

class FixtureSessionVerificationService implements SessionVerificationServiceContract {
  verificationFlowState: MatrixLiveValue<string> = liveValue<string>('idle', 1);
  sessionVerifiedStatus: MatrixLiveValue<string> = liveValue<string>('verified', 1);
  needsSessionVerification: MatrixLiveValue<boolean> = liveValue<boolean>(false, 1);

  requestDeviceVerification(): ClientResult<void> {
    return successVoid();
  }

  requestUserVerification(userId: string): ClientResult<void> {
    return userId.length > 0 ? successVoid() : failure('Invalid user id');
  }

  cancelVerification(): ClientResult<void> {
    return successVoid();
  }

  approveVerification(): ClientResult<void> {
    return successVoid();
  }

  declineVerification(): ClientResult<void> {
    return successVoid();
  }

  startSasVerification(): ClientResult<void> {
    return successVoid();
  }

  reset(cancelAnyPendingVerificationAttempt: boolean): ClientResult<void> {
    return cancelAnyPendingVerificationAttempt || !cancelAnyPendingVerificationAttempt ? successVoid() : failure('Invalid reset');
  }

  setListener(listenerId: string): void {
    listenerId.length;
  }

  acknowledgeVerificationRequest(requestId: string): ClientResult<void> {
    return requestId.length > 0 ? successVoid() : failure('Invalid request id');
  }

  acceptVerificationRequest(): ClientResult<void> {
    return successVoid();
  }
}

class FixturePushersService implements PushersServiceContract {
  setHttpPusher(setHttpPusherData: string): ClientResult<void> {
    return setHttpPusherData.length >= 0 ? successVoid() : failure('Invalid pusher');
  }

  unsetHttpPusher(unsetHttpPusherData: string): ClientResult<void> {
    return unsetHttpPusherData.length >= 0 ? successVoid() : failure('Invalid pusher');
  }
}

class FixtureNotificationService implements NotificationServiceContract {
  getNotifications(ids: string): ClientResult<string> {
    return success<string>(ids.length > 0 ? ids : '{}');
  }
}

class FixtureNotificationSettingsService implements NotificationSettingsServiceContract {
  notificationSettingsChangeFlow: MatrixLiveEvent<string> = liveEvent<string>('', 0);

  getRoomNotificationSettings(roomId: string, isEncrypted: boolean, isOneToOne: boolean): ClientResult<string> {
    return roomId.length > 0 || isEncrypted || isOneToOne ? success<string>('all_messages') : failure<string>('Invalid room');
  }

  getDefaultRoomNotificationMode(isEncrypted: boolean, isOneToOne: boolean): ClientResult<string> {
    return success<string>(isEncrypted || isOneToOne ? 'mentions_and_keywords_only' : 'all_messages');
  }

  setDefaultRoomNotificationMode(isEncrypted: boolean, mode: string, isDM: boolean): ClientResult<void> {
    return mode.length > 0 || isEncrypted || isDM ? successVoid() : failure('Invalid mode');
  }

  setRoomNotificationMode(roomId: string, mode: string): ClientResult<void> {
    return roomId.length > 0 && mode.length > 0 ? successVoid() : failure('Invalid room notification mode');
  }

  restoreDefaultRoomNotificationMode(roomId: string): ClientResult<void> {
    return roomId.length > 0 ? successVoid() : failure('Invalid room');
  }

  muteRoom(roomId: string): ClientResult<void> {
    return roomId.length > 0 ? successVoid() : failure('Invalid room');
  }

  unmuteRoom(roomId: string, isEncrypted: boolean, isOneToOne: boolean): ClientResult<void> {
    return roomId.length > 0 || isEncrypted || isOneToOne ? successVoid() : failure('Invalid room');
  }

  isRoomMentionEnabled(): ClientResult<boolean> {
    return success<boolean>(true);
  }

  setRoomMentionEnabled(enabled: boolean): ClientResult<void> {
    return enabled || !enabled ? successVoid() : failure('Invalid mention setting');
  }

  isCallEnabled(): ClientResult<boolean> {
    return success<boolean>(true);
  }

  setCallEnabled(enabled: boolean): ClientResult<void> {
    return enabled || !enabled ? successVoid() : failure('Invalid call setting');
  }

  isInviteForMeEnabled(): ClientResult<boolean> {
    return success<boolean>(true);
  }

  setInviteForMeEnabled(enabled: boolean): ClientResult<void> {
    return enabled || !enabled ? successVoid() : failure('Invalid invite setting');
  }

  getRoomsWithUserDefinedRules(): ClientResult<string[]> {
    const roomIds: string[] = [];
    return success<string[]>(roomIds);
  }

  canHomeServerPushEncryptedEventsToDevice(): ClientResult<boolean> {
    return success<boolean>(false);
  }

  getRawPushRules(): ClientResult<string> {
    return success<string>('{}');
  }
}

class FixtureEncryptionService implements EncryptionServiceContract {
  backupStateStateFlow: MatrixLiveValue<string> = liveValue<string>('unknown', 1);
  recoveryStateStateFlow: MatrixLiveValue<string> = liveValue<string>('enabled', 1);
  enableRecoveryProgressStateFlow: MatrixLiveValue<string> = liveValue<string>('idle', 1);
  isLastDevice: MatrixLiveValue<boolean> = liveValue<boolean>(false, 1);
  hasDevicesToVerifyAgainst: MatrixLiveValue<boolean> = liveValue<boolean>(true, 1);

  enableBackups(): ClientResult<void> {
    return successVoid();
  }

  enableRecovery(waitForBackupsToUpload: boolean, passphrase: string): ClientResult<string> {
    return waitForBackupsToUpload || passphrase.length >= 0 ? success<string>('fixture-recovery-key') : failure<string>('Invalid recovery');
  }

  resetRecoveryKey(): ClientResult<string> {
    return success<string>('fixture-recovery-key');
  }

  disableRecovery(): ClientResult<void> {
    return successVoid();
  }

  doesBackupExistOnServer(): ClientResult<boolean> {
    return success<boolean>(false);
  }

  recover(recoveryKey: string): ClientResult<void> {
    return recoveryKey.length > 0 ? successVoid() : failure('Invalid recovery key');
  }

  waitForBackupUploadSteadyState(): MatrixLiveValue<string> {
    return liveValue<string>('done', 1);
  }

  deviceCurve25519(): ClientResult<string> {
    return success<string>('fixture-curve25519');
  }

  deviceEd25519(): ClientResult<string> {
    return success<string>('fixture-ed25519');
  }

  startIdentityReset(): ClientResult<string> {
    return success<string>('fixture-identity-reset');
  }

  pinUserIdentity(userId: string): ClientResult<void> {
    return userId.length > 0 ? successVoid() : failure('Invalid user id');
  }

  withdrawVerification(userId: string): ClientResult<void> {
    return userId.length > 0 ? successVoid() : failure('Invalid user id');
  }

  getUserIdentity(userId: string, fallbackToServer: boolean): ClientResult<string> {
    return userId.length > 0 || fallbackToServer ? success<string>(userId) : failure<string>('Invalid user id');
  }
}

class FixtureRoomDirectoryService implements RoomDirectoryServiceContract {
  createRoomDirectoryList(scopeId: string): MatrixLiveValue<RoomPreview[]> {
    const previews: RoomPreview[] = [];
    return liveValue<RoomPreview[]>(scopeId.length >= 0 ? previews : [], 1);
  }
}

class FixtureMessageSearchService implements MessageSearchServiceContract {
  private readonly timeline: TimelineEvent[];

  constructor(timeline: TimelineEvent[]) {
    this.timeline = timeline;
  }

  createMessageSearch(scopeId: string, roomId: string): MatrixLiveValue<TimelineEvent[]> {
    const filtered = roomId.length > 0 ? this.timeline.filter((event: TimelineEvent) => event.roomId === roomId) : this.timeline;
    return liveValue<TimelineEvent[]>(scopeId.length >= 0 ? filtered : [], 1);
  }
}

class FixtureMediaPreviewService implements MediaPreviewServiceContract {
  mediaPreviewConfigFlow: MatrixLiveValue<string>;
  private mediaPreviewValue: string;

  constructor(mediaPreviewValue: string) {
    this.mediaPreviewValue = mediaPreviewValue;
    this.mediaPreviewConfigFlow = liveValue<string>(mediaPreviewValue, 1);
  }

  fetchMediaPreviewConfig(): ClientResult<string> {
    return success<string>(this.mediaPreviewValue);
  }

  setMediaPreviewValue(mediaPreviewValue: string): ClientResult<void> {
    if (mediaPreviewValue.length === 0) {
      return failure('Invalid media preview value');
    }
    this.mediaPreviewValue = mediaPreviewValue;
    this.mediaPreviewConfigFlow = liveValue<string>(mediaPreviewValue, this.mediaPreviewConfigFlow.version + 1);
    return successVoid();
  }

  setHideInviteAvatars(hide: boolean): ClientResult<void> {
    return hide || !hide ? successVoid() : failure('Invalid avatar setting');
  }

  getMediaPreviewValue(): string {
    return this.mediaPreviewValue;
  }
}

class FixtureMatrixMediaLoader implements MatrixMediaLoaderContract {
  loadMediaContent(source: string): ClientResult<ArrayBuffer> {
    return source.length > 0 ? success<ArrayBuffer>(new ArrayBuffer(0)) : failure<ArrayBuffer>('Invalid media source');
  }

  loadMediaThumbnail(source: string, width: number, height: number): ClientResult<ArrayBuffer> {
    return source.length > 0 && width >= 0 && height >= 0 ? success<ArrayBuffer>(new ArrayBuffer(0)) : failure<ArrayBuffer>('Invalid media thumbnail');
  }

  downloadMediaFile(source: string, filename: string): ClientResult<string> {
    return source.length > 0 && filename.length > 0 ? success<string>(filename) : failure<string>('Invalid media file');
  }
}

class FixtureRoomMembershipObserver implements RoomMembershipObserverContract {
  updates: MatrixLiveEvent<RoomMembershipUpdate>;

  constructor() {
    const initialUpdate: RoomMembershipUpdate = {
      roomId: '',
      isSpace: false,
      isUserInRoom: true,
      change: 'none'
    };
    this.updates = liveEvent<RoomMembershipUpdate>(initialUpdate, 0);
  }

  notifyUserLeftRoom(roomId: string, isSpace: boolean, membershipBeforeLeft: string): ClientResult<void> {
    const update: RoomMembershipUpdate = {
      roomId: roomId,
      isSpace: isSpace,
      isUserInRoom: false,
      change: membershipBeforeLeft
    };
    this.updates = liveEvent<RoomMembershipUpdate>(update, this.updates.sequence + 1);
    return roomId.length > 0 ? successVoid() : failure('Invalid room');
  }
}

class FixtureContentScanner implements ContentScannerContract {
  scan(mediaSource: string): ClientResult<boolean> {
    return mediaSource.length > 0 ? success<boolean>(true) : failure<boolean>('Invalid media source');
  }
}

function liveValue<T>(current: T, version: number): MatrixLiveValue<T> {
  const value: MatrixLiveValue<T> = {
    current: current,
    version: version
  };
  return value;
}

function liveEvent<T>(latest: T, sequence: number): MatrixLiveEvent<T> {
  const event: MatrixLiveEvent<T> = {
    latest: latest,
    sequence: sequence
  };
  return event;
}

function roomInfoFromSummary(room: RoomSummary, membership: string): RoomInfo {
  const info: RoomInfo = {
    roomId: room.id,
    name: room.name,
    membership: membership,
    isEncrypted: true
  };
  return info;
}
