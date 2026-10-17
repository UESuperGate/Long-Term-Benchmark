export interface NativeBridgeStatus {
  contractVersion: string;
  addonVersion: string;
  abiVersion: number;
  availability: string;
  sdkLinked: boolean;
  sdkVersion: string;
  message: string;
}

export interface NativeBridgeCapabilityInfo {
  capability: string;
  status: string;
  detail: string;
}

export interface NativeBridgeError {
  code: string;
  message: string;
  retryable: boolean;
  nativeCode: number;
}

export interface NativeClientStatus {
  handle: number;
  state: string;
}

export interface NativeClientOperationResult {
  ok: boolean;
  client: NativeClientStatus | null;
  error: NativeBridgeError | null;
}

export interface NativeDataOperationResult {
  ok: boolean;
  value: string | null;
  error: NativeBridgeError | null;
}

export interface MatrixNativeAddon {
  getBridgeStatus(): NativeBridgeStatus;
  getCapabilities(): NativeBridgeCapabilityInfo[];
  createClient(homeserverUrl: string): Promise<NativeClientOperationResult>;
  restoreClient(homeserverUrl: string, userId: string, deviceId: string,
    accessToken: string, refreshToken: string): Promise<NativeClientOperationResult>;
  releaseClient(handle: number): Promise<NativeClientOperationResult>;
  getClientStatus(handle: number): Promise<NativeClientOperationResult>;
  syncRooms(handle: number): Promise<NativeDataOperationResult>;
  loadTimeline(handle: number, roomId: string, fromToken: string): Promise<NativeDataOperationResult>;
  sendText(handle: number, roomId: string, body: string,
    transactionId: string): Promise<NativeDataOperationResult>;
}

declare const matrixNativeAddon: MatrixNativeAddon;
export default matrixNativeAddon;
