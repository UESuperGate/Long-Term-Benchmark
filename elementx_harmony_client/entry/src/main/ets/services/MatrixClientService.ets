import {
  AccountProfile,
  BaseFeatureFlags,
  ReadReceiptSummary,
  RoomSummary,
  TimelineEvent,
  TimelineEventKind,
  TimelineMediaItem
} from '../model/ElementModels';
import { ClientSession, ClientSnapshot } from '../model/ClientModels';
import {
  AsyncDataState,
  AsyncDataStatus,
  HomeserverCapabilitiesState,
  LocalNetworkPermissionDialog,
  LoggedInRuntimeState,
  MatrixClientRuntime,
  NetworkStatus,
  RecoveryState,
  ResolvedIntentKind,
  RootNavState,
  RootNavTargetKind,
  SessionStoreRecord,
  SessionVerificationStatus,
  TimelineMediaPreviewMode,
  SyncIndicatorState,
  SyncRuntimeState,
  SyncServiceState
} from '../model/ClientRuntimeModels';
import { FixtureMatrixClientAdapter } from './FixtureMatrixClientAdapter';
import { MatrixClientContract, MatrixUser, RoomInfo, RoomPreview } from './MatrixClientContract';
import { MatrixSyncMapper, MatrixSyncMappingResult, RoomTimelineMapping } from './MatrixSyncMapper';

interface RoomTimelineState {
  roomId: string;
  events: TimelineEvent[];
}

interface RoomReadMarkerState {
  roomId: string;
  eventId: string;
}

interface RoomOwnDisplayNameState {
  roomId: string;
  displayName: string;
}

interface RoomReportState {
  roomId: string;
  reason: string;
  timestamp: string;
}

export class MatrixClientService {
  private readonly sessions: SessionStoreRecord[] = [];
  private readonly clients: MatrixClientRuntime[] = [];
  private readonly fixtureRooms: RoomSummary[] = [
    {
      id: 'room-general',
      name: 'Element X General',
      topic: 'Cross-platform product discussion',
      unreadCount: 3,
      isMarkedUnread: false,
      isFavorite: false,
      isDirect: false
    },
    {
      id: 'room-design',
      name: 'Design Review',
      topic: 'Mobile UI and accessibility',
      unreadCount: 0,
      isMarkedUnread: false,
      isFavorite: false,
      isDirect: false
    },
    {
      id: 'dm-bob',
      name: 'Bob',
      topic: 'Direct message - Away',
      unreadCount: 1,
      isMarkedUnread: false,
      isFavorite: true,
      isDirect: true
    }
  ];
  private syncedRooms: RoomSummary[] = [];
  private syncedTimeline: TimelineEvent[] = [];
  private syncedRoomTimelines: RoomTimelineState[] = [];
  private readonly readMarkers: RoomReadMarkerState[] = [];
  private readonly roomOwnDisplayNames: RoomOwnDisplayNameState[] = [];
  private readonly roomReports: RoomReportState[] = [];
  private selectedRoomId: string = 'room-general';
  private latestSessionId: string = '';
  private cacheIndex: number = 0;
  private pendingIntent: ResolvedIntentKind = ResolvedIntentKind.None;

  hydrateSessionStore(latestSessionId: string, sessions: SessionStoreRecord[]): void {
    this.sessions.splice(0, this.sessions.length);
    sessions.forEach((item: SessionStoreRecord) => {
      this.sessions.push({
        userId: item.userId,
        deviceId: item.deviceId,
        homeserver: item.homeserver,
        accessToken: item.accessToken,
        nextSyncBatch: item.nextSyncBatch ?? '',
        ignoredUsers: this.normalizedUserIds(item.ignoredUsers),
        displayName: item.displayName,
        avatarUrl: item.avatarUrl,
        userStatus: item.userStatus,
        sendPublicReadReceipts: item.sendPublicReadReceipts,
        renderReadReceipts: item.renderReadReceipts ?? item.sendPublicReadReceipts,
        timelineMediaPreviewMode: item.timelineMediaPreviewMode ?? TimelineMediaPreviewMode.AlwaysShow,
        lastUsageIndex: item.lastUsageIndex,
        isTokenValid: item.isTokenValid
      });
      if (item.lastUsageIndex > this.cacheIndex) {
        this.cacheIndex = item.lastUsageIndex;
      }
    });
    this.latestSessionId = latestSessionId;
  }

  exportSessionStore(): SessionStoreRecord[] {
    return this.sessions.map((item: SessionStoreRecord) => {
      const record: SessionStoreRecord = {
        userId: item.userId,
        deviceId: item.deviceId,
        homeserver: item.homeserver,
        accessToken: item.accessToken,
        nextSyncBatch: item.nextSyncBatch,
        ignoredUsers: this.normalizedUserIds(item.ignoredUsers),
        displayName: item.displayName,
        avatarUrl: item.avatarUrl,
        userStatus: item.userStatus,
        sendPublicReadReceipts: item.sendPublicReadReceipts,
        renderReadReceipts: item.renderReadReceipts,
        timelineMediaPreviewMode: item.timelineMediaPreviewMode,
        lastUsageIndex: item.lastUsageIndex,
        isTokenValid: item.isTokenValid
      };
      return record;
    });
  }

  getLatestSessionId(): string {
    return this.latestSessionId;
  }

  applySyncResponse(raw: string): void {
    const mapper = new MatrixSyncMapper();
    const mapped: MatrixSyncMappingResult = mapper.map(raw);
    if (mapped.rooms.length > 0) {
      this.syncedRooms = mapped.rooms;
    }
    if (mapped.timeline.length > 0) {
      this.syncedTimeline = mapped.timeline;
    }
    this.syncedRoomTimelines = mapped.roomTimelines.map((item: RoomTimelineMapping) => {
      const state: RoomTimelineState = {
        roomId: item.roomId,
        events: item.events
      };
      return state;
    });
    if (!this.hasRoom(this.selectedRoomId) && mapped.rooms.length > 0) {
      this.selectedRoomId = mapped.rooms[0].id;
    }
  }

  createFixtureSession(homeserver: string, username: string): ClientSession {
    const displayName = username.length > 0 ? username : 'Alice';
    const serverName = homeserver.length > 0 ? homeserver : 'matrix.org';
    const userId = `@${displayName.toLowerCase()}:${serverName}`;
    const sessionId = userId;
    const deviceId = 'HARMONYSDK23';
    this.cacheIndex += 1;
    this.upsertSession({
      userId: sessionId,
      deviceId: deviceId,
      homeserver: serverName,
      accessToken: '',
      nextSyncBatch: '',
      ignoredUsers: [],
      displayName: displayName,
      avatarUrl: '',
      userStatus: 'Away',
      sendPublicReadReceipts: true,
      renderReadReceipts: true,
      timelineMediaPreviewMode: TimelineMediaPreviewMode.AlwaysShow,
      lastUsageIndex: this.cacheIndex,
      isTokenValid: true
    });
    this.latestSessionId = sessionId;
    this.putClient(this.createClientRuntime(sessionId, userId, deviceId, serverName, '', '', [], displayName, '', 'Away', true, true, TimelineMediaPreviewMode.AlwaysShow));
    return {
      sessionId: sessionId,
      homeserver: serverName,
      deviceId: deviceId,
      accessToken: '',
      nextSyncBatch: '',
      ignoredUsers: [],
      sendPublicReadReceipts: true,
      renderReadReceipts: true,
      timelineMediaPreviewMode: TimelineMediaPreviewMode.AlwaysShow,
      account: {
        userId: userId,
        displayName: displayName,
        avatarInitials: displayName.substring(0, 2).toUpperCase(),
        avatarUrl: '',
        userStatus: 'Away',
        canSetUserStatus: true
      }
    };
  }

  createAuthenticatedSession(homeserver: string, userId: string, deviceId: string, accessToken: string): ClientSession {
    const displayName = this.displayNameFromUserId(userId);
    const sessionId = userId;
    this.cacheIndex += 1;
    this.upsertSession({
      userId: userId,
      deviceId: deviceId,
      homeserver: homeserver,
      accessToken: accessToken,
      nextSyncBatch: '',
      ignoredUsers: [],
      displayName: displayName,
      avatarUrl: '',
      userStatus: 'Available',
      sendPublicReadReceipts: true,
      renderReadReceipts: true,
      timelineMediaPreviewMode: TimelineMediaPreviewMode.AlwaysShow,
      lastUsageIndex: this.cacheIndex,
      isTokenValid: accessToken.length > 0
    });
    this.latestSessionId = sessionId;
    this.putClient(this.createClientRuntime(sessionId, userId, deviceId, homeserver, accessToken, '', [], displayName, '', 'Available', true, true, TimelineMediaPreviewMode.AlwaysShow));
    return {
      sessionId: sessionId,
      homeserver: homeserver,
      deviceId: deviceId,
      accessToken: accessToken,
      nextSyncBatch: '',
      ignoredUsers: [],
      sendPublicReadReceipts: true,
      renderReadReceipts: true,
      timelineMediaPreviewMode: TimelineMediaPreviewMode.AlwaysShow,
      account: {
        userId: userId,
        displayName: displayName,
        avatarInitials: displayName.substring(0, 2).toUpperCase(),
        avatarUrl: '',
        userStatus: 'Available',
        canSetUserStatus: true
      }
    };
  }

  getSignedOutSnapshot(): ClientSnapshot {
    return {
      appName: 'Element X',
      versionName: '26.08.4',
      session: null,
      rootNavState: this.createRootNavState(null, RootNavTargetKind.NotLoggedInFlow),
      loggedInState: null,
      rooms: [],
      selectedRoomId: '',
      timeline: [],
      featureFlags: this.getFeatureFlags(),
      runtimeRows: this.getSignedOutRuntimeRows(),
      intentRows: this.getIntentRows(),
      featureStatusRows: [],
      deviceRows: [],
      securityRows: []
    };
  }

  getSignedInSnapshot(session: ClientSession): ClientSnapshot {
    const client = this.getOrRestore(session.sessionId);
    const loggedInState = this.createLoggedInState(client);
    return {
      appName: 'Element X',
      versionName: '26.08.4',
      session: session,
      rootNavState: this.createRootNavState(session.sessionId, RootNavTargetKind.LoggedInFlow),
      loggedInState: loggedInState,
      rooms: this.getRooms(),
      selectedRoomId: this.currentSelectedRoomId(),
      timeline: this.getTimelineEvents(this.currentSelectedRoomId()),
      featureFlags: this.getFeatureFlags(),
      runtimeRows: this.getRuntimeRows(loggedInState, client),
      intentRows: this.getIntentRows(),
      featureStatusRows: this.getFeatureStatusRows(client),
      deviceRows: this.getDeviceRows(),
      securityRows: this.getSecurityRows()
    };
  }

  signOut(sessionId: string): ClientSnapshot {
    this.removeSession(sessionId);
    this.latestSessionId = '';
    this.cacheIndex += 1;
    return this.getSignedOutSnapshot();
  }

  restoreLatestSession(): ClientSnapshot {
    const latest = this.getLatestSession();
    if (latest === null || !latest.isTokenValid) {
      return this.getSignedOutSnapshot();
    }
    const displayName = latest.displayName.length > 0 ? latest.displayName : this.displayNameFromUserId(latest.userId);
    const session: ClientSession = {
      sessionId: latest.userId,
      homeserver: latest.homeserver,
      deviceId: latest.deviceId,
      accessToken: latest.accessToken,
      nextSyncBatch: latest.nextSyncBatch,
      ignoredUsers: this.normalizedUserIds(latest.ignoredUsers),
      sendPublicReadReceipts: latest.sendPublicReadReceipts,
      renderReadReceipts: latest.renderReadReceipts,
      timelineMediaPreviewMode: latest.timelineMediaPreviewMode,
      account: {
        userId: latest.userId,
        displayName: displayName,
        avatarInitials: displayName.substring(0, 2).toUpperCase(),
        avatarUrl: latest.avatarUrl,
        userStatus: latest.userStatus,
        canSetUserStatus: true
      }
    };
    return this.getSignedInSnapshot(session);
  }

  resolveIntent(action: string, data: string): ResolvedIntentKind {
    if (
      action === 'android.intent.action.SEND' ||
      action === 'android.intent.action.SEND_MULTIPLE' ||
      action.indexOf('sendData') >= 0 ||
      action.indexOf('sendMultipleData') >= 0 ||
      data.indexOf('/share') >= 0
    ) {
      this.pendingIntent = ResolvedIntentKind.IncomingShare;
    } else if (data.indexOf('mobile.element.io') >= 0) {
      this.pendingIntent = ResolvedIntentKind.Login;
    } else if (data.indexOf('matrix.to') >= 0 || data.indexOf('element.io') >= 0) {
      this.pendingIntent = ResolvedIntentKind.Permalink;
    } else if (data.indexOf('oauth') >= 0) {
      this.pendingIntent = ResolvedIntentKind.OAuth;
    } else if (data.indexOf('room') >= 0) {
      this.pendingIntent = ResolvedIntentKind.Navigation;
    } else {
      this.pendingIntent = ResolvedIntentKind.None;
    }
    return this.pendingIntent;
  }

  clearIntent(): void {
    this.pendingIntent = ResolvedIntentKind.None;
  }

  selectRoom(roomId: string): void {
    if (this.hasRoom(roomId)) {
      this.selectedRoomId = roomId;
    }
  }

  updateSelectedRoomName(name: string): boolean {
    const room = this.getRooms().find((item: RoomSummary) => item.id === this.currentSelectedRoomId());
    if (room === undefined) {
      return false;
    }
    room.name = name.trim();
    return true;
  }

  updateSelectedRoomTopic(topic: string): boolean {
    const room = this.getRooms().find((item: RoomSummary) => item.id === this.currentSelectedRoomId());
    if (room === undefined) {
      return false;
    }
    room.topic = topic.trim();
    return true;
  }

  updateSelectedRoomOwnDisplayName(displayName: string): boolean {
    const roomId = this.currentSelectedRoomId();
    const trimmedDisplayName = displayName.trim();
    if (roomId.length === 0 || trimmedDisplayName.length === 0) {
      return false;
    }
    const existing = this.roomOwnDisplayNames.find((item: RoomOwnDisplayNameState) => item.roomId === roomId);
    if (existing !== undefined) {
      existing.displayName = trimmedDisplayName;
      return true;
    }
    this.roomOwnDisplayNames.push({
      roomId: roomId,
      displayName: trimmedDisplayName
    });
    return true;
  }

  leaveSelectedRoom(roomId: string): boolean {
    const targetRoomId = roomId.length > 0 ? roomId : this.currentSelectedRoomId();
    if (targetRoomId.length === 0 || !this.hasRoom(targetRoomId)) {
      return false;
    }
    const rooms = this.getRooms();
    this.removeRoomSummary(rooms, targetRoomId);
    this.removeRoomTimeline(targetRoomId);
    this.removeReadMarker(targetRoomId);
    this.removeOwnRoomDisplayName(targetRoomId);
    if (this.selectedRoomId === targetRoomId) {
      this.selectedRoomId = rooms.length > 0 ? rooms[0].id : '';
    }
    return true;
  }

  getProfile(userId: string): MatrixUser {
    const client = this.currentClientRuntime();
    const adapter: MatrixClientContract = new FixtureMatrixClientAdapter(client, this.getRooms(), this.getTimelineEvents(this.currentSelectedRoomId()));
    const profile = adapter.getProfile(userId);
    if (profile.ok && profile.value !== undefined) {
      return profile.value;
    }
    return {
      userId: userId,
      displayName: this.displayNameFromUserId(userId),
      avatarUrl: '',
      status: ''
    };
  }

  getRoomPreview(roomIdOrAlias: string, serverNames: string[]): RoomPreview {
    const client = this.currentClientRuntime();
    const adapter: MatrixClientContract = new FixtureMatrixClientAdapter(client, this.getRooms(), this.getTimelineEvents(this.currentSelectedRoomId()));
    const preview = adapter.getRoomPreview(roomIdOrAlias, serverNames);
    if (preview.ok && preview.value !== undefined) {
      return preview.value;
    }
    return {
      roomIdOrAlias: roomIdOrAlias,
      name: roomIdOrAlias,
      topic: 'Room preview unavailable',
      canJoin: false
    };
  }

  joinRoomByIdOrAlias(roomIdOrAlias: string, serverNames: string[]): RoomInfo {
    const client = this.currentClientRuntime();
    const adapter: MatrixClientContract = new FixtureMatrixClientAdapter(client, this.getRooms(), this.getTimelineEvents(this.currentSelectedRoomId()));
    const joined = adapter.joinRoomByIdOrAlias(roomIdOrAlias, serverNames);
    const fallbackRoomInfo: RoomInfo = {
      roomId: roomIdOrAlias,
      name: roomIdOrAlias,
      membership: 'join',
      isEncrypted: true
    };
    const roomInfo: RoomInfo = joined.ok && joined.value !== undefined ? joined.value : fallbackRoomInfo;
    this.upsertRoomSummary(roomInfo.roomId, roomInfo.name, 'Joined from permalink', false);
    this.upsertRoomTimeline(roomInfo.roomId, []);
    this.selectedRoomId = roomInfo.roomId;
    return roomInfo;
  }

  createDirectRoom(userId: string): RoomInfo {
    return this.createDirectRoomFromResolvedRoom(userId, '');
  }

  createDirectRoomFromResolvedRoom(userId: string, resolvedRoomId: string): RoomInfo {
    const client = this.currentClientRuntime();
    const adapter: MatrixClientContract = new FixtureMatrixClientAdapter(client, this.getRooms(), this.getTimelineEvents(this.currentSelectedRoomId()));
    const existing = adapter.findDM(userId);
    const roomId = existing.ok && existing.value !== undefined && existing.value.length > 0
      ? existing.value
      : resolvedRoomId.length > 0 ? resolvedRoomId : `!dm-${this.displayNameFromUserId(userId).toLowerCase()}:${client.homeserver}`;
    const displayName = this.displayNameFromUserId(userId);
    this.upsertRoomSummary(roomId, displayName, 'Direct message - encrypted', true);
    this.upsertRoomTimeline(roomId, []);
    this.selectedRoomId = roomId;
    return {
      roomId: roomId,
      name: displayName,
      membership: 'join',
      isEncrypted: true
    };
  }

  appendLocalTimelineMessage(sender: string, roomId: string, body: string): void {
    this.appendLocalTimelineEvent(sender, roomId, body, TimelineEventKind.Text);
  }

  appendLocalTimelineEvent(sender: string, roomId: string, body: string, kind: TimelineEventKind): void {
    this.selectRoom(roomId);
    const effectiveRoomId = this.currentSelectedRoomId();
    const events = this.getTimelineEvents(effectiveRoomId);
    const event: TimelineEvent = {
      id: `local-${new Date().getTime()}`,
      roomId: effectiveRoomId,
      sender: this.localTimelineSenderLabel(sender, effectiveRoomId),
      senderUserId: sender,
      timestamp: this.localTimeLabel(),
      kind: kind,
      body: body,
      supported: true
    };
    this.upsertRoomTimeline(effectiveRoomId, [event, ...events]);
    this.syncedTimeline = this.flattenTimelines();
  }

  appendLocalMediaMessage(sender: string, roomId: string, caption: string, attachmentRows: string[]): void {
    if (attachmentRows.length === 0) {
      this.appendLocalTimelineMessage(sender, roomId, caption);
      return;
    }
    this.selectRoom(roomId);
    const effectiveRoomId = this.currentSelectedRoomId();
    const events = this.getTimelineEvents(effectiveRoomId);
    const firstAttachment = attachmentRows[0];
    const firstMimeType = this.mimeTypeFromAttachmentRow(firstAttachment);
    const eventKind = attachmentRows.length > 1 ? TimelineEventKind.Gallery : this.mediaKindFromMimeType(firstMimeType);
    const body = attachmentRows.length > 1
      ? this.mediaBodyLabel(caption, 'Shared gallery')
      : this.mediaBodyLabel(caption, this.singleMediaLabel(eventKind));
    const event: TimelineEvent = {
      id: `local-media-${new Date().getTime()}`,
      roomId: effectiveRoomId,
      sender: this.localTimelineSenderLabel(sender, effectiveRoomId),
      senderUserId: sender,
      timestamp: this.localTimeLabel(),
      kind: eventKind,
      body: body,
      mediaCount: attachmentRows.length,
      mediaUri: this.uriFromAttachmentRow(firstAttachment),
      mimeType: firstMimeType,
      mediaSize: 0,
      caption: caption.trim(),
      mediaItems: this.mediaItemsFromAttachmentRows(attachmentRows),
      supported: true
    };
    this.upsertRoomTimeline(effectiveRoomId, [event, ...events]);
    this.syncedTimeline = this.flattenTimelines();
  }

  ensureTimelineContainsEvent(roomId: string, eventId: string): void {
    if (roomId.length === 0 || eventId.length === 0) {
      return;
    }
    this.selectRoom(roomId);
    const effectiveRoomId = this.currentSelectedRoomId();
    const events = this.getTimelineEvents(effectiveRoomId);
    if (events.find((event: TimelineEvent) => event.id === eventId) !== undefined) {
      return;
    }
    const event: TimelineEvent = {
      id: eventId,
      roomId: effectiveRoomId,
      sender: 'Permalink',
      timestamp: this.localTimeLabel(),
      kind: TimelineEventKind.Text,
      body: `Loaded focused event ${eventId}`,
      supported: true
    };
    this.upsertRoomTimeline(effectiveRoomId, [event, ...events]);
    this.syncedTimeline = this.flattenTimelines();
  }

  markRoomAsRead(roomId: string): void {
    const room = this.getRooms().find((item: RoomSummary) => item.id === roomId);
    if (room !== undefined) {
      room.unreadCount = 0;
      room.isMarkedUnread = false;
    }
    const eventId = this.latestTimelineEventId(roomId);
    if (eventId.length > 0) {
      this.rememberReadMarker(roomId, eventId);
    }
  }

  markRoomAsUnread(roomId: string): boolean {
    const room = this.getRooms().find((item: RoomSummary) => item.id === roomId);
    if (room === undefined) {
      return false;
    }
    room.isMarkedUnread = true;
    return true;
  }

  clearRoomUnreadFlag(roomId: string): boolean {
    const room = this.getRooms().find((item: RoomSummary) => item.id === roomId);
    if (room === undefined) {
      return false;
    }
    room.isMarkedUnread = false;
    return true;
  }

  isRoomMarkedUnread(roomId: string): boolean {
    const room = this.getRooms().find((item: RoomSummary) => item.id === roomId);
    return room !== undefined && room.isMarkedUnread;
  }

  setRoomIsFavorite(roomId: string, isFavorite: boolean): boolean {
    const room = this.getRooms().find((item: RoomSummary) => item.id === roomId);
    if (room === undefined) {
      return false;
    }
    room.isFavorite = isFavorite;
    return true;
  }

  reportRoom(roomId: string, reason: string): boolean {
    const room = this.getRooms().find((item: RoomSummary) => item.id === roomId);
    if (room === undefined) {
      return false;
    }
    this.roomReports.push({
      roomId: roomId,
      reason: reason.trim(),
      timestamp: this.localTimeLabel()
    });
    return true;
  }

  markAllRoomsAsRead(): void {
    this.getRooms().forEach((room: RoomSummary) => {
      this.markRoomAsRead(room.id);
    });
  }

  latestTimelineEventId(roomId: string): string {
    const events = this.getTimelineEvents(roomId);
    if (events.length === 0) {
      return '';
    }
    return events[0].id;
  }

  shouldAutoMarkRoomAsRead(roomId: string): boolean {
    const latestEventId = this.latestTimelineEventId(roomId);
    if (latestEventId.length === 0) {
      return false;
    }
    const marker = this.readMarkers.find((item: RoomReadMarkerState) => item.roomId === roomId);
    return marker === undefined || marker.eventId !== latestEventId;
  }

  updateOwnProfile(sessionId: string, displayName: string, userStatus: string, avatarUrl: string): ClientSession | null {
    const record = this.sessions.find((item: SessionStoreRecord) => item.userId === sessionId);
    if (record === undefined) {
      return null;
    }
    const safeDisplayName = displayName.trim().length > 0 ? displayName.trim() : this.displayNameFromUserId(record.userId);
    record.displayName = safeDisplayName;
    record.userStatus = userStatus.trim();
    record.avatarUrl = avatarUrl;
    const client = this.getOrRestore(sessionId);
    client.displayName = record.displayName;
    client.userStatus = record.userStatus;
    client.avatarUrl = record.avatarUrl;
    return this.sessionFromRecord(record);
  }

  updateReadReceiptPreference(sessionId: string, sendPublicReadReceipts: boolean): ClientSession | null {
    const record = this.sessions.find((item: SessionStoreRecord) => item.userId === sessionId);
    if (record === undefined) {
      return null;
    }
    record.sendPublicReadReceipts = sendPublicReadReceipts;
    record.renderReadReceipts = sendPublicReadReceipts;
    const client = this.getOrRestore(sessionId);
    client.sendPublicReadReceipts = sendPublicReadReceipts;
    client.renderReadReceipts = sendPublicReadReceipts;
    return this.sessionFromRecord(record);
  }

  updateTimelineMediaPreviewMode(sessionId: string, mode: TimelineMediaPreviewMode): ClientSession | null {
    const record = this.sessions.find((item: SessionStoreRecord) => item.userId === sessionId);
    if (record === undefined) {
      return null;
    }
    record.timelineMediaPreviewMode = mode;
    const client = this.getOrRestore(sessionId);
    client.timelineMediaPreviewMode = mode;
    return this.sessionFromRecord(record);
  }

  updateNextSyncBatch(sessionId: string, nextSyncBatch: string): ClientSession | null {
    const record = this.sessions.find((item: SessionStoreRecord) => item.userId === sessionId);
    if (record === undefined) {
      return null;
    }
    record.nextSyncBatch = nextSyncBatch;
    const client = this.getOrRestore(sessionId);
    client.nextSyncBatch = nextSyncBatch;
    return this.sessionFromRecord(record);
  }

  isUserIgnored(sessionId: string, userId: string): boolean {
    const record = this.sessions.find((item: SessionStoreRecord) => item.userId === sessionId);
    if (record === undefined) {
      return false;
    }
    return this.normalizedUserIds(record.ignoredUsers).includes(userId.trim());
  }

  replaceIgnoredUsers(sessionId: string, ignoredUsers: string[]): ClientSession | null {
    const record = this.sessions.find((item: SessionStoreRecord) => item.userId === sessionId);
    if (record === undefined) {
      return null;
    }
    record.ignoredUsers = this.normalizedUserIds(ignoredUsers);
    const client = this.getOrRestore(sessionId);
    client.ignoredUsers = this.normalizedUserIds(record.ignoredUsers);
    return this.sessionFromRecord(record);
  }

  updateHomeserverCapabilities(sessionId: string, capabilities: HomeserverCapabilitiesState): ClientSession | null {
    const record = this.sessions.find((item: SessionStoreRecord) => item.userId === sessionId);
    if (record === undefined) {
      return null;
    }
    const client = this.getOrRestore(sessionId);
    client.homeserverCapabilities = capabilities;
    return this.sessionFromRecord(record);
  }

  updateIgnoredUser(sessionId: string, userId: string, ignored: boolean): ClientSession | null {
    const record = this.sessions.find((item: SessionStoreRecord) => item.userId === sessionId);
    if (record === undefined) {
      return null;
    }
    const targetUserId = userId.trim();
    if (targetUserId.length === 0) {
      return this.sessionFromRecord(record);
    }
    const ignoredUsers = this.normalizedUserIds(record.ignoredUsers);
    if (ignored && !ignoredUsers.includes(targetUserId)) {
      ignoredUsers.push(targetUserId);
    }
    if (!ignored) {
      const index = ignoredUsers.indexOf(targetUserId);
      if (index >= 0) {
        ignoredUsers.splice(index, 1);
      }
    }
    record.ignoredUsers = this.normalizedUserIds(ignoredUsers);
    const client = this.getOrRestore(sessionId);
    client.ignoredUsers = this.normalizedUserIds(record.ignoredUsers);
    return this.sessionFromRecord(record);
  }

  private upsertSession(record: SessionStoreRecord): void {
    const index = this.sessions.findIndex((item: SessionStoreRecord) => item.userId === record.userId);
    if (index >= 0) {
      this.sessions[index] = record;
    } else {
      this.sessions.push(record);
    }
  }

  private removeSession(sessionId: string): void {
    const sessionIndex = this.sessions.findIndex((item: SessionStoreRecord) => item.userId === sessionId);
    if (sessionIndex >= 0) {
      this.sessions.splice(sessionIndex, 1);
    }
    const clientIndex = this.clients.findIndex((item: MatrixClientRuntime) => item.sessionId === sessionId);
    if (clientIndex >= 0) {
      this.clients.splice(clientIndex, 1);
    }
  }

  private getLatestSession(): SessionStoreRecord | null {
    if (this.latestSessionId.length > 0) {
      const latest = this.sessions.find((item: SessionStoreRecord) => item.userId === this.latestSessionId);
      if (latest !== undefined) {
        return latest;
      }
    }
    if (this.sessions.length === 0) {
      return null;
    }
    return this.sessions.sort((left: SessionStoreRecord, right: SessionStoreRecord) => {
      return right.lastUsageIndex - left.lastUsageIndex;
    })[0];
  }

  private putClient(client: MatrixClientRuntime): void {
    const index = this.clients.findIndex((item: MatrixClientRuntime) => item.sessionId === client.sessionId);
    if (index >= 0) {
      this.clients[index] = client;
    } else {
      this.clients.push(client);
    }
  }

  private getOrRestore(sessionId: string): MatrixClientRuntime {
    const cached = this.clients.find((item: MatrixClientRuntime) => item.sessionId === sessionId);
    if (cached !== undefined) {
      return cached;
    }
    const record = this.sessions.find((item: SessionStoreRecord) => item.userId === sessionId);
    if (record !== undefined) {
      const restored = this.createClientRuntime(record.userId, record.userId, record.deviceId, record.homeserver, record.accessToken, record.nextSyncBatch, record.ignoredUsers, record.displayName, record.avatarUrl, record.userStatus, record.sendPublicReadReceipts, record.renderReadReceipts, record.timelineMediaPreviewMode);
      this.putClient(restored);
      return restored;
    }
    return this.createClientRuntime(sessionId, sessionId, 'HARMONYSDK23', 'matrix.org', '', '', [], this.displayNameFromUserId(sessionId), '', '', true, true, TimelineMediaPreviewMode.AlwaysShow);
  }

  private createRootNavState(sessionId: string | null, targetKind: RootNavTargetKind): RootNavState {
    return {
      cacheIndex: this.cacheIndex,
      isLoggedIn: sessionId !== null,
      isTokenValid: sessionId !== null,
      currentTarget: {
        kind: targetKind,
        sessionId: sessionId ?? '',
        navId: this.cacheIndex,
        pendingLoginProvider: this.pendingIntent === ResolvedIntentKind.Login ? 'mobile.element.io' : ''
      },
      pendingIntent: this.pendingIntent
    };
  }

  private mediaKindFromMimeType(mimeType: string): TimelineEventKind {
    if (mimeType.indexOf('image/') === 0) {
      return TimelineEventKind.Image;
    }
    if (mimeType.indexOf('video/') === 0) {
      return TimelineEventKind.Video;
    }
    if (mimeType.indexOf('audio/') === 0) {
      return TimelineEventKind.Audio;
    }
    return TimelineEventKind.File;
  }

  private singleMediaLabel(kind: TimelineEventKind): string {
    if (kind === TimelineEventKind.Image) {
      return 'Shared image';
    }
    if (kind === TimelineEventKind.Video) {
      return 'Shared video';
    }
    if (kind === TimelineEventKind.Audio) {
      return 'Shared audio';
    }
    return 'Shared file';
  }

  private mediaBodyLabel(caption: string, fallback: string): string {
    const trimmedCaption = caption.trim();
    if (trimmedCaption.length > 0) {
      return trimmedCaption;
    }
    return fallback;
  }

  private localTimelineSenderLabel(sender: string, roomId: string): string {
    const roomDisplayName = this.roomOwnDisplayNames.find((item: RoomOwnDisplayNameState) => item.roomId === roomId);
    if (roomDisplayName !== undefined && roomDisplayName.displayName.length > 0) {
      return roomDisplayName.displayName;
    }
    return sender;
  }

  private removeRoomSummary(rooms: RoomSummary[], roomId: string): void {
    const index = rooms.findIndex((item: RoomSummary) => item.id === roomId);
    if (index >= 0) {
      rooms.splice(index, 1);
    }
  }

  private removeRoomTimeline(roomId: string): void {
    const syncedIndex = this.syncedRoomTimelines.findIndex((item: RoomTimelineState) => item.roomId === roomId);
    if (syncedIndex >= 0) {
      this.syncedRoomTimelines.splice(syncedIndex, 1);
    }
    this.syncedTimeline = this.flattenTimelines();
  }

  private removeReadMarker(roomId: string): void {
    const index = this.readMarkers.findIndex((item: RoomReadMarkerState) => item.roomId === roomId);
    if (index >= 0) {
      this.readMarkers.splice(index, 1);
    }
  }

  private removeOwnRoomDisplayName(roomId: string): void {
    const index = this.roomOwnDisplayNames.findIndex((item: RoomOwnDisplayNameState) => item.roomId === roomId);
    if (index >= 0) {
      this.roomOwnDisplayNames.splice(index, 1);
    }
  }

  private mimeTypeFromAttachmentRow(row: string): string {
    const divider = row.indexOf(' ');
    if (divider <= 0) {
      return 'application/octet-stream';
    }
    const mimeType = row.substring(0, divider).trim();
    return mimeType.length > 0 ? mimeType : 'application/octet-stream';
  }

  private uriFromAttachmentRow(row: string): string {
    const divider = row.indexOf(' ');
    if (divider < 0 || divider >= row.length - 1) {
      return row.trim();
    }
    return row.substring(divider + 1).trim();
  }

  private mediaItemsFromAttachmentRows(rows: string[]): TimelineMediaItem[] {
    const items: TimelineMediaItem[] = [];
    for (let index = 0; index < rows.length; index += 1) {
      const row = rows[index];
      items.push({
        uri: this.uriFromAttachmentRow(row),
        mimeType: this.mimeTypeFromAttachmentRow(row),
        size: 0
      });
    }
    return items;
  }

  private createClientRuntime(
    sessionId: string,
    userId: string,
    deviceId: string,
    homeserver: string,
    accessToken: string,
    nextSyncBatch: string,
    ignoredUsers: string[],
    displayName: string,
    avatarUrl: string,
    userStatus: string,
    sendPublicReadReceipts: boolean,
    renderReadReceipts: boolean,
    timelineMediaPreviewMode: TimelineMediaPreviewMode
  ): MatrixClientRuntime {
    return {
      sessionId: sessionId,
      userId: userId,
      deviceId: deviceId,
      homeserver: homeserver,
      accessToken: accessToken,
      nextSyncBatch: nextSyncBatch,
      ignoredUsers: this.normalizedUserIds(ignoredUsers),
      displayName: displayName,
      avatarUrl: avatarUrl,
      userStatus: userStatus,
      sendPublicReadReceipts: sendPublicReadReceipts,
      renderReadReceipts: renderReadReceipts,
      timelineMediaPreviewMode: timelineMediaPreviewMode,
      isShuttingDown: false,
      syncService: this.createRunningSyncState(),
      homeserverCapabilities: this.createHomeserverCapabilities()
    };
  }

  private createRunningSyncState(): SyncRuntimeState {
    return {
      serviceState: SyncServiceState.Running,
      indicatorState: SyncIndicatorState.Hidden,
      appForeground: true,
      inCall: false,
      sharingLiveLocation: true,
      firstSyncState: SyncServiceState.Running
    };
  }

  private createHomeserverCapabilities(): HomeserverCapabilitiesState {
    return {
      canChangeDisplayName: true,
      canChangeAvatarUrl: true,
      canDeactivateAccount: true,
      canReportRoom: true,
      canLinkNewDevice: true,
      maxFileUploadSizeBytes: 104857600,
      livekitRtcSupported: true
    };
  }

  private createLoggedInState(client: MatrixClientRuntime): LoggedInRuntimeState {
    return {
      sync: client.syncService,
      pusherRegistrationState: this.createSuccessState('Registered'),
      ignoreRegistrationError: false,
      forceNativeSlidingSyncMigration: false,
      appName: 'Element X',
      localNetworkPermissionDialog: LocalNetworkPermissionDialog.Hidden,
      verificationStatus: SessionVerificationStatus.Verified,
      recoveryState: RecoveryState.Enabled,
      networkStatus: NetworkStatus.Connected,
      automaticCallStatusEnabled: true
    };
  }

  private createSuccessState(message: string): AsyncDataState {
    return {
      status: AsyncDataStatus.Success,
      message: message
    };
  }

  private getFeatureFlags(): BaseFeatureFlags {
    return {
      userStatus: true,
      galleryMessages: true,
      activeCallTimeline: true,
      liveLocationSharing: true,
      richLinkNewDevice: true
    };
  }

  private getRooms(): RoomSummary[] {
    if (this.syncedRooms.length > 0) {
      return this.syncedRooms;
    }
    return this.fixtureRooms;
  }

  private currentClientRuntime(): MatrixClientRuntime {
    if (this.latestSessionId.length > 0) {
      return this.getOrRestore(this.latestSessionId);
    }
    return this.createClientRuntime('', '@alice:matrix.org', 'HARMONYSDK23', 'matrix.org', '', '', [], 'Alice', '', '', true, true, TimelineMediaPreviewMode.AlwaysShow);
  }

  private upsertRoomSummary(roomId: string, name: string, topic: string, isDirect: boolean): void {
    const rooms = this.getRooms();
    const existing = rooms.find((item: RoomSummary) => item.id === roomId);
    if (existing !== undefined) {
      existing.name = name;
      existing.topic = topic;
      existing.isDirect = isDirect;
      return;
    }
    rooms.push({
      id: roomId,
      name: name,
      topic: topic,
      unreadCount: 0,
      isMarkedUnread: false,
      isFavorite: false,
      isDirect: isDirect
    });
  }

  private getTimelineEvents(roomId: string): TimelineEvent[] {
    const synced = this.syncedRoomTimelines.find((item: RoomTimelineState) => item.roomId === roomId);
    let events: TimelineEvent[] = [];
    if (synced !== undefined) {
      events = synced.events;
    } else {
      events = this.getFixtureTimelineEvents(roomId);
    }
    return this.filterIgnoredTimelineEvents(events, this.currentIgnoredUsers());
  }

  private filterIgnoredTimelineEvents(events: TimelineEvent[], ignoredUsers: string[]): TimelineEvent[] {
    if (ignoredUsers.length === 0) {
      return events;
    }
    const visibleEvents: TimelineEvent[] = [];
    events.forEach((event: TimelineEvent) => {
      if (this.isIgnoredEvent(event, ignoredUsers)) {
        return;
      }
      const copy = this.copyTimelineEvent(event);
      if (copy.readReceipts !== undefined) {
        copy.readReceipts = copy.readReceipts.filter((receipt: ReadReceiptSummary) => !ignoredUsers.includes(receipt.userId));
      }
      visibleEvents.push(copy);
    });
    return visibleEvents;
  }

  private isIgnoredEvent(event: TimelineEvent, ignoredUsers: string[]): boolean {
    const senderUserId = this.eventSenderUserId(event);
    return senderUserId.length > 0 && ignoredUsers.includes(senderUserId);
  }

  private eventSenderUserId(event: TimelineEvent): string {
    if (event.senderUserId !== undefined && event.senderUserId.trim().length > 0) {
      return event.senderUserId.trim();
    }
    if (event.sender.startsWith('@')) {
      return event.sender.trim();
    }
    return '';
  }

  private currentIgnoredUsers(): string[] {
    if (this.latestSessionId.length === 0) {
      return [];
    }
    const record = this.sessions.find((item: SessionStoreRecord) => item.userId === this.latestSessionId);
    if (record === undefined) {
      return [];
    }
    return this.normalizedUserIds(record.ignoredUsers);
  }

  private copyTimelineEvent(event: TimelineEvent): TimelineEvent {
    return {
      id: event.id,
      roomId: event.roomId,
      sender: event.sender,
      senderUserId: event.senderUserId,
      timestamp: event.timestamp,
      kind: event.kind,
      body: event.body,
      mediaCount: event.mediaCount,
      mediaUri: event.mediaUri,
      mimeType: event.mimeType,
      mediaSize: event.mediaSize,
      caption: event.caption,
      mediaItems: event.mediaItems === undefined ? undefined : event.mediaItems.slice(),
      readReceipts: event.readReceipts === undefined ? undefined : event.readReceipts.slice(),
      supported: event.supported
    };
  }

  private getFixtureTimelineEvents(roomId: string): TimelineEvent[] {
    if (roomId === 'room-design') {
      return [
        {
          id: 'evt-design-001',
          roomId: roomId,
          sender: 'Jamie',
          senderUserId: '@jamie:matrix.org',
          timestamp: '10:02',
          kind: TimelineEventKind.Text,
          body: 'Can we keep the room list density close to Android?',
          readReceipts: [
            {
              userId: '@sam:matrix.org',
              displayName: 'Sam',
              avatarInitials: 'SM',
              timestamp: '10:07'
            }
          ],
          supported: true
        },
        {
          id: 'evt-design-002',
          roomId: roomId,
          sender: 'Alice',
          senderUserId: '@alice:matrix.org',
          timestamp: '10:04',
          kind: TimelineEventKind.Text,
          body: 'Yes, selected room state is now shared with the timeline.',
          supported: true
        }
      ];
    }
    if (roomId === 'dm-bob') {
      return [
        {
          id: 'evt-dm-bob-001',
          roomId: roomId,
          sender: 'Bob',
          senderUserId: '@bob:matrix.org',
          timestamp: '11:20',
          kind: TimelineEventKind.Text,
          body: 'Direct message timeline is separate from the room timeline.',
          readReceipts: [
            {
              userId: '@alice:matrix.org',
              displayName: 'Alice',
              avatarInitials: 'AL',
              timestamp: '11:22'
            }
          ],
          supported: true
        }
      ];
    }
    return [
      {
        id: 'evt-001',
        roomId: roomId,
        sender: 'Alice',
        senderUserId: '@alice:matrix.org',
        timestamp: '09:20',
        kind: TimelineEventKind.Text,
        body: 'Morning! The latest room sync is in.',
        readReceipts: [
          {
            userId: '@bob:matrix.org',
            displayName: 'Bob',
            avatarInitials: 'BO',
            timestamp: '09:24'
          },
          {
            userId: '@dana:matrix.org',
            displayName: 'Dana',
            avatarInitials: 'DA',
            timestamp: '09:27'
          }
        ],
        supported: true
      },
      {
        id: 'evt-gallery-fixture',
        roomId: roomId,
        sender: 'Dana',
        senderUserId: '@dana:matrix.org',
        timestamp: '09:31',
        kind: TimelineEventKind.Gallery,
        body: 'Gallery message fixture',
        mediaCount: 4,
        mediaUri: 'file:///storage/media/gallery-1.jpg',
        mimeType: 'image/jpeg',
        mediaItems: [
          {
            uri: 'file:///storage/media/gallery-1.jpg',
            mimeType: 'image/jpeg',
            size: 0
          },
          {
            uri: 'file:///storage/media/gallery-2.jpg',
            mimeType: 'image/jpeg',
            size: 0
          },
          {
            uri: 'file:///storage/media/gallery-3.jpg',
            mimeType: 'image/jpeg',
            size: 0
          },
          {
            uri: 'file:///storage/media/gallery-4.jpg',
            mimeType: 'image/jpeg',
            size: 0
          }
        ],
        supported: true
      },
      {
        id: 'evt-call-fixture',
        roomId: roomId,
        sender: 'Element Call',
        senderUserId: '@element-call:matrix.org',
        timestamp: '09:35',
        kind: TimelineEventKind.ActiveCall,
        body: 'Active call is available in this room',
        supported: true
      },
      {
        id: 'evt-live-location-fixture',
        roomId: roomId,
        sender: 'Bob',
        senderUserId: '@bob:matrix.org',
        timestamp: '09:41',
        kind: TimelineEventKind.LiveLocation,
        body: 'Live location sharing active',
        supported: true
      }
    ];
  }

  private getFeatureStatusRows(client: MatrixClientRuntime): string[] {
    return [
      `Display name: ${client.displayName}`,
      `User status: ${client.userStatus.length > 0 ? client.userStatus : 'None'}`,
      `Read receipts: ${client.sendPublicReadReceipts ? 'public' : 'private'}`,
      'Gallery messages: 4 attachments',
      'Active call: available',
      'Live location: sharing',
      'Link new device: ready'
    ];
  }

  private getDeviceRows(): string[] {
    return [
      'This device: Harmony SDK 23',
      'Link new device: QR flow ready',
      'Owner verification: verified',
      'QR rotation: refreshable',
      'Timeout handling: available'
    ];
  }

  private getSecurityRows(): string[] {
    return [
      'Session verification: verified',
      'Recovery key: enabled',
      'Device list: available',
      'Cross-signing status: verified'
    ];
  }

  private getSignedOutRuntimeRows(): string[] {
    return [
      'Root: NotLoggedInFlow',
      'Session cache: empty',
      'Pending intent: none'
    ];
  }

  private getRuntimeRows(loggedInState: LoggedInRuntimeState, client: MatrixClientRuntime): string[] {
    const adapter: MatrixClientContract = new FixtureMatrixClientAdapter(client, this.getRooms(), this.getTimelineEvents(this.currentSelectedRoomId()));
    const joinedRoomIds = adapter.getJoinedRoomIds();
    const profile = adapter.getUserProfile();
    const uploadLimit = adapter.getMaxFileUploadSize();
    return [
      `Root: LoggedInFlow cache=${this.cacheIndex}`,
      `Matrix client: ${profile.value?.userId ?? client.userId}`,
      `Joined rooms: ${joinedRoomIds.value?.length ?? 0}`,
      `Sync: ${loggedInState.sync.serviceState}`,
      `Sync batch: ${client.nextSyncBatch.length > 0 ? client.nextSyncBatch : 'not started'}`,
      `Ignored users: ${client.ignoredUsers.length}`,
      `Push: ${loggedInState.pusherRegistrationState.message}`,
      `Network: ${loggedInState.networkStatus}`,
      `Verification: ${loggedInState.verificationStatus}`,
      `Recovery: ${loggedInState.recoveryState}`,
      `Homeserver upload limit: ${uploadLimit.value ?? client.homeserverCapabilities.maxFileUploadSizeBytes} bytes`
    ];
  }

  private getIntentRows(): string[] {
    return [
      `Resolved intent: ${this.pendingIntent}`,
      'Navigation link: room and thread targets',
      'Permalink: matrix.to and element.io',
      'Incoming share: single and multiple payloads',
      'OAuth/login link: pending-login route'
    ];
  }

  private displayNameFromUserId(userId: string): string {
    const withoutAt = userId.startsWith('@') ? userId.substring(1) : userId;
    const localpart = withoutAt.split(':')[0];
    if (localpart.length === 0) {
      return 'Alice';
    }
    return `${localpart.substring(0, 1).toUpperCase()}${localpart.substring(1)}`;
  }

  private sessionFromRecord(record: SessionStoreRecord): ClientSession {
    const displayName = record.displayName.length > 0 ? record.displayName : this.displayNameFromUserId(record.userId);
    return {
      sessionId: record.userId,
      homeserver: record.homeserver,
      deviceId: record.deviceId,
      accessToken: record.accessToken,
      nextSyncBatch: record.nextSyncBatch,
      ignoredUsers: this.normalizedUserIds(record.ignoredUsers),
      sendPublicReadReceipts: record.sendPublicReadReceipts,
      renderReadReceipts: record.renderReadReceipts,
      timelineMediaPreviewMode: record.timelineMediaPreviewMode,
      account: {
        userId: record.userId,
        displayName: displayName,
        avatarInitials: displayName.substring(0, 2).toUpperCase(),
        avatarUrl: record.avatarUrl,
        userStatus: record.userStatus,
        canSetUserStatus: true
      }
    };
  }

  private normalizedUserIds(value: string[] | undefined): string[] {
    if (value === undefined || value === null) {
      return [];
    }
    const result: string[] = [];
    value.forEach((item: string) => {
      const userId = item.trim();
      if (userId.length > 0 && !result.includes(userId)) {
        result.push(userId);
      }
    });
    return result.sort();
  }

  private localTimeLabel(): string {
    const date = new Date();
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
  }

  private hasRoom(roomId: string): boolean {
    return this.getRooms().find((item: RoomSummary) => item.id === roomId) !== undefined;
  }

  private currentSelectedRoomId(): string {
    if (this.hasRoom(this.selectedRoomId)) {
      return this.selectedRoomId;
    }
    const rooms = this.getRooms();
    if (rooms.length === 0) {
      return '';
    }
    this.selectedRoomId = rooms[0].id;
    return this.selectedRoomId;
  }

  private upsertRoomTimeline(roomId: string, events: TimelineEvent[]): void {
    const index = this.syncedRoomTimelines.findIndex((item: RoomTimelineState) => item.roomId === roomId);
    const state: RoomTimelineState = {
      roomId: roomId,
      events: events
    };
    if (index >= 0) {
      this.syncedRoomTimelines[index] = state;
    } else {
      this.syncedRoomTimelines.push(state);
    }
  }

  private rememberReadMarker(roomId: string, eventId: string): void {
    const index = this.readMarkers.findIndex((item: RoomReadMarkerState) => item.roomId === roomId);
    const marker: RoomReadMarkerState = {
      roomId: roomId,
      eventId: eventId
    };
    if (index >= 0) {
      this.readMarkers[index] = marker;
    } else {
      this.readMarkers.push(marker);
    }
  }

  private flattenTimelines(): TimelineEvent[] {
    const events: TimelineEvent[] = [];
    this.syncedRoomTimelines.forEach((item: RoomTimelineState) => {
      events.push(...item.events);
    });
    return events;
  }
}
