import { DomainError } from '../../core/DomainResult';

export const SECURITY_CONTRACT_VERSION: string = '1';

export enum SecurityPhase {
  Loading = 'loading',
  Ready = 'ready',
  Offline = 'offline',
  Error = 'error'
}

export enum EncryptionState {
  WaitingForSync = 'waiting_for_sync',
  Unknown = 'unknown',
  Disabled = 'disabled',
  Enabled = 'enabled'
}

export enum SessionVerifiedStatus {
  Unknown = 'unknown',
  NotVerified = 'not_verified',
  Verified = 'verified'
}

export enum CrossSigningState {
  Unknown = 'unknown',
  Unavailable = 'unavailable',
  Incomplete = 'incomplete',
  Ready = 'ready'
}

export enum BackupState {
  WaitingForSync = 'waiting_for_sync',
  Unknown = 'unknown',
  Creating = 'creating',
  Enabling = 'enabling',
  Resuming = 'resuming',
  Enabled = 'enabled',
  Downloading = 'downloading',
  Disabling = 'disabling'
}

export enum BackupUploadState {
  Unknown = 'unknown',
  Waiting = 'waiting',
  Uploading = 'uploading',
  Done = 'done',
  Error = 'error',
  SteadyException = 'steady_exception'
}

export interface BackupUploadProgress {
  state: BackupUploadState;
  backedUpCount: number;
  totalCount: number;
  error: DomainError | null;
}

export enum RecoveryState {
  WaitingForSync = 'waiting_for_sync',
  Unknown = 'unknown',
  Enabled = 'enabled',
  Disabled = 'disabled',
  Incomplete = 'incomplete'
}

export enum RecoveryOperation {
  Idle = 'idle',
  Starting = 'starting',
  CreatingBackup = 'creating_backup',
  CreatingRecoveryKey = 'creating_recovery_key',
  BackingUp = 'backing_up',
  Recovering = 'recovering',
  Disabling = 'disabling',
  Done = 'done',
  Failed = 'failed'
}

/** Recovery keys are deliberately absent. A native adapter must deliver them to a secure sink. */
export interface RecoveryProgress {
  operation: RecoveryOperation;
  backedUpCount: number;
  totalCount: number;
  secretAvailable: boolean;
  error: DomainError | null;
}

export enum UtdKeyRequestState {
  Idle = 'idle',
  Requesting = 'requesting',
  Waiting = 'waiting',
  Received = 'received',
  Withheld = 'withheld',
  Failed = 'failed',
  Cancelled = 'cancelled'
}

export interface UtdKeyRequest {
  requestId: string;
  roomId: string;
  eventId: string;
  sessionId: string | null;
  state: UtdKeyRequestState;
  error: DomainError | null;
}

export interface SecuritySnapshot {
  phase: SecurityPhase;
  encryptionState: EncryptionState;
  sessionVerifiedStatus: SessionVerifiedStatus;
  needsSessionVerification: boolean;
  crossSigningState: CrossSigningState;
  backupState: BackupState;
  backupUpload: BackupUploadProgress;
  recoveryState: RecoveryState;
  recoveryProgress: RecoveryProgress;
  isLastDevice: boolean;
  hasDevicesToVerifyAgainst: boolean | null;
  keyRequests: UtdKeyRequest[];
  error: DomainError | null;
}

export interface SecurityStateInput {
  encryptionState: EncryptionState;
  sessionVerifiedStatus: SessionVerifiedStatus;
  needsSessionVerification: boolean;
  crossSigningState: CrossSigningState;
  backupState: BackupState;
  backupUpload: BackupUploadProgress;
  recoveryState: RecoveryState;
  isLastDevice: boolean;
  hasDevicesToVerifyAgainst: boolean;
}

export enum DeviceTrustState {
  Unverified = 'unverified',
  LocallyTrusted = 'locally_trusted',
  CrossSigned = 'cross_signed',
  Blocked = 'blocked'
}

export interface DeviceSummary {
  deviceId: string;
  displayName: string | null;
  isCurrent: boolean;
  lastSeenAtMs: number | null;
  lastSeenIp: string | null;
  trustState: DeviceTrustState;
}

export enum DeviceListPhase {
  Loading = 'loading',
  Ready = 'ready',
  Empty = 'empty',
  Offline = 'offline',
  Error = 'error'
}

export interface DeviceListSnapshot {
  phase: DeviceListPhase;
  devices: DeviceSummary[];
  crossSigningState: CrossSigningState;
  isRefreshing: boolean;
  error: DomainError | null;
}

export interface DeviceListInput {
  devices: DeviceSummary[];
  crossSigningState: CrossSigningState;
}

export enum VerificationPhase {
  Initial = 'initial',
  Requesting = 'requesting',
  WaitingForAcceptance = 'waiting_for_acceptance',
  Accepted = 'accepted',
  SasStarted = 'sas_started',
  SasReady = 'sas_ready',
  QrReady = 'qr_ready',
  Approving = 'approving',
  Completed = 'completed',
  Cancelled = 'cancelled',
  Offline = 'offline',
  Failed = 'failed'
}

export enum VerificationMethod {
  None = 'none',
  SasEmoji = 'sas_emoji',
  SasDecimal = 'sas_decimal',
  Qr = 'qr'
}

export interface VerificationData {
  emojiNumbers: number[];
  decimals: number[];
  qrCodeData: string | null;
}

export interface VerificationSnapshot {
  attemptId: string | null;
  phase: VerificationPhase;
  method: VerificationMethod;
  peerUserId: string | null;
  peerDeviceId: string | null;
  peerDeviceName: string | null;
  data: VerificationData;
  error: DomainError | null;
}

export enum VerificationUpdateKind {
  RequestAccepted = 'request_accepted',
  SasStarted = 'sas_started',
  SasData = 'sas_data',
  QrData = 'qr_data',
  Finished = 'finished',
  Cancelled = 'cancelled',
  Failed = 'failed'
}

export interface VerificationUpdate {
  attemptId: string;
  kind: VerificationUpdateKind;
  method: VerificationMethod;
  emojiNumbers: number[];
  decimals: number[];
  qrCodeData: string | null;
  error: DomainError | null;
}
