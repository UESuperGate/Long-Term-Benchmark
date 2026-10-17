import {
  NativeBridgeCapabilityInfo,
  NativeBridgeStatus,
  NativeClientOperationResult,
  NativeDataOperationResult,
  NativeSessionRestoreRequest
} from './NativeMatrixBridgeTypes';

/** Owns opaque native Matrix Client handles without exposing credentials. */
export interface NativeMatrixBridge {
  getStatus(): NativeBridgeStatus;
  getCapabilities(): NativeBridgeCapabilityInfo[];
  createClient(homeserverUrl: string): Promise<NativeClientOperationResult>;
  restoreClient(request: NativeSessionRestoreRequest): Promise<NativeClientOperationResult>;
  releaseClient(handle: number): Promise<NativeClientOperationResult>;
  getClientStatus(handle: number): Promise<NativeClientOperationResult>;
  syncRooms(handle: number): Promise<NativeDataOperationResult>;
  loadTimeline(handle: number, roomId: string, fromToken: string | null): Promise<NativeDataOperationResult>;
  sendText(handle: number, roomId: string, body: string, transactionId: string): Promise<NativeDataOperationResult>;
}
