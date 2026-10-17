import { DomainError, DomainErrorCode, DomainFailure, DomainResult } from '../core/DomainResult';
import {
  CrossSigningState,
  DeviceListPhase,
  DeviceListSnapshot,
  DeviceSummary,
  DeviceTrustState
} from '../matrix/api/SecurityModels';

function copyDevice(device: DeviceSummary): DeviceSummary {
  return {
    deviceId: device.deviceId,
    displayName: device.displayName,
    isCurrent: device.isCurrent,
    lastSeenAtMs: device.lastSeenAtMs,
    lastSeenIp: device.lastSeenIp,
    trustState: device.trustState
  };
}

function sortDevices(devices: DeviceSummary[]): DeviceSummary[] {
  return devices.sort((left: DeviceSummary, right: DeviceSummary) => {
    if (left.isCurrent !== right.isCurrent) {
      return left.isCurrent ? -1 : 1;
    }
    const leftSeen = left.lastSeenAtMs === null ? -1 : left.lastSeenAtMs;
    const rightSeen = right.lastSeenAtMs === null ? -1 : right.lastSeenAtMs;
    if (leftSeen !== rightSeen) {
      return rightSeen - leftSeen;
    }
    return left.deviceId.localeCompare(right.deviceId);
  });
}

export class DeviceListReducer {
  private snapshot: DeviceListSnapshot = {
    phase: DeviceListPhase.Loading,
    devices: [],
    crossSigningState: CrossSigningState.Unknown,
    isRefreshing: false,
    error: null
  };

  getSnapshot(): DeviceListSnapshot {
    return {
      phase: this.snapshot.phase,
      devices: this.snapshot.devices.map((device: DeviceSummary) => copyDevice(device)),
      crossSigningState: this.snapshot.crossSigningState,
      isRefreshing: this.snapshot.isRefreshing,
      error: this.snapshot.error
    };
  }

  beginLoading(refreshing: boolean): DeviceListSnapshot {
    this.snapshot.isRefreshing = refreshing;
    this.snapshot.error = null;
    if (this.snapshot.devices.length === 0) {
      this.snapshot.phase = DeviceListPhase.Loading;
    }
    return this.getSnapshot();
  }

  replace(devices: DeviceSummary[], crossSigningState: CrossSigningState): DomainResult<DeviceListSnapshot> {
    const unique: DeviceSummary[] = [];
    for (let index = 0; index < devices.length; index += 1) {
      const device = devices[index];
      if (device.deviceId.length === 0) {
        return DomainResult.fail<DeviceListSnapshot>(new DomainFailure(
          DomainErrorCode.InvalidInput,
          'A device list item is missing its device ID',
          false
        ));
      }
      const existing = unique.findIndex((candidate: DeviceSummary) => candidate.deviceId === device.deviceId);
      if (existing >= 0) {
        unique[existing] = copyDevice(device);
      } else {
        unique.push(copyDevice(device));
      }
    }
    this.snapshot.devices = sortDevices(unique);
    this.snapshot.crossSigningState = crossSigningState;
    this.snapshot.phase = unique.length === 0 ? DeviceListPhase.Empty : DeviceListPhase.Ready;
    this.snapshot.isRefreshing = false;
    this.snapshot.error = null;
    return DomainResult.succeed<DeviceListSnapshot>(this.getSnapshot());
  }

  updateTrust(deviceId: string, trustState: DeviceTrustState): DomainResult<DeviceListSnapshot> {
    const index = this.snapshot.devices.findIndex((device: DeviceSummary) => device.deviceId === deviceId);
    if (index < 0) {
      return DomainResult.fail<DeviceListSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        `Cannot update unknown device ${deviceId}`,
        false
      ));
    }
    const updated = copyDevice(this.snapshot.devices[index]);
    updated.trustState = trustState;
    this.snapshot.devices[index] = updated;
    return DomainResult.succeed<DeviceListSnapshot>(this.getSnapshot());
  }

  fail(error: DomainError, offline: boolean): DeviceListSnapshot {
    this.snapshot.phase = offline ? DeviceListPhase.Offline : DeviceListPhase.Error;
    this.snapshot.isRefreshing = false;
    this.snapshot.error = error;
    return this.getSnapshot();
  }
}
