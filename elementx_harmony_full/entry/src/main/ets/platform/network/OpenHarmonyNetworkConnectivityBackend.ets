import connection from '@ohos.net.connection';
import { BusinessError } from '@ohos.base';
import {
  NetworkBackendSubscription,
  NetworkConnectivityBackend,
  NetworkConnectivitySnapshot,
  NetworkConnectivityStatus,
  NetworkSnapshotListener,
  NetworkTransport
} from './NetworkConnectivity';
import { platformSdkError } from '../errors/PlatformFailure';

class OpenHarmonyNetworkSubscription implements NetworkBackendSubscription {
  private readonly networkConnection: connection.NetConnection;

  constructor(networkConnection: connection.NetConnection) {
    this.networkConnection = networkConnection;
  }

  close(): Promise<void> {
    return new Promise<void>((resolve: () => void, reject: (error: BusinessError) => void) => {
      this.networkConnection.unregister((error?: BusinessError): void => {
        if (error !== undefined) {
          reject(error);
        } else {
          resolve();
        }
      });
    });
  }
}

/** Requires ohos.permission.GET_NETWORK_INFO in the eventual application manifest. */
export class OpenHarmonyNetworkConnectivityBackend implements NetworkConnectivityBackend {
  private blocked: boolean = false;

  async readSnapshot(): Promise<NetworkConnectivitySnapshot> {
    try {
      const now = new Date().getTime();
      if (!(await connection.hasDefaultNet())) {
        return {
          status: NetworkConnectivityStatus.Disconnected,
          blocked: false,
          metered: false,
          hasInternetCapability: false,
          validated: false,
          airGapped: false,
          transports: [],
          updatedAtMs: now
        };
      }
      const handle = await connection.getDefaultNet();
      const capabilities = await connection.getNetCapabilities(handle);
      const networkCapabilities = capabilities.networkCap === undefined ? [] : capabilities.networkCap;
      const hasInternet = networkCapabilities.includes(connection.NetCap.NET_CAPABILITY_INTERNET);
      const validated = networkCapabilities.includes(connection.NetCap.NET_CAPABILITY_VALIDATED);
      return {
        status: NetworkConnectivityStatus.Connected,
        blocked: this.blocked,
        metered: await connection.isDefaultNetMetered(),
        hasInternetCapability: hasInternet,
        validated: validated,
        airGapped: hasInternet && !validated,
        transports: this.mapTransports(capabilities.bearerTypes),
        updatedAtMs: now
      };
    } catch (error) {
      throw platformSdkError('network.read_snapshot', error as Error);
    }
  }

  async subscribe(listener: NetworkSnapshotListener): Promise<NetworkBackendSubscription> {
    const networkConnection = connection.createNetConnection();
    networkConnection.on('netAvailable', (): void => this.emitCurrent(listener));
    networkConnection.on('netLost', (): void => this.emitCurrent(listener));
    networkConnection.on('netUnavailable', (): void => this.emitCurrent(listener));
    networkConnection.on('netCapabilitiesChange', (): void => this.emitCurrent(listener));
    networkConnection.on('netBlockStatusChange', (info: connection.NetBlockStatusInfo): void => {
      this.blocked = info.blocked;
      this.emitCurrent(listener);
    });
    await this.register(networkConnection);
    this.emitCurrent(listener);
    return new OpenHarmonyNetworkSubscription(networkConnection);
  }

  private emitCurrent(listener: NetworkSnapshotListener): void {
    this.readSnapshot().then((snapshot: NetworkConnectivitySnapshot) => listener(snapshot)).catch(() => {
      // A failed refresh does not synthesize a disconnected state.
    });
  }

  private register(networkConnection: connection.NetConnection): Promise<void> {
    return new Promise<void>((resolve: () => void, reject: (error: BusinessError) => void) => {
      networkConnection.register((error?: BusinessError): void => {
        if (error !== undefined) {
          reject(error);
        } else {
          resolve();
        }
      });
    });
  }

  private mapTransports(bearers: connection.NetBearType[]): NetworkTransport[] {
    const transports: NetworkTransport[] = [];
    bearers.forEach((bearer: connection.NetBearType) => {
      if (bearer === connection.NetBearType.BEARER_CELLULAR) {
        transports.push(NetworkTransport.Cellular);
      } else if (bearer === connection.NetBearType.BEARER_WIFI) {
        transports.push(NetworkTransport.Wifi);
      } else if (bearer === connection.NetBearType.BEARER_BLUETOOTH) {
        transports.push(NetworkTransport.Bluetooth);
      } else if (bearer === connection.NetBearType.BEARER_ETHERNET) {
        transports.push(NetworkTransport.Ethernet);
      } else if (bearer === connection.NetBearType.BEARER_VPN) {
        transports.push(NetworkTransport.Vpn);
      } else {
        transports.push(NetworkTransport.Unknown);
      }
    });
    return transports;
  }
}
