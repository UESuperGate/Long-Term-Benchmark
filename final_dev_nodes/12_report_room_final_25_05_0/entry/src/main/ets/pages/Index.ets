import { ReportActionState, ReportRoomGateway, ReportRoomPresenter, ReportRoomService } from '../features/ReportRoomFeature';

@Entry
@Component
struct Index {
  private gateway: ReportRoomGateway = new ReportRoomGateway();
  private presenter: ReportRoomPresenter = new ReportRoomPresenter(new ReportRoomService(this.gateway));
  @State private reason: string = '';
  @State private leaveRoom: boolean = false;
  @State private reportAction: ReportActionState = ReportActionState.Uninitialized;

  build() {
    Column() {
      Column({ space: 4 }) {
        Text('Report room')
          .fontSize(24)
          .fontWeight(FontWeight.Bold)
        Text('Community support')
          .fontSize(13)
          .fontColor('#64748B')
      }
      .alignItems(HorizontalAlign.Start)
      .padding(20)
      .width('100%')
      .backgroundColor('#FFFFFF')

      Scroll() {
        Column({ space: 16 }) {
          Text('Tell us what is wrong with this room.')
            .width('100%')
          TextInput({ text: this.reason, placeholder: 'Reason for reporting' })
            .id('report_room_reason')
            .enabled(this.reportAction !== ReportActionState.Loading)
            .onChange((value: string) => {
              this.presenter.updateReason(value);
              this.refresh();
            })
          Row({ space: 12 }) {
            Text('Leave this room after reporting')
              .layoutWeight(1)
            Toggle({ type: ToggleType.Switch, isOn: this.leaveRoom })
              .id('report_room_leave_toggle')
              .enabled(this.reportAction !== ReportActionState.Loading)
              .onChange(() => {
                this.presenter.toggleLeaveRoom();
                this.refresh();
              })
          }
          .width('100%')

          Button(this.reportAction === ReportActionState.Loading ? 'Reporting...' : 'Report room')
            .id('submit_report_room')
            .enabled(this.reason.trim().length > 0 && this.reportAction !== ReportActionState.Loading)
            .width('100%')
            .onClick(() => {
              this.presenter.submit();
              this.refresh();
            })

          if (this.reportAction === ReportActionState.Success) {
            Text(this.leaveRoom ? 'Room reported and left' : 'Room reported')
              .id('report_room_success')
              .fontColor('#16784A')
              .width('100%')
          } else if (this.reportAction === ReportActionState.ReportFailed ||
            this.reportAction === ReportActionState.RoomNotFound) {
            Column({ space: 8 }) {
              Text('Unable to report this room. Your form has been kept.')
                .fontColor('#B42318')
              Button('Retry report')
                .id('retry_report_room')
                .onClick(() => {
                  this.presenter.retry();
                  this.refresh();
                })
              Button('Dismiss error')
                .onClick(() => {
                  this.presenter.clearReportAction();
                  this.refresh();
                })
            }
            .width('100%')
          } else if (this.reportAction === ReportActionState.LeaveFailed) {
            Column({ space: 8 }) {
              Text('The room was reported, but leaving failed.')
                .id('report_room_partial_failure')
                .fontColor('#B42318')
              Button('Retry leaving')
                .id('retry_leave_room')
                .onClick(() => {
                  this.presenter.retry();
                  this.refresh();
                })
              Button('Dismiss error')
                .onClick(() => {
                  this.presenter.clearReportAction();
                  this.refresh();
                })
            }
            .width('100%')
          }
        }
        .padding(20)
        .width('100%')
      }
      .layoutWeight(1)
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }

  private refresh(): void {
    this.reason = this.presenter.reason;
    this.leaveRoom = this.presenter.leaveRoom;
    this.reportAction = this.presenter.reportAction;
  }
}
