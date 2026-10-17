import { UserProfileGateway, UserProfilePresenter } from '../features/UserProfileFeature';

@Entry
@Component
struct Index {
  private presenter: UserProfilePresenter = new UserProfilePresenter(new UserProfileGateway());
  @State private blocked: boolean = false;
  @State private statusText: string = 'User profile';

  build() {
    Column() {
      Column({ space: 8 }) {
        Text('Alice')
          .fontSize(28)
          .fontWeight(FontWeight.Bold)
        Text('@alice:example.org')
          .fontSize(15)
          .fontColor('#64748B')
      }
      .padding(28)
      .width('100%')
      .backgroundColor('#FFFFFF')

      Column({ space: 12 }) {
        Button('Message Alice')
          .id('start_direct_message')
          .width('100%')
          .onClick(() => {
            this.presenter.startDirectMessage();
            this.statusText = 'Opening direct message';
          })
        Button(this.blocked ? 'Unblock user' : 'Block user')
          .id('toggle_block_user')
          .width('100%')
          .onClick(() => {
            this.presenter.toggleBlocked();
            this.blocked = this.presenter.blocked;
            this.statusText = this.blocked ? 'User blocked' : 'User unblocked';
          })
        Text(this.statusText)
          .fontSize(13)
          .fontColor('#64748B')
          .width('100%')
      }
      .padding(20)
      .width('100%')
      .layoutWeight(1)
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }
}
