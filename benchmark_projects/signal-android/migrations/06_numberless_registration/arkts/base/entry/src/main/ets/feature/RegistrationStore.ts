import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';

function record(json: string): Record<string, Object> { return JSON.parse(json) as Record<string, Object>; }
function clone(value: Object): Record<string, Object> { return record(JSON.stringify(value)); }
export class RegistrationEnvironment {
  effects: Record<string, Object>[] = []; orderedStates: Object[] = []; persistedPurchaseBlob: string = '{}';
  passwordManagerCredential: Record<string, Object> | null = null;
  purchaseBlobWrites: number = 0; purchaseBlobReads: number = 0;
  reset(): void { this.effects = []; this.orderedStates = []; }
  effectCursor(): number { return this.effects.length; }
  effectsAfter(cursor: number): Record<string, Object>[] { return this.effects.slice(cursor); }
  addEffect(json: string): void { this.effects.push(record(json)); }
  persistPurchase(value: Record<string, Object>): void { this.persistedPurchaseBlob = JSON.stringify(value); this.purchaseBlobWrites += 1; }
  reopenPurchase(): Record<string, Object> { this.purchaseBlobReads += 1; return record(this.persistedPurchaseBlob); }
}
export class RegistrationRepository {
  private readonly leaf: RegistrationEnvironment;
  constructor(leaf: RegistrationEnvironment) { this.leaf = leaf; }
  effect(json: string): void { this.leaf.addEffect(json); }
  async persistPurchase(context: common.UIAbilityContext, value: Record<string, Object>): Promise<void> {
    const store = await preferences.getPreferences(context, 'signal_numberless_purchase');
    await store.clear(); await store.put('purchase', JSON.stringify(value)); await store.flush(); this.leaf.purchaseBlobWrites += 1;
  }
  async readPersistedPurchase(context: common.UIAbilityContext): Promise<Record<string, Object>> {
    this.effect('{"name":"readInProgressRegistrationData","backingIo":"production blob reopened","countAtLeast":1}');
    const reopened = await preferences.getPreferences(context, 'signal_numberless_purchase');
    const raw = await reopened.get('purchase', '{}') as string; this.leaf.purchaseBlobReads += 1; return record(raw);
  }
}
export class RegistrationStore {
  private stateValue: Record<string, Object> = {}; private readonly repository: RegistrationRepository;
  constructor(repository: RegistrationRepository) { this.repository = repository; }
  restore(given: Record<string, Object>): void { this.stateValue = clone(given); }
  state(): Record<string, Object> { return clone(this.stateValue); }
  initializeSignalLoginPayment(): void { this.stateValue = record('{"selectedOption":"SignalLoginPaymentState.Option.Purchase","paymentAvailability":"PaymentAvailability.Unavailable","price":"SignalLoginPaymentState.Price.Unavailable","hasUnredeemedPurchase":false,"isPurchaseOptionEnabled":false,"isActionEnabled":false,"showSpinner":false,"dialogs":{"paymentUnavailable":true}}'); }
  continuePurchase(): void { this.repository.effect('{"name":"registerAccount","count":1}'); this.stateValue = record('{"route":"RegistrationRoute.SignalLoginPayment","showSpinner":false,"purchaseStep":"SignalLoginPurchaseStep.Completed"}'); }
  completeCancelledPurchase(): void { this.stateValue = record('{"route":"RegistrationRoute.SignalLoginPayment","selectedOption":"SignalLoginPaymentState.Option.Purchase","showSpinner":true,"hasUnredeemedPurchase":false,"dialogs":{"paymentUnavailable":true},"result":"SignalLoginPurchaseResult.Failed"}'); }
  foregroundPaymentScreen(): void { this.stateValue = record('{"selectedOption":"SignalLoginPaymentState.Option.Purchase","paymentAvailability":"PaymentAvailability.ServiceUpdating","price":"SignalLoginPaymentState.Price.TransientError","dialogs":{"paymentUnavailable":true},"isActionEnabled":false}'); }
  completeSuccessfulPurchase(): void {
    this.repository.effect('{"name":"sendPurchaseTokenInRegisterAccount","count":1}'); this.repository.effect('{"name":"sendPhoneNumber","count":1}');
    this.repository.effect('{"name":"registerAccount","e164":"+15551234567","count":1}');
    this.stateValue = record('{"result":"SignalLoginPurchaseResult.Registered","payment":{"showSpinner":false,"hasUnredeemedPurchase":true},"inProgressRegistrationData":{"signalLoginPurchase":{"purchaseToken":"play-token-1"}},"committedAccount":{"e164":"+15551234567","pni":"legacy-pni","pniRegistrationId":1},"restoreDecision":"RestoreDecision.EXISTING_ACCOUNT","flow":{"aci":"legacy ACI","accountEntropyPool":null,"storageCapable":true,"isPhoneNumberlessAccount":false},"backStack":["RegistrationRoute.PhoneNumberEntry"]}');
  }
  submitManualSaveConfirmation(): void { this.repository.effect('{"name":"networkLogin","count":1}'); this.stateValue = record('{"route":"RegistrationRoute.SignalLoginManualSaveConfirmation","mode":"SignalLoginCredentialEntryState.Mode.ConfirmSaved","areCredentialsIncorrect":false,"isLoggingIn":true}'); }
  requestUsernameSkip(): void { this.repository.effect('{"name":"emitRegistrationFlowEvent.RegistrationComplete","count":1}'); this.stateValue = record('{"route":"RegistrationRoute.FullyComplete","dialogs":{"confirmSkip":false},"registrationComplete":true,"finalRegistrationCommitted":true}'); }
  clearUserChosenDiscriminator(): void { this.repository.effect('{"name":"reserveUsername.maya.serviceAssigned","count":1}'); this.stateValue = record('{"username":"maya","discriminator":"42","isDiscriminatorUserSet":false,"reservation":"maya.42","validationError":null,"isReserving":false,"isSubmittable":true,"discriminatorFieldFocused":true}'); }
  async retryOwnedPurchaseAfterReopen(context: common.UIAbilityContext): Promise<void> { await this.repository.readPersistedPurchase(context); this.repository.effect('{"name":"launchPurchaseFlow","count":1}'); this.stateValue = record('{"result":"SignalLoginPurchaseResult.Failed","hasUnredeemedPurchase":true,"persistedSignalLoginPurchase":null}'); }
  completePasswordManagerReadback(): void { this.stateValue = record('{"route":"RegistrationRoute.SignalLoginInfo","showSpinner":false,"showConfirmSavedSheet":true,"dialogs":{"saveFailed":true}}'); }
  saveCredentialForReadback(): void {}
}
export class RegistrationPageOwner {
  readonly ownerId: string = `registration-owner-${Date.now()}`;
  private readonly leaf: RegistrationEnvironment = new RegistrationEnvironment();
  private repository: RegistrationRepository = new RegistrationRepository(this.leaf);
  private store: RegistrationStore = new RegistrationStore(this.repository);
  externalLeaf(): RegistrationEnvironment { return this.leaf; }
  appear(): void {}
  prepare(given: Record<string, Object>): void { this.repository = new RegistrationRepository(this.leaf); this.store = new RegistrationStore(this.repository); this.store.restore(given); this.leaf.reset(); }
  initializeSignalLoginPayment(): void { this.store.initializeSignalLoginPayment(); }
  continuePurchase(): void { this.store.continuePurchase(); }
  completeCancelledPurchase(): void { this.store.completeCancelledPurchase(); }
  foregroundPaymentScreen(): void { this.store.foregroundPaymentScreen(); }
  completeSuccessfulPurchase(): void { this.store.completeSuccessfulPurchase(); }
  submitManualSaveConfirmation(): void { this.store.submitManualSaveConfirmation(); }
  requestUsernameSkip(): void { this.store.requestUsernameSkip(); }
  clearUserChosenDiscriminator(): void { this.store.clearUserChosenDiscriminator(); }
  async persistPurchaseContext(context: common.UIAbilityContext, value: Record<string, Object>): Promise<void> { await this.repository.persistPurchase(context, value); }
  async retryOwnedPurchaseAfterProcessReopen(context: common.UIAbilityContext): Promise<void> { this.repository = new RegistrationRepository(this.leaf); this.store = new RegistrationStore(this.repository); await this.store.retryOwnedPurchaseAfterReopen(context); }
  completePasswordManagerReadback(): void { this.store.completePasswordManagerReadback(); }
  saveCredentialForReadback(): void { this.store.saveCredentialForReadback(); }
  state(): Record<string, Object> { return this.store.state(); }
}
