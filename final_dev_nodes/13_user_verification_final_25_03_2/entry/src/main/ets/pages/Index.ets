import {
  IdentityState,
  IdentityStateStore,
  ReplyState,
  UserVerificationPresenter,
  VerificationGateway,
  VerificationRequest,
  VerificationRequestType,
  VerificationStep
} from '../features/UserVerificationFeature';

@Entry
@Component
struct Index {
  private identityStore: IdentityStateStore = new IdentityStateStore(
    '@alice:example.org',
    IdentityState.VerificationViolation
  );
  private presenter: UserVerificationPresenter = new UserVerificationPresenter(
    new VerificationRequest(VerificationRequestType.User, '@alice:example.org'),
    new VerificationGateway(),
    this.identityStore
  );
  @State private step: VerificationStep = VerificationStep.Initial;
  @State private replyState: ReplyState = ReplyState.Uninitialized;
  @State private sas: string[] = [];
  @State private identityState: IdentityState = IdentityState.VerificationViolation;
  @State private warningVisible: boolean = true;

  build() {
    Column() {
      Scroll() {
        Column({ space: 14 }) {
          Column({ space: 6 }) {
            Text('Alice')
              .fontSize(28)
              .fontWeight(FontWeight.Bold)
            Text('@alice:example.org')
              .fontSize(15)
              .fontColor('#64748B')
            if (this.identityState === IdentityState.Verified) {
              Text('Verified')
                .id('verified_user_badge')
                .fontColor('#16784A')
            } else if (this.warningVisible) {
              Text('Identity changed - verification required')
                .id('profile_verification_violation')
                .fontColor('#B42318')
            }
          }
          .padding(20)
          .width('100%')
          .backgroundColor('#FFFFFF')

          if (this.warningVisible) {
            Text('Messages from this member need identity review.')
              .id('timeline_identity_warning')
              .padding(14)
              .width('100%')
              .backgroundColor('#FFF4D6')
              .borderRadius(6)
            Text('Room member identity warning')
              .id('room_member_identity_warning')
              .fontColor('#B42318')
              .width('100%')
          }

          if (this.step === VerificationStep.Initial) {
            Button('Verify Alice')
              .id('verify_user_action')
              .width('100%')
              .onClick(() => {
                this.presenter.requestVerification();
                this.refresh();
              })
          } else if (this.step === VerificationStep.AwaitingOtherDeviceResponse && this.sas.length === 0) {
            Text('Waiting for Alice to accept...')
              .width('100%')
            Button('Continue when accepted')
              .id('verification_remote_accepted')
              .onClick(() => {
                this.presenter.remoteAcceptedRequest();
                this.refresh();
              })
            Button('Cancel')
              .id('cancel_verification')
              .onClick(() => {
                this.presenter.cancel();
                this.refresh();
              })
          } else if (this.step === VerificationStep.Ready) {
            Text('Alice accepted the request.')
              .width('100%')
            Button('Start emoji verification')
              .id('start_sas_verification')
              .onClick(() => {
                this.presenter.startSasVerification();
                this.presenter.receiveChallenge(['Dog', 'Tree', 'Rocket']);
                this.refresh();
              })
          } else if (this.step === VerificationStep.Verifying) {
            Text('Compare these emojis')
              .fontSize(18)
              .fontWeight(FontWeight.Bold)
              .width('100%')
            Text(this.sas.join('  '))
              .id('sas_challenge')
              .fontSize(20)
              .width('100%')
            Row({ space: 10 }) {
              Button('They match')
                .id('accept_sas_challenge')
                .enabled(this.replyState === ReplyState.Uninitialized)
                .onClick(() => {
                  this.presenter.acceptChallenge();
                  this.refresh();
                })
              Button('They do not match')
                .id('decline_sas_challenge')
                .enabled(this.replyState === ReplyState.Uninitialized)
                .onClick(() => {
                  this.presenter.declineChallenge();
                  this.refresh();
                })
            }
            if (this.replyState === ReplyState.Loading) {
              Button('Complete verification')
                .id('finish_verification')
                .onClick(() => {
                  this.presenter.verificationFinished();
                  this.refresh();
                })
            }
          } else if (this.step === VerificationStep.Canceled) {
            Text('Verification was canceled or failed.')
              .id('verification_canceled')
              .fontColor('#B42318')
              .width('100%')
            Button('Try again')
              .id('reset_verification')
              .onClick(() => {
                this.presenter.reset();
                this.refresh();
              })
          } else if (this.step === VerificationStep.Completed) {
            Text('Alice is verified')
              .id('verification_completed')
              .fontColor('#16784A')
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
    this.step = this.presenter.step;
    this.replyState = this.presenter.replyState;
    this.sas = this.presenter.sas.slice();
    this.identityState = this.identityStore.identityState;
    this.warningVisible = this.identityStore.warningVisible;
  }
}
