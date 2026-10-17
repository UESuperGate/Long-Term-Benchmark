import { DomainResult } from '../../core/DomainResult';
import {
  LinkAttemptMode,
  LinkNewDeviceObserver,
  LinkNewDeviceSnapshot,
  LinkNewDeviceSubscription,
  LinkSdkStep,
  OwnerVerificationMethod
} from './LinkNewDeviceModels';

/** Production boundary for owner authentication and Matrix Rust QR-login handlers. */
export interface LinkNewDeviceDataSource {
  canLinkNewDevice(): Promise<DomainResult<boolean>>;
  verifyOwner(method: OwnerVerificationMethod): Promise<DomainResult<boolean>>;
  createHandler(attemptId: string, mode: LinkAttemptMode): Promise<DomainResult<boolean>>;
  scanQrCode(attemptId: string, payload: string): Promise<DomainResult<boolean>>;
  submitCheckCode(attemptId: string, code: number): Promise<DomainResult<boolean>>;
  cancel(attemptId: string): Promise<DomainResult<boolean>>;
}

export interface LinkNewDeviceService {
  getSnapshot(): LinkNewDeviceSnapshot;
  subscribe(observer: LinkNewDeviceObserver): LinkNewDeviceSubscription;
  loadSupport(): Promise<DomainResult<LinkNewDeviceSnapshot>>;
  verifyOwner(method: OwnerVerificationMethod): Promise<DomainResult<LinkNewDeviceSnapshot>>;
  verifyOwnerAndStart(method: OwnerVerificationMethod, mode: LinkAttemptMode, nowMs: number, timeoutMs: number): Promise<DomainResult<LinkNewDeviceSnapshot>>;
  startAttempt(mode: LinkAttemptMode, nowMs: number, timeoutMs: number): Promise<DomainResult<LinkNewDeviceSnapshot>>;
  scanQrCode(payload: string): Promise<DomainResult<LinkNewDeviceSnapshot>>;
  tryAgain(): DomainResult<LinkNewDeviceSnapshot>;
  submitCheckCode(code: number): Promise<DomainResult<LinkNewDeviceSnapshot>>;
  receiveSdkStep(step: LinkSdkStep): DomainResult<LinkNewDeviceSnapshot>;
  tick(attemptId: string, nowMs: number): DomainResult<LinkNewDeviceSnapshot>;
  retry(mode: LinkAttemptMode, nowMs: number, timeoutMs: number, requireOwnerVerification: boolean): Promise<DomainResult<LinkNewDeviceSnapshot>>;
  cancel(): Promise<DomainResult<LinkNewDeviceSnapshot>>;
  resetCompleted(): LinkNewDeviceSnapshot;
}
