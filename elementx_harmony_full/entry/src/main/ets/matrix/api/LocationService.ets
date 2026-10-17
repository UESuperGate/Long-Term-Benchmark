import { DomainResult } from '../../core/DomainResult';
import {
  GeoPoint,
  LiveLocationBootstrap,
  LiveLocationNotificationRoute,
  LiveLocationShare,
  LocationPermissionState
} from './LocationModels';

export interface LiveLocationDataSource {
  load(): Promise<DomainResult<LiveLocationBootstrap>>;
  requestPermission(): Promise<DomainResult<LocationPermissionState>>;
  persistDisclaimerAccepted(): Promise<DomainResult<boolean>>;
  start(roomId: string, durationMs: number, point: GeoPoint): Promise<DomainResult<LiveLocationShare>>;
  update(sessionId: string, point: GeoPoint): Promise<DomainResult<LiveLocationShare>>;
  stop(sessionId: string): Promise<DomainResult<boolean>>;
}

export interface LiveLocationNotificationRouter {
  showOrUpdate(share: LiveLocationShare): Promise<DomainResult<boolean>>;
  remove(sessionId: string): Promise<DomainResult<boolean>>;
  resolve(route: LiveLocationNotificationRoute): DomainResult<boolean>;
}
