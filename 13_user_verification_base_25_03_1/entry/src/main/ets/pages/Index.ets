import { UserProfileGateway, UserProfilePresenter, getRoomIdentityDataSource,
  TimelineIdentityPresenter, IdentityState, RoomMember } from '../features/UserProfileFeature';

@Entry
@Component
struct Index {
  private presenter: UserProfilePresenter = new UserProfilePresenter(new UserProfileGateway());
  private timeline: TimelineIdentityPresenter = new TimelineIdentityPresenter(getRoomIdentityDataSource());
  private unsubscribe: (() => void) | undefined = undefined;
  @State private profileName: string = '@alice:example.org';
  @State private profileUserId: string = '@alice:example.org';
  @State private profileVerified: boolean = false;
  @State private profileIsCurrentUser: boolean = false;
  @State private timelineWarning: string = '';
  @State private timelineViolation: IdentityState = IdentityState.Pinned;
  @State private members: RoomMember[] = [];
  @State private screen: string = 'profile';
  @State private search: string = '';
  @State private blocked: boolean = false;
  @State private statusText: string = 'User profile';

  aboutToAppear(): void {
    this.unsubscribe = getRoomIdentityDataSource().subscribe(() => { this.refreshSurfaces(); });
  }

  aboutToDisappear(): void { this.unsubscribe?.(); }

  private refreshSurfaces(): void {
    this.profileName = this.presenter.displayName;
    this.profileUserId = this.presenter.userId;
    this.profileVerified = this.presenter.isVerified;
    this.profileIsCurrentUser = this.presenter.isCurrentUser;
    const violation = this.timeline.violation;
    this.timelineWarning = violation ? this.timeline.displayName + ' identity changed' : '';
    this.timelineViolation = violation?.identityState || IdentityState.Pinned;
    this.members = getRoomIdentityDataSource().visibleMembers(this.search);
  }

  private openProfile(userId: string): void {
    this.presenter = new UserProfilePresenter(this.presenter.gateway, userId);
    this.screen = 'profile';
    this.blocked = this.presenter.blocked;
    this.refreshSurfaces();
  }

  build() {
    Column({ space: 8 }) {
      Row({ space: 16 }) {
        Button('Profile').id('open_profile').onClick(() => { this.openProfile('@alice:example.org'); })
        Button('Timeline').id('open_timeline').onClick(() => { this.screen = 'timeline'; })
        Button('Members').id('open_members').onClick(() => { this.screen = 'members'; })
      }.padding(12)
      if (this.screen === 'profile') {
      Column({ space: 8 }) {
        Text(this.profileName)
          .id('profile_display_name')
          .fontSize(28)
          .fontWeight(FontWeight.Bold)
        Text(this.profileUserId)
          .id('profile_user_id')
          .fontSize(15)
          .fontColor('#64748B')
        if (this.profileVerified) {
          Text('Verified').id('profile_verified_badge')
        }
      }
      .padding(28)
      .width('100%')
      .backgroundColor('#FFFFFF')

      Column({ space: 12 }) {
        if (!this.profileIsCurrentUser && !this.profileVerified) {
          Button('Verify identity').id('legacy_verify_identity').enabled(false)
        }
        Button('Message ' + this.profileName)
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
      } else if (this.screen === 'timeline') {
        Text('Messages').fontSize(22)
        if (this.timelineWarning) {
          Text(this.timelineWarning).id('timeline_identity_warning')
          Button(this.timelineViolation === IdentityState.VerificationViolation ?
            'Withdraw verification' : 'OK')
            .id('timeline_acknowledge_identity')
            .onClick(async () => {
              try { await this.timeline.acknowledge(); }
              catch (error) { this.statusText = 'Unable to update identity'; console.error(String(error)); }
            })
        }
        Text(this.statusText)
      } else {
        Text('Room members').fontSize(22)
        TextInput({ placeholder: 'Search', text: this.search })
          .onChange(value => {
            this.search = value;
            this.members = getRoomIdentityDataSource().visibleMembers(value);
          })
          ForEach(this.members, (member: RoomMember) => {
            Button(member.displayName).onClick(() => { this.openProfile(member.userId); })
          }, (member: RoomMember) => member.userId)
      }
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }
}
