import { RoomSummary, TimelineEvent } from '../model/ElementModels';
import { HomeserverCapabilitiesState } from '../model/ClientRuntimeModels';

export interface ClientResult<T> {
  ok: boolean;
  value?: T;
  errorMessage: string;
}

export interface MatrixLiveValue<T> {
  current: T;
  version: number;
}

export interface MatrixLiveEvent<T> {
  latest: T;
  sequence: number;
}

export interface MatrixUser {
  userId: string;
  displayName: string;
  avatarUrl: string;
  status: string;
}

export interface RoomInfo {
  roomId: string;
  name: string;
  membership: string;
  isEncrypted: boolean;
}

export interface RoomPreview {
  roomIdOrAlias: string;
  name: string;
  topic: string;
  canJoin: boolean;
}

export interface SdkStoreSizes {
  stateStoreBytes: number;
  cryptoStoreBytes: number;
  eventCacheBytes: number;
  mediaCacheBytes: number;
}

export interface CreateRoomParameters {
  name: string;
  topic: string;
  preset: string;
  invitees: string[];
  isEncrypted: boolean;
}

export interface MatrixSearchUserResults {
  results: MatrixUser[];
  limited: boolean;
}

export interface MatrixSessionPaths {
  basePath: string;
  cachePath: string;
  mediaPath: string;
  cryptoStorePath: string;
}

export interface ResolvedRoomAlias {
  roomId: string;
  serverNames: string[];
}

export interface LinkNewDeviceHandlerState {
  mode: string;
  qrCodeData: string;
  expiresAtMs: number;
  ownerVerified: boolean;
}

export interface RoomListServiceContract {
  isInitialSyncDone: boolean;
  allRooms: MatrixLiveValue<RoomSummary[]>;
  syncIndicator: MatrixLiveValue<string>;
  state: MatrixLiveValue<string>;
  createRoomList(pageSize: number, filters: string[]): MatrixLiveValue<RoomSummary[]>;
  subscribeToVisibleRooms(roomIds: string[]): ClientResult<void>;
}

export interface SpaceServiceContract {
  topLevelSpacesFlow: MatrixLiveValue<RoomInfo[]>;
  spaceFiltersFlow: MatrixLiveValue<string[]>;
  joinedParents(spaceId: string): ClientResult<RoomInfo[]>;
  getSpaceRoom(spaceId: string): RoomInfo | null;
  spaceRoomList(id: string): MatrixLiveValue<RoomInfo[]>;
  editableSpaces(): ClientResult<RoomInfo[]>;
  getLeaveSpaceHandle(spaceId: string): string;
  addChildToSpace(spaceId: string, childId: string): ClientResult<void>;
  removeChildFromSpace(spaceId: string, childId: string): ClientResult<void>;
}

export interface SyncServiceContract {
  syncState: MatrixLiveValue<string>;
  isOnline: MatrixLiveValue<boolean>;
  startSync(): ClientResult<void>;
  stopSync(): ClientResult<void>;
}

export interface SessionVerificationServiceContract {
  verificationFlowState: MatrixLiveValue<string>;
  sessionVerifiedStatus: MatrixLiveValue<string>;
  needsSessionVerification: MatrixLiveValue<boolean>;
  requestDeviceVerification(): ClientResult<void>;
  requestUserVerification(userId: string): ClientResult<void>;
  cancelVerification(): ClientResult<void>;
  approveVerification(): ClientResult<void>;
  declineVerification(): ClientResult<void>;
  startSasVerification(): ClientResult<void>;
  reset(cancelAnyPendingVerificationAttempt: boolean): ClientResult<void>;
  setListener(listenerId: string): void;
  acknowledgeVerificationRequest(requestId: string): ClientResult<void>;
  acceptVerificationRequest(): ClientResult<void>;
}

export interface PushersServiceContract {
  setHttpPusher(setHttpPusherData: string): ClientResult<void>;
  unsetHttpPusher(unsetHttpPusherData: string): ClientResult<void>;
}

export interface NotificationServiceContract {
  getNotifications(ids: string): ClientResult<string>;
}

export interface NotificationSettingsServiceContract {
  notificationSettingsChangeFlow: MatrixLiveEvent<string>;
  getRoomNotificationSettings(roomId: string, isEncrypted: boolean, isOneToOne: boolean): ClientResult<string>;
  getDefaultRoomNotificationMode(isEncrypted: boolean, isOneToOne: boolean): ClientResult<string>;
  setDefaultRoomNotificationMode(isEncrypted: boolean, mode: string, isDM: boolean): ClientResult<void>;
  setRoomNotificationMode(roomId: string, mode: string): ClientResult<void>;
  restoreDefaultRoomNotificationMode(roomId: string): ClientResult<void>;
  muteRoom(roomId: string): ClientResult<void>;
  unmuteRoom(roomId: string, isEncrypted: boolean, isOneToOne: boolean): ClientResult<void>;
  isRoomMentionEnabled(): ClientResult<boolean>;
  setRoomMentionEnabled(enabled: boolean): ClientResult<void>;
  isCallEnabled(): ClientResult<boolean>;
  setCallEnabled(enabled: boolean): ClientResult<void>;
  isInviteForMeEnabled(): ClientResult<boolean>;
  setInviteForMeEnabled(enabled: boolean): ClientResult<void>;
  getRoomsWithUserDefinedRules(): ClientResult<string[]>;
  canHomeServerPushEncryptedEventsToDevice(): ClientResult<boolean>;
  getRawPushRules(): ClientResult<string>;
}

export interface EncryptionServiceContract {
  backupStateStateFlow: MatrixLiveValue<string>;
  recoveryStateStateFlow: MatrixLiveValue<string>;
  enableRecoveryProgressStateFlow: MatrixLiveValue<string>;
  isLastDevice: MatrixLiveValue<boolean>;
  hasDevicesToVerifyAgainst: MatrixLiveValue<boolean>;
  enableBackups(): ClientResult<void>;
  enableRecovery(waitForBackupsToUpload: boolean, passphrase: string): ClientResult<string>;
  resetRecoveryKey(): ClientResult<string>;
  disableRecovery(): ClientResult<void>;
  doesBackupExistOnServer(): ClientResult<boolean>;
  recover(recoveryKey: string): ClientResult<void>;
  waitForBackupUploadSteadyState(): MatrixLiveValue<string>;
  deviceCurve25519(): ClientResult<string>;
  deviceEd25519(): ClientResult<string>;
  startIdentityReset(): ClientResult<string>;
  pinUserIdentity(userId: string): ClientResult<void>;
  withdrawVerification(userId: string): ClientResult<void>;
  getUserIdentity(userId: string, fallbackToServer: boolean): ClientResult<string>;
}

export interface RoomDirectoryServiceContract {
  createRoomDirectoryList(scopeId: string): MatrixLiveValue<RoomPreview[]>;
}

export interface MessageSearchServiceContract {
  createMessageSearch(scopeId: string, roomId: string): MatrixLiveValue<TimelineEvent[]>;
}

export interface MediaPreviewServiceContract {
  mediaPreviewConfigFlow: MatrixLiveValue<string>;
  fetchMediaPreviewConfig(): ClientResult<string>;
  setMediaPreviewValue(mediaPreviewValue: string): ClientResult<void>;
  setHideInviteAvatars(hide: boolean): ClientResult<void>;
  getMediaPreviewValue(): string;
}

export interface MatrixMediaLoaderContract {
  loadMediaContent(source: string): ClientResult<ArrayBuffer>;
  loadMediaThumbnail(source: string, width: number, height: number): ClientResult<ArrayBuffer>;
  downloadMediaFile(source: string, filename: string): ClientResult<string>;
}

export interface MatrixSessionCoroutineScope {
  isActive: boolean;
}

export interface RoomMembershipUpdate {
  roomId: string;
  isSpace: boolean;
  isUserInRoom: boolean;
  change: string;
}

export interface RoomMembershipObserverContract {
  updates: MatrixLiveEvent<RoomMembershipUpdate>;
  notifyUserLeftRoom(roomId: string, isSpace: boolean, membershipBeforeLeft: string): ClientResult<void>;
}

export interface ContentScannerContract {
  scan(mediaSource: string): ClientResult<boolean>;
}

export interface MatrixClientContract {
  sessionId: string;
  deviceId: string;
  sessionPaths: MatrixSessionPaths;
  userProfile: MatrixLiveValue<MatrixUser>;
  roomListService: RoomListServiceContract;
  spaceService: SpaceServiceContract;
  syncService: SyncServiceContract;
  sessionVerificationService: SessionVerificationServiceContract;
  pushersService: PushersServiceContract;
  notificationService: NotificationServiceContract;
  notificationSettingsService: NotificationSettingsServiceContract;
  encryptionService: EncryptionServiceContract;
  roomDirectoryService: RoomDirectoryServiceContract;
  isMessageSearchAvailable: boolean;
  messageSearchService: MessageSearchServiceContract;
  mediaPreviewService: MediaPreviewServiceContract;
  matrixMediaLoader: MatrixMediaLoaderContract;
  sessionCoroutineScope: MatrixSessionCoroutineScope;
  ignoredUsersFlow: MatrixLiveValue<string[]>;
  roomMembershipObserver: RoomMembershipObserverContract;
  ownBeaconInfoUpdates: MatrixLiveEvent<string>;
  contentScanner: ContentScannerContract | null;
  isShuttingDown: boolean;

  getJoinedRoom(roomId: string): RoomInfo | null;
  getRoom(roomId: string): RoomInfo | null;
  findDM(userId: string): ClientResult<string>;
  getJoinedRoomIds(): ClientResult<string[]>;
  ignoreUser(userId: string): ClientResult<void>;
  unignoreUser(userId: string): ClientResult<void>;
  createRoom(createRoomParams: CreateRoomParameters): ClientResult<string>;
  createDM(userId: string, isEncrypted: boolean): ClientResult<string>;
  getProfile(userId: string): ClientResult<MatrixUser>;
  searchUsers(searchTerm: string, limit: number): ClientResult<MatrixSearchUserResults>;
  setDisplayName(displayName: string): ClientResult<void>;
  uploadAvatar(mimeType: string, data: ArrayBuffer): ClientResult<void>;
  removeAvatar(): ClientResult<void>;
  setUserStatus(status: string): ClientResult<void>;
  clearUserStatus(): ClientResult<void>;
  isUserStatusSupported(): ClientResult<boolean>;
  isProfilesSlidingSyncExtensionSupported(): ClientResult<boolean>;
  enableAutomaticCallStatus(enabled: boolean): void;
  joinRoom(roomId: string): ClientResult<RoomInfo>;
  joinRoomByIdOrAlias(roomIdOrAlias: string, serverNames: string[]): ClientResult<RoomInfo>;
  knockRoom(roomIdOrAlias: string, message: string, serverNames: string[]): ClientResult<RoomInfo>;
  getCacheSize(): number;
  getDatabaseSizes(): ClientResult<SdkStoreSizes>;
  clearCache(): void;
  logout(userInitiated: boolean, ignoreSdkError: boolean): void;
  getUserProfile(): ClientResult<MatrixUser>;
  getAccountManagementUrl(action: string): ClientResult<string>;
  uploadMedia(mimeType: string, data: ArrayBuffer): ClientResult<string>;
  getRoomInfoFlow(roomId: string): MatrixLiveValue<RoomInfo | null>;
  isMe(userId: string): boolean;
  trackRecentlyVisitedRoom(roomId: string): ClientResult<void>;
  getRecentlyVisitedRooms(): ClientResult<string[]>;
  resolveRoomAlias(roomAlias: string): ClientResult<ResolvedRoomAlias>;
  setAllSendQueuesEnabled(enabled: boolean): ClientResult<void>;
  sendQueueDisabledFlow(): MatrixLiveEvent<string>;
  userIdServerName(): string;
  getRoomPreview(roomIdOrAlias: string, serverNames: string[]): ClientResult<RoomPreview>;
  currentSlidingSyncVersion(): ClientResult<string>;
  canDeactivateAccount(): boolean;
  deactivateAccount(password: string, eraseData: boolean): ClientResult<void>;
  canReportRoom(): boolean;
  isLivekitRtcSupported(): boolean;
  getMaxFileUploadSize(): ClientResult<number>;
  getRecentEmojis(): ClientResult<string[]>;
  addRecentEmoji(emoji: string): ClientResult<void>;
  getAccountData(eventType: string): ClientResult<string>;
  setAccountData(eventType: string, content: string): ClientResult<void>;
  markRoomAsFullyRead(roomId: string, eventId: string): ClientResult<void>;
  markAllRoomsAsRead(): ClientResult<void>;
  canLinkNewDevice(): ClientResult<boolean>;
  createLinkMobileHandler(): ClientResult<LinkNewDeviceHandlerState>;
  createLinkDesktopHandler(): ClientResult<LinkNewDeviceHandlerState>;
  performDatabaseVacuum(): ClientResult<void>;
  resetWellKnownConfig(): ClientResult<void>;
  homeserverCapabilities(): HomeserverCapabilitiesState;
}

export function success<T>(value: T): ClientResult<T> {
  return {
    ok: true,
    value: value,
    errorMessage: ''
  };
}

export function successVoid(): ClientResult<void> {
  return {
    ok: true,
    errorMessage: ''
  };
}

export function failure<T>(message: string): ClientResult<T> {
  return {
    ok: false,
    errorMessage: message
  };
}
