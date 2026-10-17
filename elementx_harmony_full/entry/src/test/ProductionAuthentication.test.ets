import { describe, expect, it } from '@ohos/hypium';
import {
  NativeBridgeAvailability,
  NativeBridgeCapabilityInfo,
  NativeBridgeStatus,
  NativeClientOperationResult,
  NativeDataOperationResult,
  NativeClientState,
  NativeMatrixBridge,
  NativeSessionRestoreRequest
} from '../main/ets/nativebridge/Index';
import {
  MatrixPasswordApi,
  NativeMatrixAuthenticationService
} from '../main/ets/matrix/production/NativeMatrixAuthenticationService';
import {
  MatrixHomeserverDetails,
  MatrixSessionRestoreRequest
} from '../main/ets/matrix/api/MatrixAuthentication';
import {
  MatrixLoginResponse,
  MatrixWellKnownResult
} from '../main/ets/services/MatrixClientServerApi';

class RecordingBridge implements NativeMatrixBridge {
  createCount: number = 0;
  restoreRequests: NativeSessionRestoreRequest[] = [];
  releasedHandles: number[] = [];
  ready: boolean = true;

  getStatus(): NativeBridgeStatus {
    return {
      contractVersion: '3',
      addonVersion: 'test',
      abiVersion: 3,
      availability: this.ready ? NativeBridgeAvailability.Ready : NativeBridgeAvailability.Unavailable,
      sdkLinked: this.ready,
      sdkVersion: this.ready ? 'test-sdk' : '',
      message: this.ready ? 'ready' : 'unavailable'
    };
  }

  getCapabilities(): NativeBridgeCapabilityInfo[] {
    return [];
  }

  async createClient(_homeserverUrl: string): Promise<NativeClientOperationResult> {
    this.createCount += 1;
    return {
      ok: true,
      client: { handle: 41, state: NativeClientState.Ready },
      error: null
    };
  }

  async restoreClient(request: NativeSessionRestoreRequest): Promise<NativeClientOperationResult> {
    this.restoreRequests.push(request);
    return {
      ok: true,
      client: { handle: 41, state: NativeClientState.Ready },
      error: null
    };
  }

  async releaseClient(handle: number): Promise<NativeClientOperationResult> {
    this.releasedHandles.push(handle);
    return {
      ok: true,
      client: { handle: handle, state: NativeClientState.Released },
      error: null
    };
  }

  async getClientStatus(handle: number): Promise<NativeClientOperationResult> {
    return {
      ok: true,
      client: { handle: handle, state: NativeClientState.Ready },
      error: null
    };
  }

  async syncRooms(_handle: number): Promise<NativeDataOperationResult> {
    return { ok: true, value: '{"rooms":[],"totalCount":0}', error: null };
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
}

class RecordingPasswordApi implements MatrixPasswordApi {
  acceptLogin: boolean = true;

  async discoverHomeserver(_serverName: string): Promise<MatrixWellKnownResult> {
    return {
      ok: true,
      homeserverBaseUrl: 'https://matrix.example.org',
      identityServerBaseUrl: '',
      raw: '{}',
      errorMessage: ''
    };
  }

  async loginWithPassword(
    homeserverBaseUrl: string,
    _username: string,
    _password: string,
    _deviceDisplayName: string
  ): Promise<MatrixLoginResponse> {
    if (!this.acceptLogin) {
      return {
        ok: false,
        accessToken: '',
        userId: '',
        deviceId: '',
        homeserverBaseUrl: homeserverBaseUrl,
        raw: '{}',
        errorMessage: 'rejected'
      };
    }
    return {
      ok: true,
      accessToken: 'secret-token',
      userId: '@alice:example.org',
      deviceId: 'DEVICE',
      homeserverBaseUrl: homeserverBaseUrl,
      raw: '{}',
      errorMessage: ''
    };
  }
}

const HOMESERVER: MatrixHomeserverDetails = {
  canonicalUrl: 'https://matrix.example.org',
  serverName: 'matrix.example.org',
  supportsPasswordLogin: true,
  supportsOidcLogin: false
};

export default function productionAuthenticationTest(): void {
  describe('productionAuthentication', () => {
    it('resolves a canonical homeserver', 0, async () => {
      const service = new NativeMatrixAuthenticationService(new RecordingBridge(), new RecordingPasswordApi());
      const result = await service.resolveHomeserver('example.org');
      expect(result.success).assertTrue();
      expect(result.value?.canonicalUrl).assertEqual('https://matrix.example.org');
    });

    it('owns a native handle for a successful login', 0, async () => {
      const bridge = new RecordingBridge();
      const service = new NativeMatrixAuthenticationService(bridge, new RecordingPasswordApi());
      const result = await service.loginWithPassword(HOMESERVER, {
        username: 'alice',
        password: 'password',
        deviceDisplayName: 'Element X Harmony'
      });
      expect(result.success).assertTrue();
      expect(result.value?.handle.runtimeId).assertEqual('native:41');
      expect(bridge.createCount).assertEqual(0);
      expect(bridge.restoreRequests.length).assertEqual(1);
      expect(bridge.restoreRequests[0].accessToken).assertEqual('secret-token');
    });

    it('does not allocate a native handle when login is rejected', 0, async () => {
      const bridge = new RecordingBridge();
      const api = new RecordingPasswordApi();
      api.acceptLogin = false;
      const service = new NativeMatrixAuthenticationService(bridge, api);
      const result = await service.loginWithPassword(HOMESERVER, {
        username: 'alice',
        password: 'bad-password',
        deviceDisplayName: 'Element X Harmony'
      });
      expect(result.success).assertFalse();
      expect(bridge.restoreRequests.length).assertEqual(0);
      expect(bridge.releasedHandles.length).assertEqual(0);
    });

    it('restores a persisted session into the native SDK client', 0, async () => {
      const bridge = new RecordingBridge();
      const service = new NativeMatrixAuthenticationService(bridge, new RecordingPasswordApi());
      const request: MatrixSessionRestoreRequest = {
        sessionId: '@alice:example.org',
        userId: '@alice:example.org',
        deviceId: 'DEVICE',
        homeserverUrl: 'https://matrix.example.org',
        accessToken: 'secret-token',
        refreshToken: null,
        databasePassphrase: null
      };
      const result = await service.restoreSession(request);
      expect(result.success).assertTrue();
      expect(result.value?.runtimeId).assertEqual('native:41');
      expect(bridge.restoreRequests.length).assertEqual(1);
      expect(bridge.restoreRequests[0].userId).assertEqual('@alice:example.org');
    });
  });
}
