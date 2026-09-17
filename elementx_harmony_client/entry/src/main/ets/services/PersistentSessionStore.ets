import preferences from '@ohos.data.preferences';
import common from '@ohos.app.ability.common';
import { SessionStoreRecord, TimelineMediaPreviewMode } from '../model/ClientRuntimeModels';

export interface PersistedSessionSnapshot {
  latestSessionId: string;
  sessions: SessionStoreRecord[];
}

interface SerializedSessionRecord {
  userId: string;
  deviceId: string;
  homeserver: string;
  accessToken: string;
  nextSyncBatch: string;
  ignoredUsers: string[];
  displayName: string;
  avatarUrl: string;
  userStatus: string;
  sendPublicReadReceipts: boolean;
  renderReadReceipts: boolean;
  timelineMediaPreviewMode: string;
  lastUsageIndex: number;
  isTokenValid: boolean;
}

interface SerializedSessionSnapshot {
  latestSessionId: string;
  sessions: SerializedSessionRecord[];
}

export class PersistentSessionStore {
  private static readonly STORE_NAME: string = 'element_x_session_store';
  private static readonly SNAPSHOT_KEY: string = 'session_snapshot';

  async load(context: common.UIAbilityContext): Promise<PersistedSessionSnapshot> {
    try {
      const store = await preferences.getPreferences(context, PersistentSessionStore.STORE_NAME);
      const value = await store.get(PersistentSessionStore.SNAPSHOT_KEY, '');
      if (typeof value !== 'string' || value.length === 0) {
        return this.emptySnapshot();
      }
      return this.decode(value);
    } catch (error) {
      return this.emptySnapshot();
    }
  }

  async save(context: common.UIAbilityContext, snapshot: PersistedSessionSnapshot): Promise<void> {
    try {
      const store = await preferences.getPreferences(context, PersistentSessionStore.STORE_NAME);
      await store.put(PersistentSessionStore.SNAPSHOT_KEY, this.encode(snapshot));
      await store.flush();
    } catch (error) {
    }
  }

  async clear(context: common.UIAbilityContext): Promise<void> {
    try {
      const store = await preferences.getPreferences(context, PersistentSessionStore.STORE_NAME);
      await store.put(PersistentSessionStore.SNAPSHOT_KEY, '');
      await store.flush();
    } catch (error) {
    }
  }

  private emptySnapshot(): PersistedSessionSnapshot {
    return {
      latestSessionId: '',
      sessions: []
    };
  }

  private encode(snapshot: PersistedSessionSnapshot): string {
    const serializable: SerializedSessionSnapshot = {
      latestSessionId: snapshot.latestSessionId,
      sessions: snapshot.sessions.map((item: SessionStoreRecord) => {
        const record: SerializedSessionRecord = {
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
      })
    };
    return JSON.stringify(serializable);
  }

  private decode(value: string): PersistedSessionSnapshot {
    try {
      const parsed = JSON.parse(value) as SerializedSessionSnapshot;
      const sessions: SessionStoreRecord[] = [];
      parsed.sessions.forEach((item: SerializedSessionRecord) => {
        sessions.push({
          userId: item.userId,
          deviceId: item.deviceId,
          homeserver: item.homeserver,
          accessToken: item.accessToken ?? '',
          nextSyncBatch: item.nextSyncBatch ?? '',
          ignoredUsers: this.normalizedUserIds(item.ignoredUsers),
          displayName: item.displayName ?? this.displayNameFromUserId(item.userId),
          avatarUrl: item.avatarUrl ?? '',
          userStatus: item.userStatus ?? 'Away',
          sendPublicReadReceipts: item.sendPublicReadReceipts ?? true,
          renderReadReceipts: item.renderReadReceipts ?? (item.sendPublicReadReceipts ?? true),
          timelineMediaPreviewMode: this.decodeTimelineMediaPreviewMode(item.timelineMediaPreviewMode),
          lastUsageIndex: item.lastUsageIndex,
          isTokenValid: item.isTokenValid
        });
      });
      return {
        latestSessionId: parsed.latestSessionId,
        sessions: sessions
      };
    } catch (error) {
      return this.emptySnapshot();
    }
  }

  private displayNameFromUserId(userId: string): string {
    const withoutAt = userId.startsWith('@') ? userId.substring(1) : userId;
    const localpart = withoutAt.split(':')[0];
    if (localpart.length === 0) {
      return 'Alice';
    }
    return `${localpart.substring(0, 1).toUpperCase()}${localpart.substring(1)}`;
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

  private decodeTimelineMediaPreviewMode(value: string | undefined): TimelineMediaPreviewMode {
    if (value === TimelineMediaPreviewMode.PrivateRooms) {
      return TimelineMediaPreviewMode.PrivateRooms;
    }
    if (value === TimelineMediaPreviewMode.AlwaysHide) {
      return TimelineMediaPreviewMode.AlwaysHide;
    }
    return TimelineMediaPreviewMode.AlwaysShow;
  }
}
