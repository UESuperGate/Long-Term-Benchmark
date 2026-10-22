import { MatrixRoomClient, RoomSession } from '../features/RoomClient';
import { SdkRoomTransport } from '../features/SdkRoomTransport';
import { LeaveAction, RoomDetailsPresenter } from '../features/RoomDetailsFeature';
import { MatrixReportingRoomClient } from '../features/ReportRoomClient';
import { ReportActionState, RoomFlow } from '../features/ReportRoomFeature';

@Entry
@Component
struct Index {
  private details: RoomDetailsPresenter | undefined = undefined;
  private flow: RoomFlow | undefined = undefined;
  @State private homeserver: string = '';
  @State private accessToken: string = '';
  @State private selectedRoomId: string = '';
  @State private connected: boolean = false;
  @State private loading: boolean = false;
  @State private roomLoaded: boolean = false;
  @State private roomName: string = '';
  @State private roomTopic: string = '';
  @State private memberCount: number = 0;
  @State private errorMessage: string = '';
  @State private leaveAction: LeaveAction = LeaveAction.Uninitialized;
  @State private screen: string = 'details';
  @State private reportEntryVisible: boolean = false;
  @State private reason: string = '';
  @State private leaveRoom: boolean = false;
  @State private reportAction: ReportActionState = ReportActionState.Uninitialized;
  @State private canReport: boolean = false;

  build() {
    Column() {
      Scroll() {
        Column({ space: 16 }) {
          if (!this.connected) {
            Text('Open room').fontSize(24).fontWeight(FontWeight.Bold).width('100%')
            TextInput({ text: this.homeserver, placeholder: 'Homeserver URL' })
              .id('room_homeserver').onChange((value: string) => this.homeserver = value)
            TextInput({ text: this.accessToken, placeholder: 'Access token' })
              .id('room_access_token').type(InputType.Password).onChange((value: string) => this.accessToken = value)
            TextInput({ text: this.selectedRoomId, placeholder: 'Room ID' })
              .id('room_id_input').onChange((value: string) => this.selectedRoomId = value)
            Button('Open room').id('open_room')
              .enabled(this.homeserver.trim().length > 0 && this.accessToken.length > 0 && this.selectedRoomId.length > 0)
              .onClick(() => this.openRoom())
            if (this.errorMessage.length > 0) { Text(this.errorMessage).fontColor('#B42318') }
          } else if (this.screen === 'report') {
            this.reportContent()
          } else {
            this.detailsContent()
          }
        }
        .padding(20)
        .width('100%')
      }
      .width('100%')
      .layoutWeight(1)
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#FFFFFF')
  }

  @Builder
  detailsContent() {
    Text('Room details').id('room_details_title').fontSize(24).fontWeight(FontWeight.Bold).width('100%')
    Text(this.selectedRoomId).id('room_details_id').fontSize(13).width('100%')
    if (this.loading) {
      LoadingProgress().width(32).height(32)
    }
    if (this.roomLoaded) {
      Text(this.roomName).id('room_details_name').fontSize(20).width('100%')
      Text(this.memberCount.toString() + ' members').id('room_member_count').width('100%')
      if (this.roomTopic.length > 0) { Text(this.roomTopic).width('100%') }
      if (this.reportEntryVisible && this.leaveAction !== LeaveAction.Success) {
        Button('Report room').id('report_room_entry').fontColor('#B42318').width('100%')
          .enabled(this.leaveAction !== LeaveAction.Loading)
          .onClick(() => {
            this.flow?.openReport();
            this.refresh();
          })
      }
      Button('Leave room').id('leave_room').fontColor('#B42318').width('100%')
        .enabled(this.leaveAction !== LeaveAction.Loading && this.leaveAction !== LeaveAction.Success)
        .onClick(() => {
          this.details?.requestLeave();
          this.refresh();
        })
    }
    if (this.errorMessage.length > 0) {
      Text(this.errorMessage).id('room_details_error').fontColor('#B42318')
      Button('Retry loading').id('retry_room_details').onClick(() => this.reload())
    }
    if (this.leaveAction === LeaveAction.Confirming) {
      Text('Leave this room?').id('leave_room_confirmation')
      Row({ space: 12 }) {
        Button('Cancel').id('cancel_leave_room').onClick(() => {
          this.details?.cancelLeave();
          this.refresh();
        })
        Button('Confirm leave').id('confirm_leave_room').onClick(() => this.confirmLeave())
      }
    } else if (this.leaveAction === LeaveAction.Loading) {
      Text('Leaving room...').id('leave_room_loading')
    } else if (this.leaveAction === LeaveAction.Failure) {
      Text('Unable to leave this room.').id('leave_room_error').fontColor('#B42318')
      Button('Retry leaving').id('retry_details_leave').onClick(() => this.confirmLeave())
      Button('Dismiss error').onClick(() => {
        this.details?.cancelLeave();
        this.refresh();
      })
    } else if (this.leaveAction === LeaveAction.Success) {
      Text('Left room').id('leave_room_success').fontColor('#16784A')
    }
  }

  @Builder
  reportContent() {
    Button('Back').id('report_room_back').enabled(this.reportAction !== ReportActionState.Loading).onClick(() => {
      this.flow?.closeReport();
      this.refresh();
    })
    Text('Report room').id('report_room_title').fontSize(24).fontWeight(FontWeight.Bold).width('100%')
    Text(this.selectedRoomId).id('report_room_id').fontSize(13).width('100%')
    TextArea({ text: this.reason, placeholder: 'Reason for reporting' })
      .id('report_room_reason').height(120).enabled(this.reportAction !== ReportActionState.Loading)
      .onChange((value: string) => {
        this.flow?.report?.updateReason(value);
        this.refresh();
      })
    Row({ space: 12 }) {
      Text('Leave this room after reporting').layoutWeight(1)
      Toggle({ type: ToggleType.Switch, isOn: this.leaveRoom })
        .id('report_room_leave_toggle').enabled(this.reportAction !== ReportActionState.Loading)
        .onChange(() => {
          this.flow?.report?.toggleLeaveRoom();
          this.refresh();
        })
    }
    .width('100%')
    Button(this.reportAction === ReportActionState.Loading ? 'Reporting...' : 'Report room')
      .id('submit_report_room').fontColor('#B42318').width('100%')
      .enabled(this.canReport && this.reportAction !== ReportActionState.Loading)
      .onClick(() => this.submitReport())
    if (this.reportAction === ReportActionState.LeaveFailed) {
      Text('The room was reported, but leaving failed.').id('report_room_partial_failure').fontColor('#B42318')
      Button('Retry leaving').id('retry_leave_room').onClick(() => this.submitReport())
      Button('Dismiss error').id('dismiss_report_error').onClick(() => this.clearReport())
    } else if (this.reportAction === ReportActionState.ReportFailed || this.reportAction === ReportActionState.RoomNotFound) {
      Text('Unable to report this room. Your form has been kept.').id('report_room_error').fontColor('#B42318')
      Button('Retry report').id('retry_report_room').onClick(() => this.submitReport())
      Button('Dismiss error').id('dismiss_report_error').onClick(() => this.clearReport())
    }
  }

  private submitReport(): void {
    if (!this.flow) return;
    const pending = this.flow.submitReport();
    this.refresh();
    pending.then(() => this.refresh());
  }

  private clearReport(): void {
    this.flow?.report?.clearReportAction();
    this.refresh();
  }

  private openRoom(): void {
    try {
      const session = new RoomSession(this.homeserver, this.accessToken);
      const transport = new SdkRoomTransport(session);
      this.flow = new RoomFlow(this.selectedRoomId, new MatrixReportingRoomClient(transport));
      this.details = this.flow.details;
      this.connected = true;
      this.accessToken = '';
      this.reload();
    } catch (error) {
      this.errorMessage = 'Enter a valid homeserver, access token and room ID.';
    }
  }

  private reload(): void {
    if (!this.details) return;
    const pending = this.details.load();
    this.refresh();
    pending.then(() => this.refresh());
  }

  private confirmLeave(): void {
    if (!this.details) return;
    const pending = this.details.confirmLeave();
    this.refresh();
    pending.then(() => this.refresh());
  }

  private refresh(): void {
    if (!this.details) return;
    this.loading = this.details.loading;
    this.roomLoaded = this.details.room !== undefined;
    this.roomName = this.details.room?.name || '';
    this.roomTopic = this.details.room?.topic || '';
    this.memberCount = this.details.room?.memberCount || 0;
    this.errorMessage = this.details.errorMessage;
    this.leaveAction = this.details.leaveAction;
    if (this.flow) {
      this.screen = this.flow.screen;
      this.reportEntryVisible = this.flow.details.canReportRoom;
      this.reason = this.flow.report?.reason || '';
      this.leaveRoom = this.flow.report?.leaveRoom || false;
      this.reportAction = this.flow.report?.reportAction || ReportActionState.Uninitialized;
      this.canReport = this.flow.report?.canReport || false;
    }
  }
}
