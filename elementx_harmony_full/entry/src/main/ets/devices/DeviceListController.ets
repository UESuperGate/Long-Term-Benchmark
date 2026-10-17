import { DomainErrorCode, DomainResult, unexpectedFailure } from '../core/DomainResult';
import {
  DeviceListInput,
  DeviceListSnapshot,
  DeviceTrustState
} from '../matrix/api/SecurityModels';
import {
  DeviceDataSource,
  DeviceListObserver,
  DeviceListService,
  SecuritySubscription
} from '../matrix/api/SecurityServices';
import { DeviceListReducer } from './DeviceListReducer';

class DeviceSubscription implements SecuritySubscription {
  readonly subscriptionId: number;
  private readonly onClose: (subscriptionId: number) => void;
  private closed: boolean = false;

  constructor(subscriptionId: number, onClose: (subscriptionId: number) => void) {
    this.subscriptionId = subscriptionId;
    this.onClose = onClose;
  }

  close(): void {
    if (!this.closed) {
      this.closed = true;
      this.onClose(this.subscriptionId);
    }
  }
}

export class DeviceListController implements DeviceListService {
  private readonly source: DeviceDataSource;
  private readonly reducer: DeviceListReducer = new DeviceListReducer();
  private readonly observers: Map<number, DeviceListObserver> = new Map<number, DeviceListObserver>();
  private nextObserverId: number = 1;
  private generation: number = 0;

  constructor(source: DeviceDataSource) {
    this.source = source;
  }

  getSnapshot(): DeviceListSnapshot {
    return this.reducer.getSnapshot();
  }

  subscribe(observer: DeviceListObserver): SecuritySubscription {
    const id = this.nextObserverId++;
    this.observers.set(id, observer);
    observer.onDeviceListChanged(this.getSnapshot());
    return new DeviceSubscription(id, (subscriptionId: number) => this.observers.delete(subscriptionId));
  }

  async start(): Promise<DomainResult<DeviceListSnapshot>> {
    return this.load(false);
  }

  async refresh(): Promise<DomainResult<DeviceListSnapshot>> {
    return this.load(true);
  }

  async setLocalTrust(
    deviceId: string,
    trustState: DeviceTrustState
  ): Promise<DomainResult<DeviceListSnapshot>> {
    const result = await this.source.setLocalTrust(deviceId, trustState);
    if (!result.success) {
      return DomainResult.fail<DeviceListSnapshot>(
        result.error === null ? unexpectedFailure('device trust update') : result.error
      );
    }
    const updated = this.reducer.updateTrust(deviceId, trustState);
    if (updated.success && updated.value !== null) {
      this.publish(updated.value);
    }
    return updated;
  }

  private async load(refreshing: boolean): Promise<DomainResult<DeviceListSnapshot>> {
    const generation = ++this.generation;
    this.publish(this.reducer.beginLoading(refreshing));
    const result = await this.source.loadDevices();
    if (generation !== this.generation) {
      return DomainResult.fail<DeviceListSnapshot>(unexpectedFailure('superseded device load'));
    }
    if (!result.success || result.value === null) {
      const error = result.error === null ? unexpectedFailure('device load') : result.error;
      this.publish(this.reducer.fail(error, error.code === DomainErrorCode.NetworkUnavailable));
      return DomainResult.fail<DeviceListSnapshot>(error);
    }
    const input: DeviceListInput = result.value;
    const reduced = this.reducer.replace(input.devices, input.crossSigningState);
    if (!reduced.success || reduced.value === null) {
      const error = reduced.error === null ? unexpectedFailure('device list validation') : reduced.error;
      this.publish(this.reducer.fail(error, false));
      return DomainResult.fail<DeviceListSnapshot>(error);
    }
    this.publish(reduced.value);
    return reduced;
  }

  private publish(snapshot: DeviceListSnapshot): void {
    this.observers.forEach((observer: DeviceListObserver) => observer.onDeviceListChanged(snapshot));
  }
}
