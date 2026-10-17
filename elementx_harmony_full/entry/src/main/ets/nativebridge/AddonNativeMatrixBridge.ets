import matrixNativeAddon from 'libmatrix_native.so';
import { NativeMatrixBridge } from './NativeMatrixBridge';
import {
  NativeBridgeCapabilityInfo,
  NativeBridgeStatus,
  NativeClientOperationResult,
  NativeDataOperationResult,
  NativeSessionRestoreRequest
} from './NativeMatrixBridgeTypes';

export class AddonNativeMatrixBridge implements NativeMatrixBridge {
  getStatus(): NativeBridgeStatus {
    return matrixNativeAddon.getBridgeStatus() as NativeBridgeStatus;
  }

  getCapabilities(): NativeBridgeCapabilityInfo[] {
    return matrixNativeAddon.getCapabilities() as NativeBridgeCapabilityInfo[];
  }

  createClient(homeserverUrl: string): Promise<NativeClientOperationResult> {
    return matrixNativeAddon.createClient(homeserverUrl) as Promise<NativeClientOperationResult>;
  }

  restoreClient(request: NativeSessionRestoreRequest): Promise<NativeClientOperationResult> {
    return matrixNativeAddon.restoreClient(
      request.homeserverUrl,
      request.userId,
      request.deviceId,
      request.accessToken,
      request.refreshToken === null ? '' : request.refreshToken
    ) as Promise<NativeClientOperationResult>;
  }

  releaseClient(handle: number): Promise<NativeClientOperationResult> {
    return matrixNativeAddon.releaseClient(handle) as Promise<NativeClientOperationResult>;
  }

  getClientStatus(handle: number): Promise<NativeClientOperationResult> {
    return matrixNativeAddon.getClientStatus(handle) as Promise<NativeClientOperationResult>;
  }

  syncRooms(handle: number): Promise<NativeDataOperationResult> {
    return matrixNativeAddon.syncRooms(handle) as Promise<NativeDataOperationResult>;
  }

  loadTimeline(handle: number, roomId: string, fromToken: string | null): Promise<NativeDataOperationResult> {
    return matrixNativeAddon.loadTimeline(handle, roomId, fromToken === null ? '' : fromToken) as
      Promise<NativeDataOperationResult>;
  }

  sendText(handle: number, roomId: string, body: string, transactionId: string): Promise<NativeDataOperationResult> {
    return matrixNativeAddon.sendText(handle, roomId, body, transactionId) as Promise<NativeDataOperationResult>;
  }
}
