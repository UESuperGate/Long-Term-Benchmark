import { DomainError } from '../../core/DomainResult';

export enum LinkSupportState {
  Loading = 'loading',
  Supported = 'supported',
  Unsupported = 'unsupported',
  Offline = 'offline',
  Error = 'error'
}

export enum OwnerVerificationState {
  NotRequested = 'not_requested',
  Required = 'required',
  Loading = 'loading',
  Passed = 'passed',
  Failed = 'failed',
  Cancelled = 'cancelled',
  DeviceCredentialRequired = 'device_credential_required'
}

export enum OwnerVerificationMethod {
  Biometric = 'biometric',
  DeviceCredential = 'device_credential'
}

export enum LinkFlowMode {
  None = 'none',
  MobileScan = 'mobile_scan',
  DesktopNotice = 'desktop_notice',
  ShowQr = 'show_qr',
  Digits = 'digits',
  Complete = 'complete',
  Error = 'error'
}

export enum LinkAttemptMode {
  MobileScansQr = 'mobile_scans_qr',
  OtherDeviceScansQr = 'other_device_scans_qr',
  Desktop = 'desktop'
}

export enum QrDataState {
  None = 'none',
  Loading = 'loading',
  Available = 'available',
  Expired = 'expired',
  Failed = 'failed'
}

export enum ScanActionState {
  Idle = 'idle',
  Loading = 'loading',
  Success = 'success',
  Failure = 'failure'
}

export enum LinkTimeoutState {
  NotStarted = 'not_started',
  Running = 'running',
  Expired = 'expired'
}

export enum DigitsMatchState {
  Pending = 'pending',
  Match = 'match',
  Mismatch = 'mismatch'
}

export enum LinkHandlerState {
  None = 'none',
  Active = 'active',
  Cleaned = 'cleaned'
}

export enum LinkErrorCode {
  OwnerVerificationFailed = 'owner_verification_failed',
  BiometricLockout = 'biometric_lockout',
  InvalidQrCode = 'invalid_qr_code',
  DeviceIdAlreadyInUse = 'device_id_already_in_use',
  InvalidCheckCode = 'invalid_check_code',
  UnsupportedProtocol = 'unsupported_protocol',
  UnsupportedQrCodeType = 'unsupported_qr_code_type',
  MissingSecretsBackup = 'missing_secrets_backup',
  NotFound = 'not_found',
  DeviceNotFound = 'device_not_found',
  OtherDeviceAlreadySignedIn = 'other_device_already_signed_in',
  OtherDeviceSignedOut = 'other_device_signed_out',
  ConnectionInsecure = 'connection_insecure',
  ContinuationFailed = 'continuation_failed',
  CancellationFailed = 'cancellation_failed',
  Cancelled = 'cancelled',
  Expired = 'expired',
  Unknown = 'unknown'
}

export interface LinkNewDeviceSnapshot {
  support: LinkSupportState;
  ownerVerification: OwnerVerificationState;
  ownerVerificationAttempts: number;
  attemptId: string | null;
  attemptMode: LinkAttemptMode | null;
  flowMode: LinkFlowMode;
  qrDataState: QrDataState;
  qrCodeData: string | null;
  scanAction: ScanActionState;
  timeout: LinkTimeoutState;
  expiresAtMs: number | null;
  checkCodeDigits: number[];
  digitsMatch: DigitsMatchState;
  handlerState: LinkHandlerState;
  errorCode: LinkErrorCode | null;
  error: DomainError | null;
}

export enum LinkSdkStepKind {
  Starting = 'starting',
  WaitingForAuth = 'waiting_for_auth',
  QrReady = 'qr_ready',
  QrScanned = 'qr_scanned',
  ShowDigits = 'show_digits',
  SyncingSecrets = 'syncing_secrets',
  Done = 'done',
  InvalidQrCode = 'invalid_qr_code',
  DigitsMismatch = 'digits_mismatch',
  Error = 'error'
}

export interface LinkSdkStep {
  attemptId: string;
  kind: LinkSdkStepKind;
  qrCodeData: string | null;
  checkCodeDigits: number[];
  errorCode: LinkErrorCode | null;
  error: DomainError | null;
}

export interface LinkNewDeviceObserver {
  onLinkNewDeviceChanged(snapshot: LinkNewDeviceSnapshot): void;
}

export interface LinkNewDeviceSubscription {
  subscriptionId: number;
  close(): void;
}
