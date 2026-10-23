import { RegistrationPageOwner } from '../feature/RegistrationStore';

@Entry
@Component
struct Index {
  private readonly owner: RegistrationPageOwner = new RegistrationPageOwner();
  @State private revision: number = 0;
  aboutToAppear(): void { this.owner.appear(); this.refresh(); }
  private refresh(): void { this.revision += 1; }
  build() {
    Column({ space: 16 }) {
      Text('Signal registration').fontSize(24).fontWeight(FontWeight.Bold)
      Text('Register without sharing a phone number')
      Button('Check purchase').id('payment-init').onClick(() => { this.owner.initializeSignalLoginPayment(); this.refresh(); })
      Button('Continue').id('payment-continue').onClick(() => { this.owner.continuePurchase(); this.refresh(); })
      Button('Skip username').id('username-skip').onClick(() => { this.owner.requestUsernameSkip(); this.refresh(); })
      Button('Verify saved login').id('credential-readback').onClick(() => { this.owner.completePasswordManagerReadback(); this.refresh(); })
    }.width('100%').height('100%').padding(24)
  }
}
