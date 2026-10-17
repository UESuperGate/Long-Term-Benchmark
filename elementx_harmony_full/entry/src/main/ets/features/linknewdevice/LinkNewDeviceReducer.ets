import { DomainError, DomainErrorCode, DomainFailure, DomainResult } from '../../core/DomainResult';
import {
  DigitsMatchState,
  LinkAttemptMode,
  LinkErrorCode,
  LinkFlowMode,
  LinkHandlerState,
  LinkNewDeviceSnapshot,
  LinkSdkStep,
  LinkSdkStepKind,
  LinkSupportState,
  LinkTimeoutState,
  OwnerVerificationMethod,
  OwnerVerificationState,
  QrDataState,
  ScanActionState
} from './LinkNewDeviceModels';

export class LinkNewDeviceReducer {
  private snapshot: LinkNewDeviceSnapshot = {
    support: LinkSupportState.Loading,
    ownerVerification: OwnerVerificationState.NotRequested,
    ownerVerificationAttempts: 0,
    attemptId: null,
    attemptMode: null,
    flowMode: LinkFlowMode.None,
    qrDataState: QrDataState.None,
    qrCodeData: null,
    scanAction: ScanActionState.Idle,
    timeout: LinkTimeoutState.NotStarted,
    expiresAtMs: null,
    checkCodeDigits: [],
    digitsMatch: DigitsMatchState.Pending,
    handlerState: LinkHandlerState.None,
    errorCode: null,
    error: null
  };

  getSnapshot(): LinkNewDeviceSnapshot {
    return {
      support: this.snapshot.support,
      ownerVerification: this.snapshot.ownerVerification,
      ownerVerificationAttempts: this.snapshot.ownerVerificationAttempts,
      attemptId: this.snapshot.attemptId,
      attemptMode: this.snapshot.attemptMode,
      flowMode: this.snapshot.flowMode,
      qrDataState: this.snapshot.qrDataState,
      qrCodeData: this.snapshot.qrCodeData,
      scanAction: this.snapshot.scanAction,
      timeout: this.snapshot.timeout,
      expiresAtMs: this.snapshot.expiresAtMs,
      checkCodeDigits: this.snapshot.checkCodeDigits.slice(),
      digitsMatch: this.snapshot.digitsMatch,
      handlerState: this.snapshot.handlerState,
      errorCode: this.snapshot.errorCode,
      error: this.snapshot.error
    };
  }

  beginSupportLoad(): LinkNewDeviceSnapshot {
    this.snapshot.support = LinkSupportState.Loading;
    this.snapshot.error = null;
    return this.getSnapshot();
  }

  setSupported(supported: boolean): LinkNewDeviceSnapshot {
    this.snapshot.support = supported ? LinkSupportState.Supported : LinkSupportState.Unsupported;
    this.snapshot.ownerVerification = supported ? OwnerVerificationState.Required : OwnerVerificationState.NotRequested;
    this.snapshot.error = null;
    return this.getSnapshot();
  }

  failSupport(error: DomainError): LinkNewDeviceSnapshot {
    this.snapshot.support = error.code === DomainErrorCode.NetworkUnavailable ?
      LinkSupportState.Offline : LinkSupportState.Error;
    this.snapshot.error = error;
    return this.getSnapshot();
  }

  beginOwnerVerification(): LinkNewDeviceSnapshot {
    this.snapshot.ownerVerification = OwnerVerificationState.Loading;
    this.snapshot.ownerVerificationAttempts += 1;
    this.snapshot.error = null;
    return this.getSnapshot();
  }

  finishOwnerVerification(success: boolean, method: OwnerVerificationMethod, error: DomainError | null): LinkNewDeviceSnapshot {
    if (success) {
      this.snapshot.ownerVerification = OwnerVerificationState.Passed;
      this.snapshot.error = null;
    } else if (method === OwnerVerificationMethod.Biometric && error !== null && !error.retryable) {
      this.snapshot.ownerVerification = OwnerVerificationState.DeviceCredentialRequired;
      this.snapshot.error = error;
      this.snapshot.errorCode = LinkErrorCode.BiometricLockout;
    } else {
      this.snapshot.ownerVerification = OwnerVerificationState.Failed;
      this.snapshot.error = error;
      this.snapshot.errorCode = LinkErrorCode.OwnerVerificationFailed;
    }
    return this.getSnapshot();
  }

  requireOwnerVerification(): LinkNewDeviceSnapshot {
    this.clearAttempt();
    this.snapshot.ownerVerification = OwnerVerificationState.Required;
    return this.getSnapshot();
  }

  ownerCancelled(): LinkNewDeviceSnapshot {
    this.clearAttempt();
    this.snapshot.ownerVerification = OwnerVerificationState.Cancelled;
    return this.getSnapshot();
  }

  startAttempt(attemptId: string, mode: LinkAttemptMode, nowMs: number, timeoutMs: number): DomainResult<LinkNewDeviceSnapshot> {
    if (this.snapshot.support !== LinkSupportState.Supported ||
      this.snapshot.ownerVerification !== OwnerVerificationState.Passed) {
      return DomainResult.fail<LinkNewDeviceSnapshot>(new DomainFailure(
        DomainErrorCode.AuthenticationRejected,
        'Owner verification is required before linking a device',
        false
      ));
    }
    if (timeoutMs <= 0) {
      return DomainResult.fail<LinkNewDeviceSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Link attempt timeout must be positive',
        false
      ));
    }
    this.snapshot.attemptId = attemptId;
    this.snapshot.attemptMode = mode;
    this.snapshot.flowMode = this.initialMode(mode);
    this.snapshot.qrDataState = mode === LinkAttemptMode.OtherDeviceScansQr ? QrDataState.Loading : QrDataState.None;
    this.snapshot.qrCodeData = null;
    this.snapshot.scanAction = ScanActionState.Idle;
    this.snapshot.timeout = LinkTimeoutState.Running;
    this.snapshot.expiresAtMs = nowMs + timeoutMs;
    this.snapshot.checkCodeDigits = [];
    this.snapshot.digitsMatch = DigitsMatchState.Pending;
    this.snapshot.handlerState = LinkHandlerState.Active;
    this.snapshot.errorCode = null;
    this.snapshot.error = null;
    return DomainResult.succeed<LinkNewDeviceSnapshot>(this.getSnapshot());
  }

  beginScan(): DomainResult<LinkNewDeviceSnapshot> {
    if (this.snapshot.attemptId === null || this.snapshot.flowMode !== LinkFlowMode.MobileScan) {
      return this.invalidActiveAttempt('QR scanning is not active');
    }
    this.snapshot.scanAction = ScanActionState.Loading;
    this.snapshot.error = null;
    return DomainResult.succeed<LinkNewDeviceSnapshot>(this.getSnapshot());
  }

  tryAgain(): DomainResult<LinkNewDeviceSnapshot> {
    if (this.snapshot.attemptId === null) {
      return this.invalidActiveAttempt('No link attempt is active');
    }
    if (this.snapshot.errorCode === LinkErrorCode.InvalidQrCode) {
      this.snapshot.flowMode = LinkFlowMode.MobileScan;
      this.snapshot.scanAction = ScanActionState.Idle;
    } else if (this.snapshot.errorCode === LinkErrorCode.InvalidCheckCode &&
      this.snapshot.attemptMode === LinkAttemptMode.Desktop) {
      this.snapshot.flowMode = LinkFlowMode.DesktopNotice;
      this.snapshot.qrDataState = QrDataState.Loading;
      this.snapshot.qrCodeData = null;
      this.snapshot.digitsMatch = DigitsMatchState.Pending;
    } else {
      return this.invalidActiveAttempt('The current link error cannot be retried in place');
    }
    this.snapshot.errorCode = null;
    this.snapshot.error = null;
    return DomainResult.succeed<LinkNewDeviceSnapshot>(this.getSnapshot());
  }

  receiveSdkStep(step: LinkSdkStep): DomainResult<LinkNewDeviceSnapshot> {
    if (step.attemptId !== this.snapshot.attemptId) {
      return DomainResult.fail<LinkNewDeviceSnapshot>(new DomainFailure(
        DomainErrorCode.Cancelled,
        'SDK step belongs to a stale link attempt',
        false
      ));
    }
    if (step.kind === LinkSdkStepKind.QrReady) {
      if (step.qrCodeData === null || step.qrCodeData.length === 0) {
        return this.failAttempt(LinkErrorCode.Unknown, step.error);
      }
      this.snapshot.flowMode = LinkFlowMode.ShowQr;
      this.snapshot.qrDataState = QrDataState.Available;
      this.snapshot.qrCodeData = step.qrCodeData;
    } else if (step.kind === LinkSdkStepKind.ShowDigits || step.kind === LinkSdkStepKind.QrScanned) {
      this.snapshot.flowMode = LinkFlowMode.Digits;
      this.snapshot.scanAction = ScanActionState.Success;
      this.snapshot.checkCodeDigits = step.checkCodeDigits.slice();
      this.snapshot.digitsMatch = DigitsMatchState.Pending;
    } else if (step.kind === LinkSdkStepKind.InvalidQrCode) {
      this.snapshot.flowMode = LinkFlowMode.MobileScan;
      this.snapshot.scanAction = ScanActionState.Failure;
      this.snapshot.errorCode = LinkErrorCode.InvalidQrCode;
      this.snapshot.error = step.error;
    } else if (step.kind === LinkSdkStepKind.DigitsMismatch) {
      this.snapshot.flowMode = LinkFlowMode.Error;
      this.snapshot.digitsMatch = DigitsMatchState.Mismatch;
      this.snapshot.errorCode = LinkErrorCode.InvalidCheckCode;
      this.snapshot.error = step.error;
    } else if (step.kind === LinkSdkStepKind.Done) {
      this.snapshot.flowMode = LinkFlowMode.Complete;
      this.snapshot.scanAction = ScanActionState.Success;
      this.snapshot.timeout = LinkTimeoutState.NotStarted;
      this.snapshot.expiresAtMs = null;
      this.snapshot.qrDataState = QrDataState.None;
      this.snapshot.qrCodeData = null;
      this.snapshot.handlerState = LinkHandlerState.Cleaned;
      this.snapshot.errorCode = null;
      this.snapshot.error = null;
    } else if (step.kind === LinkSdkStepKind.Error) {
      return this.failAttempt(step.errorCode === null ? LinkErrorCode.Unknown : step.errorCode, step.error);
    }
    return DomainResult.succeed<LinkNewDeviceSnapshot>(this.getSnapshot());
  }

  tick(attemptId: string, nowMs: number): DomainResult<LinkNewDeviceSnapshot> {
    if (attemptId !== this.snapshot.attemptId) {
      return DomainResult.fail<LinkNewDeviceSnapshot>(new DomainFailure(
        DomainErrorCode.Cancelled,
        'Timer belongs to a stale link attempt',
        false
      ));
    }
    if (this.snapshot.timeout !== LinkTimeoutState.Running || this.snapshot.expiresAtMs === null ||
      nowMs < this.snapshot.expiresAtMs) {
      return DomainResult.succeed<LinkNewDeviceSnapshot>(this.getSnapshot());
    }
    this.snapshot.timeout = LinkTimeoutState.Expired;
    this.snapshot.flowMode = LinkFlowMode.Error;
    this.snapshot.qrDataState = QrDataState.Expired;
    this.snapshot.qrCodeData = null;
    this.snapshot.scanAction = ScanActionState.Failure;
    this.snapshot.handlerState = LinkHandlerState.Cleaned;
    this.snapshot.errorCode = LinkErrorCode.Expired;
    return DomainResult.succeed<LinkNewDeviceSnapshot>(this.getSnapshot());
  }

  markCheckCodeSent(matches: boolean): LinkNewDeviceSnapshot {
    this.snapshot.digitsMatch = matches ? DigitsMatchState.Match : DigitsMatchState.Mismatch;
    if (!matches) {
      this.snapshot.flowMode = LinkFlowMode.Error;
      this.snapshot.errorCode = LinkErrorCode.InvalidCheckCode;
    }
    return this.getSnapshot();
  }

  markCancelled(error: DomainError | null): LinkNewDeviceSnapshot {
    this.clearAttempt();
    if (error !== null) {
      this.snapshot.flowMode = LinkFlowMode.Error;
      this.snapshot.errorCode = LinkErrorCode.CancellationFailed;
      this.snapshot.error = error;
    }
    return this.getSnapshot();
  }

  resetCompleted(): LinkNewDeviceSnapshot {
    this.clearAttempt();
    return this.getSnapshot();
  }

  private initialMode(mode: LinkAttemptMode): LinkFlowMode {
    if (mode === LinkAttemptMode.Desktop) {
      return LinkFlowMode.DesktopNotice;
    }
    if (mode === LinkAttemptMode.OtherDeviceScansQr) {
      return LinkFlowMode.ShowQr;
    }
    return LinkFlowMode.MobileScan;
  }

  private failAttempt(errorCode: LinkErrorCode, error: DomainError | null): DomainResult<LinkNewDeviceSnapshot> {
    this.snapshot.flowMode = LinkFlowMode.Error;
    this.snapshot.errorCode = errorCode;
    this.snapshot.error = error;
    if (this.snapshot.qrDataState === QrDataState.Loading) {
      this.snapshot.qrDataState = QrDataState.Failed;
    }
    if (errorCode === LinkErrorCode.InvalidQrCode) {
      this.snapshot.scanAction = ScanActionState.Failure;
    }
    if (this.snapshot.attemptMode === LinkAttemptMode.MobileScansQr) {
      this.snapshot.scanAction = ScanActionState.Failure;
    }
    if (errorCode !== LinkErrorCode.InvalidQrCode && errorCode !== LinkErrorCode.InvalidCheckCode) {
      this.snapshot.timeout = LinkTimeoutState.NotStarted;
      this.snapshot.expiresAtMs = null;
      this.snapshot.handlerState = LinkHandlerState.Cleaned;
    }
    return DomainResult.succeed<LinkNewDeviceSnapshot>(this.getSnapshot());
  }

  private clearAttempt(): void {
    this.snapshot.attemptId = null;
    this.snapshot.attemptMode = null;
    this.snapshot.flowMode = LinkFlowMode.None;
    this.snapshot.qrDataState = QrDataState.None;
    this.snapshot.qrCodeData = null;
    this.snapshot.scanAction = ScanActionState.Idle;
    this.snapshot.timeout = LinkTimeoutState.NotStarted;
    this.snapshot.expiresAtMs = null;
    this.snapshot.checkCodeDigits = [];
    this.snapshot.digitsMatch = DigitsMatchState.Pending;
    this.snapshot.handlerState = LinkHandlerState.Cleaned;
    this.snapshot.errorCode = null;
    this.snapshot.error = null;
  }

  private invalidActiveAttempt(message: string): DomainResult<LinkNewDeviceSnapshot> {
    return DomainResult.fail<LinkNewDeviceSnapshot>(new DomainFailure(
      DomainErrorCode.InvalidInput,
      message,
      false
    ));
  }
}
