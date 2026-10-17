import { DomainErrorCode, DomainFailure, DomainResult } from '../main/ets/core/DomainResult';
import { DeviceListController } from '../main/ets/devices/DeviceListController';
import {
  DigitsMatchState,
  LinkAttemptMode,
  LinkErrorCode,
  LinkFlowMode,
  LinkHandlerState,
  LinkSdkStep,
  LinkSdkStepKind,
  LinkSupportState,
  LinkTimeoutState,
  OwnerVerificationMethod,
  OwnerVerificationState,
  QrDataState,
  ScanActionState
} from '../main/ets/features/linknewdevice/LinkNewDeviceModels';
import { LinkNewDeviceController } from '../main/ets/features/linknewdevice/LinkNewDeviceController';
import { LinkNewDeviceDataSource } from '../main/ets/features/linknewdevice/LinkNewDeviceService';
import {
  BackupState,
  BackupUploadState,
  CrossSigningState,
  DeviceListPhase,
  DeviceListInput,
  DeviceSummary,
  DeviceTrustState,
  EncryptionState,
  RecoveryState,
  SecurityPhase,
  SecurityStateInput,
  SessionVerifiedStatus,
  UtdKeyRequest,
  UtdKeyRequestState,
  VerificationMethod,
  VerificationPhase,
  VerificationUpdate,
  VerificationUpdateKind
} from '../main/ets/matrix/api/SecurityModels';
import {
  DeviceDataSource,
  SecurityDataSource,
  VerificationDataSource
} from '../main/ets/matrix/api/SecurityServices';
import { SecurityController } from '../main/ets/security/SecurityController';
import { VerificationController } from '../main/ets/security/VerificationController';

function check(condition: boolean, message: string): void {
  if (!condition) {
    throw new Error(message);
  }
}

function securityInput(): SecurityStateInput {
  return {
    encryptionState: EncryptionState.Enabled,
    sessionVerifiedStatus: SessionVerifiedStatus.NotVerified,
    needsSessionVerification: true,
    crossSigningState: CrossSigningState.Ready,
    backupState: BackupState.Enabled,
    backupUpload: {
      state: BackupUploadState.Done,
      backedUpCount: 4,
      totalCount: 4,
      error: null
    },
    recoveryState: RecoveryState.Enabled,
    isLastDevice: false,
    hasDevicesToVerifyAgainst: true
  };
}

class SecuritySource implements SecurityDataSource {
  loadFailure: DomainFailure | null = null;
  recoveredInput: string | null = null;

  async loadState(): Promise<DomainResult<SecurityStateInput>> {
    if (this.loadFailure !== null) {
      return DomainResult.fail<SecurityStateInput>(this.loadFailure);
    }
    return DomainResult.succeed<SecurityStateInput>(securityInput());
  }

  async requestRoomKey(request: UtdKeyRequest): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(request.eventId.length > 0);
  }

  async cancelRoomKeyRequest(requestId: string): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(requestId.length > 0);
  }

  async enableBackups(): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(true);
  }

  async enableRecovery(waitForBackupsToUpload: boolean): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(waitForBackupsToUpload);
  }

  async recover(recoveryKeyOrPassphrase: string): Promise<DomainResult<boolean>> {
    this.recoveredInput = recoveryKeyOrPassphrase;
    return DomainResult.succeed<boolean>(true);
  }

  async disableRecovery(): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(true);
  }
}

class DevicesSource implements DeviceDataSource {
  failure: DomainFailure | null = null;
  devices: DeviceSummary[] = [];

  async loadDevices(): Promise<DomainResult<DeviceListInput>> {
    if (this.failure !== null) {
      return DomainResult.fail<DeviceListInput>(this.failure);
    }
    return DomainResult.succeed<DeviceListInput>({
      devices: this.devices.slice(),
      crossSigningState: this.devices.length === 0 ? CrossSigningState.Unknown : CrossSigningState.Ready
    });
  }

  async setLocalTrust(deviceId: string, trustState: DeviceTrustState): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(deviceId.length > 0 && trustState !== DeviceTrustState.Blocked);
  }
}

class VerificationSource implements VerificationDataSource {
  requestFailure: DomainFailure | null = null;

  async requestCurrentSession(attemptId: string): Promise<DomainResult<boolean>> {
    if (this.requestFailure !== null) {
      return DomainResult.fail<boolean>(this.requestFailure);
    }
    return DomainResult.succeed<boolean>(attemptId.length > 0);
  }

  async requestUser(attemptId: string, userId: string): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(attemptId.length > 0 && userId.length > 0);
  }

  async accept(attemptId: string): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(attemptId.length > 0);
  }

  async approve(attemptId: string): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(attemptId.length > 0);
  }

  async decline(attemptId: string): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(attemptId.length > 0);
  }

  async cancel(attemptId: string): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(attemptId.length > 0);
  }
}

class LinkSource implements LinkNewDeviceDataSource {
  supportResult: DomainResult<boolean> = DomainResult.succeed<boolean>(true);
  ownerResult: DomainResult<boolean> = DomainResult.succeed<boolean>(true);
  cancelResult: DomainResult<boolean> = DomainResult.succeed<boolean>(true);
  cancelledAttempts: string[] = [];

  async canLinkNewDevice(): Promise<DomainResult<boolean>> {
    return this.supportResult;
  }

  async verifyOwner(method: OwnerVerificationMethod): Promise<DomainResult<boolean>> {
    if (method === OwnerVerificationMethod.Biometric || method === OwnerVerificationMethod.DeviceCredential) {
      return this.ownerResult;
    }
    return DomainResult.succeed<boolean>(false);
  }

  async createHandler(attemptId: string, mode: LinkAttemptMode): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(attemptId.length > 0 && mode.length > 0);
  }

  async scanQrCode(attemptId: string, payload: string): Promise<DomainResult<boolean>> {
    if (payload === 'invalid') {
      return DomainResult.fail<boolean>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'invalid QR code',
        true
      ));
    }
    return DomainResult.succeed<boolean>(attemptId.length > 0);
  }

  async submitCheckCode(attemptId: string, code: number): Promise<DomainResult<boolean>> {
    return DomainResult.succeed<boolean>(attemptId.length > 0 && code === 42);
  }

  async cancel(attemptId: string): Promise<DomainResult<boolean>> {
    this.cancelledAttempts.push(attemptId);
    return this.cancelResult;
  }
}

function verificationUpdate(
  attemptId: string,
  kind: VerificationUpdateKind,
  method: VerificationMethod,
  emojis: number[] = [],
  decimals: number[] = []
): VerificationUpdate {
  return {
    attemptId: attemptId,
    kind: kind,
    method: method,
    emojiNumbers: emojis,
    decimals: decimals,
    qrCodeData: null,
    error: null
  };
}

function sdkStep(
  attemptId: string,
  kind: LinkSdkStepKind,
  qrCodeData: string | null = null,
  checkCodeDigits: number[] = [],
  errorCode: LinkErrorCode | null = null
): LinkSdkStep {
  return {
    attemptId: attemptId,
    kind: kind,
    qrCodeData: qrCodeData,
    checkCodeDigits: checkCodeDigits,
    errorCode: errorCode,
    error: null
  };
}

async function readyLinkController(source: LinkSource): Promise<LinkNewDeviceController> {
  const controller = new LinkNewDeviceController(source);
  check((await controller.loadSupport()).success, 'link support should load');
  check(controller.getSnapshot().support === LinkSupportState.Supported, 'linking should be supported');
  check(controller.getSnapshot().ownerVerification === OwnerVerificationState.Required,
    'supported linking must require owner verification');
  check((await controller.verifyOwner(OwnerVerificationMethod.Biometric)).success,
    'owner verification should pass');
  return controller;
}

async function testSecurityFailureAndUtdLifecycle(): Promise<void> {
  const source = new SecuritySource();
  source.loadFailure = new DomainFailure(DomainErrorCode.NetworkUnavailable, 'offline', true);
  const offline = new SecurityController(source);
  check(!(await offline.start()).success, 'security network failure must propagate');
  check(offline.getSnapshot().phase === SecurityPhase.Offline, 'network failure must enter offline state');
  check(offline.getSnapshot().keyRequests.length === 0, 'offline state must not invent key requests');

  source.loadFailure = null;
  const controller = new SecurityController(source);
  check((await controller.start()).success, 'security state should load');
  check((await controller.requestRoomKey('!room:example.org', '$utd', 'session-1')).success,
    'UTD key request should start');
  check(controller.getSnapshot().keyRequests[0].state === UtdKeyRequestState.Waiting,
    'successful key request must wait for a real key callback');
  const requestId = controller.getSnapshot().keyRequests[0].requestId;
  check(controller.receiveRoomKeyRequestState(requestId, UtdKeyRequestState.Received).success,
    'native key callback should complete the matching request');
  check(controller.getSnapshot().keyRequests[0].state === UtdKeyRequestState.Received,
    'received room key must remain explicit');
  check((await controller.cancelRoomKeyRequest(requestId)).success, 'key request should cancel');
  check(controller.getSnapshot().keyRequests[0].state === UtdKeyRequestState.Cancelled,
    'cancelled key request must remain explicit');
}

async function testRecoverySecretIsNotObservable(): Promise<void> {
  const source = new SecuritySource();
  const controller = new SecurityController(source);
  await controller.start();
  check((await controller.enableBackups()).success, 'backup enable should succeed');
  check(controller.getSnapshot().backupState === BackupState.Enabled, 'backup state should become enabled');
  check((await controller.enableRecovery(true)).success, 'recovery enable should succeed');
  check(controller.getSnapshot().recoveryState === RecoveryState.Enabled, 'recovery state should become enabled');
  check(controller.getSnapshot().recoveryProgress.secretAvailable,
    'recovery setup may indicate that a secret was delivered to the secure sink');
  const secret = 'ESECRET-RECOVERY-KEY-DO-NOT-STORE';
  check((await controller.recover(secret)).success, 'recovery should succeed');
  check(source.recoveredInput === secret, 'secret must reach only the datasource call');
  const serialized = JSON.stringify(controller.getSnapshot());
  check(serialized.indexOf(secret) < 0, 'recovery secret must never enter observable state');
  check(serialized.indexOf('recoveryKey') < 0, 'snapshot must not expose a recovery key field');
  check((await controller.disableRecovery()).success, 'recovery disable should succeed');
  check(controller.getSnapshot().recoveryState === RecoveryState.Disabled, 'recovery should become disabled');
}

async function testDeviceFailureAndTrust(): Promise<void> {
  const failing = new DevicesSource();
  failing.failure = new DomainFailure(DomainErrorCode.NetworkUnavailable, 'offline', true);
  const offline = new DeviceListController(failing);
  check(!(await offline.start()).success, 'device load failure must propagate');
  check(offline.getSnapshot().phase === DeviceListPhase.Offline, 'device network failure must be offline');
  check(offline.getSnapshot().devices.length === 0, 'device failure must not generate fake devices');

  const source = new DevicesSource();
  source.devices = [{
    deviceId: 'CURRENT',
    displayName: 'This device',
    isCurrent: true,
    lastSeenAtMs: 100,
    lastSeenIp: null,
    trustState: DeviceTrustState.Unverified
  }, {
    deviceId: 'OTHER',
    displayName: null,
    isCurrent: false,
    lastSeenAtMs: 200,
    lastSeenIp: null,
    trustState: DeviceTrustState.CrossSigned
  }];
  const controller = new DeviceListController(source);
  check((await controller.start()).success, 'device list should load');
  check(controller.getSnapshot().devices[0].deviceId === 'CURRENT', 'current device must sort first');
  check(controller.getSnapshot().crossSigningState === CrossSigningState.Ready,
    'cross-signed device must expose ready cross-signing state');
  check((await controller.setLocalTrust('CURRENT', DeviceTrustState.LocallyTrusted)).success,
    'known device trust should update');
}

async function testVerificationSasAndStaleCallbacks(): Promise<void> {
  const offlineSource = new VerificationSource();
  offlineSource.requestFailure = new DomainFailure(DomainErrorCode.NetworkUnavailable, 'offline', true);
  const offline = new VerificationController(offlineSource);
  check(!(await offline.requestCurrentSession('offline-attempt')).success,
    'verification network failure must propagate');
  check(offline.getSnapshot().phase === VerificationPhase.Offline,
    'verification network failure must enter explicit offline phase');

  const controller = new VerificationController(new VerificationSource());
  check((await controller.requestCurrentSession('verification-1')).success, 'verification request should start');
  check(controller.getSnapshot().phase === VerificationPhase.WaitingForAcceptance,
    'verification should wait for peer acceptance');
  check(controller.receive(verificationUpdate(
    'verification-1',
    VerificationUpdateKind.SasData,
    VerificationMethod.SasEmoji,
    [1, 2, 3, 4, 5, 6, 7]
  )).success, 'valid seven-emoji SAS should be accepted');
  check(controller.getSnapshot().phase === VerificationPhase.SasReady, 'SAS data must become ready');

  await controller.requestCurrentSession('verification-2');
  const stale = controller.receive(verificationUpdate(
    'verification-1',
    VerificationUpdateKind.Finished,
    VerificationMethod.SasEmoji
  ));
  check(!stale.success, 'old verification callback must be rejected');
  check(controller.getSnapshot().attemptId === 'verification-2', 'stale callback must not replace active attempt');
}

async function testOwnerGateQrAndCompletion(): Promise<void> {
  const source = new LinkSource();
  const controller = new LinkNewDeviceController(source);
  await controller.loadSupport();
  check((await controller.verifyOwnerAndStart(
    OwnerVerificationMethod.Biometric,
    LinkAttemptMode.OtherDeviceScansQr,
    1000,
    120000
  )).success, 'owner-verification success event should start QR attempt atomically');
  const attemptId = controller.getSnapshot().attemptId;
  check(attemptId !== null, 'attempt must have an identity');
  check(controller.getSnapshot().qrDataState === QrDataState.Loading, 'QR must load without fixture data');
  check(controller.getSnapshot().qrCodeData === null, 'loading state must not invent a QR code');
  check(controller.receiveSdkStep(sdkStep(attemptId!, LinkSdkStepKind.QrReady, 'matrix:real-qr')).success,
    'real SDK QR callback should be accepted');
  check(controller.getSnapshot().qrDataState === QrDataState.Available, 'QR must become available');
  check(controller.receiveSdkStep(sdkStep(attemptId!, LinkSdkStepKind.Done)).success,
    'SDK done should complete active attempt');
  check(controller.getSnapshot().flowMode === LinkFlowMode.Complete, 'done must enter complete mode');
  check(controller.getSnapshot().handlerState === LinkHandlerState.Cleaned, 'completion must clean handler');
  check(controller.getSnapshot().timeout === LinkTimeoutState.NotStarted, 'completion must stop timeout');
}

async function testTimeoutRetryRejectsStaleEvents(): Promise<void> {
  const source = new LinkSource();
  const controller = await readyLinkController(source);
  await controller.startAttempt(LinkAttemptMode.MobileScansQr, 0, 100);
  const oldAttempt = controller.getSnapshot().attemptId;
  check(oldAttempt !== null, 'old attempt must exist');
  check(controller.tick(oldAttempt!, 99).success, 'timer before deadline should be accepted');
  check(controller.getSnapshot().timeout === LinkTimeoutState.Running, 'timer before deadline must not expire');
  check(controller.tick(oldAttempt!, 100).success, 'timer at deadline should expire');
  check(controller.getSnapshot().timeout === LinkTimeoutState.Expired, 'deadline must enter expired state');

  check((await controller.retry(LinkAttemptMode.OtherDeviceScansQr, 200, 100, false)).success,
    'retry should create a new attempt');
  const newAttempt = controller.getSnapshot().attemptId;
  check(newAttempt !== null && newAttempt !== oldAttempt, 'retry must rotate attempt identity');
  check(!controller.tick(oldAttempt!, 999999).success, 'old timer must be rejected');
  check(!controller.receiveSdkStep(sdkStep(oldAttempt!, LinkSdkStepKind.Done)).success,
    'old SDK done callback must be rejected');
  check(controller.getSnapshot().attemptId === newAttempt, 'stale events must preserve new attempt');
  check(controller.getSnapshot().flowMode === LinkFlowMode.ShowQr, 'stale done must not complete new attempt');
}

async function testScanDigitsAndCancellation(): Promise<void> {
  const source = new LinkSource();
  const controller = await readyLinkController(source);
  await controller.startAttempt(LinkAttemptMode.MobileScansQr, 0, 1000);
  check(!(await controller.scanQrCode('invalid')).success, 'invalid QR must propagate failure');
  check(controller.getSnapshot().scanAction === ScanActionState.Failure, 'invalid QR must expose retryable failure');
  check(controller.tryAgain().success, 'invalid QR failure should allow TryAgain');
  check(controller.getSnapshot().scanAction === ScanActionState.Idle, 'TryAgain must restore idle scanner state');

  const attemptId = controller.getSnapshot().attemptId;
  check(attemptId !== null, 'scan attempt must remain active for retry');
  check(controller.receiveSdkStep(sdkStep(attemptId!, LinkSdkStepKind.ShowDigits, null, [4, 2])).success,
    'SDK digits should enter confirmation mode');
  check(controller.getSnapshot().flowMode === LinkFlowMode.Digits, 'digits must be visible');
  check((await controller.submitCheckCode(41)).success, 'SDK may explicitly report a mismatch');
  check(controller.getSnapshot().digitsMatch === DigitsMatchState.Mismatch, 'mismatch must remain explicit');
  check(controller.getSnapshot().timeout === LinkTimeoutState.Running,
    'digits mismatch must keep the attempt timeout running');
  check((await controller.cancel()).success, 'active flow should cancel');
  check(controller.getSnapshot().handlerState === LinkHandlerState.Cleaned, 'cancel must clean handler');
  check(controller.getSnapshot().flowMode === LinkFlowMode.None, 'cancel must leave no active flow');
}

async function testOwnerLockoutFallbackAndPolicyRetry(): Promise<void> {
  const offlineSource = new LinkSource();
  offlineSource.supportResult = DomainResult.fail<boolean>(new DomainFailure(
    DomainErrorCode.NetworkUnavailable,
    'offline',
    true
  ));
  const offline = new LinkNewDeviceController(offlineSource);
  check(!(await offline.loadSupport()).success, 'offline capability check must propagate');
  check(offline.getSnapshot().support === LinkSupportState.Offline,
    'capability network failure must be explicitly offline');

  const source = new LinkSource();
  const controller = new LinkNewDeviceController(source);
  await controller.loadSupport();
  source.ownerResult = DomainResult.fail<boolean>(new DomainFailure(
    DomainErrorCode.AuthenticationRejected,
    'biometric locked',
    false
  ));
  check(!(await controller.verifyOwner(OwnerVerificationMethod.Biometric)).success,
    'biometric lockout must fail the biometric attempt');
  check(controller.getSnapshot().ownerVerification === OwnerVerificationState.DeviceCredentialRequired,
    'biometric lockout must require device credential fallback');
  source.ownerResult = DomainResult.succeed<boolean>(true);
  check((await controller.verifyOwner(OwnerVerificationMethod.DeviceCredential)).success,
    'device credential fallback should pass');
  await controller.startAttempt(LinkAttemptMode.MobileScansQr, 0, 1000);
  check((await controller.retry(LinkAttemptMode.MobileScansQr, 10, 1000, true)).success,
    'policy retry should return to owner gate');
  check(controller.getSnapshot().ownerVerification === OwnerVerificationState.Required,
    'policy retry must require fresh owner verification');
  check(controller.getSnapshot().attemptId === null, 'owner-policy retry must clear old attempt');
}

async function testDesktopTimeoutDigitsRetryAndReset(): Promise<void> {
  const source = new LinkSource();
  const controller = await readyLinkController(source);
  await controller.startAttempt(LinkAttemptMode.Desktop, 100, 1000);
  const attemptId = controller.getSnapshot().attemptId;
  check(attemptId !== null, 'desktop attempt must exist');
  check(controller.getSnapshot().flowMode === LinkFlowMode.DesktopNotice,
    'desktop flow must start with the notice');
  check(controller.receiveSdkStep(sdkStep(attemptId!, LinkSdkStepKind.ShowDigits, null, [1, 2])).success,
    'desktop SDK digits should be accepted');
  check(controller.receiveSdkStep(sdkStep(
    attemptId!,
    LinkSdkStepKind.DigitsMismatch,
    null,
    [],
    LinkErrorCode.InvalidCheckCode
  )).success, 'desktop mismatch should become an explicit error');
  check(controller.getSnapshot().timeout === LinkTimeoutState.Running,
    'desktop mismatch must preserve the overall attempt timeout');
  check(controller.tryAgain().success, 'desktop mismatch should allow in-place retry');
  check(controller.getSnapshot().flowMode === LinkFlowMode.DesktopNotice,
    'desktop retry must return to the desktop notice');
  check(controller.getSnapshot().qrDataState === QrDataState.Loading,
    'desktop retry must wait for new QR data without inventing it');

  check(controller.receiveSdkStep(sdkStep(attemptId!, LinkSdkStepKind.Done)).success,
    'desktop flow should complete');
  check(controller.resetCompleted().flowMode === LinkFlowMode.None,
    'done action must return to the session list state');
}

async function testCapabilityAndTerminalErrorCleanup(): Promise<void> {
  const unsupportedSource = new LinkSource();
  unsupportedSource.supportResult = DomainResult.succeed<boolean>(false);
  const unsupported = new LinkNewDeviceController(unsupportedSource);
  check((await unsupported.loadSupport()).success, 'unsupported capability is a successful query');
  check(unsupported.getSnapshot().support === LinkSupportState.Unsupported,
    'unsupported server must disable the flow without fake handlers');

  const source = new LinkSource();
  const controller = await readyLinkController(source);
  await controller.startAttempt(LinkAttemptMode.MobileScansQr, 0, 1000);
  const attemptId = controller.getSnapshot().attemptId;
  check(attemptId !== null, 'terminal-error attempt must exist');
  check(controller.receiveSdkStep(sdkStep(
    attemptId!,
    LinkSdkStepKind.Error,
    null,
    [],
    LinkErrorCode.OtherDeviceAlreadySignedIn
  )).success, 'typed SDK error should be reduced');
  check(controller.getSnapshot().flowMode === LinkFlowMode.Error, 'SDK error must enter error mode');
  check(controller.getSnapshot().scanAction === ScanActionState.Failure,
    'mobile SDK error must expose scan failure');
  check(controller.getSnapshot().handlerState === LinkHandlerState.Cleaned,
    'terminal SDK error must clean its handler');

  const cancelSource = new LinkSource();
  const cancelling = await readyLinkController(cancelSource);
  await cancelling.startAttempt(LinkAttemptMode.OtherDeviceScansQr, 0, 1000);
  cancelSource.cancelResult = DomainResult.fail<boolean>(new DomainFailure(
    DomainErrorCode.ServiceUnavailable,
    'SDK cancellation failed',
    true
  ));
  check(!(await cancelling.cancel()).success, 'SDK cancellation failure must propagate');
  check(cancelling.getSnapshot().errorCode === LinkErrorCode.CancellationFailed,
    'cancellation failure must retain its typed error');
  check(cancelling.getSnapshot().handlerState === LinkHandlerState.Cleaned,
    'cancellation failure must still clean local handler state');
}

export async function runSecurityDomainTests(): Promise<string[]> {
  const passed: string[] = [];
  await testSecurityFailureAndUtdLifecycle();
  passed.push('security offline and UTD lifecycle');
  await testRecoverySecretIsNotObservable();
  passed.push('recovery secret isolation');
  await testDeviceFailureAndTrust();
  passed.push('device list trust and explicit failure');
  await testVerificationSasAndStaleCallbacks();
  passed.push('verification SAS and stale callback protection');
  await testOwnerGateQrAndCompletion();
  passed.push('owner gate, QR readiness, completion cleanup');
  await testTimeoutRetryRejectsStaleEvents();
  passed.push('attempt timeout and stale-event protection');
  await testScanDigitsAndCancellation();
  passed.push('scan, digits mismatch, cancellation cleanup');
  await testOwnerLockoutFallbackAndPolicyRetry();
  passed.push('credential fallback and policy retry');
  await testDesktopTimeoutDigitsRetryAndReset();
  passed.push('desktop digits retry and completed reset');
  await testCapabilityAndTerminalErrorCleanup();
  passed.push('capability and terminal error cleanup');
  return passed;
}
