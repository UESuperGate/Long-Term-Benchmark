import { JoinRoomByAddressPresenter, RoomAddressState } from '../features/JoinRoomByAddressFeature';
import { SessionRoomAliasResolver, RoutedJoinRoomNavigator } from '../features/JoinRoomRuntime';
import { roomGateway, chatNavigator } from '../features/ChatRuntime';
import { StartChatView } from '../components/StartChatView';

@Entry
@Component
struct Index {
  private navigator: RoutedJoinRoomNavigator = new RoutedJoinRoomNavigator(chatNavigator);
  private presenter: JoinRoomByAddressPresenter =
    new JoinRoomByAddressPresenter(new SessionRoomAliasResolver(roomGateway), this.navigator);
  @State private addressFlowVisible: boolean = false;
  @State private address: string = '';
  @State private addressState: RoomAddressState = RoomAddressState.Unknown;
  @State private navigationError: string = '';

  build() {
    Scroll() {
      Column() {
        Text('Start a chat').fontSize(24).fontWeight(FontWeight.Bold).padding(20).width('100%')
        if (!this.addressFlowVisible) {
          StartChatView({
            showJoin: true,
            onJoin: () => {
              this.navigator.showJoinRoomByAddress();
              this.refresh();
            }
          })
        } else {
          Column({ space: 14 }) {
            Text('Join a room by address').fontSize(20).fontWeight(FontWeight.Bold)
            TextInput({ text: this.address, placeholder: '#lobby:demo.local' })
              .id('room_address_input')
              .onChange((value: string) => {
                this.presenter.updateAddress(value).then(() => this.afterNavigation());
                this.refresh();
                setTimeout(() => this.refresh(), 300);
              })
            Text(this.stateMessage()).fontColor(this.addressState === RoomAddressState.RoomFound ? '#17635C' : '#B42318')
            if (this.navigationError.length > 0) {
              Text(this.navigationError).id('join_navigation_error').fontColor('#B42318')
            }
            Button(this.addressState === RoomAddressState.Resolving ? 'Resolving...' : 'Continue')
              .id('join_room_continue').width('100%')
              .onClick(() => {
                this.presenter.continue();
                this.afterNavigation();
              })
            Button('Cancel').id('join_room_cancel').width('100%')
              .onClick(() => {
                this.presenter.dismiss();
                this.refresh();
              })
          }.padding(20).width('100%')
        }
      }.width('100%')
    }.height('100%').width('100%').backgroundColor('#F4F6F8')
  }

  private afterNavigation(): void {
    this.refresh();
    this.navigator.navigation.then(() => this.refresh());
  }

  private refresh(): void {
    this.addressFlowVisible = this.navigator.addressFlowVisible;
    this.address = this.presenter.address;
    this.addressState = this.presenter.visibleAddressState();
    this.navigationError = this.navigator.navigationError;
  }

  private stateMessage(): string {
    switch (this.addressState) {
      case RoomAddressState.Invalid: return 'Enter a valid Matrix room address';
      case RoomAddressState.Resolving: return 'Looking up room...';
      case RoomAddressState.RoomNotFound: return 'Room not found. Check the address and retry.';
      case RoomAddressState.RoomFound: return 'Room found';
      default: return 'Use the full address, including the server name.';
    }
  }
}
