import { DomainErrorCode, DomainResult } from '../../core/DomainResult';
import { PlatformFailure, PlatformFailureKind } from '../errors/PlatformFailure';

export enum NetworkConnectivityStatus {
  Connected = 'connected',
  Disconnected = 'disconnected'
}

export enum NetworkTransport {
  Cellular = 'cellular',
  Wifi = 'wifi',
  Bluetooth = 'bluetooth',
  Ethernet = 'ethernet',
  Vpn = 'vpn',
  Unknown = 'unknown'
}

export interface NetworkConnectivitySnapshot {
  status: NetworkConnectivityStatus;
  blocked: boolean;
  metered: boolean;
  hasInternetCapability: boolean;
  validated: boolean;
  airGapped: boolean;
  transports: NetworkTransport[];
  updatedAtMs: number;
}

export interface NetworkBackendSubscription {
  close(): Promise<void>;
}

export type NetworkSnapshotListener = (snapshot: NetworkConnectivitySnapshot) => void;

export interface NetworkConnectivityBackend {
  readSnapshot(): Promise<NetworkConnectivitySnapshot>;
  subscribe(listener: NetworkSnapshotListener): Promise<NetworkBackendSubscription>;
}

export interface NetworkSubscription {
  close(): Promise<DomainResult<boolean>>;
}

class NetworkSubscriptionImpl implements NetworkSubscription {
  private readonly backendSubscription: NetworkBackendSubscription;

  constructor(backendSubscription: NetworkBackendSubscription) {
    this.backendSubscription = backendSubscription;
  }

  async close(): Promise<DomainResult<boolean>> {
    try {
      await this.backendSubscription.close();
      return DomainResult.succeed<boolean>(true);
    } catch (error) {
      return DomainResult.fail<boolean>(new PlatformFailure(
        DomainErrorCode.ServiceUnavailable,
        PlatformFailureKind.SubscriptionFailed,
        'network.unsubscribe',
        'Unable to unregister network monitoring',
        true
      ));
    }
  }
}

/** Typed boundary consumed by sync, login and background work. */
export class NetworkConnectivityService {
  private readonly backend: NetworkConnectivityBackend;

  constructor(backend: NetworkConnectivityBackend) {
    this.backend = backend;
  }

  async snapshot(): Promise<DomainResult<NetworkConnectivitySnapshot>> {
    try {
      return DomainResult.succeed<NetworkConnectivitySnapshot>(await this.backend.readSnapshot());
    } catch (error) {
      return DomainResult.fail<NetworkConnectivitySnapshot>(new PlatformFailure(
        DomainErrorCode.ServiceUnavailable,
        PlatformFailureKind.ReadFailed,
        'network.snapshot',
        'Unable to read network connectivity',
        true
      ));
    }
  }

  async subscribe(listener: NetworkSnapshotListener): Promise<DomainResult<NetworkSubscription>> {
    try {
      const backendSubscription = await this.backend.subscribe(listener);
      const subscription: NetworkSubscription = new NetworkSubscriptionImpl(backendSubscription);
      return DomainResult.succeed<NetworkSubscription>(subscription);
    } catch (error) {
      return DomainResult.fail<NetworkSubscription>(new PlatformFailure(
        DomainErrorCode.ServiceUnavailable,
        PlatformFailureKind.SubscriptionFailed,
        'network.subscribe',
        'Unable to register network monitoring',
        true
      ));
    }
  }
}
