import {
  DomainError,
  DomainErrorCode,
  DomainFailure,
  DomainResult,
  unexpectedFailure
} from '../../core/DomainResult';
import {
  GeoPoint,
  LiveLocationBootstrap,
  LiveLocationNotificationRoute,
  LiveLocationPhase,
  LiveLocationShare,
  LiveLocationSnapshot,
  LiveLocationState,
  LocationDisclaimerState,
  LocationPermissionState
} from '../../matrix/api/LocationModels';
import {
  LiveLocationDataSource,
  LiveLocationNotificationRouter
} from '../../matrix/api/LocationService';

const MIN_DURATION_MS: number = 60 * 1000;
const MAX_DURATION_MS: number = 24 * 60 * 60 * 1000;

function validPoint(point: GeoPoint): boolean {
  return point.latitude >= -90 && point.latitude <= 90 &&
    point.longitude >= -180 && point.longitude <= 180 &&
    (point.accuracyMeters === null || point.accuracyMeters >= 0);
}

export class LiveLocationController {
  private readonly source: LiveLocationDataSource;
  private readonly notifications: LiveLocationNotificationRouter;
  private startGeneration: number = 0;
  private snapshot: LiveLocationSnapshot = {
    phase: LiveLocationPhase.Loading,
    permission: LocationPermissionState.Unknown,
    disclaimer: LocationDisclaimerState.Required,
    locationServiceAvailable: false,
    pendingRoomId: null,
    pendingDurationMs: null,
    shares: [],
    error: null
  };

  constructor(source: LiveLocationDataSource, notifications: LiveLocationNotificationRouter) {
    this.source = source;
    this.notifications = notifications;
  }

  getSnapshot(): LiveLocationSnapshot {
    return {
      phase: this.snapshot.phase,
      permission: this.snapshot.permission,
      disclaimer: this.snapshot.disclaimer,
      locationServiceAvailable: this.snapshot.locationServiceAvailable,
      pendingRoomId: this.snapshot.pendingRoomId,
      pendingDurationMs: this.snapshot.pendingDurationMs,
      shares: this.snapshot.shares.slice(),
      error: this.snapshot.error
    };
  }

  async start(): Promise<DomainResult<LiveLocationSnapshot>> {
    this.snapshot.phase = LiveLocationPhase.Loading;
    this.snapshot.error = null;
    const result = await this.source.load();
    if (!result.success || result.value === null) {
      return this.fail(result.error, 'live location load');
    }
    this.applyBootstrap(result.value);
    return DomainResult.succeed<LiveLocationSnapshot>(this.getSnapshot());
  }

  async requestPermission(): Promise<DomainResult<LiveLocationSnapshot>> {
    const result = await this.source.requestPermission();
    if (!result.success || result.value === null) {
      return this.fail(result.error, 'location permission');
    }
    this.snapshot.permission = result.value;
    this.snapshot.phase = LiveLocationPhase.Ready;
    this.snapshot.error = null;
    return DomainResult.succeed<LiveLocationSnapshot>(this.getSnapshot());
  }

  async acceptDisclaimer(): Promise<DomainResult<LiveLocationSnapshot>> {
    const result = await this.source.persistDisclaimerAccepted();
    if (!result.success || result.value !== true) {
      return this.fail(result.error, 'location disclaimer persistence');
    }
    this.snapshot.disclaimer = LocationDisclaimerState.Accepted;
    this.snapshot.phase = LiveLocationPhase.Ready;
    this.snapshot.error = null;
    return DomainResult.succeed<LiveLocationSnapshot>(this.getSnapshot());
  }

  selectDuration(roomId: string, durationMs: number): DomainResult<LiveLocationSnapshot> {
    if (roomId.length === 0 || durationMs < MIN_DURATION_MS || durationMs > MAX_DURATION_MS) {
      return DomainResult.fail<LiveLocationSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Live location room and duration are invalid',
        true
      ));
    }
    this.snapshot.pendingRoomId = roomId;
    this.snapshot.pendingDurationMs = durationMs;
    this.snapshot.error = null;
    return DomainResult.succeed<LiveLocationSnapshot>(this.getSnapshot());
  }

  async startShare(point: GeoPoint): Promise<DomainResult<LiveLocationSnapshot>> {
    const gate = this.startGate(point);
    if (gate !== null) {
      return DomainResult.fail<LiveLocationSnapshot>(gate);
    }
    const roomId = this.snapshot.pendingRoomId!;
    const durationMs = this.snapshot.pendingDurationMs!;
    const generation = ++this.startGeneration;
    const result = await this.source.start(roomId, durationMs, point);
    if (generation !== this.startGeneration) {
      return DomainResult.fail<LiveLocationSnapshot>(new DomainFailure(
        DomainErrorCode.Cancelled,
        'Stale live location start result was ignored',
        false
      ));
    }
    if (!result.success || result.value === null) {
      return this.fail(result.error, 'live location start');
    }
    if (result.value.roomId !== roomId || result.value.sessionId.length === 0) {
      return this.fail(new DomainFailure(
        DomainErrorCode.ServiceUnavailable,
        'Live location source returned a mismatched share',
        true
      ), 'live location start');
    }
    this.upsert(result.value);
    this.snapshot.pendingRoomId = null;
    this.snapshot.pendingDurationMs = null;
    this.snapshot.phase = LiveLocationPhase.Ready;
    this.snapshot.error = null;
    await this.notifications.showOrUpdate(result.value);
    return DomainResult.succeed<LiveLocationSnapshot>(this.getSnapshot());
  }

  async updateShare(sessionId: string, point: GeoPoint): Promise<DomainResult<LiveLocationSnapshot>> {
    const existing = this.findShare(sessionId);
    if (existing === null || existing.state !== LiveLocationState.Live || !validPoint(point)) {
      return DomainResult.fail<LiveLocationSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'A valid active live location share is required',
        true
      ));
    }
    const result = await this.source.update(sessionId, point);
    const current = this.findShare(sessionId);
    if (current === null || current.state !== LiveLocationState.Live) {
      return DomainResult.fail<LiveLocationSnapshot>(new DomainFailure(
        DomainErrorCode.Cancelled,
        'Stale live location update was ignored',
        false
      ));
    }
    if (!result.success || result.value === null) {
      return this.markShareFailed(sessionId, result.error, 'live location update');
    }
    this.upsert(result.value);
    await this.notifications.showOrUpdate(result.value);
    return DomainResult.succeed<LiveLocationSnapshot>(this.getSnapshot());
  }

  async stopShare(sessionId: string): Promise<DomainResult<LiveLocationSnapshot>> {
    return this.stop(sessionId, false);
  }

  async tick(sessionId: string, nowMs: number): Promise<DomainResult<LiveLocationSnapshot>> {
    const share = this.findShare(sessionId);
    if (share === null || share.state !== LiveLocationState.Live) {
      return DomainResult.fail<LiveLocationSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Stale live location timer was ignored',
        false
      ));
    }
    if (nowMs < share.expiresAtMs) {
      return DomainResult.succeed<LiveLocationSnapshot>(this.getSnapshot());
    }
    return this.stop(sessionId, true);
  }

  routeNotification(route: LiveLocationNotificationRoute): DomainResult<LiveLocationSnapshot> {
    const share = this.findShare(route.sessionId);
    if (share === null || share.roomId !== route.roomId || share.state !== LiveLocationState.Live) {
      return DomainResult.fail<LiveLocationSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Notification route does not identify an active share',
        false
      ));
    }
    const result = this.notifications.resolve(route);
    if (!result.success) {
      return DomainResult.fail<LiveLocationSnapshot>(result.error === null ?
        unexpectedFailure('location notification route') : result.error);
    }
    return DomainResult.succeed<LiveLocationSnapshot>(this.getSnapshot());
  }

  private async stop(sessionId: string, timedOut: boolean): Promise<DomainResult<LiveLocationSnapshot>> {
    const share = this.findShare(sessionId);
    if (share === null || share.state !== LiveLocationState.Live) {
      return DomainResult.fail<LiveLocationSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Active live location share not found',
        false
      ));
    }
    share.state = LiveLocationState.Stopping;
    const result = await this.source.stop(sessionId);
    const current = this.findShare(sessionId);
    if (current === null || current.state !== LiveLocationState.Stopping) {
      return DomainResult.fail<LiveLocationSnapshot>(new DomainFailure(
        DomainErrorCode.Cancelled,
        'Stale live location stop result was ignored',
        false
      ));
    }
    if (!result.success || result.value !== true) {
      return this.markShareFailed(sessionId, result.error, 'live location stop');
    }
    current.state = timedOut ? LiveLocationState.TimedOut : LiveLocationState.Stopped;
    current.error = null;
    await this.notifications.remove(sessionId);
    return DomainResult.succeed<LiveLocationSnapshot>(this.getSnapshot());
  }

  private startGate(point: GeoPoint): DomainFailure | null {
    if (this.snapshot.permission !== LocationPermissionState.Granted) {
      return new DomainFailure(DomainErrorCode.InvalidInput, 'Location permission is required', true);
    }
    if (this.snapshot.disclaimer !== LocationDisclaimerState.Accepted) {
      return new DomainFailure(DomainErrorCode.InvalidInput, 'Location disclaimer must be accepted', true);
    }
    if (!this.snapshot.locationServiceAvailable) {
      return new DomainFailure(DomainErrorCode.ServiceUnavailable, 'Location service is unavailable', true);
    }
    if (this.snapshot.pendingRoomId === null || this.snapshot.pendingDurationMs === null || !validPoint(point)) {
      return new DomainFailure(DomainErrorCode.InvalidInput, 'Location share input is incomplete', true);
    }
    return null;
  }

  private applyBootstrap(input: LiveLocationBootstrap): void {
    this.snapshot.permission = input.permission;
    this.snapshot.disclaimer = input.disclaimerAccepted ?
      LocationDisclaimerState.Accepted : LocationDisclaimerState.Required;
    this.snapshot.locationServiceAvailable = input.locationServiceAvailable;
    this.snapshot.shares = input.shares.slice();
    this.snapshot.phase = LiveLocationPhase.Ready;
    this.snapshot.error = null;
  }

  private findShare(sessionId: string): LiveLocationShare | null {
    const share = this.snapshot.shares.find((candidate: LiveLocationShare) => candidate.sessionId === sessionId);
    return share === undefined ? null : share;
  }

  private upsert(share: LiveLocationShare): void {
    const index = this.snapshot.shares.findIndex((candidate: LiveLocationShare) =>
      candidate.sessionId === share.sessionId || candidate.roomId === share.roomId);
    if (index >= 0) {
      this.snapshot.shares[index] = share;
    } else {
      this.snapshot.shares.push(share);
    }
  }

  private markShareFailed(
    sessionId: string,
    error: DomainError | null,
    operation: string
  ): DomainResult<LiveLocationSnapshot> {
    const failure = error === null ? unexpectedFailure(operation) : error;
    const share = this.findShare(sessionId);
    if (share !== null) {
      share.state = LiveLocationState.Failed;
      share.error = failure;
    }
    this.snapshot.error = failure;
    return DomainResult.fail<LiveLocationSnapshot>(failure);
  }

  private fail(error: DomainError | null, operation: string): DomainResult<LiveLocationSnapshot> {
    const failure = error === null ? unexpectedFailure(operation) : error;
    this.snapshot.phase = failure.code === DomainErrorCode.NetworkUnavailable ?
      LiveLocationPhase.Offline : LiveLocationPhase.Error;
    this.snapshot.error = failure;
    return DomainResult.fail<LiveLocationSnapshot>(failure);
  }
}
