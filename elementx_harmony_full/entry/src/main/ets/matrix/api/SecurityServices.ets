import { DomainResult } from '../../core/DomainResult';
import {
  DeviceListSnapshot,
  DeviceListInput,
  DeviceTrustState,
  SecuritySnapshot,
  SecurityStateInput,
  UtdKeyRequest,
  UtdKeyRequestState,
  VerificationSnapshot,
  VerificationUpdate
} from './SecurityModels';

export interface SecurityObserver {
  onSecurityChanged(snapshot: SecuritySnapshot): void;
}

export interface DeviceListObserver {
  onDeviceListChanged(snapshot: DeviceListSnapshot): void;
}

export interface VerificationObserver {
  onVerificationChanged(snapshot: VerificationSnapshot): void;
}

export interface SecuritySubscription {
  subscriptionId: number;
  close(): void;
}

/** Native Matrix boundary. Secret parameters must never be logged or copied into returned state. */
export interface SecurityDataSource {
  loadState(): Promise<DomainResult<SecurityStateInput>>;
  requestRoomKey(request: UtdKeyRequest): Promise<DomainResult<boolean>>;
  cancelRoomKeyRequest(requestId: string): Promise<DomainResult<boolean>>;
  enableBackups(): Promise<DomainResult<boolean>>;
  enableRecovery(waitForBackupsToUpload: boolean): Promise<DomainResult<boolean>>;
  recover(recoveryKeyOrPassphrase: string): Promise<DomainResult<boolean>>;
  disableRecovery(): Promise<DomainResult<boolean>>;
}

export interface DeviceDataSource {
  loadDevices(): Promise<DomainResult<DeviceListInput>>;
  setLocalTrust(deviceId: string, trustState: DeviceTrustState): Promise<DomainResult<boolean>>;
}

/** Attempt IDs must be forwarded unchanged by the bridge for stale-event rejection. */
export interface VerificationDataSource {
  requestCurrentSession(attemptId: string): Promise<DomainResult<boolean>>;
  requestUser(attemptId: string, userId: string): Promise<DomainResult<boolean>>;
  accept(attemptId: string): Promise<DomainResult<boolean>>;
  approve(attemptId: string): Promise<DomainResult<boolean>>;
  decline(attemptId: string): Promise<DomainResult<boolean>>;
  cancel(attemptId: string): Promise<DomainResult<boolean>>;
}

export interface SecurityService {
  getSnapshot(): SecuritySnapshot;
  subscribe(observer: SecurityObserver): SecuritySubscription;
  start(): Promise<DomainResult<SecuritySnapshot>>;
  requestRoomKey(roomId: string, eventId: string, sessionId: string | null): Promise<DomainResult<SecuritySnapshot>>;
  receiveRoomKeyRequestState(requestId: string, state: UtdKeyRequestState): DomainResult<SecuritySnapshot>;
  cancelRoomKeyRequest(requestId: string): Promise<DomainResult<SecuritySnapshot>>;
  enableBackups(): Promise<DomainResult<SecuritySnapshot>>;
  enableRecovery(waitForBackupsToUpload: boolean): Promise<DomainResult<SecuritySnapshot>>;
  recover(recoveryKeyOrPassphrase: string): Promise<DomainResult<SecuritySnapshot>>;
  disableRecovery(): Promise<DomainResult<SecuritySnapshot>>;
  setOffline(isOffline: boolean): void;
}

export interface DeviceListService {
  getSnapshot(): DeviceListSnapshot;
  subscribe(observer: DeviceListObserver): SecuritySubscription;
  start(): Promise<DomainResult<DeviceListSnapshot>>;
  refresh(): Promise<DomainResult<DeviceListSnapshot>>;
  setLocalTrust(deviceId: string, trustState: DeviceTrustState): Promise<DomainResult<DeviceListSnapshot>>;
}

export interface VerificationService {
  getSnapshot(): VerificationSnapshot;
  subscribe(observer: VerificationObserver): SecuritySubscription;
  requestCurrentSession(attemptId: string): Promise<DomainResult<VerificationSnapshot>>;
  requestUser(attemptId: string, userId: string): Promise<DomainResult<VerificationSnapshot>>;
  receive(update: VerificationUpdate): DomainResult<VerificationSnapshot>;
  accept(): Promise<DomainResult<VerificationSnapshot>>;
  approve(): Promise<DomainResult<VerificationSnapshot>>;
  decline(): Promise<DomainResult<VerificationSnapshot>>;
  cancel(): Promise<DomainResult<VerificationSnapshot>>;
}
