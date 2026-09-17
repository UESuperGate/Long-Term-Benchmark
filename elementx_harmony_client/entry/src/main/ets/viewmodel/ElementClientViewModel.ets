import { ClientSession, ClientSnapshot } from '../model/ClientModels';
import common from '@ohos.app.ability.common';
import { PersistedSessionSnapshot, PersistentSessionStore } from '../services/PersistentSessionStore';
import { MatrixClientServerApi, MatrixCreateRoomResponse, MatrixHttpResult, MatrixIgnoredUsersResponse, MatrixJoinRoomResponse, MatrixLoginResponse, MatrixMediaUploadResponse, MatrixProfileResponse, MatrixSyncResponse, MatrixWellKnownResult } from '../services/MatrixClientServerApi';
import { MatrixClientService } from '../services/MatrixClientService';
import { MatrixUser, RoomInfo, RoomPreview } from '../services/MatrixClientContract';
import { SharedMediaFileReader, SharedMediaReadResult } from '../services/SharedMediaFileReader';
import { HomeserverCapabilitiesState, TimelineMediaPreviewMode } from '../model/ClientRuntimeModels';
import { TimelineEventKind } from '../model/ElementModels';

export interface SignInResult {
  ok: boolean;
  snapshot: ClientSnapshot;
  errorMessage: string;
  usedFixture: boolean;
}

export interface SendMessageResult {
  ok: boolean;
  snapshot: ClientSnapshot;
  errorMessage: string;
}

export interface UpdateProfileResult {
  ok: boolean;
  snapshot: ClientSnapshot;
  errorMessage: string;
}

export interface UpdateRoomMetadataResult {
  ok: boolean;
  snapshot: ClientSnapshot;
  errorMessage: string;
}

export interface UpdateRoomMembershipResult {
  ok: boolean;
  snapshot: ClientSnapshot;
  errorMessage: string;
}

export interface MarkRoomReadResult {
  ok: boolean;
  snapshot: ClientSnapshot;
  errorMessage: string;
}

export interface UpdateReadReceiptPreferenceResult {
  ok: boolean;
  snapshot: ClientSnapshot;
  errorMessage: string;
}

export interface UpdateTimelineMediaPreviewModeResult {
  ok: boolean;
  snapshot: ClientSnapshot;
  errorMessage: string;
}

export interface UpdateIgnoredUserResult {
  ok: boolean;
  snapshot: ClientSnapshot;
  ignored: boolean;
  errorMessage: string;
}

export interface ForegroundSyncResult {
  ok: boolean;
  snapshot: ClientSnapshot;
  errorMessage: string;
  skipped: boolean;
  nextBatch: string;
}

export interface UserProfileResult {
  ok: boolean;
  profile: MatrixUser | null;
  errorMessage: string;
}

export interface RoomPreviewResult {
  ok: boolean;
  preview: RoomPreview | null;
  errorMessage: string;
}

export interface JoinRoomResult {
  ok: boolean;
  snapshot: ClientSnapshot;
  roomInfo: RoomInfo | null;
  errorMessage: string;
}

interface MatrixVersionsContent {
  versions?: string[];
  unstable_features?: Record<string, boolean>;
}

export class ElementClientViewModel {
  private readonly service: MatrixClientService = new MatrixClientService();
  private readonly serverApi: MatrixClientServerApi = new MatrixClientServerApi();
  private readonly sessionStore: PersistentSessionStore = new PersistentSessionStore();
  private readonly sharedMediaFileReader: SharedMediaFileReader = new SharedMediaFileReader();

  getSignedOutSnapshot(): ClientSnapshot {
    return this.service.getSignedOutSnapshot();
  }

  restoreLatestSession(): ClientSnapshot {
    return this.service.restoreLatestSession();
  }

  async restorePersistedLatestSession(context: common.UIAbilityContext): Promise<ClientSnapshot> {
    const persisted = await this.sessionStore.load(context);
    this.service.hydrateSessionStore(persisted.latestSessionId, persisted.sessions);
    return this.service.restoreLatestSession();
  }

  signInWithFixture(homeserver: string, username: string): ClientSnapshot {
    const session: ClientSession = this.service.createFixtureSession(homeserver, username);
    return this.service.getSignedInSnapshot(session);
  }

  async signIn(homeserver: string, username: string, password: string, context: common.UIAbilityContext): Promise<SignInResult> {
    if (password.trim().length === 0) {
      const snapshot = this.signInWithFixture(homeserver, username);
      await this.persistCurrentStore(context);
      return this.createSignInResult(true, snapshot, '', true);
    }

    const wellKnown: MatrixWellKnownResult = await this.serverApi.discoverHomeserver(homeserver);
    if (!wellKnown.ok) {
      return this.createSignInResult(false, this.service.getSignedOutSnapshot(), wellKnown.errorMessage, false);
    }

    const login: MatrixLoginResponse = await this.serverApi.loginWithPassword(
      wellKnown.homeserverBaseUrl,
      username,
      password,
      'Element X Harmony API 23'
    );
    if (!login.ok || login.accessToken.length === 0 || login.userId.length === 0) {
      const message = login.errorMessage.length > 0 ? login.errorMessage : 'Matrix password login did not return a session';
      return this.createSignInResult(false, this.service.getSignedOutSnapshot(), message, false);
    }
    return await this.finishAuthenticatedSignIn(wellKnown.homeserverBaseUrl, login, context, false);
  }

  async signInWithLoginToken(homeserver: string, loginToken: string, context: common.UIAbilityContext): Promise<SignInResult> {
    if (loginToken.trim().length === 0) {
      return this.createSignInResult(false, this.service.getSignedOutSnapshot(), 'OAuth callback did not contain a login token', false);
    }
    const wellKnown: MatrixWellKnownResult = await this.serverApi.discoverHomeserver(homeserver);
    if (!wellKnown.ok) {
      return this.createSignInResult(false, this.service.getSignedOutSnapshot(), wellKnown.errorMessage, false);
    }
    const login: MatrixLoginResponse = await this.serverApi.loginWithToken(
      wellKnown.homeserverBaseUrl,
      loginToken.trim(),
      'Element X Harmony API 23'
    );
    if (!login.ok || login.accessToken.length === 0 || login.userId.length === 0) {
      const message = login.errorMessage.length > 0 ? login.errorMessage : 'Matrix token login did not return a session';
      return this.createSignInResult(false, this.service.getSignedOutSnapshot(), message, false);
    }
    return await this.finishAuthenticatedSignIn(wellKnown.homeserverBaseUrl, login, context, false);
  }

  private async finishAuthenticatedSignIn(
    homeserverBaseUrl: string,
    login: MatrixLoginResponse,
    context: common.UIAbilityContext,
    usedFixture: boolean
  ): Promise<SignInResult> {
    let session = this.service.createAuthenticatedSession(
      homeserverBaseUrl,
      login.userId,
      login.deviceId.length > 0 ? login.deviceId : 'HARMONYSDK23',
      login.accessToken
    );
    const versions: MatrixHttpResult = await this.serverApi.getVersions(homeserverBaseUrl);
    if (versions.ok) {
      const capableSession = this.service.updateHomeserverCapabilities(session.sessionId, this.homeserverCapabilitiesFromVersions(versions.body));
      if (capableSession !== null) {
        session = capableSession;
      }
    }
    const profile: MatrixProfileResponse = await this.serverApi.getProfile(homeserverBaseUrl, login.accessToken, login.userId);
    if (profile.ok) {
      const profiledSession = this.service.updateOwnProfile(
        session.sessionId,
        profile.displayName.length > 0 ? profile.displayName : session.account.displayName,
        session.account.userStatus,
        profile.avatarUrl
      );
      if (profiledSession !== null) {
        session = profiledSession;
      }
    }
    const ignoredUsers: MatrixIgnoredUsersResponse = await this.serverApi.getIgnoredUsers(homeserverBaseUrl, login.accessToken, login.userId);
    if (ignoredUsers.ok) {
      const ignoredSession = this.service.replaceIgnoredUsers(session.sessionId, ignoredUsers.ignoredUsers);
      if (ignoredSession !== null) {
        session = ignoredSession;
      }
    }
    const sync: MatrixSyncResponse = await this.serverApi.sync(homeserverBaseUrl, login.accessToken, '', 0);
    if (sync.ok) {
      this.service.applySyncResponse(sync.raw);
      if (sync.nextBatch.length > 0) {
        const syncedSession = this.service.updateNextSyncBatch(session.sessionId, sync.nextBatch);
        if (syncedSession !== null) {
          session = syncedSession;
        }
      }
    }
    const snapshot = this.service.getSignedInSnapshot(session);
    await this.persistCurrentStore(context);
    return this.createSignInResult(true, snapshot, '', usedFixture);
  }

  signOut(snapshot: ClientSnapshot): ClientSnapshot {
    const session = snapshot.session;
    if (session === null) {
      return this.service.getSignedOutSnapshot();
    }
    return this.service.signOut(session.sessionId);
  }

  async signOutPersisted(snapshot: ClientSnapshot, context: common.UIAbilityContext): Promise<ClientSnapshot> {
    const signedOut = this.signOut(snapshot);
    await this.sessionStore.clear(context);
    return signedOut;
  }

  async sendTextMessage(snapshot: ClientSnapshot, body: string): Promise<SendMessageResult> {
    const session = snapshot.session;
    const trimmedBody = body.trim();
    if (session === null || trimmedBody.length === 0) {
      return this.createSendMessageResult(false, snapshot, 'Message is empty');
    }

    if (session.accessToken.length > 0) {
      const result = await this.serverApi.sendTextMessage(
        session.homeserver,
        session.accessToken,
        snapshot.selectedRoomId,
        `harmony-${new Date().getTime()}`,
        trimmedBody
      );
      if (!result.ok) {
        return this.createSendMessageResult(false, snapshot, result.errorMessage);
      }
    }

    this.service.appendLocalTimelineMessage(session.account.userId, snapshot.selectedRoomId, trimmedBody);
    return this.createSendMessageResult(true, this.service.getSignedInSnapshot(session), '');
  }

  async sendEmoteMessage(snapshot: ClientSnapshot, body: string): Promise<SendMessageResult> {
    const session = snapshot.session;
    const trimmedBody = body.trim();
    if (session === null || trimmedBody.length === 0) {
      return this.createSendMessageResult(false, snapshot, 'Message is empty');
    }

    if (session.accessToken.length > 0) {
      const result = await this.serverApi.sendMessage(
        session.homeserver,
        session.accessToken,
        snapshot.selectedRoomId,
        `harmony-${new Date().getTime()}`,
        trimmedBody,
        'm.emote'
      );
      if (!result.ok) {
        return this.createSendMessageResult(false, snapshot, result.errorMessage);
      }
    }

    this.service.appendLocalTimelineEvent(session.account.userId, snapshot.selectedRoomId, trimmedBody, TimelineEventKind.Emote);
    return this.createSendMessageResult(true, this.service.getSignedInSnapshot(session), '');
  }

  async sendFormattedMessage(
    snapshot: ClientSnapshot,
    body: string,
    formattedBody: string,
    msgtype: string,
    localKind: TimelineEventKind
  ): Promise<SendMessageResult> {
    const session = snapshot.session;
    const trimmedBody = body.trim();
    if (session === null || trimmedBody.length === 0) {
      return this.createSendMessageResult(false, snapshot, 'Message is empty');
    }

    if (session.accessToken.length > 0) {
      const result = await this.serverApi.sendFormattedMessage(
        session.homeserver,
        session.accessToken,
        snapshot.selectedRoomId,
        `harmony-${new Date().getTime()}`,
        trimmedBody,
        formattedBody,
        msgtype
      );
      if (!result.ok) {
        return this.createSendMessageResult(false, snapshot, result.errorMessage);
      }
    }

    this.service.appendLocalTimelineEvent(session.account.userId, snapshot.selectedRoomId, trimmedBody, localKind);
    return this.createSendMessageResult(true, this.service.getSignedInSnapshot(session), '');
  }

  async sendSharedAttachmentMessage(snapshot: ClientSnapshot, caption: string, attachmentRows: string[]): Promise<SendMessageResult> {
    const session = snapshot.session;
    if (session === null) {
      return this.createSendMessageResult(false, snapshot, 'No signed-in session');
    }
    const trimmedCaption = caption.trim();
    if (attachmentRows.length === 0) {
      return this.sendTextMessage(snapshot, trimmedCaption);
    }

    if (session.accessToken.length > 0) {
      for (let index = 0; index < attachmentRows.length; index += 1) {
        const attachment = attachmentRows[index];
        const attachmentCaption = index === 0 ? trimmedCaption : '';
        const result = await this.sendOneSharedAttachment(session, snapshot.selectedRoomId, attachment, attachmentCaption, index);
        if (!result.ok) {
          return this.createSendMessageResult(false, snapshot, result.errorMessage);
        }
      }
    }

    this.service.appendLocalMediaMessage(session.account.userId, snapshot.selectedRoomId, trimmedCaption, attachmentRows);
    return this.createSendMessageResult(true, this.service.getSignedInSnapshot(session), '');
  }

  async updateOwnProfile(snapshot: ClientSnapshot, displayName: string, userStatus: string, context: common.UIAbilityContext): Promise<UpdateProfileResult> {
    const session = snapshot.session;
    if (session === null) {
      return this.createUpdateProfileResult(false, snapshot, 'No signed-in session');
    }
    const trimmedDisplayName = displayName.trim();
    if (trimmedDisplayName.length === 0) {
      return this.createUpdateProfileResult(false, snapshot, 'Display name is empty');
    }

    if (session.accessToken.length > 0) {
      const result: MatrixHttpResult = await this.serverApi.setDisplayName(
        session.homeserver,
        session.accessToken,
        session.account.userId,
        trimmedDisplayName
      );
      if (!result.ok) {
        return this.createUpdateProfileResult(false, snapshot, result.errorMessage);
      }
    }

    const updatedSession = this.service.updateOwnProfile(session.sessionId, trimmedDisplayName, userStatus, session.account.avatarUrl);
    if (updatedSession === null) {
      return this.createUpdateProfileResult(false, snapshot, 'Session cache entry not found');
    }
    await this.persistCurrentStore(context);
    return this.createUpdateProfileResult(true, this.service.getSignedInSnapshot(updatedSession), '');
  }

  async updateSelectedRoomName(snapshot: ClientSnapshot, name: string): Promise<UpdateRoomMetadataResult> {
    const session = snapshot.session;
    if (session === null) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'No signed-in session');
    }
    if (snapshot.selectedRoomId.length === 0) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'No selected room');
    }
    const trimmedName = name.trim();
    if (trimmedName.length === 0) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'Room name is empty');
    }
    if (session.accessToken.length > 0) {
      const result: MatrixHttpResult = await this.serverApi.setRoomName(
        session.homeserver,
        session.accessToken,
        snapshot.selectedRoomId,
        trimmedName
      );
      if (!result.ok) {
        return this.createUpdateRoomMetadataResult(false, snapshot, result.errorMessage);
      }
    }
    this.service.selectRoom(snapshot.selectedRoomId);
    if (!this.service.updateSelectedRoomName(trimmedName)) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'Selected room not found');
    }
    return this.createUpdateRoomMetadataResult(true, this.service.getSignedInSnapshot(session), '');
  }

  async updateSelectedRoomTopic(snapshot: ClientSnapshot, topic: string): Promise<UpdateRoomMetadataResult> {
    const session = snapshot.session;
    if (session === null) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'No signed-in session');
    }
    if (snapshot.selectedRoomId.length === 0) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'No selected room');
    }
    const trimmedTopic = topic.trim();
    if (trimmedTopic.length === 0) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'Room topic is empty');
    }
    if (session.accessToken.length > 0) {
      const result: MatrixHttpResult = await this.serverApi.setRoomTopic(
        session.homeserver,
        session.accessToken,
        snapshot.selectedRoomId,
        trimmedTopic
      );
      if (!result.ok) {
        return this.createUpdateRoomMetadataResult(false, snapshot, result.errorMessage);
      }
    }
    this.service.selectRoom(snapshot.selectedRoomId);
    if (!this.service.updateSelectedRoomTopic(trimmedTopic)) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'Selected room not found');
    }
    return this.createUpdateRoomMetadataResult(true, this.service.getSignedInSnapshot(session), '');
  }

  async updateSelectedRoomOwnDisplayName(snapshot: ClientSnapshot, displayName: string): Promise<UpdateRoomMetadataResult> {
    const session = snapshot.session;
    if (session === null) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'No signed-in session');
    }
    if (snapshot.selectedRoomId.length === 0) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'No selected room');
    }
    const trimmedDisplayName = displayName.trim();
    if (trimmedDisplayName.length === 0) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'Room nickname is empty');
    }
    if (session.accessToken.length > 0) {
      const result: MatrixHttpResult = await this.serverApi.setOwnRoomDisplayName(
        session.homeserver,
        session.accessToken,
        snapshot.selectedRoomId,
        session.account.userId,
        trimmedDisplayName
      );
      if (!result.ok) {
        return this.createUpdateRoomMetadataResult(false, snapshot, result.errorMessage);
      }
    }
    this.service.selectRoom(snapshot.selectedRoomId);
    if (!this.service.updateSelectedRoomOwnDisplayName(trimmedDisplayName)) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'Selected room not found');
    }
    return this.createUpdateRoomMetadataResult(true, this.service.getSignedInSnapshot(session), '');
  }

  async updateSelectedRoomMembership(
    snapshot: ClientSnapshot,
    action: string,
    userId: string,
    reason: string
  ): Promise<UpdateRoomMembershipResult> {
    const session = snapshot.session;
    if (session === null) {
      return this.createUpdateRoomMembershipResult(false, snapshot, 'No signed-in session');
    }
    if (snapshot.selectedRoomId.length === 0) {
      return this.createUpdateRoomMembershipResult(false, snapshot, 'No selected room');
    }
    const targetUserId = userId.trim();
    if (targetUserId.length === 0) {
      return this.createUpdateRoomMembershipResult(false, snapshot, 'User id is empty');
    }
    if (session.accessToken.length === 0) {
      return this.createUpdateRoomMembershipResult(true, this.service.getSignedInSnapshot(session), '');
    }
    let result: MatrixHttpResult;
    if (action === 'invite') {
      result = await this.serverApi.inviteUser(session.homeserver, session.accessToken, snapshot.selectedRoomId, targetUserId, reason);
    } else if (action === 'kick') {
      result = await this.serverApi.kickUser(session.homeserver, session.accessToken, snapshot.selectedRoomId, targetUserId, reason);
    } else if (action === 'ban') {
      result = await this.serverApi.banUser(session.homeserver, session.accessToken, snapshot.selectedRoomId, targetUserId, reason);
    } else if (action === 'unban') {
      result = await this.serverApi.unbanUser(session.homeserver, session.accessToken, snapshot.selectedRoomId, targetUserId, reason);
    } else {
      return this.createUpdateRoomMembershipResult(false, snapshot, 'Unsupported room membership action');
    }
    if (!result.ok) {
      return this.createUpdateRoomMembershipResult(false, snapshot, result.errorMessage);
    }
    return this.createUpdateRoomMembershipResult(true, this.service.getSignedInSnapshot(session), '');
  }

  async leaveSelectedRoom(snapshot: ClientSnapshot): Promise<UpdateRoomMetadataResult> {
    if (snapshot.selectedRoomId.length === 0) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'No selected room');
    }
    return this.leaveRoom(snapshot, snapshot.selectedRoomId);
  }

  async leaveRoom(snapshot: ClientSnapshot, roomId: string): Promise<UpdateRoomMetadataResult> {
    const session = snapshot.session;
    if (session === null) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'No signed-in session');
    }
    if (roomId.length === 0) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'No room selected');
    }
    if (session.accessToken.length > 0) {
      const result: MatrixHttpResult = await this.serverApi.leaveRoom(session.homeserver, session.accessToken, roomId);
      if (!result.ok) {
        return this.createUpdateRoomMetadataResult(false, snapshot, result.errorMessage);
      }
    }
    if (!this.service.leaveSelectedRoom(roomId)) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'Selected room not found');
    }
    return this.createUpdateRoomMetadataResult(true, this.service.getSignedInSnapshot(session), '');
  }

  async markSelectedRoomAsRead(snapshot: ClientSnapshot): Promise<MarkRoomReadResult> {
    if (snapshot.selectedRoomId.length === 0) {
      return this.createMarkRoomReadResult(false, snapshot, 'No selected room');
    }
    return this.markRoomAsRead(snapshot, snapshot.selectedRoomId);
  }

  async markRoomAsRead(snapshot: ClientSnapshot, roomId: string): Promise<MarkRoomReadResult> {
    const session = snapshot.session;
    if (session === null) {
      return this.createMarkRoomReadResult(false, snapshot, 'No signed-in session');
    }
    if (roomId.length === 0) {
      return this.createMarkRoomReadResult(false, snapshot, 'No room selected');
    }

    const latestEventId = this.service.latestTimelineEventId(roomId);
    if (session.accessToken.length > 0 && latestEventId.length > 0) {
      const result: MatrixHttpResult = await this.serverApi.sendReadReceipt(
        session.homeserver,
        session.accessToken,
        roomId,
        latestEventId,
        session.sendPublicReadReceipts
      );
      if (!result.ok) {
        return this.createMarkRoomReadResult(false, snapshot, result.errorMessage);
      }
      const markerResult: MatrixHttpResult = await this.serverApi.setFullyReadMarker(
        session.homeserver,
        session.accessToken,
        roomId,
        latestEventId
      );
      if (!markerResult.ok) {
        return this.createMarkRoomReadResult(false, snapshot, markerResult.errorMessage);
      }
    }
    if (session.accessToken.length > 0) {
      const unreadFlagResult: MatrixHttpResult = await this.serverApi.setRoomMarkedUnread(
        session.homeserver,
        session.accessToken,
        session.account.userId,
        roomId,
        false
      );
      if (!unreadFlagResult.ok) {
        return this.createMarkRoomReadResult(false, snapshot, unreadFlagResult.errorMessage);
      }
    }

    this.service.markRoomAsRead(roomId);
    return this.createMarkRoomReadResult(true, this.service.getSignedInSnapshot(session), '');
  }

  async markSelectedRoomAsUnread(snapshot: ClientSnapshot): Promise<MarkRoomReadResult> {
    if (snapshot.selectedRoomId.length === 0) {
      return this.createMarkRoomReadResult(false, snapshot, 'No selected room');
    }
    return this.markRoomAsUnread(snapshot, snapshot.selectedRoomId);
  }

  async markRoomAsUnread(snapshot: ClientSnapshot, roomId: string): Promise<MarkRoomReadResult> {
    const session = snapshot.session;
    if (session === null) {
      return this.createMarkRoomReadResult(false, snapshot, 'No signed-in session');
    }
    if (roomId.length === 0) {
      return this.createMarkRoomReadResult(false, snapshot, 'No room selected');
    }
    if (session.accessToken.length > 0) {
      const result: MatrixHttpResult = await this.serverApi.setRoomMarkedUnread(
        session.homeserver,
        session.accessToken,
        session.account.userId,
        roomId,
        true
      );
      if (!result.ok) {
        return this.createMarkRoomReadResult(false, snapshot, result.errorMessage);
      }
    }
    if (!this.service.markRoomAsUnread(roomId)) {
      return this.createMarkRoomReadResult(false, snapshot, 'Selected room not found');
    }
    return this.createMarkRoomReadResult(true, this.service.getSignedInSnapshot(session), '');
  }

  async setRoomIsFavorite(snapshot: ClientSnapshot, roomId: string, isFavorite: boolean): Promise<UpdateRoomMetadataResult> {
    const session = snapshot.session;
    if (session === null) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'No signed-in session');
    }
    if (roomId.length === 0) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'No room selected');
    }
    if (session.accessToken.length > 0) {
      const result: MatrixHttpResult = await this.serverApi.setRoomFavorite(
        session.homeserver,
        session.accessToken,
        session.account.userId,
        roomId,
        isFavorite
      );
      if (!result.ok) {
        return this.createUpdateRoomMetadataResult(false, snapshot, result.errorMessage);
      }
    }
    if (!this.service.setRoomIsFavorite(roomId, isFavorite)) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'Selected room not found');
    }
    return this.createUpdateRoomMetadataResult(true, this.service.getSignedInSnapshot(session), '');
  }

  async reportRoom(
    snapshot: ClientSnapshot,
    roomId: string,
    reason: string,
    shouldLeave: boolean,
    shouldReport: boolean
  ): Promise<UpdateRoomMetadataResult> {
    const session = snapshot.session;
    if (session === null) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'No signed-in session');
    }
    if (roomId.length === 0) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'No room selected');
    }
    if (shouldReport && session.accessToken.length > 0) {
      const reportResult: MatrixHttpResult = await this.serverApi.reportRoom(
        session.homeserver,
        session.accessToken,
        roomId,
        reason
      );
      if (!reportResult.ok) {
        return this.createUpdateRoomMetadataResult(false, snapshot, `Report room failed: ${reportResult.errorMessage}`);
      }
    }
    if (shouldReport && !this.service.reportRoom(roomId, reason)) {
      return this.createUpdateRoomMetadataResult(false, snapshot, 'Selected room not found');
    }
    if (shouldLeave) {
      const leaveResult = await this.leaveRoom(this.service.getSignedInSnapshot(session), roomId);
      if (!leaveResult.ok) {
        return this.createUpdateRoomMetadataResult(false, leaveResult.snapshot, `Leave room failed: ${leaveResult.errorMessage}`);
      }
      return leaveResult;
    }
    return this.createUpdateRoomMetadataResult(true, this.service.getSignedInSnapshot(session), '');
  }

  async markAllRoomsAsRead(snapshot: ClientSnapshot): Promise<MarkRoomReadResult> {
    const session = snapshot.session;
    if (session === null) {
      return this.createMarkRoomReadResult(false, snapshot, 'No signed-in session');
    }

    if (session.accessToken.length > 0) {
      for (let index = 0; index < snapshot.rooms.length; index += 1) {
        const room = snapshot.rooms[index];
        const latestEventId = this.service.latestTimelineEventId(room.id);
        if (latestEventId.length === 0) {
          continue;
        }
        const receiptResult: MatrixHttpResult = await this.serverApi.sendReadReceipt(
          session.homeserver,
          session.accessToken,
          room.id,
          latestEventId,
          session.sendPublicReadReceipts
        );
        if (!receiptResult.ok) {
          continue;
        }
        await this.serverApi.setFullyReadMarker(
          session.homeserver,
          session.accessToken,
          room.id,
          latestEventId
        );
      }
    }

    this.service.markAllRoomsAsRead();
    return this.createMarkRoomReadResult(true, this.service.getSignedInSnapshot(session), '');
  }

  async autoMarkSelectedRoomAsRead(snapshot: ClientSnapshot): Promise<MarkRoomReadResult> {
    const session = snapshot.session;
    if (session === null || snapshot.selectedRoomId.length === 0) {
      return this.createMarkRoomReadResult(true, snapshot, '');
    }
    if (!this.service.shouldAutoMarkRoomAsRead(snapshot.selectedRoomId)) {
      if (this.service.isRoomMarkedUnread(snapshot.selectedRoomId)) {
        this.service.clearRoomUnreadFlag(snapshot.selectedRoomId);
        return this.createMarkRoomReadResult(true, this.service.getSignedInSnapshot(session), '');
      }
      return this.createMarkRoomReadResult(true, snapshot, '');
    }
    const result = await this.markSelectedRoomAsRead(snapshot);
    if (!result.ok) {
      return this.createMarkRoomReadResult(true, snapshot, '');
    }
    return result;
  }

  async updateReadReceiptPreference(snapshot: ClientSnapshot, sendPublicReadReceipts: boolean, context: common.UIAbilityContext): Promise<UpdateReadReceiptPreferenceResult> {
    const session = snapshot.session;
    if (session === null) {
      return this.createUpdateReadReceiptPreferenceResult(false, snapshot, 'No signed-in session');
    }
    const updatedSession = this.service.updateReadReceiptPreference(session.sessionId, sendPublicReadReceipts);
    if (updatedSession === null) {
      return this.createUpdateReadReceiptPreferenceResult(false, snapshot, 'Session cache entry not found');
    }
    await this.persistCurrentStore(context);
    return this.createUpdateReadReceiptPreferenceResult(true, this.service.getSignedInSnapshot(updatedSession), '');
  }

  async updateTimelineMediaPreviewMode(snapshot: ClientSnapshot, mode: TimelineMediaPreviewMode, context: common.UIAbilityContext): Promise<UpdateTimelineMediaPreviewModeResult> {
    const session = snapshot.session;
    if (session === null) {
      return this.createUpdateTimelineMediaPreviewModeResult(false, snapshot, 'No signed-in session');
    }
    const updatedSession = this.service.updateTimelineMediaPreviewMode(session.sessionId, mode);
    if (updatedSession === null) {
      return this.createUpdateTimelineMediaPreviewModeResult(false, snapshot, 'Session cache entry not found');
    }
    await this.persistCurrentStore(context);
    return this.createUpdateTimelineMediaPreviewModeResult(true, this.service.getSignedInSnapshot(updatedSession), '');
  }

  async updateIgnoredUser(snapshot: ClientSnapshot, userId: string, ignored: boolean, context: common.UIAbilityContext): Promise<UpdateIgnoredUserResult> {
    const session = snapshot.session;
    const targetUserId = userId.trim();
    if (session === null) {
      return this.createUpdateIgnoredUserResult(false, snapshot, ignored, 'No signed-in session');
    }
    if (targetUserId.length === 0) {
      return this.createUpdateIgnoredUserResult(false, snapshot, ignored, 'User id is empty');
    }
    if (targetUserId === session.account.userId) {
      return this.createUpdateIgnoredUserResult(false, snapshot, this.service.isUserIgnored(session.sessionId, targetUserId), 'Cannot block your own account');
    }

    if (session.accessToken.length > 0) {
      const result: MatrixHttpResult = await this.serverApi.updateIgnoredUser(
        session.homeserver,
        session.accessToken,
        session.account.userId,
        targetUserId,
        ignored
      );
      if (!result.ok) {
        return this.createUpdateIgnoredUserResult(false, snapshot, this.service.isUserIgnored(session.sessionId, targetUserId), result.errorMessage);
      }
    }

    const updatedSession = this.service.updateIgnoredUser(session.sessionId, targetUserId, ignored);
    if (updatedSession === null) {
      return this.createUpdateIgnoredUserResult(false, snapshot, ignored, 'Session cache entry not found');
    }
    await this.persistCurrentStore(context);
    return this.createUpdateIgnoredUserResult(true, this.service.getSignedInSnapshot(updatedSession), ignored, '');
  }

  async runForegroundSyncOnce(snapshot: ClientSnapshot, context: common.UIAbilityContext): Promise<ForegroundSyncResult> {
    const session = snapshot.session;
    if (session === null) {
      return this.createForegroundSyncResult(false, snapshot, 'No signed-in session', true, '');
    }
    if (session.accessToken.length === 0) {
      return this.createForegroundSyncResult(true, this.service.getSignedInSnapshot(session), '', true, session.nextSyncBatch);
    }
    const sync: MatrixSyncResponse = await this.serverApi.sync(
      session.homeserver,
      session.accessToken,
      session.nextSyncBatch,
      session.nextSyncBatch.length > 0 ? 30000 : 0
    );
    if (!sync.ok) {
      return this.createForegroundSyncResult(false, snapshot, sync.errorMessage, false, session.nextSyncBatch);
    }
    this.service.applySyncResponse(sync.raw);
    let updatedSession = session;
    if (sync.nextBatch.length > 0) {
      const syncedSession = this.service.updateNextSyncBatch(session.sessionId, sync.nextBatch);
      if (syncedSession !== null) {
        updatedSession = syncedSession;
      }
    }
    await this.persistCurrentStore(context);
    return this.createForegroundSyncResult(true, this.service.getSignedInSnapshot(updatedSession), '', false, updatedSession.nextSyncBatch);
  }

  selectRoom(snapshot: ClientSnapshot, roomId: string): ClientSnapshot {
    const session = snapshot.session;
    if (session === null) {
      return snapshot;
    }
    this.service.selectRoom(roomId);
    return this.service.getSignedInSnapshot(session);
  }

  getUserProfile(snapshot: ClientSnapshot, userId: string): UserProfileResult {
    if (snapshot.session === null || userId.trim().length === 0) {
      return {
        ok: false,
        profile: null,
        errorMessage: 'No signed-in session'
      };
    }
    return {
      ok: true,
      profile: this.service.getProfile(userId.trim()),
      errorMessage: ''
    };
  }

  getRoomPreview(snapshot: ClientSnapshot, roomIdOrAlias: string, serverNames: string[]): RoomPreviewResult {
    if (snapshot.session === null || roomIdOrAlias.trim().length === 0) {
      return {
        ok: false,
        preview: null,
        errorMessage: 'No signed-in session'
      };
    }
    return {
      ok: true,
      preview: this.service.getRoomPreview(roomIdOrAlias.trim(), serverNames),
      errorMessage: ''
    };
  }

  async joinRoomByIdOrAlias(snapshot: ClientSnapshot, roomIdOrAlias: string, serverNames: string[]): Promise<JoinRoomResult> {
    const session = snapshot.session;
    if (session === null || roomIdOrAlias.trim().length === 0) {
      return this.createJoinRoomResult(false, snapshot, null, 'No signed-in session');
    }
    let resolvedRoomId = roomIdOrAlias.trim();
    if (session.accessToken.length > 0) {
      const joinResult: MatrixJoinRoomResponse = await this.serverApi.joinRoomByIdOrAlias(
        session.homeserver,
        session.accessToken,
        roomIdOrAlias.trim(),
        serverNames
      );
      if (!joinResult.ok) {
        return this.createJoinRoomResult(false, snapshot, null, joinResult.errorMessage);
      }
      if (joinResult.roomId.length > 0) {
        resolvedRoomId = joinResult.roomId;
      }
    }
    const roomInfo = this.service.joinRoomByIdOrAlias(resolvedRoomId, serverNames);
    return this.createJoinRoomResult(true, this.service.getSignedInSnapshot(session), roomInfo, '');
  }

  async createDirectRoom(snapshot: ClientSnapshot, userId: string): Promise<JoinRoomResult> {
    const session = snapshot.session;
    if (session === null || userId.trim().length === 0) {
      return this.createJoinRoomResult(false, snapshot, null, 'No signed-in session');
    }
    let resolvedRoomId = '';
    if (session.accessToken.length > 0) {
      const createResult: MatrixCreateRoomResponse = await this.serverApi.createDirectRoom(
        session.homeserver,
        session.accessToken,
        userId.trim()
      );
      if (!createResult.ok) {
        return this.createJoinRoomResult(false, snapshot, null, createResult.errorMessage);
      }
      resolvedRoomId = createResult.roomId;
    }
    const roomInfo = this.service.createDirectRoomFromResolvedRoom(userId.trim(), resolvedRoomId);
    return this.createJoinRoomResult(true, this.service.getSignedInSnapshot(session), roomInfo, '');
  }

  ensureFocusedPermalinkEvent(snapshot: ClientSnapshot, roomId: string, eventId: string): ClientSnapshot {
    const session = snapshot.session;
    if (session === null || roomId.length === 0 || eventId.length === 0) {
      return snapshot;
    }
    this.service.ensureTimelineContainsEvent(roomId, eventId);
    return this.service.getSignedInSnapshot(session);
  }

  handleIntent(action: string, data: string): ClientSnapshot {
    this.service.resolveIntent(action, data);
    return this.service.restoreLatestSession();
  }

  clearIntent(): ClientSnapshot {
    this.service.clearIntent();
    return this.service.restoreLatestSession();
  }

  private async persistCurrentStore(context: common.UIAbilityContext): Promise<void> {
    const snapshot: PersistedSessionSnapshot = {
      latestSessionId: this.service.getLatestSessionId(),
      sessions: this.service.exportSessionStore()
    };
    await this.sessionStore.save(context, snapshot);
  }

  private createSignInResult(ok: boolean, snapshot: ClientSnapshot, errorMessage: string, usedFixture: boolean): SignInResult {
    return {
      ok: ok,
      snapshot: snapshot,
      errorMessage: errorMessage,
      usedFixture: usedFixture
    };
  }

  private createSendMessageResult(ok: boolean, snapshot: ClientSnapshot, errorMessage: string): SendMessageResult {
    return {
      ok: ok,
      snapshot: snapshot,
      errorMessage: errorMessage
    };
  }

  private createUpdateProfileResult(ok: boolean, snapshot: ClientSnapshot, errorMessage: string): UpdateProfileResult {
    return {
      ok: ok,
      snapshot: snapshot,
      errorMessage: errorMessage
    };
  }

  private createUpdateRoomMetadataResult(ok: boolean, snapshot: ClientSnapshot, errorMessage: string): UpdateRoomMetadataResult {
    return {
      ok: ok,
      snapshot: snapshot,
      errorMessage: errorMessage
    };
  }

  private createUpdateRoomMembershipResult(ok: boolean, snapshot: ClientSnapshot, errorMessage: string): UpdateRoomMembershipResult {
    return {
      ok: ok,
      snapshot: snapshot,
      errorMessage: errorMessage
    };
  }

  private createMarkRoomReadResult(ok: boolean, snapshot: ClientSnapshot, errorMessage: string): MarkRoomReadResult {
    return {
      ok: ok,
      snapshot: snapshot,
      errorMessage: errorMessage
    };
  }

  private createUpdateReadReceiptPreferenceResult(ok: boolean, snapshot: ClientSnapshot, errorMessage: string): UpdateReadReceiptPreferenceResult {
    return {
      ok: ok,
      snapshot: snapshot,
      errorMessage: errorMessage
    };
  }

  private createUpdateTimelineMediaPreviewModeResult(ok: boolean, snapshot: ClientSnapshot, errorMessage: string): UpdateTimelineMediaPreviewModeResult {
    return {
      ok: ok,
      snapshot: snapshot,
      errorMessage: errorMessage
    };
  }

  private createUpdateIgnoredUserResult(ok: boolean, snapshot: ClientSnapshot, ignored: boolean, errorMessage: string): UpdateIgnoredUserResult {
    return {
      ok: ok,
      snapshot: snapshot,
      ignored: ignored,
      errorMessage: errorMessage
    };
  }

  private createForegroundSyncResult(ok: boolean, snapshot: ClientSnapshot, errorMessage: string, skipped: boolean, nextBatch: string): ForegroundSyncResult {
    return {
      ok: ok,
      snapshot: snapshot,
      errorMessage: errorMessage,
      skipped: skipped,
      nextBatch: nextBatch
    };
  }

  private createJoinRoomResult(ok: boolean, snapshot: ClientSnapshot, roomInfo: RoomInfo | null, errorMessage: string): JoinRoomResult {
    return {
      ok: ok,
      snapshot: snapshot,
      roomInfo: roomInfo,
      errorMessage: errorMessage
    };
  }

  private async sendOneSharedAttachment(
    session: ClientSession,
    roomId: string,
    attachmentRow: string,
    caption: string,
    index: number
  ): Promise<MatrixHttpResult> {
    const mimeType = this.mimeTypeFromAttachmentRow(attachmentRow);
    const uri = this.uriFromAttachmentRow(attachmentRow);
    let contentUri = uri;
    let mediaSize = 0;
    let body = caption.length > 0 ? caption : this.filenameFromUri(uri);
    if (uri.indexOf('mxc://') !== 0) {
      const mediaFile: SharedMediaReadResult = this.sharedMediaFileReader.readFileUri(uri);
      if (!mediaFile.ok) {
        return this.createHttpResult(false, 0, '', mediaFile.errorMessage);
      }
      const uploadResult: MatrixMediaUploadResponse = await this.serverApi.uploadMedia(
        session.homeserver,
        session.accessToken,
        mimeType,
        mediaFile.data,
        mediaFile.filename
      );
      if (!uploadResult.ok || uploadResult.contentUri.length === 0) {
        const message = uploadResult.errorMessage.length > 0 ? uploadResult.errorMessage : 'Matrix media upload did not return content_uri';
        return this.createHttpResult(false, 0, uploadResult.raw, message);
      }
      contentUri = uploadResult.contentUri;
      mediaSize = mediaFile.size;
      body = caption.length > 0 ? caption : mediaFile.filename;
    }
    return this.serverApi.sendMediaMessage(
      session.homeserver,
      session.accessToken,
      roomId,
      `harmony-media-${new Date().getTime()}-${index}`,
      this.mediaMsgtypeFromMimeType(mimeType),
      body,
      contentUri,
      mimeType,
      mediaSize
    );
  }

  private createHttpResult(ok: boolean, statusCode: number, body: string, errorMessage: string): MatrixHttpResult {
    return {
      ok: ok,
      statusCode: statusCode,
      body: body,
      errorMessage: errorMessage
    };
  }

  private homeserverCapabilitiesFromVersions(raw: string): HomeserverCapabilitiesState {
    return {
      canChangeDisplayName: true,
      canChangeAvatarUrl: true,
      canDeactivateAccount: true,
      canReportRoom: this.isReportRoomApiSupported(raw),
      canLinkNewDevice: true,
      maxFileUploadSizeBytes: 104857600,
      livekitRtcSupported: true
    };
  }

  private isReportRoomApiSupported(raw: string): boolean {
    try {
      const parsed = JSON.parse(raw) as MatrixVersionsContent;
      if (parsed.unstable_features !== undefined && parsed.unstable_features['org.matrix.msc4151'] === true) {
        return true;
      }
      const versions = parsed.versions ?? [];
      return versions.some((version: string) => this.isAtLeastMatrixVersion(version, 1, 13));
    } catch (error) {
      return false;
    }
  }

  private isAtLeastMatrixVersion(version: string, major: number, minor: number): boolean {
    if (!version.startsWith('v')) {
      return false;
    }
    const parts = version.substring(1).split('.');
    if (parts.length < 2) {
      return false;
    }
    const versionMajor = Number.parseInt(parts[0], 10);
    const versionMinor = Number.parseInt(parts[1], 10);
    if (Number.isNaN(versionMajor) || Number.isNaN(versionMinor)) {
      return false;
    }
    if (versionMajor !== major) {
      return versionMajor > major;
    }
    return versionMinor >= minor;
  }

  private mediaMsgtypeFromMimeType(mimeType: string): string {
    if (mimeType.indexOf('image/') === 0) {
      return 'm.image';
    }
    if (mimeType.indexOf('video/') === 0) {
      return 'm.video';
    }
    if (mimeType.indexOf('audio/') === 0) {
      return 'm.audio';
    }
    return 'm.file';
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

  private filenameFromUri(uri: string): string {
    const slashIndex = uri.lastIndexOf('/');
    if (slashIndex >= 0 && slashIndex < uri.length - 1) {
      return uri.substring(slashIndex + 1);
    }
    return 'Shared media';
  }
}
