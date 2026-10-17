import { DemoRoomAliasResolver, JoinRoomByAddressPresenter, JoinRoomNavigator, RoomAddressState } from '../features/JoinRoomByAddressFeature';

@Entry
@Component
struct Index {
  private navigator: JoinRoomNavigator = new JoinRoomNavigator();
  private presenter: JoinRoomByAddressPresenter = new JoinRoomByAddressPresenter(new DemoRoomAliasResolver(), this.navigator);
  @State private addressFlowVisible: boolean = false;
  @State private address: string = '';
  @State private addressState: RoomAddressState = RoomAddressState.Unknown;
  @State private openedRoom: string = '';

  build() {
    Column() {
      Column({ space: 4 }) {
        Text('Start a chat').fontSize(24).fontWeight(FontWeight.Bold)
        Text('Find people, create rooms, or join by Matrix address').fontSize(13).fontColor('#64748B')
      }
      .alignItems(HorizontalAlign.Start)
      .padding(20)
      .width('100%')
      .backgroundColor('#FFFFFF')
      if (!this.addressFlowVisible) {
        Column({ space: 12 }) {
          TextInput({ placeholder: 'Search people' })
          Button('Create room').width('100%')
          Button('Invite friends').width('100%')
          Button('Join a room by address')
            .id('join_room_by_address')
            .width('100%')
            .onClick(() => {
              this.navigator.showJoinRoomByAddress();
              this.refresh();
            })
          if (this.openedRoom.length > 0) {
            Text(`Opening ${this.openedRoom}`).fontColor('#0F766E')
          }
        }
        .padding(20)
        .width('100%')
      } else {
        Column({ space: 14 }) {
          Text('Join a room by address').fontSize(20).fontWeight(FontWeight.Bold)
          TextInput({ text: this.address, placeholder: '#room:example.org' })
            .id('room_address_input')
            .onChange((value: string) => {
              this.presenter.updateAddress(value).then(() => this.refresh());
              this.address = value.trim();
              this.addressState = RoomAddressState.Unknown;
              setTimeout(() => this.refresh(), 300);
            })
          Text(this.stateMessage()).fontColor(this.addressState === RoomAddressState.RoomFound ? '#0F766E' : '#B42318')
          Button(this.addressState === RoomAddressState.Resolving ? 'Resolving...' : 'Continue')
            .id('join_room_continue')
            .width('100%')
            .onClick(() => {
              this.presenter.continue();
              this.refresh();
            })
          Button('Cancel')
            .width('100%')
            .onClick(() => {
              this.presenter.dismiss();
              this.refresh();
            })
        }
        .padding(20)
        .width('100%')
      }
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }

  private refresh(): void {
    this.addressFlowVisible = this.navigator.addressFlowVisible;
    this.address = this.presenter.address;
    this.addressState = this.presenter.visibleAddressState();
    this.openedRoom = this.navigator.openedRoomId;
  }

  private stateMessage(): string {
    switch (this.addressState) {
      case RoomAddressState.Invalid:
        return 'Enter a valid Matrix room address';
      case RoomAddressState.Resolving:
        return 'Looking up room...';
      case RoomAddressState.RoomNotFound:
        return 'Room not found. Check the address and retry.';
      case RoomAddressState.RoomFound:
        return 'Room found';
      default:
        return 'Use the full address, including the server name.';
    }
  }
}
