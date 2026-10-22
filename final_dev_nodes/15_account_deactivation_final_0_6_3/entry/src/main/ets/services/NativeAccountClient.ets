import http from '@ohos.net.http';
import asset from '@ohos.security.asset';
import util from '@ohos.util';
import fs from '@ohos.file.fs';
import common from '@ohos.app.ability.common';
import { AccountClient, AccountResponse, AccountSession, AccountSessionStore, AccountTransport, validateAccountSession } from './AccountClient';

interface SdkError {
  code: number;
}

interface SessionMetadata {
  schemaVersion: number;
  userId: string;
  deviceId: string;
  homeserver: string;
  phase: string;
}

export class NativeAccountTransport implements AccountTransport {
  private requests: Set<http.HttpRequest> = new Set<http.HttpRequest>();

  async post(homeserver: string, path: string, token: string, body: string): Promise<AccountResponse> {
    const request: http.HttpRequest = http.createHttp();
    this.requests.add(request);
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token.length > 0) {
      headers['Authorization'] = 'Bearer ' + token;
    }
    try {
      const response: http.HttpResponse = await request.request(homeserver + path, {
        method: http.RequestMethod.POST, header: headers, extraData: body,
        expectDataType: http.HttpDataType.STRING, connectTimeout: 15000, readTimeout: 60000,
        usingCache: false
      });
      return { status: response.responseCode, body: response.result as string };
    } finally {
      this.requests.delete(request);
      request.destroy();
    }
  }

  close(): void {
    this.requests.forEach((request: http.HttpRequest) => request.destroy());
    this.requests.clear();
  }
}

export class NativeAccountSessionStore implements AccountSessionStore {
  private filesDir: string;
  private cacheDir: string;
  private alias: Uint8Array = new util.TextEncoder().encode('element.account.session.v1');

  constructor(filesDir: string, cacheDir: string) {
    this.filesDir = filesDir;
    this.cacheDir = cacheDir;
  }

  async read(): Promise<AccountSession | null> {
    const query: Map<asset.Tag, asset.Value> = new Map<asset.Tag, asset.Value>();
    query.set(asset.Tag.ALIAS, this.alias);
    query.set(asset.Tag.RETURN_TYPE, asset.ReturnType.ALL);
    query.set(asset.Tag.RETURN_LIMIT, 1);
    try {
      const records: Array<asset.AssetMap> = await asset.query(query);
      if (records.length === 0) {
        return null;
      }
      const secret: asset.Value | undefined = records[0].get(asset.Tag.SECRET);
      if (!(secret instanceof Uint8Array)) {
        throw new Error('Secure session payload unavailable');
      }
      const json: string = new util.TextDecoder('utf-8', { fatal: true }).decodeWithStream(secret);
      const session: AccountSession = validateAccountSession(JSON.parse(json) as AccountSession);
      if (session.phase === 'active') {
        const metadata: SessionMetadata = JSON.parse(await fs.readText(
          this.sessionPath(this.filesDir, session) + '/session.json')) as SessionMetadata;
        if (metadata.userId !== session.userId || metadata.deviceId !== session.deviceId ||
          metadata.homeserver !== session.homeserver ||
          (metadata.phase !== 'active' && metadata.phase !== 'cleanup_pending')) {
          throw new Error('Local and secure session records disagree');
        }
        // File tombstone also protects restore if updating the Asset record failed.
        session.phase = metadata.phase;
      }
      return session;
    } catch (error) {
      if ((error as SdkError).code === 24000002) {
        return null;
      }
      throw error as Error;
    }
  }

  async save(session: AccountSession): Promise<void> {
    validateAccountSession(session);
    const directory: string = this.sessionPath(this.filesDir, session);
    await this.ensureDirectory(directory);
    await this.ensureDirectory(this.sessionPath(this.cacheDir, session));
    const metadata: SessionMetadata = {
      schemaVersion: 1, userId: session.userId, deviceId: session.deviceId, homeserver: session.homeserver, phase: session.phase
    };
    const file: fs.File = await fs.open(directory + '/session.json', fs.OpenMode.CREATE | fs.OpenMode.READ_WRITE | fs.OpenMode.TRUNC);
    try {
      await fs.write(file.fd, JSON.stringify(metadata));
    } finally {
      await fs.close(file);
    }
    const attributes: Map<asset.Tag, asset.Value> = new Map<asset.Tag, asset.Value>();
    attributes.set(asset.Tag.ALIAS, this.alias);
    attributes.set(asset.Tag.SECRET, new util.TextEncoder().encode(JSON.stringify(session)));
    attributes.set(asset.Tag.ACCESSIBILITY, asset.Accessibility.DEVICE_FIRST_UNLOCKED);
    attributes.set(asset.Tag.AUTH_TYPE, asset.AuthType.NONE);
    attributes.set(asset.Tag.SYNC_TYPE, asset.SyncType.NEVER);
    attributes.set(asset.Tag.CONFLICT_RESOLUTION, asset.ConflictResolution.OVERWRITE);
    await asset.add(attributes);
  }

  private async ensureDirectory(path: string): Promise<void> {
    try {
      await fs.mkdir(path, true);
    } catch (error) {
      if ((error as SdkError).code !== 13900015) {
        throw error as Error;
      }
      const existing: fs.Stat = await fs.stat(path);
      if (!existing.isDirectory()) {
        throw error as Error;
      }
    }
  }

  async clear(session: AccountSession): Promise<void> {
    // Only this account/device's app-private data is removed, never another session.
    for (const path of [this.sessionPath(this.cacheDir, session), this.sessionPath(this.filesDir, session)]) {
      if (await fs.access(path)) {
        await fs.rmdir(path);
      }
    }
    const query: Map<asset.Tag, asset.Value> = new Map<asset.Tag, asset.Value>();
    query.set(asset.Tag.ALIAS, this.alias);
    try {
      await asset.remove(query);
    } catch (error) {
      if ((error as SdkError).code !== 24000002) {
        throw error as Error;
      }
    }
  }

  private sessionPath(root: string, session: AccountSession): string {
    return root + '/account-sessions/' + encodeURIComponent(session.userId) + '/' + encodeURIComponent(session.deviceId);
  }
}

export function createAccountClient(context: common.Context): AccountClient {
  return new AccountClient(new NativeAccountTransport(), new NativeAccountSessionStore(context.filesDir, context.cacheDir));
}
