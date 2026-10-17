import { DomainError } from '../../core/DomainResult';

export const LOCATION_CONTRACT_VERSION: string = '1';

export enum LocationPermissionState {
  Unknown = 'unknown',
  Granted = 'granted',
  Denied = 'denied',
  DeniedPermanently = 'denied_permanently'
}

export enum LocationDisclaimerState {
  Required = 'required',
  Accepted = 'accepted'
}

export interface GeoPoint {
  latitude: number;
  longitude: number;
  accuracyMeters: number | null;
  timestampMs: number;
}

export enum LiveLocationState {
  Starting = 'starting',
  Live = 'live',
  Stopping = 'stopping',
  Stopped = 'stopped',
  TimedOut = 'timed_out',
  Failed = 'failed'
}

export interface LiveLocationShare {
  sessionId: string;
  roomId: string;
  userId: string;
  description: string | null;
  lastPoint: GeoPoint | null;
  startedAtMs: number;
  expiresAtMs: number;
  state: LiveLocationState;
  error: DomainError | null;
}

export enum LiveLocationPhase {
  Loading = 'loading',
  Ready = 'ready',
  Offline = 'offline',
  Error = 'error'
}

export interface LiveLocationSnapshot {
  phase: LiveLocationPhase;
  permission: LocationPermissionState;
  disclaimer: LocationDisclaimerState;
  locationServiceAvailable: boolean;
  pendingRoomId: string | null;
  pendingDurationMs: number | null;
  shares: LiveLocationShare[];
  error: DomainError | null;
}

export interface LiveLocationBootstrap {
  permission: LocationPermissionState;
  disclaimerAccepted: boolean;
  locationServiceAvailable: boolean;
  shares: LiveLocationShare[];
}

export interface LiveLocationNotificationRoute {
  roomId: string;
  sessionId: string;
}
