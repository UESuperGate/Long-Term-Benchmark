export const NATIVE_MATRIX_BRIDGE_CONTRACT_VERSION: string = '3';

export enum NativeBridgeAvailability {
  Unavailable = 'unavailable',
  Ready = 'ready',
  Failed = 'failed'
}

export enum NativeBridgeCapability {
  ClientRuntime = 'client_runtime',
  Authentication = 'authentication',
  SessionRestoration = 'session_restoration',
  SlidingSync = 'sliding_sync',
  RoomList = 'room_list',
  Timeline = 'timeline',
  Encryption = 'encryption',
  SessionVerification = 'session_verification',
  Media = 'media',
  PushNotifications = 'push_notifications'
}

export enum NativeBridgeCapabilityStatus {
  Unavailable = 'unavailable',
  Available = 'available',
  Degraded = 'degraded'
}

export enum NativeBridgeErrorCode {
  Ok = 'ok',
  InvalidArgument = 'invalid_argument',
  InvalidHomeserverUrl = 'invalid_homeserver_url',
  RuntimeUnavailable = 'runtime_unavailable',
  ClientBuildFailed = 'client_build_failed',
  ClientNotFound = 'client_not_found',
  HandleExhausted = 'handle_exhausted',
  InternalFailure = 'internal_failure',
  MatrixSdkUnavailable = 'matrix_sdk_unavailable',
  SessionRestoreFailed = 'session_restore_failed',
  SyncFailed = 'sync_failed',
  SerializationFailed = 'serialization_failed',
  RoomNotFound = 'room_not_found',
  TimelineFailed = 'timeline_failed',
  SendFailed = 'send_failed'
}

export enum NativeClientState {
  None = 'none',
  Ready = 'ready',
  Released = 'released'
}

export interface NativeBridgeStatus {
  contractVersion: string;
  addonVersion: string;
  abiVersion: number;
  availability: NativeBridgeAvailability;
  sdkLinked: boolean;
  sdkVersion: string;
  message: string;
}

export interface NativeBridgeCapabilityInfo {
  capability: NativeBridgeCapability;
  status: NativeBridgeCapabilityStatus;
  detail: string;
}

export interface NativeBridgeError {
  code: NativeBridgeErrorCode;
  message: string;
  retryable: boolean;
  nativeCode: number;
}

export interface NativeClientStatus {
  handle: number;
  state: NativeClientState;
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

export interface NativeSessionRestoreRequest {
  homeserverUrl: string;
  userId: string;
  deviceId: string;
  accessToken: string;
  refreshToken: string | null;
}
