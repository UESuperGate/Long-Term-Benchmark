import { DomainError, DomainErrorCode, DomainFailure, DomainResult } from '../core/DomainResult';
import {
  VerificationMethod,
  VerificationPhase,
  VerificationData,
  VerificationSnapshot,
  VerificationUpdate,
  VerificationUpdateKind
} from '../matrix/api/SecurityModels';

function emptyData(): VerificationData {
  return { emojiNumbers: [], decimals: [], qrCodeData: null };
}

export class VerificationReducer {
  private snapshot: VerificationSnapshot = {
    attemptId: null,
    phase: VerificationPhase.Initial,
    method: VerificationMethod.None,
    peerUserId: null,
    peerDeviceId: null,
    peerDeviceName: null,
    data: emptyData(),
    error: null
  };

  getSnapshot(): VerificationSnapshot {
    return {
      attemptId: this.snapshot.attemptId,
      phase: this.snapshot.phase,
      method: this.snapshot.method,
      peerUserId: this.snapshot.peerUserId,
      peerDeviceId: this.snapshot.peerDeviceId,
      peerDeviceName: this.snapshot.peerDeviceName,
      data: {
        emojiNumbers: this.snapshot.data.emojiNumbers.slice(),
        decimals: this.snapshot.data.decimals.slice(),
        qrCodeData: this.snapshot.data.qrCodeData
      },
      error: this.snapshot.error
    };
  }

  begin(attemptId: string, peerUserId: string | null): VerificationSnapshot {
    this.snapshot = {
      attemptId: attemptId,
      phase: VerificationPhase.Requesting,
      method: VerificationMethod.None,
      peerUserId: peerUserId,
      peerDeviceId: null,
      peerDeviceName: null,
      data: emptyData(),
      error: null
    };
    return this.getSnapshot();
  }

  waitForAcceptance(): VerificationSnapshot {
    this.snapshot.phase = VerificationPhase.WaitingForAcceptance;
    return this.getSnapshot();
  }

  receive(update: VerificationUpdate): DomainResult<VerificationSnapshot> {
    if (update.attemptId !== this.snapshot.attemptId) {
      return DomainResult.fail<VerificationSnapshot>(new DomainFailure(
        DomainErrorCode.Cancelled,
        'Verification update belongs to a stale attempt',
        false
      ));
    }
    this.snapshot.method = update.method;
    this.snapshot.error = update.error;
    if (update.kind === VerificationUpdateKind.RequestAccepted) {
      this.snapshot.phase = VerificationPhase.Accepted;
    } else if (update.kind === VerificationUpdateKind.SasStarted) {
      this.snapshot.phase = VerificationPhase.SasStarted;
    } else if (update.kind === VerificationUpdateKind.SasData) {
      if (!this.validSas(update)) {
        return DomainResult.fail<VerificationSnapshot>(new DomainFailure(
          DomainErrorCode.InvalidInput,
          'SAS data must contain seven emoji numbers or three decimals',
          false
        ));
      }
      this.snapshot.phase = VerificationPhase.SasReady;
      this.snapshot.data = {
        emojiNumbers: update.emojiNumbers.slice(),
        decimals: update.decimals.slice(),
        qrCodeData: null
      };
    } else if (update.kind === VerificationUpdateKind.QrData) {
      if (update.qrCodeData === null || update.qrCodeData.length === 0) {
        return DomainResult.fail<VerificationSnapshot>(new DomainFailure(
          DomainErrorCode.InvalidInput,
          'Verification QR update contains no data',
          false
        ));
      }
      this.snapshot.phase = VerificationPhase.QrReady;
      this.snapshot.data = { emojiNumbers: [], decimals: [], qrCodeData: update.qrCodeData };
    } else if (update.kind === VerificationUpdateKind.Finished) {
      this.snapshot.phase = VerificationPhase.Completed;
      this.snapshot.data = emptyData();
      this.snapshot.error = null;
    } else if (update.kind === VerificationUpdateKind.Cancelled) {
      this.snapshot.phase = VerificationPhase.Cancelled;
      this.snapshot.data = emptyData();
    } else if (update.kind === VerificationUpdateKind.Failed) {
      this.snapshot.phase = VerificationPhase.Failed;
      this.snapshot.data = emptyData();
    }
    return DomainResult.succeed<VerificationSnapshot>(this.getSnapshot());
  }

  beginApproving(): VerificationSnapshot {
    this.snapshot.phase = VerificationPhase.Approving;
    this.snapshot.error = null;
    return this.getSnapshot();
  }

  cancel(error: DomainError | null): VerificationSnapshot {
    this.snapshot.phase = VerificationPhase.Cancelled;
    this.snapshot.data = emptyData();
    this.snapshot.error = error;
    return this.getSnapshot();
  }

  fail(error: DomainError, offline: boolean): VerificationSnapshot {
    this.snapshot.phase = offline ? VerificationPhase.Offline : VerificationPhase.Failed;
    this.snapshot.data = emptyData();
    this.snapshot.error = error;
    return this.getSnapshot();
  }

  private validSas(update: VerificationUpdate): boolean {
    if (update.method === VerificationMethod.SasEmoji) {
      return update.emojiNumbers.length === 7;
    }
    if (update.method === VerificationMethod.SasDecimal) {
      return update.decimals.length === 3;
    }
    return false;
  }
}
