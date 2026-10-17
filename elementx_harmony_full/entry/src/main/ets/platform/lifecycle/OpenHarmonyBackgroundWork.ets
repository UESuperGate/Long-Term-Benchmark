import backgroundTaskManager from '@ohos.resourceschedule.backgroundTaskManager';
import workScheduler from '@ohos.resourceschedule.workScheduler';
import { DomainErrorCode, DomainResult } from '../../core/DomainResult';
import {
  PlatformFailure,
  PlatformFailureKind,
  platformCodeOf,
  platformSdkError
} from '../errors/PlatformFailure';
import {
  BackgroundNetworkRequirement,
  BackgroundWorkRequest,
  BackgroundWorkSchedulerBackend,
  SuspendDelayLease,
  SuspendDelayService
} from './LifecycleAndBackgroundWork';

class OpenHarmonySuspendDelayLease implements SuspendDelayLease {
  private readonly requestId: number;
  private closed: boolean = false;

  constructor(requestId: number) {
    this.requestId = requestId;
  }

  close(): DomainResult<boolean> {
    if (this.closed) {
      return DomainResult.succeed<boolean>(false);
    }
    try {
      backgroundTaskManager.cancelSuspendDelay(this.requestId);
      this.closed = true;
      return DomainResult.succeed<boolean>(true);
    } catch (error) {
      return DomainResult.fail<boolean>(new PlatformFailure(
        DomainErrorCode.ServiceUnavailable,
        PlatformFailureKind.SchedulingFailed,
        'suspend_delay.cancel',
        'Unable to cancel suspend delay',
        true,
        platformCodeOf(error as Error)
      ));
    }
  }
}

export class OpenHarmonyBackgroundWorkBackend implements BackgroundWorkSchedulerBackend {
  private readonly bundleName: string;
  private readonly abilityName: string;

  constructor(bundleName: string, abilityName: string) {
    this.bundleName = bundleName;
    this.abilityName = abilityName;
  }

  async schedule(request: BackgroundWorkRequest): Promise<void> {
    try {
      const work = this.toWorkInfo(request);
      workScheduler.startWork(work);
    } catch (error) {
      throw platformSdkError('background_work.schedule', error as Error);
    }
  }

  async cancel(request: BackgroundWorkRequest): Promise<void> {
    try {
      workScheduler.stopWork(this.toWorkInfo(request), true);
    } catch (error) {
      throw platformSdkError('background_work.cancel', error as Error);
    }
  }

  private toWorkInfo(request: BackgroundWorkRequest): workScheduler.WorkInfo {
    const work: workScheduler.WorkInfo = {
      workId: request.id,
      bundleName: this.bundleName,
      abilityName: this.abilityName,
      isPersisted: request.persisted,
      isCharging: request.requiresCharging
    };
    const networkType = this.networkType(request.network);
    if (networkType !== null) {
      work.networkType = networkType;
    }
    if (request.repeatIntervalMs !== null) {
      work.isRepeat = true;
      work.repeatCycleTime = request.repeatIntervalMs;
    }
    return work;
  }

  private networkType(requirement: BackgroundNetworkRequirement): workScheduler.NetworkType | null {
    if (requirement === BackgroundNetworkRequirement.Any) {
      return workScheduler.NetworkType.NETWORK_TYPE_ANY;
    }
    if (requirement === BackgroundNetworkRequirement.Wifi) {
      return workScheduler.NetworkType.NETWORK_TYPE_WIFI;
    }
    if (requirement === BackgroundNetworkRequirement.Ethernet) {
      return workScheduler.NetworkType.NETWORK_TYPE_ETHERNET;
    }
    return null;
  }
}

export class OpenHarmonySuspendDelayService implements SuspendDelayService {
  request(reason: string, onExpired: () => void): DomainResult<SuspendDelayLease> {
    if (reason.length === 0) {
      return DomainResult.fail<SuspendDelayLease>(new PlatformFailure(
        DomainErrorCode.InvalidInput,
        PlatformFailureKind.InvalidData,
        'suspend_delay.validate',
        'Suspend delay reason is empty',
        false
      ));
    }
    try {
      const info = backgroundTaskManager.requestSuspendDelay(reason, onExpired);
      const lease: SuspendDelayLease = new OpenHarmonySuspendDelayLease(info.requestId);
      return DomainResult.succeed<SuspendDelayLease>(lease);
    } catch (error) {
      return DomainResult.fail<SuspendDelayLease>(new PlatformFailure(
        DomainErrorCode.ServiceUnavailable,
        PlatformFailureKind.SchedulingFailed,
        'suspend_delay.request',
        'Unable to request suspend delay',
        true,
        platformCodeOf(error as Error)
      ));
    }
  }
}
