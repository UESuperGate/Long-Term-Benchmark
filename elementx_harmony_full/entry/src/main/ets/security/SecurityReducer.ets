import { DomainError } from '../core/DomainResult';
import {
  BackupState,
  BackupUploadProgress,
  BackupUploadState,
  CrossSigningState,
  EncryptionState,
  RecoveryOperation,
  RecoveryState,
  SecurityPhase,
  SecuritySnapshot,
  SecurityStateInput,
  SessionVerifiedStatus,
  UtdKeyRequest,
  UtdKeyRequestState
} from '../matrix/api/SecurityModels';

function copyUpload(value: BackupUploadProgress): BackupUploadProgress {
  return {
    state: value.state,
    backedUpCount: value.backedUpCount,
    totalCount: value.totalCount,
    error: value.error
  };
}

function copyRequest(value: UtdKeyRequest): UtdKeyRequest {
  return {
    requestId: value.requestId,
    roomId: value.roomId,
    eventId: value.eventId,
    sessionId: value.sessionId,
    state: value.state,
    error: value.error
  };
}

export class SecurityReducer {
  private snapshot: SecuritySnapshot = {
    phase: SecurityPhase.Loading,
    encryptionState: EncryptionState.WaitingForSync,
    sessionVerifiedStatus: SessionVerifiedStatus.Unknown,
    needsSessionVerification: false,
    crossSigningState: CrossSigningState.Unknown,
    backupState: BackupState.WaitingForSync,
    backupUpload: {
      state: BackupUploadState.Unknown,
      backedUpCount: 0,
      totalCount: 0,
      error: null
    },
    recoveryState: RecoveryState.WaitingForSync,
    recoveryProgress: {
      operation: RecoveryOperation.Idle,
      backedUpCount: 0,
      totalCount: 0,
      secretAvailable: false,
      error: null
    },
    isLastDevice: false,
    hasDevicesToVerifyAgainst: null,
    keyRequests: [],
    error: null
  };

  getSnapshot(): SecuritySnapshot {
    return {
      phase: this.snapshot.phase,
      encryptionState: this.snapshot.encryptionState,
      sessionVerifiedStatus: this.snapshot.sessionVerifiedStatus,
      needsSessionVerification: this.snapshot.needsSessionVerification,
      crossSigningState: this.snapshot.crossSigningState,
      backupState: this.snapshot.backupState,
      backupUpload: copyUpload(this.snapshot.backupUpload),
      recoveryState: this.snapshot.recoveryState,
      recoveryProgress: {
        operation: this.snapshot.recoveryProgress.operation,
        backedUpCount: this.snapshot.recoveryProgress.backedUpCount,
        totalCount: this.snapshot.recoveryProgress.totalCount,
        secretAvailable: this.snapshot.recoveryProgress.secretAvailable,
        error: this.snapshot.recoveryProgress.error
      },
      isLastDevice: this.snapshot.isLastDevice,
      hasDevicesToVerifyAgainst: this.snapshot.hasDevicesToVerifyAgainst,
      keyRequests: this.snapshot.keyRequests.map((item: UtdKeyRequest) => copyRequest(item)),
      error: this.snapshot.error
    };
  }

  beginLoading(): SecuritySnapshot {
    this.snapshot.phase = SecurityPhase.Loading;
    this.snapshot.error = null;
    return this.getSnapshot();
  }

  replace(input: SecurityStateInput): SecuritySnapshot {
    this.snapshot.phase = SecurityPhase.Ready;
    this.snapshot.encryptionState = input.encryptionState;
    this.snapshot.sessionVerifiedStatus = input.sessionVerifiedStatus;
    this.snapshot.needsSessionVerification = input.needsSessionVerification;
    this.snapshot.crossSigningState = input.crossSigningState;
    this.snapshot.backupState = input.backupState;
    this.snapshot.backupUpload = copyUpload(input.backupUpload);
    this.snapshot.recoveryState = input.recoveryState;
    this.snapshot.isLastDevice = input.isLastDevice;
    this.snapshot.hasDevicesToVerifyAgainst = input.hasDevicesToVerifyAgainst;
    this.snapshot.error = null;
    return this.getSnapshot();
  }

  fail(error: DomainError, offline: boolean): SecuritySnapshot {
    this.snapshot.phase = offline ? SecurityPhase.Offline : SecurityPhase.Error;
    this.snapshot.error = error;
    return this.getSnapshot();
  }

  setOffline(isOffline: boolean): SecuritySnapshot {
    this.snapshot.phase = isOffline ? SecurityPhase.Offline : SecurityPhase.Ready;
    if (!isOffline) {
      this.snapshot.error = null;
    }
    return this.getSnapshot();
  }

  beginKeyRequest(request: UtdKeyRequest): SecuritySnapshot {
    const pending = copyRequest(request);
    pending.state = UtdKeyRequestState.Requesting;
    pending.error = null;
    this.putRequest(pending);
    return this.getSnapshot();
  }

  updateKeyRequest(requestId: string, state: UtdKeyRequestState, error: DomainError | null): SecuritySnapshot {
    const index = this.snapshot.keyRequests.findIndex((item: UtdKeyRequest) => item.requestId === requestId);
    if (index >= 0) {
      const updated = copyRequest(this.snapshot.keyRequests[index]);
      updated.state = state;
      updated.error = error;
      this.snapshot.keyRequests[index] = updated;
    }
    return this.getSnapshot();
  }

  beginRecovery(): SecuritySnapshot {
    this.snapshot.recoveryProgress = {
      operation: RecoveryOperation.Recovering,
      backedUpCount: 0,
      totalCount: 0,
      secretAvailable: false,
      error: null
    };
    return this.getSnapshot();
  }

  beginBackups(): SecuritySnapshot {
    this.snapshot.backupState = BackupState.Enabling;
    this.snapshot.backupUpload = {
      state: BackupUploadState.Waiting,
      backedUpCount: 0,
      totalCount: 0,
      error: null
    };
    return this.getSnapshot();
  }

  finishBackups(): SecuritySnapshot {
    this.snapshot.backupState = BackupState.Enabled;
    this.snapshot.backupUpload.state = BackupUploadState.Done;
    return this.getSnapshot();
  }

  failBackups(error: DomainError): SecuritySnapshot {
    this.snapshot.backupState = BackupState.Unknown;
    this.snapshot.backupUpload = {
      state: BackupUploadState.Error,
      backedUpCount: 0,
      totalCount: 0,
      error: error
    };
    return this.getSnapshot();
  }

  beginEnableRecovery(): SecuritySnapshot {
    this.snapshot.recoveryProgress = {
      operation: RecoveryOperation.Starting,
      backedUpCount: 0,
      totalCount: 0,
      secretAvailable: false,
      error: null
    };
    return this.getSnapshot();
  }

  finishEnableRecovery(): SecuritySnapshot {
    this.snapshot.recoveryState = RecoveryState.Enabled;
    this.snapshot.recoveryProgress = {
      operation: RecoveryOperation.Done,
      backedUpCount: 0,
      totalCount: 0,
      secretAvailable: true,
      error: null
    };
    return this.getSnapshot();
  }

  beginDisableRecovery(): SecuritySnapshot {
    this.snapshot.recoveryProgress.operation = RecoveryOperation.Disabling;
    this.snapshot.recoveryProgress.secretAvailable = false;
    this.snapshot.recoveryProgress.error = null;
    return this.getSnapshot();
  }

  finishDisableRecovery(): SecuritySnapshot {
    this.snapshot.recoveryState = RecoveryState.Disabled;
    this.snapshot.recoveryProgress = {
      operation: RecoveryOperation.Done,
      backedUpCount: 0,
      totalCount: 0,
      secretAvailable: false,
      error: null
    };
    return this.getSnapshot();
  }

  finishRecovery(): SecuritySnapshot {
    this.snapshot.recoveryState = RecoveryState.Enabled;
    this.snapshot.recoveryProgress = {
      operation: RecoveryOperation.Done,
      backedUpCount: 0,
      totalCount: 0,
      secretAvailable: false,
      error: null
    };
    return this.getSnapshot();
  }

  failRecovery(error: DomainError): SecuritySnapshot {
    this.snapshot.recoveryProgress = {
      operation: RecoveryOperation.Failed,
      backedUpCount: 0,
      totalCount: 0,
      secretAvailable: false,
      error: error
    };
    return this.getSnapshot();
  }

  private putRequest(request: UtdKeyRequest): void {
    const index = this.snapshot.keyRequests.findIndex((item: UtdKeyRequest) => item.requestId === request.requestId);
    if (index >= 0) {
      this.snapshot.keyRequests[index] = request;
    } else {
      this.snapshot.keyRequests.push(request);
    }
  }
}
