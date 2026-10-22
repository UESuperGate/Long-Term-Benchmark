import { MatrixRoomClient, RoomSession } from '../features/RoomClient';
import { SdkRoomTransport } from '../features/SdkRoomTransport';
import { LeaveAction, RoomDetailsPresenter } from '../features/RoomDetailsFeature';

@Entry
@Component
struct Index {
  private details: RoomDetailsPresenter | undefined = undefined;
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

  private openRoom(): void {
    try {
      const session = new RoomSession(this.homeserver, this.accessToken);
      const transport = new SdkRoomTransport(session);
      this.details = new RoomDetailsPresenter(this.selectedRoomId, new MatrixRoomClient(transport));
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
  }
}
