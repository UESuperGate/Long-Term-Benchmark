import { describe, expect, it } from '@ohos/hypium';
import { AuthenticationSource } from '../main/ets/appnav/RootNavigationState';
import { RootNavigationStateMachine } from '../main/ets/appnav/RootNavigationStateMachine';
import { DomainErrorCode } from '../main/ets/core/DomainResult';
import { NativeRoomListDataSource } from '../main/ets/matrix/production/NativeRoomListDataSource';
import {
  NativeBridgeAvailability,
  NativeBridgeCapabilityInfo,
  NativeBridgeErrorCode,
  NativeBridgeStatus,
  NativeClientOperationResult,
  NativeClientState,
  NativeDataOperationResult,
  NativeMatrixBridge,
  NativeSessionRestoreRequest
} from '../main/ets/nativebridge/Index';
import { RoomListFilters } from '../main/ets/rooms/RoomListFilters';
import { SessionLoginType, SessionMetadata } from '../main/ets/session/SessionModels';

class RoomTransportBridge implements NativeMatrixBridge {
  syncCount: number = 0;
  syncResult: NativeDataOperationResult = {
    ok: true,
    value: '{"rooms":[],"totalCount":0}',
    error: null
  };

  getStatus(): NativeBridgeStatus {
    return {
      contractVersion: '3',
      addonVersion: 'test',
      abiVersion: 3,
      availability: NativeBridgeAvailability.Ready,
      sdkLinked: true,
      sdkVersion: 'test',
      message: 'ready'
    };
  }

  getCapabilities(): NativeBridgeCapabilityInfo[] {
    return [];
  }

  async createClient(_homeserverUrl: string): Promise<NativeClientOperationResult> {
    return this.clientResult();
  }

  async restoreClient(_request: NativeSessionRestoreRequest): Promise<NativeClientOperationResult> {
    return this.clientResult();
  }

  async releaseClient(_handle: number): Promise<NativeClientOperationResult> {
    return this.clientResult();
  }

  async getClientStatus(_handle: number): Promise<NativeClientOperationResult> {
    return this.clientResult();
  }

  async syncRooms(_handle: number): Promise<NativeDataOperationResult> {
    this.syncCount += 1;
    return this.syncResult;
  }

  async loadTimeline(_handle: number, _roomId: string, _fromToken: string | null): Promise<NativeDataOperationResult> {
    return { ok: true, value: '{"events":[],"end":null}', error: null };
  }

  async sendText(
    _handle: number,
    _roomId: string,
    _body: string,
    _transactionId: string
  ): Promise<NativeDataOperationResult> {
    return { ok: true, value: '{"eventId":"$sent"}', error: null };
  }

  private clientResult(): NativeClientOperationResult {
    return {
      ok: true,
      client: { handle: 41, state: NativeClientState.Ready },
      error: null
    };
  }
}

function loggedInNavigation(): RootNavigationStateMachine {
  const navigation = new RootNavigationStateMachine();
  const attemptId = navigation.beginAuthentication(AuthenticationSource.Password);
  const metadata: SessionMetadata = {
    sessionId: '@alice:example.org',
    userId: '@alice:example.org',
    deviceId: 'DEVICE',
    homeserverUrl: 'https://matrix.example.org',
    loginType: SessionLoginType.Password,
    loginTimestampMs: 1,
    isTokenValid: true,
    position: 1,
    lastUsageIndex: 1,
    userDisplayName: null,
    userAvatarUrl: null
  };
  navigation.completeAuthentication(attemptId, metadata, {
    sessionId: metadata.sessionId,
    runtimeId: 'native:41'
  });
  return navigation;
}

export default function productionRoomTransportTest(): void {
  describe('productionRoomTransport', () => {
    it('maps an SDK room sync response', 0, async () => {
      const bridge = new RoomTransportBridge();
      bridge.syncResult = {
        ok: true,
        value: '{"rooms":[{"roomId":"!room:example.org","displayName":"General","canonicalAlias":null,"avatarUrl":null,"membership":"joined","category":"group","isFavorite":false,"isDirect":false,"isMarkedUnread":true,"unreadNotificationCount":2,"unreadMentionCount":1,"activeMembersCount":3,"latestEventTimestampMs":10,"latestEventPreview":null}],"totalCount":1}',
        error: null
      };
      const source = new NativeRoomListDataSource(bridge, loggedInNavigation());
      const result = await source.loadInitial(20, RoomListFilters.all());
      expect(result.success).assertTrue();
      expect(result.value?.rooms.length).assertEqual(1);
      expect(result.value?.rooms[0].roomId).assertEqual('!room:example.org');
      expect(result.value?.rooms[0].unreadMentionCount).assertEqual(1);
    });

    it('fails before native sync without a session handle', 0, async () => {
      const bridge = new RoomTransportBridge();
      const source = new NativeRoomListDataSource(bridge, new RootNavigationStateMachine());
      const result = await source.loadInitial(20, RoomListFilters.all());
      expect(result.success).assertFalse();
      expect(result.error?.code).assertEqual(DomainErrorCode.SessionMissing);
      expect(bridge.syncCount).assertEqual(0);
    });

    it('maps native sync failures to an offline domain failure', 0, async () => {
      const bridge = new RoomTransportBridge();
      bridge.syncResult = {
        ok: false,
        value: null,
        error: {
          code: NativeBridgeErrorCode.SyncFailed,
          message: 'sync failed',
          retryable: true,
          nativeCode: 10
        }
      };
      const source = new NativeRoomListDataSource(bridge, loggedInNavigation());
      const result = await source.refresh(RoomListFilters.all());
      expect(result.success).assertFalse();
      expect(result.error?.code).assertEqual(DomainErrorCode.NetworkUnavailable);
    });
  });
}
