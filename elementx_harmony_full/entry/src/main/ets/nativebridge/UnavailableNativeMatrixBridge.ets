import { NativeMatrixBridge } from './NativeMatrixBridge';
import {
  NATIVE_MATRIX_BRIDGE_CONTRACT_VERSION,
  NativeBridgeAvailability,
  NativeBridgeCapability,
  NativeBridgeCapabilityInfo,
  NativeBridgeCapabilityStatus,
  NativeBridgeError,
  NativeBridgeErrorCode,
  NativeBridgeStatus,
  NativeClientOperationResult,
  NativeDataOperationResult,
  NativeSessionRestoreRequest
} from './NativeMatrixBridgeTypes';

const UNAVAILABLE_MESSAGE: string = 'Matrix SDK is not linked into this application';
const UNAVAILABLE_CAPABILITIES: NativeBridgeCapability[] = [
  NativeBridgeCapability.ClientRuntime,
  NativeBridgeCapability.Authentication,
  NativeBridgeCapability.SessionRestoration,
  NativeBridgeCapability.SlidingSync,
  NativeBridgeCapability.RoomList,
  NativeBridgeCapability.Timeline,
  NativeBridgeCapability.Encryption,
  NativeBridgeCapability.SessionVerification,
  NativeBridgeCapability.Media,
  NativeBridgeCapability.PushNotifications
];

export class UnavailableNativeMatrixBridge implements NativeMatrixBridge {
  getStatus(): NativeBridgeStatus {
    return {
      contractVersion: NATIVE_MATRIX_BRIDGE_CONTRACT_VERSION,
      addonVersion: '0.3.0-unavailable',
      abiVersion: 3,
      availability: NativeBridgeAvailability.Unavailable,
      sdkLinked: false,
      sdkVersion: '',
      message: UNAVAILABLE_MESSAGE
    };
  }

  getCapabilities(): NativeBridgeCapabilityInfo[] {
    const capabilities: NativeBridgeCapabilityInfo[] = [];
    UNAVAILABLE_CAPABILITIES.forEach((capability: NativeBridgeCapability) => {
      const capabilityInfo: NativeBridgeCapabilityInfo = {
        capability: capability,
        status: NativeBridgeCapabilityStatus.Unavailable,
        detail: UNAVAILABLE_MESSAGE
      };
      capabilities.push(capabilityInfo);
    });
    return capabilities;
  }

  async createClient(_homeserverUrl: string): Promise<NativeClientOperationResult> {
    return this.unavailableResult();
  }

  async restoreClient(_request: NativeSessionRestoreRequest): Promise<NativeClientOperationResult> {
    return this.unavailableResult();
  }

  async releaseClient(_handle: number): Promise<NativeClientOperationResult> {
    return this.unavailableResult();
  }

  async getClientStatus(_handle: number): Promise<NativeClientOperationResult> {
    return this.unavailableResult();
  }

  async syncRooms(_handle: number): Promise<NativeDataOperationResult> {
    return this.unavailableDataResult();
  }

  async loadTimeline(_handle: number, _roomId: string, _fromToken: string | null): Promise<NativeDataOperationResult> {
    return this.unavailableDataResult();
  }

  async sendText(
    _handle: number,
    _roomId: string,
    _body: string,
    _transactionId: string
  ): Promise<NativeDataOperationResult> {
    return this.unavailableDataResult();
  }

  private unavailableDataResult(): NativeDataOperationResult {
    const error: NativeBridgeError = {
      code: NativeBridgeErrorCode.MatrixSdkUnavailable,
      message: UNAVAILABLE_MESSAGE,
      retryable: false,
      nativeCode: 8
    };
    return { ok: false, value: null, error: error };
  }

  private unavailableResult(): NativeClientOperationResult {
    const error: NativeBridgeError = {
      code: NativeBridgeErrorCode.MatrixSdkUnavailable,
      message: UNAVAILABLE_MESSAGE,
      retryable: false,
      nativeCode: 8
    };
    return { ok: false, client: null, error: error };
  }
}
