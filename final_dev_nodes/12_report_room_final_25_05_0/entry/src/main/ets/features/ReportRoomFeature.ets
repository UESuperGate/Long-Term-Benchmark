export enum ReportActionState {
  Uninitialized = 'uninitialized',
  Loading = 'loading',
  Success = 'success',
  ReportFailed = 'report_failed',
  LeaveFailed = 'leave_failed',
  RoomNotFound = 'room_not_found'
}

export class ReportRoomGateway {
  roomExists: boolean = true;
  reportShouldFail: boolean = false;
  leaveShouldFail: boolean = false;
  reportCalls: number = 0;
  leaveCalls: number = 0;
  lastReportReason: string = '';
  effects: string[] = [];

  reportRoom(reason: string): boolean {
    this.reportCalls += 1;
    this.lastReportReason = reason;
    this.effects.push('report_room');
    return !this.reportShouldFail;
  }

  leaveRoom(): boolean {
    this.leaveCalls += 1;
    this.effects.push('leave_room');
    return !this.leaveShouldFail;
  }
}

export class ReportRoomService {
  readonly gateway: ReportRoomGateway;

  constructor(gateway: ReportRoomGateway) {
    this.gateway = gateway;
  }

  execute(reason: string, shouldReport: boolean, shouldLeave: boolean): ReportActionState {
    if (!this.gateway.roomExists) {
      return ReportActionState.RoomNotFound;
    }
    if (shouldReport && !this.gateway.reportRoom(reason.trim())) {
      return ReportActionState.ReportFailed;
    }
    if (shouldLeave && !this.gateway.leaveRoom()) {
      return ReportActionState.LeaveFailed;
    }
    return ReportActionState.Success;
  }
}

export class ReportRoomPresenter {
  readonly service: ReportRoomService;
  reason: string = '';
  leaveRoom: boolean = false;
  reportAction: ReportActionState = ReportActionState.Uninitialized;

  constructor(service: ReportRoomService) {
    this.service = service;
  }

  get canReport(): boolean {
    return this.reason.trim().length > 0;
  }

  updateReason(reason: string): void {
    this.reason = reason;
  }

  toggleLeaveRoom(): void {
    this.leaveRoom = !this.leaveRoom;
  }

  submit(): void {
    if (!this.canReport || this.reportAction === ReportActionState.Loading) {
      return;
    }
    const shouldReport = this.reportAction !== ReportActionState.LeaveFailed;
    this.reportAction = ReportActionState.Loading;
    this.reportAction = this.service.execute(this.reason, shouldReport, this.leaveRoom);
  }

  retry(): void {
    this.submit();
  }

  clearReportAction(): void {
    this.reportAction = ReportActionState.Uninitialized;
  }
}
