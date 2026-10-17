import { describe, expect, it } from '@ohos/hypium';
import { AuthenticationSource } from '../main/ets/appnav/RootNavigationState';
import { RootNavigationStateMachine } from '../main/ets/appnav/RootNavigationStateMachine';
import { DomainErrorCode } from '../main/ets/core/DomainResult';
import {
  LocalSendState,
  PaginationDirection,
  TextContent,
  TimelineContentKind
} from '../main/ets/matrix/api/TimelineModels';
import { NativeTimelineDataSource } from '../main/ets/matrix/production/NativeTimelineDataSource';
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
import { SessionLoginType, SessionMetadata } from '../main/ets/session/SessionModels';
import { TimelineController } from '../main/ets/timeline/TimelineController';

class TimelineTransportBridge implements NativeMatrixBridge {
  loadTokens: string[] = [];
  sendBodies: string[] = [];
  timelineResult: NativeDataOperationResult = {
    ok: true,
    value: '{"events":[],"end":null}',
    error: null
  };
  sendResult: NativeDataOperationResult = {
    ok: true,
    value: '{"eventId":"$sent:example.org"}',
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
    return { ok: true, value: '{"rooms":[],"totalCount":0}', error: null };
  }

  async loadTimeline(_handle: number, _roomId: string, fromToken: string | null): Promise<NativeDataOperationResult> {
    this.loadTokens.push(fromToken === null ? '' : fromToken);
    return this.timelineResult;
  }

  async sendText(
    _handle: number,
    _roomId: string,
    body: string,
    _transactionId: string
  ): Promise<NativeDataOperationResult> {
    this.sendBodies.push(body);
    return this.sendResult;
  }

  private clientResult(): NativeClientOperationResult {
    return {
      ok: true,
      client: { handle: 41, state: NativeClientState.Ready },
      error: null
    };
  }
}

function navigation(loggedIn: boolean = true): RootNavigationStateMachine {
  const value = new RootNavigationStateMachine();
  if (!loggedIn) {
    return value;
  }
  const attemptId = value.beginAuthentication(AuthenticationSource.Password);
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
  value.completeAuthentication(attemptId, metadata, {
    sessionId: metadata.sessionId,
    runtimeId: 'native:41'
  });
  return value;
}

export default function productionTimelineTransportTest(): void {
  describe('productionTimelineTransport', () => {
    it('maps SDK text and encrypted events', 0, async () => {
      const bridge = new TimelineTransportBridge();
      bridge.timelineResult = {
        ok: true,
        value: '{"events":[{"event_id":"$one","sender":"@alice:example.org","type":"m.room.message","origin_server_ts":10,"content":{"msgtype":"m.text","body":"hello"}},{"event_id":"$two","sender":"@bob:example.org","type":"m.room.encrypted","origin_server_ts":20,"content":{"session_id":"session"}}],"end":"older"}',
        error: null
      };
      const source = new NativeTimelineDataSource(bridge, navigation());
      const result = await source.loadInitial('!room:example.org');
      expect(result.success).assertTrue();
      expect(result.value?.events.length).assertEqual(2);
      expect(result.value?.events[0].isOwn).assertTrue();
      expect(result.value?.events[0].content.kind).assertEqual(TimelineContentKind.Text);
      expect(result.value?.events[1].content.kind).assertEqual(TimelineContentKind.UnableToDecrypt);
    });

    it('reuses the native backward pagination token', 0, async () => {
      const bridge = new TimelineTransportBridge();
      bridge.timelineResult = { ok: true, value: '{"events":[],"end":"older"}', error: null };
      const source = new NativeTimelineDataSource(bridge, navigation());
      await source.loadInitial('!room:example.org');
      await source.paginate('!room:example.org', PaginationDirection.Backwards);
      expect(bridge.loadTokens.length).assertEqual(2);
      expect(bridge.loadTokens[1]).assertEqual('older');
    });

    it('acknowledges a native text send with the server event id', 0, async () => {
      const bridge = new TimelineTransportBridge();
      const controller = new TimelineController(
        '!room:example.org',
        new NativeTimelineDataSource(bridge, navigation())
      );
      const content: TextContent = { kind: TimelineContentKind.Text, body: 'hello', formattedBody: null };
      const result = await controller.send({
        transactionId: 'txn-1',
        content: content,
        replyToEventId: null
      }, '@alice:example.org', 100);
      expect(result.success).assertTrue();
      expect(result.value?.items[0].eventId).assertEqual('$sent:example.org');
      expect(bridge.sendBodies[0]).assertEqual('hello');
    });

    it('acknowledges a successful retry instead of leaving it sending', 0, async () => {
      const bridge = new TimelineTransportBridge();
      bridge.sendResult = {
        ok: false,
        value: null,
        error: { code: NativeBridgeErrorCode.SendFailed, message: 'offline', retryable: true, nativeCode: 14 }
      };
      const controller = new TimelineController(
        '!room:example.org',
        new NativeTimelineDataSource(bridge, navigation())
      );
      const content: TextContent = { kind: TimelineContentKind.Text, body: 'retry me', formattedBody: null };
      await controller.send({ transactionId: 'txn-retry', content: content, replyToEventId: null },
        '@alice:example.org', 100);
      bridge.sendResult = { ok: true, value: '{"eventId":"$retried:example.org"}', error: null };
      const result = await controller.retry('txn-retry');
      expect(result.success).assertTrue();
      expect(result.value?.items[0].eventId).assertEqual('$retried:example.org');
      expect(result.value?.sendQueue[0].state).assertEqual(LocalSendState.Sent);
    });

    it('fails before native work when no authenticated handle exists', 0, async () => {
      const bridge = new TimelineTransportBridge();
      const source = new NativeTimelineDataSource(bridge, navigation(false));
      const result = await source.loadInitial('!room:example.org');
      expect(result.success).assertFalse();
      expect(result.error?.code).assertEqual(DomainErrorCode.SessionMissing);
      expect(bridge.loadTokens.length).assertEqual(0);
    });
  });
}
