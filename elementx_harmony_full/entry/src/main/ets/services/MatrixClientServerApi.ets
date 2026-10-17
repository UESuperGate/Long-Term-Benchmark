import http from '@ohos.net.http';

export interface MatrixHttpResult {
  ok: boolean;
  statusCode: number;
  body: string;
  errorMessage: string;
}

export interface MatrixWellKnownResult {
  ok: boolean;
  homeserverBaseUrl: string;
  identityServerBaseUrl: string;
  raw: string;
  errorMessage: string;
}

export interface MatrixLoginResponse {
  ok: boolean;
  accessToken: string;
  userId: string;
  deviceId: string;
  homeserverBaseUrl: string;
  raw: string;
  errorMessage: string;
}

export interface MatrixSyncResponse {
  ok: boolean;
  nextBatch: string;
  raw: string;
  errorMessage: string;
}

export interface MatrixProfileResponse {
  ok: boolean;
  userId: string;
  displayName: string;
  avatarUrl: string;
  raw: string;
  errorMessage: string;
}

export interface MatrixIgnoredUsersResponse {
  ok: boolean;
  ignoredUsers: string[];
  raw: string;
  errorMessage: string;
}

export interface MatrixJoinRoomResponse {
  ok: boolean;
  roomId: string;
  raw: string;
  errorMessage: string;
}

export interface MatrixCreateRoomResponse {
  ok: boolean;
  roomId: string;
  raw: string;
  errorMessage: string;
}

export interface MatrixMediaUploadResponse {
  ok: boolean;
  contentUri: string;
  raw: string;
  errorMessage: string;
}

interface MatrixHttpHeaders {
  'Content-Type': string;
  'Accept': string;
  'Authorization': string;
  'User-Agent': string;
}

interface MatrixIgnoredUsersContent {
  ignored_users?: object;
}

export class MatrixClientServerApi {
  async discoverHomeserver(serverName: string): Promise<MatrixWellKnownResult> {
    const normalizedServer = this.normalizeServerName(serverName);
    const wellKnown = await this.get(`https://${normalizedServer}/.well-known/matrix/client`, '');
    if (!wellKnown.ok) {
      return this.createWellKnownResult(true, `https://${normalizedServer}`, '', wellKnown.body, '');
    }
    const baseUrl = this.findStringValue(wellKnown.body, 'base_url');
    if (baseUrl.length === 0) {
      return this.createWellKnownResult(true, `https://${normalizedServer}`, '', wellKnown.body, '');
    }
    return this.createWellKnownResult(true, this.trimTrailingSlash(baseUrl), this.findStringValue(wellKnown.body, 'm.identity_server'), wellKnown.body, '');
  }

  async getVersions(homeserverBaseUrl: string): Promise<MatrixHttpResult> {
    return this.get(`${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/versions`, '');
  }

  async loginWithPassword(
    homeserverBaseUrl: string,
    username: string,
    password: string,
    deviceDisplayName: string
  ): Promise<MatrixLoginResponse> {
    const payload = this.createPasswordLoginPayload(username, password, deviceDisplayName);
    const result = await this.post(`${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/login`, payload, '');
    if (!result.ok) {
      return this.createLoginResponse(false, '', '', '', homeserverBaseUrl, result.body, result.errorMessage);
    }
    return this.createLoginResponse(
      true,
      this.findStringValue(result.body, 'access_token'),
      this.findStringValue(result.body, 'user_id'),
      this.findStringValue(result.body, 'device_id'),
      homeserverBaseUrl,
      result.body,
      ''
    );
  }

  async loginWithToken(
    homeserverBaseUrl: string,
    loginToken: string,
    deviceDisplayName: string
  ): Promise<MatrixLoginResponse> {
    const payload = this.createTokenLoginPayload(loginToken, deviceDisplayName);
    const result = await this.post(`${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/login`, payload, '');
    if (!result.ok) {
      return this.createLoginResponse(false, '', '', '', homeserverBaseUrl, result.body, result.errorMessage);
    }
    return this.createLoginResponse(
      true,
      this.findStringValue(result.body, 'access_token'),
      this.findStringValue(result.body, 'user_id'),
      this.findStringValue(result.body, 'device_id'),
      homeserverBaseUrl,
      result.body,
      ''
    );
  }

  async sync(
    homeserverBaseUrl: string,
    accessToken: string,
    since: string,
    timeoutMs: number
  ): Promise<MatrixSyncResponse> {
    let url = `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/sync?timeout=${timeoutMs}`;
    if (since.length > 0) {
      url = `${url}&since=${encodeURIComponent(since)}`;
    }
    const result = await this.get(url, accessToken);
    if (!result.ok) {
      return this.createSyncResponse(false, '', result.body, result.errorMessage);
    }
    return this.createSyncResponse(true, this.findStringValue(result.body, 'next_batch'), result.body, '');
  }

  async sendTextMessage(
    homeserverBaseUrl: string,
    accessToken: string,
    roomId: string,
    transactionId: string,
    body: string
  ): Promise<MatrixHttpResult> {
    const encodedRoomId = encodeURIComponent(roomId);
    const encodedTransactionId = encodeURIComponent(transactionId);
    const payload = this.createTextMessagePayload(body);
    return this.put(
      `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/rooms/${encodedRoomId}/send/m.room.message/${encodedTransactionId}`,
      payload,
      accessToken
    );
  }

  async sendMessage(
    homeserverBaseUrl: string,
    accessToken: string,
    roomId: string,
    transactionId: string,
    body: string,
    msgtype: string
  ): Promise<MatrixHttpResult> {
    const encodedRoomId = encodeURIComponent(roomId);
    const encodedTransactionId = encodeURIComponent(transactionId);
    const payload = this.createMessagePayload(body, msgtype);
    return this.put(
      `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/rooms/${encodedRoomId}/send/m.room.message/${encodedTransactionId}`,
      payload,
      accessToken
    );
  }

  async sendFormattedMessage(
    homeserverBaseUrl: string,
    accessToken: string,
    roomId: string,
    transactionId: string,
    body: string,
    formattedBody: string,
    msgtype: string
  ): Promise<MatrixHttpResult> {
    const encodedRoomId = encodeURIComponent(roomId);
    const encodedTransactionId = encodeURIComponent(transactionId);
    const payload = this.createFormattedMessagePayload(body, formattedBody, msgtype);
    return this.put(
      `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/rooms/${encodedRoomId}/send/m.room.message/${encodedTransactionId}`,
      payload,
      accessToken
    );
  }

  async uploadMedia(
    homeserverBaseUrl: string,
    accessToken: string,
    mimeType: string,
    data: ArrayBuffer,
    filename: string
  ): Promise<MatrixMediaUploadResponse> {
    const result = await this.postBytes(
      `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/media/v3/upload?filename=${encodeURIComponent(filename)}`,
      data,
      accessToken,
      mimeType.length > 0 ? mimeType : 'application/octet-stream'
    );
    if (!result.ok) {
      return this.createMediaUploadResponse(false, '', result.body, result.errorMessage);
    }
    return this.createMediaUploadResponse(true, this.findStringValue(result.body, 'content_uri'), result.body, '');
  }

  async sendMediaMessage(
    homeserverBaseUrl: string,
    accessToken: string,
    roomId: string,
    transactionId: string,
    msgtype: string,
    body: string,
    contentUri: string,
    mimeType: string,
    size: number
  ): Promise<MatrixHttpResult> {
    const encodedRoomId = encodeURIComponent(roomId);
    const encodedTransactionId = encodeURIComponent(transactionId);
    const payload = this.createMediaMessagePayload(msgtype, body, contentUri, mimeType, size);
    return this.put(
      `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/rooms/${encodedRoomId}/send/m.room.message/${encodedTransactionId}`,
      payload,
      accessToken
    );
  }

  async sendReadReceipt(
    homeserverBaseUrl: string,
    accessToken: string,
    roomId: string,
    eventId: string,
    sendPublicReadReceipt: boolean
  ): Promise<MatrixHttpResult> {
    const receiptType = sendPublicReadReceipt ? 'm.read' : 'm.read.private';
    return this.post(
      `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/rooms/${encodeURIComponent(roomId)}/receipt/${encodeURIComponent(receiptType)}/${encodeURIComponent(eventId)}`,
      '{}',
      accessToken
    );
  }

  async setFullyReadMarker(
    homeserverBaseUrl: string,
    accessToken: string,
    roomId: string,
    eventId: string
  ): Promise<MatrixHttpResult> {
    const payload = this.createFullyReadMarkerPayload(eventId);
    return this.post(
      `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/rooms/${encodeURIComponent(roomId)}/read_markers`,
      payload,
      accessToken
    );
  }

  async setRoomMarkedUnread(
    homeserverBaseUrl: string,
    accessToken: string,
    userId: string,
    roomId: string,
    unread: boolean
  ): Promise<MatrixHttpResult> {
    return this.put(
      this.roomAccountDataUrl(homeserverBaseUrl, userId, roomId, 'm.marked_unread'),
      this.createMarkedUnreadPayload(unread),
      accessToken
    );
  }

  async getProfile(homeserverBaseUrl: string, accessToken: string, userId: string): Promise<MatrixProfileResponse> {
    const result = await this.get(`${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/profile/${encodeURIComponent(userId)}`, accessToken);
    if (!result.ok) {
      return this.createProfileResponse(false, userId, '', '', result.body, result.errorMessage);
    }
    return this.createProfileResponse(
      true,
      userId,
      this.findStringValue(result.body, 'displayname'),
      this.findStringValue(result.body, 'avatar_url'),
      result.body,
      ''
    );
  }

  async setDisplayName(homeserverBaseUrl: string, accessToken: string, userId: string, displayName: string): Promise<MatrixHttpResult> {
    const payload = this.createDisplayNamePayload(displayName);
    return this.put(
      `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/profile/${encodeURIComponent(userId)}/displayname`,
      payload,
      accessToken
    );
  }

  async setRoomName(homeserverBaseUrl: string, accessToken: string, roomId: string, name: string): Promise<MatrixHttpResult> {
    return this.put(
      `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/rooms/${encodeURIComponent(roomId)}/state/m.room.name/`,
      this.createRoomNamePayload(name),
      accessToken
    );
  }

  async setRoomTopic(homeserverBaseUrl: string, accessToken: string, roomId: string, topic: string): Promise<MatrixHttpResult> {
    return this.put(
      `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/rooms/${encodeURIComponent(roomId)}/state/m.room.topic/`,
      this.createRoomTopicPayload(topic),
      accessToken
    );
  }

  async setOwnRoomDisplayName(
    homeserverBaseUrl: string,
    accessToken: string,
    roomId: string,
    userId: string,
    displayName: string
  ): Promise<MatrixHttpResult> {
    return this.put(
      `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/rooms/${encodeURIComponent(roomId)}/state/m.room.member/${encodeURIComponent(userId)}`,
      this.createOwnRoomDisplayNamePayload(displayName),
      accessToken
    );
  }

  async inviteUser(homeserverBaseUrl: string, accessToken: string, roomId: string, userId: string, reason: string): Promise<MatrixHttpResult> {
    return this.postRoomMembershipAction(homeserverBaseUrl, accessToken, roomId, 'invite', userId, reason);
  }

  async kickUser(homeserverBaseUrl: string, accessToken: string, roomId: string, userId: string, reason: string): Promise<MatrixHttpResult> {
    return this.postRoomMembershipAction(homeserverBaseUrl, accessToken, roomId, 'kick', userId, reason);
  }

  async banUser(homeserverBaseUrl: string, accessToken: string, roomId: string, userId: string, reason: string): Promise<MatrixHttpResult> {
    return this.postRoomMembershipAction(homeserverBaseUrl, accessToken, roomId, 'ban', userId, reason);
  }

  async unbanUser(homeserverBaseUrl: string, accessToken: string, roomId: string, userId: string, reason: string): Promise<MatrixHttpResult> {
    return this.postRoomMembershipAction(homeserverBaseUrl, accessToken, roomId, 'unban', userId, reason);
  }

  async leaveRoom(homeserverBaseUrl: string, accessToken: string, roomId: string): Promise<MatrixHttpResult> {
    return this.post(
      `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/rooms/${encodeURIComponent(roomId)}/leave`,
      '{}',
      accessToken
    );
  }

  async reportRoom(homeserverBaseUrl: string, accessToken: string, roomId: string, reason: string): Promise<MatrixHttpResult> {
    return this.post(
      `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/rooms/${encodeURIComponent(roomId)}/report`,
      this.createReportRoomPayload(reason),
      accessToken
    );
  }

  async setRoomFavorite(
    homeserverBaseUrl: string,
    accessToken: string,
    userId: string,
    roomId: string,
    isFavorite: boolean
  ): Promise<MatrixHttpResult> {
    const url = this.roomTagUrl(homeserverBaseUrl, userId, roomId, 'm.favourite');
    if (isFavorite) {
      return this.put(url, '{}', accessToken);
    }
    return this.delete(url, accessToken);
  }

  async getIgnoredUsers(homeserverBaseUrl: string, accessToken: string, userId: string): Promise<MatrixIgnoredUsersResponse> {
    const result = await this.get(this.ignoredUsersAccountDataUrl(homeserverBaseUrl, userId), accessToken);
    if (!result.ok) {
      if (result.statusCode === 404) {
        return this.createIgnoredUsersResponse(true, [], result.body, '');
      }
      return this.createIgnoredUsersResponse(false, [], result.body, result.errorMessage);
    }
    return this.createIgnoredUsersResponse(true, this.parseIgnoredUsers(result.body), result.body, '');
  }

  async updateIgnoredUser(
    homeserverBaseUrl: string,
    accessToken: string,
    ownUserId: string,
    targetUserId: string,
    ignored: boolean
  ): Promise<MatrixHttpResult> {
    const existing = await this.getIgnoredUsers(homeserverBaseUrl, accessToken, ownUserId);
    if (!existing.ok) {
      return {
        ok: false,
        statusCode: 0,
        body: existing.raw,
        errorMessage: existing.errorMessage
      };
    }
    const users = this.normalizedUserIds(existing.ignoredUsers);
    const cleanTarget = targetUserId.trim();
    if (ignored && cleanTarget.length > 0 && !users.includes(cleanTarget)) {
      users.push(cleanTarget);
    }
    if (!ignored) {
      const index = users.indexOf(cleanTarget);
      if (index >= 0) {
        users.splice(index, 1);
      }
    }
    return this.put(this.ignoredUsersAccountDataUrl(homeserverBaseUrl, ownUserId), this.createIgnoredUsersPayload(users), accessToken);
  }

  async joinRoomByIdOrAlias(
    homeserverBaseUrl: string,
    accessToken: string,
    roomIdOrAlias: string,
    serverNames: string[]
  ): Promise<MatrixJoinRoomResponse> {
    const payload = this.createJoinRoomPayload(serverNames);
    const result = await this.post(
      `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/join/${encodeURIComponent(roomIdOrAlias)}`,
      payload,
      accessToken
    );
    if (!result.ok) {
      return this.createJoinRoomResponse(false, '', result.body, result.errorMessage);
    }
    return this.createJoinRoomResponse(true, this.findStringValue(result.body, 'room_id'), result.body, '');
  }

  async createDirectRoom(homeserverBaseUrl: string, accessToken: string, userId: string): Promise<MatrixCreateRoomResponse> {
    const payload = this.createDirectRoomPayload(userId);
    const result = await this.post(
      `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/createRoom`,
      payload,
      accessToken
    );
    if (!result.ok) {
      return this.createRoomResponse(false, '', result.body, result.errorMessage);
    }
    return this.createRoomResponse(true, this.findStringValue(result.body, 'room_id'), result.body, '');
  }

  private async get(url: string, accessToken: string): Promise<MatrixHttpResult> {
    return this.request(http.RequestMethod.GET, url, '', accessToken);
  }

  private async post(url: string, payload: string, accessToken: string): Promise<MatrixHttpResult> {
    return this.request(http.RequestMethod.POST, url, payload, accessToken);
  }

  private async put(url: string, payload: string, accessToken: string): Promise<MatrixHttpResult> {
    return this.request(http.RequestMethod.PUT, url, payload, accessToken);
  }

  private async delete(url: string, accessToken: string): Promise<MatrixHttpResult> {
    return this.request(http.RequestMethod.DELETE, url, '', accessToken);
  }

  private async postBytes(url: string, payload: ArrayBuffer, accessToken: string, contentType: string): Promise<MatrixHttpResult> {
    return this.requestBytes(http.RequestMethod.POST, url, payload, accessToken, contentType);
  }

  private async request(method: http.RequestMethod, url: string, payload: string, accessToken: string): Promise<MatrixHttpResult> {
    const request = http.createHttp();
    try {
      const headers = this.createHeaders(accessToken);
      const options: http.HttpRequestOptions = {
        method: method,
        extraData: payload,
        header: headers,
        readTimeout: 60000,
        connectTimeout: 60000,
        expectDataType: http.HttpDataType.STRING,
        maxLimit: 104857600
      };
      const response = await request.request(url, options);
      const statusCode = response.responseCode as number;
      const body = this.responseBodyToString(response.result);
      return {
        ok: statusCode >= 200 && statusCode < 300,
        statusCode: statusCode,
        body: body,
        errorMessage: statusCode >= 200 && statusCode < 300 ? '' : `HTTP ${statusCode}`
      };
    } catch (error) {
      return {
        ok: false,
        statusCode: 0,
        body: '',
        errorMessage: `${error}`
      };
    } finally {
      request.destroy();
    }
  }

  private async requestBytes(
    method: http.RequestMethod,
    url: string,
    payload: ArrayBuffer,
    accessToken: string,
    contentType: string
  ): Promise<MatrixHttpResult> {
    const request = http.createHttp();
    try {
      const headers = this.createHeadersWithContentType(accessToken, contentType);
      const options: http.HttpRequestOptions = {
        method: method,
        extraData: payload,
        header: headers,
        readTimeout: 60000,
        connectTimeout: 60000,
        expectDataType: http.HttpDataType.STRING,
        maxLimit: 104857600
      };
      const response = await request.request(url, options);
      const statusCode = response.responseCode as number;
      const body = this.responseBodyToString(response.result);
      return {
        ok: statusCode >= 200 && statusCode < 300,
        statusCode: statusCode,
        body: body,
        errorMessage: statusCode >= 200 && statusCode < 300 ? '' : `HTTP ${statusCode}`
      };
    } catch (error) {
      return {
        ok: false,
        statusCode: 0,
        body: '',
        errorMessage: `${error}`
      };
    } finally {
      request.destroy();
    }
  }

  private createHeaders(accessToken: string): MatrixHttpHeaders {
    return this.createHeadersWithContentType(accessToken, 'application/json');
  }

  private createHeadersWithContentType(accessToken: string, contentType: string): MatrixHttpHeaders {
    if (accessToken.length === 0) {
      const headers: MatrixHttpHeaders = {
        'Content-Type': contentType,
        'Accept': 'application/json',
        'Authorization': '',
        'User-Agent': 'ElementXHarmony/26.08.4'
      };
      return headers;
    }
    const headersWithAuth: MatrixHttpHeaders = {
      'Content-Type': contentType,
      'Accept': 'application/json',
      'Authorization': `Bearer ${accessToken}`,
      'User-Agent': 'ElementXHarmony/26.08.4'
    };
    return headersWithAuth;
  }

  private createPasswordLoginPayload(username: string, password: string, deviceDisplayName: string): string {
    const escapedUsername = this.escapeJson(username);
    const escapedPassword = this.escapeJson(password);
    const escapedDeviceName = this.escapeJson(deviceDisplayName);
    return `{"type":"m.login.password","identifier":{"type":"m.id.user","user":"${escapedUsername}"},"password":"${escapedPassword}","initial_device_display_name":"${escapedDeviceName}"}`;
  }

  private createTokenLoginPayload(loginToken: string, deviceDisplayName: string): string {
    const escapedToken = this.escapeJson(loginToken);
    const escapedDeviceName = this.escapeJson(deviceDisplayName);
    return `{"type":"m.login.token","token":"${escapedToken}","initial_device_display_name":"${escapedDeviceName}"}`;
  }

  private createTextMessagePayload(body: string): string {
    return `{"msgtype":"m.text","body":"${this.escapeJson(body)}"}`;
  }

  private createMessagePayload(body: string, msgtype: string): string {
    const cleanMsgtype = msgtype.length > 0 ? msgtype : 'm.text';
    return `{"msgtype":"${this.escapeJson(cleanMsgtype)}","body":"${this.escapeJson(body)}"}`;
  }

  private createFormattedMessagePayload(body: string, formattedBody: string, msgtype: string): string {
    const cleanMsgtype = msgtype.length > 0 ? msgtype : 'm.text';
    return `{"msgtype":"${this.escapeJson(cleanMsgtype)}","body":"${this.escapeJson(body)}","format":"org.matrix.custom.html","formatted_body":"${this.escapeJson(formattedBody)}"}`;
  }

  private createMediaMessagePayload(msgtype: string, body: string, contentUri: string, mimeType: string, size: number): string {
    const safeSize = size > 0 ? size : 0;
    return `{"msgtype":"${this.escapeJson(msgtype)}","body":"${this.escapeJson(body)}","url":"${this.escapeJson(contentUri)}","info":{"mimetype":"${this.escapeJson(mimeType)}","size":${safeSize}}}`;
  }

  private createDisplayNamePayload(displayName: string): string {
    return `{"displayname":"${this.escapeJson(displayName)}"}`;
  }

  private createRoomNamePayload(name: string): string {
    return `{"name":"${this.escapeJson(name)}"}`;
  }

  private createRoomTopicPayload(topic: string): string {
    return `{"topic":"${this.escapeJson(topic)}"}`;
  }

  private createOwnRoomDisplayNamePayload(displayName: string): string {
    return `{"membership":"join","displayname":"${this.escapeJson(displayName)}"}`;
  }

  private createRoomMembershipPayload(userId: string, reason: string): string {
    const escapedUserId = this.escapeJson(userId);
    const trimmedReason = reason.trim();
    if (trimmedReason.length === 0) {
      return `{"user_id":"${escapedUserId}"}`;
    }
    return `{"user_id":"${escapedUserId}","reason":"${this.escapeJson(trimmedReason)}"}`;
  }

  private postRoomMembershipAction(
    homeserverBaseUrl: string,
    accessToken: string,
    roomId: string,
    action: string,
    userId: string,
    reason: string
  ): Promise<MatrixHttpResult> {
    return this.post(
      `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/rooms/${encodeURIComponent(roomId)}/${action}`,
      this.createRoomMembershipPayload(userId, reason),
      accessToken
    );
  }

  private createFullyReadMarkerPayload(eventId: string): string {
    return `{"m.fully_read":"${this.escapeJson(eventId)}"}`;
  }

  private createReportRoomPayload(reason: string): string {
    return `{"reason":"${this.escapeJson(reason.trim())}"}`;
  }

  private createMarkedUnreadPayload(unread: boolean): string {
    return `{"unread":${unread ? 'true' : 'false'}}`;
  }

  private createJoinRoomPayload(serverNames: string[]): string {
    const cleanNames = serverNames.filter((serverName: string) => serverName.trim().length > 0);
    if (cleanNames.length === 0) {
      return '{}';
    }
    const encodedNames = cleanNames.map((serverName: string) => `"${this.escapeJson(serverName.trim())}"`);
    return `{"server_name":[${encodedNames.join(',')}]}`;
  }

  private createDirectRoomPayload(userId: string): string {
    return `{"preset":"trusted_private_chat","invite":["${this.escapeJson(userId)}"],"is_direct":true}`;
  }

  private ignoredUsersAccountDataUrl(homeserverBaseUrl: string, userId: string): string {
    return `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/user/${encodeURIComponent(userId)}/account_data/m.ignored_user_list`;
  }

  private roomAccountDataUrl(homeserverBaseUrl: string, userId: string, roomId: string, eventType: string): string {
    return `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/user/${encodeURIComponent(userId)}/rooms/${encodeURIComponent(roomId)}/account_data/${encodeURIComponent(eventType)}`;
  }

  private roomTagUrl(homeserverBaseUrl: string, userId: string, roomId: string, tag: string): string {
    return `${this.trimTrailingSlash(homeserverBaseUrl)}/_matrix/client/v3/user/${encodeURIComponent(userId)}/rooms/${encodeURIComponent(roomId)}/tags/${encodeURIComponent(tag)}`;
  }

  private parseIgnoredUsers(raw: string): string[] {
    try {
      const parsed = JSON.parse(raw) as MatrixIgnoredUsersContent;
      if (parsed.ignored_users === undefined || parsed.ignored_users === null) {
        return [];
      }
      return this.normalizedUserIds(Object.keys(parsed.ignored_users));
    } catch (error) {
      return [];
    }
  }

  private createIgnoredUsersPayload(ignoredUsers: string[]): string {
    const users = this.normalizedUserIds(ignoredUsers);
    const entries = users.map((userId: string) => `"${this.escapeJson(userId)}":{}`);
    return `{"ignored_users":{${entries.join(',')}}}`;
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

  private createMediaUploadResponse(ok: boolean, contentUri: string, raw: string, errorMessage: string): MatrixMediaUploadResponse {
    return {
      ok: ok,
      contentUri: contentUri,
      raw: raw,
      errorMessage: errorMessage
    };
  }

  private createIgnoredUsersResponse(ok: boolean, ignoredUsers: string[], raw: string, errorMessage: string): MatrixIgnoredUsersResponse {
    return {
      ok: ok,
      ignoredUsers: ignoredUsers,
      raw: raw,
      errorMessage: errorMessage
    };
  }

  private responseBodyToString(result: string | Object | ArrayBuffer): string {
    if (typeof result === 'string') {
      return result;
    }
    if (result instanceof ArrayBuffer) {
      return '';
    }
    return JSON.stringify(result);
  }

  private findStringValue(jsonText: string, key: string): string {
    const pattern = new RegExp(`"${key}"\\s*:\\s*"([^"]*)"`);
    const match = pattern.exec(jsonText);
    if (match === null || match.length < 2) {
      return '';
    }
    return this.unescapeJson(match[1]);
  }

  private normalizeServerName(value: string): string {
    let normalized = value.trim();
    if (normalized.startsWith('https://')) {
      normalized = normalized.substring(8);
    } else if (normalized.startsWith('http://')) {
      normalized = normalized.substring(7);
    }
    return this.trimTrailingSlash(normalized);
  }

  private trimTrailingSlash(value: string): string {
    let result = value.trim();
    while (result.endsWith('/')) {
      result = result.substring(0, result.length - 1);
    }
    return result;
  }

  private escapeJson(value: string): string {
    return value.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n').replace(/\r/g, '\\r');
  }

  private unescapeJson(value: string): string {
    return value.replace(/\\"/g, '"').replace(/\\\\/g, '\\');
  }

  private createWellKnownResult(
    ok: boolean,
    homeserverBaseUrl: string,
    identityServerBaseUrl: string,
    raw: string,
    errorMessage: string
  ): MatrixWellKnownResult {
    return {
      ok: ok,
      homeserverBaseUrl: homeserverBaseUrl,
      identityServerBaseUrl: identityServerBaseUrl,
      raw: raw,
      errorMessage: errorMessage
    };
  }

  private createLoginResponse(
    ok: boolean,
    accessToken: string,
    userId: string,
    deviceId: string,
    homeserverBaseUrl: string,
    raw: string,
    errorMessage: string
  ): MatrixLoginResponse {
    return {
      ok: ok,
      accessToken: accessToken,
      userId: userId,
      deviceId: deviceId,
      homeserverBaseUrl: homeserverBaseUrl,
      raw: raw,
      errorMessage: errorMessage
    };
  }

  private createSyncResponse(ok: boolean, nextBatch: string, raw: string, errorMessage: string): MatrixSyncResponse {
    return {
      ok: ok,
      nextBatch: nextBatch,
      raw: raw,
      errorMessage: errorMessage
    };
  }

  private createProfileResponse(
    ok: boolean,
    userId: string,
    displayName: string,
    avatarUrl: string,
    raw: string,
    errorMessage: string
  ): MatrixProfileResponse {
    return {
      ok: ok,
      userId: userId,
      displayName: displayName,
      avatarUrl: avatarUrl,
      raw: raw,
      errorMessage: errorMessage
    };
  }

  private createJoinRoomResponse(ok: boolean, roomId: string, raw: string, errorMessage: string): MatrixJoinRoomResponse {
    return {
      ok: ok,
      roomId: roomId,
      raw: raw,
      errorMessage: errorMessage
    };
  }

  private createRoomResponse(ok: boolean, roomId: string, raw: string, errorMessage: string): MatrixCreateRoomResponse {
    return {
      ok: ok,
      roomId: roomId,
      raw: raw,
      errorMessage: errorMessage
    };
  }
}
