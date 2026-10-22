import { UserVerificationPresenter, VerificationGateway, IdentityStateStore, VerificationRequest,
  VerificationRequestType, VerificationStep, ReplyState, UserProfileGateway, UserProfilePresenter,
  getRoomIdentityDataSource, getSessionVerificationService, TimelineIdentityPresenter,
  IdentityState, RoomMember } from '../features/UserVerificationFeature';

@Entry
@Component
struct Index {
  private profile: UserProfilePresenter = new UserProfilePresenter(new UserProfileGateway());
  private timeline: TimelineIdentityPresenter = new TimelineIdentityPresenter(getRoomIdentityDataSource());
  private presenter: UserVerificationPresenter | undefined = undefined;
  private unsubscribe: (() => void) | undefined = undefined;
  @State private screen: string = 'profile';
  @State private profileName: string = '@alice:example.org';
  @State private profileUserId: string = '@alice:example.org';
  @State private verified: boolean = false;
  @State private violation: boolean = false;
  @State private canVerify: boolean = false;
  @State private blocked: boolean = false;
  @State private timelineWarning: string = '';
  @State private members: RoomMember[] = [];
  @State private search: string = '';
  @State private step: VerificationStep = VerificationStep.Initial;
  @State private reply: ReplyState = ReplyState.Uninitialized;
  @State private sas: string[] = [];
  @State private error: string = '';
  @State private initializing: boolean = true;
  @State private statusText: string = 'User profile';

  aboutToAppear(): void {
    this.unsubscribe = getRoomIdentityDataSource().subscribe(() => this.refreshSurfaces());
  }
  aboutToDisappear(): void { this.unsubscribe?.(); this.presenter?.dispose(); }
  private refreshSurfaces(): void {
    const room = getRoomIdentityDataSource();
    this.profileName = this.profile.displayName; this.profileUserId = this.profile.userId;
    this.verified = this.profile.isVerified;
    this.violation = room.isEncrypted && room.identities.some(identity =>
      identity.userId === this.profile.userId && identity.identityState === IdentityState.VerificationViolation);
    this.canVerify = !this.profile.isCurrentUser && !this.verified && !this.violation &&
      room.verificationAvailable && getSessionVerificationService().available;
    this.blocked = this.profile.blocked;
    this.timelineWarning = this.timeline.violation ? this.timeline.displayName + ' identity changed' : '';
    this.members = room.visibleMembers(this.search);
    this.refreshVerification();
  }
  private refreshVerification(): void {
    if (!this.presenter) return;
    this.step = this.presenter.step; this.reply = this.presenter.replyState;
    this.sas = this.presenter.sas.slice(); this.error = this.presenter.error;
    this.initializing = this.presenter.initializing;
    if (this.step === VerificationStep.Exit) this.openProfile(this.profile.userId);
  }
  private openProfile(userId: string): void {
    this.presenter?.dispose(); this.presenter = undefined;
    this.profile = new UserProfilePresenter(this.profile.gateway, userId);
    this.screen = 'profile'; this.refreshSurfaces();
  }
  private openVerification(): void {
    if (!this.canVerify) return;
    this.presenter?.dispose();
    this.presenter = new UserVerificationPresenter(new VerificationRequest(VerificationRequestType.User,
      this.profile.userId), new VerificationGateway(), new IdentityStateStore(this.profile.userId));
    this.screen = 'verify_user';
    this.presenter.attach(() => this.refreshVerification());
    this.refreshVerification();
  }
  private memberWarning(userId: string): boolean {
    const room = getRoomIdentityDataSource();
    return room.isEncrypted && room.identities.some(identity => identity.userId === userId &&
      identity.identityState === IdentityState.VerificationViolation);
  }
  build() {
    Column({ space: 8 }) {
      Row({ space: 12 }) {
        Button('Profile').id('open_profile').onClick(() => this.openProfile('@alice:example.org'))
        Button('Timeline').id('open_timeline').onClick(() => { this.presenter?.dispose(); this.presenter = undefined; this.screen = 'timeline'; })
        Button('Members').id('open_members').onClick(() => { this.presenter?.dispose(); this.presenter = undefined; this.screen = 'members'; })
      }.padding(12)
      if (this.screen === 'profile') {
        Text(this.profileName).id('profile_display_name').fontSize(28)
        Text(this.profileUserId).id('profile_user_id')
        if (this.verified) { Text('Verified').id('profile_verified_badge') }
        if (this.violation) {
          Text('Verification violation').id('profile_verification_violation')
          Button('Withdraw verification').id('withdraw_verification_action').onClick(async () => {
            try { await getRoomIdentityDataSource().withdrawVerification(this.profile.userId); }
            catch (error) { this.statusText = String(error); }
          })
        } else if (this.canVerify) {
          Button('Verify user').id('verify_user_action').onClick(() => this.openVerification())
        } else if (!this.verified && !this.profile.isCurrentUser) {
          Text('Session verification service unavailable').id('verification_unavailable')
        }
        Button('Message ' + this.profileName).id('start_direct_message').onClick(() => {
          this.profile.startDirectMessage(); this.statusText = 'Opening direct message';
        })
        Button(this.blocked ? 'Unblock user' : 'Block user').id('toggle_block_user').onClick(() => {
          this.profile.toggleBlocked(); this.blocked = this.profile.blocked;
        })
        Text(this.statusText)
      } else if (this.screen === 'verify_user') {
        Text(this.profileUserId).id('verification_target_user')
        Text(this.step).id('verification_step')
        if (this.step === VerificationStep.Initial) {
          Button('Request verification').id('request_user_verification').enabled(!this.initializing)
            .onClick(async () => { await this.presenter?.requestVerification(); })
        } else if (this.step === VerificationStep.Ready) {
          Button('Start verification').id('start_sas_verification').onClick(async () => { await this.presenter?.startSasVerification(); })
        } else if (this.step === VerificationStep.Verifying) {
          ForEach(this.sas, (symbol: string) => { Text(symbol) }, (symbol: string) => symbol)
          if (this.reply === ReplyState.Loading) { Text('Waiting for confirmation').id('verification_reply_loading') }
          Button('They match').id('accept_sas_challenge').enabled(this.reply === ReplyState.Uninitialized)
            .onClick(async () => { await this.presenter?.acceptChallenge(); })
          Button('They do not match').id('decline_sas_challenge').enabled(this.reply === ReplyState.Uninitialized)
            .onClick(async () => { await this.presenter?.declineChallenge(); })
        } else if (this.step === VerificationStep.Canceled) {
          Button('Try again').id('reset_verification').onClick(async () => { await this.presenter?.reset(); })
        }
        if (this.error) { Text(this.error).id('verification_error') }
        Button('Cancel').id('cancel_verification').onClick(async () => { await this.presenter?.cancel(); })
      } else if (this.screen === 'timeline') {
        Text('Messages').fontSize(22)
        if (this.timelineWarning) {
          Text(this.timelineWarning).id('timeline_identity_warning')
          Button(this.timeline.violation?.identityState === IdentityState.VerificationViolation ? 'Withdraw verification' : 'OK')
            .id('timeline_acknowledge_identity').onClick(async () => {
              try { await this.timeline.acknowledge(); } catch (error) { this.statusText = String(error); }
            })
        }
        Text(this.statusText)
      } else {
        Text('Room members').fontSize(22)
        TextInput({ placeholder: 'Search', text: this.search }).onChange(value => {
          this.search = value; this.members = getRoomIdentityDataSource().visibleMembers(value);
        })
        ForEach(this.members, (member: RoomMember) => {
          Row({ space: 8 }) {
            Button(member.displayName).onClick(() => this.openProfile(member.userId))
            if (this.memberWarning(member.userId)) { Text('Verification violation').id('room_member_identity_warning') }
          }
        }, (member: RoomMember) => member.userId)
      }
    }.height('100%').width('100%').padding(12).backgroundColor('#F4F6F8')
  }
}
