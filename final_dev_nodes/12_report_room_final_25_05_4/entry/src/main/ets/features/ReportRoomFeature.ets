import { requireRoomId } from './RoomClient';
import { ReportingRoomClient } from './ReportRoomClient';
import { LeaveAction, RoomDetailsPresenter } from './RoomDetailsFeature';

export enum ReportActionState {
  Uninitialized = 'uninitialized',
  Loading = 'loading',
  Success = 'success',
  ReportFailed = 'report_failed',
  LeaveFailed = 'leave_failed',
  RoomNotFound = 'room_not_found'
}

export class ReportRoomService {
  readonly client: ReportingRoomClient;

  constructor(client: ReportingRoomClient) { this.client = client; }

  async execute(roomId: string, reason: string, shouldReport: boolean, shouldLeave: boolean): Promise<ReportActionState> {
    const room = await this.client.getRoom(roomId);
    if (!room || room.roomId !== roomId) return ReportActionState.RoomNotFound;
    if (shouldReport) {
      try {
        // Android takes nonblank reason verbatim, not trim().
        await this.client.reportRoom(roomId, reason.trim().length > 0 ? reason : undefined);
      } catch (error) {
        return ReportActionState.ReportFailed;
      }
    }
    if (shouldLeave) {
      try {
        await this.client.leaveRoom(roomId);
      } catch (error) {
        return ReportActionState.LeaveFailed;
      }
    }
    return ReportActionState.Success;
  }
}

export class ReportRoomPresenter {
  readonly roomId: string;
  readonly service: ReportRoomService;
  reason: string = '';
  leaveRoom: boolean = false;
  reportAction: ReportActionState = ReportActionState.Uninitialized;

  constructor(roomId: string, service: ReportRoomService) {
    requireRoomId(roomId);
    this.roomId = roomId;
    this.service = service;
  }

  get canReport(): boolean { return this.reason.trim().length > 0; }

  updateReason(reason: string): void { this.reason = reason; }
  toggleLeaveRoom(): void { this.leaveRoom = !this.leaveRoom; }

  async submit(): Promise<void> {
    if (!this.canReport || this.reportAction === ReportActionState.Loading) return;
    const shouldReport = this.reportAction !== ReportActionState.LeaveFailed;
    const reason = this.reason;
    const shouldLeave = this.leaveRoom;
    this.reportAction = ReportActionState.Loading;
    try {
      this.reportAction = await this.service.execute(this.roomId, reason, shouldReport, shouldLeave);
    } catch (error) {
      this.reportAction = ReportActionState.ReportFailed;
    }
  }

  async retry(): Promise<void> { await this.submit(); }

  clearReportAction(): void {
    if (this.reportAction !== ReportActionState.Loading) this.reportAction = ReportActionState.Uninitialized;
  }
}

export class ReportingRoomDetailsPresenter extends RoomDetailsPresenter {
  private readonly reportingClient: ReportingRoomClient;
  canReportRoom: boolean = false;
  capabilityLoading: boolean = false;

  constructor(roomId: string, client: ReportingRoomClient) {
    super(roomId, client);
    this.reportingClient = client;
  }

  async load(): Promise<void> {
    if (this.loading || this.capabilityLoading) return;
    this.canReportRoom = false;
    this.capabilityLoading = true;
    await super.load();
    try {
      if (this.room) this.canReportRoom = await this.reportingClient.canReportRoom();
    } catch (error) {
      this.canReportRoom = false;
    } finally {
      this.capabilityLoading = false;
    }
  }
}

export class RoomFlow {
  readonly details: ReportingRoomDetailsPresenter;
  readonly client: ReportingRoomClient;
  report: ReportRoomPresenter | undefined = undefined;
  screen: string = 'details';

  constructor(roomId: string, client: ReportingRoomClient) {
    this.client = client;
    this.details = new ReportingRoomDetailsPresenter(roomId, client);
  }

  openReport(): boolean {
    if (this.screen !== 'details' || !this.details.room || !this.details.canReportRoom || this.details.capabilityLoading ||
      this.details.leaveAction === LeaveAction.Loading || this.details.leaveAction === LeaveAction.Success) return false;
    this.report = new ReportRoomPresenter(this.details.roomId, new ReportRoomService(this.client));
    this.screen = 'report';
    return true;
  }

  closeReport(): void {
    if (this.report?.reportAction === ReportActionState.Loading) return;
    this.screen = 'details';
  }

  async submitReport(): Promise<void> {
    const report = this.report;
    if (this.screen !== 'report' || !report) return;
    await report.submit();
    if (report.reportAction === ReportActionState.Success && this.report === report) {
      if (report.leaveRoom) this.details.leaveAction = LeaveAction.Success;
      this.screen = 'details';
    }
  }
}
