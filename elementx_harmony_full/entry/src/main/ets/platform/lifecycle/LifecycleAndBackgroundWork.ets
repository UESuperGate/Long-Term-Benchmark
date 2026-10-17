import { DomainErrorCode, DomainResult } from '../../core/DomainResult';
import { PlatformFailure, PlatformFailureKind } from '../errors/PlatformFailure';

export enum ApplicationLifecyclePhase {
  Foreground = 'foreground',
  Background = 'background',
  Inactive = 'inactive',
  Terminating = 'terminating'
}

export interface ApplicationLifecycleSnapshot {
  phase: ApplicationLifecyclePhase;
  hasRingingCall: boolean;
  inCall: boolean;
  syncingNotificationEvent: boolean;
  changedAtMs: number;
}

export type ApplicationLifecycleListener = (snapshot: ApplicationLifecycleSnapshot) => void;

export interface LifecycleSubscription {
  close(): void;
}

class LifecycleSubscriptionImpl implements LifecycleSubscription {
  private closed: boolean = false;
  private readonly closeAction: () => void;

  constructor(closeAction: () => void) {
    this.closeAction = closeAction;
  }

  close(): void {
    if (this.closed) {
      return;
    }
    this.closed = true;
    this.closeAction();
  }
}

/** Updated by Ability lifecycle callbacks; consumers only observe typed snapshots. */
export class ApplicationLifecycleState {
  private snapshotValue: ApplicationLifecycleSnapshot;
  private readonly listeners: ApplicationLifecycleListener[] = [];

  constructor(nowMs: number = new Date().getTime()) {
    this.snapshotValue = {
      phase: ApplicationLifecyclePhase.Inactive,
      hasRingingCall: false,
      inCall: false,
      syncingNotificationEvent: false,
      changedAtMs: nowMs
    };
  }

  snapshot(): ApplicationLifecycleSnapshot {
    return this.copy(this.snapshotValue);
  }

  updatePhase(phase: ApplicationLifecyclePhase, nowMs: number = new Date().getTime()): void {
    this.update({
      phase: phase,
      hasRingingCall: this.snapshotValue.hasRingingCall,
      inCall: this.snapshotValue.inCall,
      syncingNotificationEvent: this.snapshotValue.syncingNotificationEvent,
      changedAtMs: nowMs
    });
  }

  updateCallState(hasRingingCall: boolean, inCall: boolean, nowMs: number = new Date().getTime()): void {
    this.update({
      phase: this.snapshotValue.phase,
      hasRingingCall: hasRingingCall,
      inCall: inCall,
      syncingNotificationEvent: this.snapshotValue.syncingNotificationEvent,
      changedAtMs: nowMs
    });
  }

  updateNotificationSync(active: boolean, nowMs: number = new Date().getTime()): void {
    this.update({
      phase: this.snapshotValue.phase,
      hasRingingCall: this.snapshotValue.hasRingingCall,
      inCall: this.snapshotValue.inCall,
      syncingNotificationEvent: active,
      changedAtMs: nowMs
    });
  }

  subscribe(listener: ApplicationLifecycleListener): LifecycleSubscription {
    this.listeners.push(listener);
    listener(this.snapshot());
    return new LifecycleSubscriptionImpl((): void => {
      const index = this.listeners.indexOf(listener);
      if (index >= 0) {
        this.listeners.splice(index, 1);
      }
    });
  }

  private update(snapshot: ApplicationLifecycleSnapshot): void {
    this.snapshotValue = snapshot;
    const copy = this.snapshot();
    this.listeners.forEach((listener: ApplicationLifecycleListener) => listener(copy));
  }

  private copy(snapshot: ApplicationLifecycleSnapshot): ApplicationLifecycleSnapshot {
    return {
      phase: snapshot.phase,
      hasRingingCall: snapshot.hasRingingCall,
      inCall: snapshot.inCall,
      syncingNotificationEvent: snapshot.syncingNotificationEvent,
      changedAtMs: snapshot.changedAtMs
    };
  }
}

export enum BackgroundNetworkRequirement {
  None = 'none',
  Any = 'any',
  Wifi = 'wifi',
  Ethernet = 'ethernet'
}

export interface BackgroundWorkRequest {
  id: number;
  uniqueName: string;
  network: BackgroundNetworkRequirement;
  requiresCharging: boolean;
  persisted: boolean;
  repeatIntervalMs: number | null;
}

export interface BackgroundWorkSchedulerBackend {
  schedule(request: BackgroundWorkRequest): Promise<void>;
  cancel(request: BackgroundWorkRequest): Promise<void>;
}

export class BackgroundWorkScheduler {
  private readonly backend: BackgroundWorkSchedulerBackend;

  constructor(backend: BackgroundWorkSchedulerBackend) {
    this.backend = backend;
  }

  async schedule(request: BackgroundWorkRequest): Promise<DomainResult<boolean>> {
    if (request.id < 0 || request.uniqueName.length === 0 ||
      (request.repeatIntervalMs !== null && request.repeatIntervalMs <= 0)) {
      return this.failure(
        DomainErrorCode.InvalidInput,
        PlatformFailureKind.InvalidData,
        'background_work.validate',
        false
      );
    }
    try {
      await this.backend.schedule(request);
      return DomainResult.succeed<boolean>(true);
    } catch (error) {
      return this.failure(
        DomainErrorCode.ServiceUnavailable,
        PlatformFailureKind.SchedulingFailed,
        'background_work.schedule',
        true
      );
    }
  }

  async cancel(request: BackgroundWorkRequest): Promise<DomainResult<boolean>> {
    try {
      await this.backend.cancel(request);
      return DomainResult.succeed<boolean>(true);
    } catch (error) {
      return this.failure(
        DomainErrorCode.ServiceUnavailable,
        PlatformFailureKind.SchedulingFailed,
        'background_work.cancel',
        true
      );
    }
  }

  private failure(
    code: DomainErrorCode,
    kind: PlatformFailureKind,
    operation: string,
    retryable: boolean
  ): DomainResult<boolean> {
    return DomainResult.fail<boolean>(new PlatformFailure(
      code,
      kind,
      operation,
      `Background work operation failed: ${operation}`,
      retryable
    ));
  }
}

export interface SuspendDelayLease {
  close(): DomainResult<boolean>;
}

export interface SuspendDelayService {
  request(reason: string, onExpired: () => void): DomainResult<SuspendDelayLease>;
}
