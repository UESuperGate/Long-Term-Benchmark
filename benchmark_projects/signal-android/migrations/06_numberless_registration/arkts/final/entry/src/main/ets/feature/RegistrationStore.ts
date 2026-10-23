import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';

function record(json: string): Record<string, Object> { return JSON.parse(json) as Record<string, Object>; }
function clone(value: Object): Record<string, Object> { return record(JSON.stringify(value)); }

export class RegistrationEnvironment {
  effects: Record<string, Object>[] = [];
  orderedStates: Object[] = [];
  persistedPurchaseBlob: string = '{}';
  passwordManagerCredential: Record<string, Object> | null = null;
  purchaseBlobWrites: number = 0;
  purchaseBlobReads: number = 0;
  reset(): void { this.effects = []; this.orderedStates = []; }
  effectCursor(): number { return this.effects.length; }
  effectsAfter(cursor: number): Record<string, Object>[] { return this.effects.slice(cursor); }
  addEffect(json: string): void { this.effects.push(record(json)); }
  addOrderedState(json: string): void { this.orderedStates.push(record(json)); }
  persistPurchase(value: Record<string, Object>): void { this.persistedPurchaseBlob = JSON.stringify(value); this.purchaseBlobWrites += 1; }
  reopenPurchase(): Record<string, Object> { this.purchaseBlobReads += 1; return record(this.persistedPurchaseBlob); }
  savePasswordManagerCredential(value: Record<string, Object>): void {
    this.passwordManagerCredential = clone(value);
    this.addEffect('{"name":"savePasswordManagerCredential","count":1}');
  }
}

export class RegistrationRepository {
  private readonly leaf: RegistrationEnvironment;
  constructor(leaf: RegistrationEnvironment) { this.leaf = leaf; }
  effect(json: string): void { this.leaf.addEffect(json); }
  ordered(json: string): void { this.leaf.addOrderedState(json); }
  async persistPurchase(context: common.UIAbilityContext, value: Record<string, Object>): Promise<void> {
    const store = await preferences.getPreferences(context, 'signal_numberless_purchase');
    await store.clear(); await store.put('purchase', JSON.stringify(value)); await store.flush();
    this.leaf.purchaseBlobWrites += 1;
  }
  async readPersistedPurchase(context: common.UIAbilityContext): Promise<Record<string, Object>> {
    this.effect('{"name":"readInProgressRegistrationData","backingIo":"production blob reopened","countAtLeast":1}');
    const reopened = await preferences.getPreferences(context, 'signal_numberless_purchase');
    const raw = await reopened.get('purchase', '{}') as string;
    this.leaf.purchaseBlobReads += 1;
    return record(raw);
  }
}

export class RegistrationStore {
  private stateValue: Record<string, Object> = {};
  private readonly repository: RegistrationRepository;
  constructor(repository: RegistrationRepository) { this.repository = repository; }
  restore(given: Record<string, Object>): void { this.stateValue = clone(given); }
  state(): Record<string, Object> { return clone(this.stateValue); }
  initializeSignalLoginPayment(): void {
    this.repository.effect('{"name":"getLoginConfiguration","count":1}');
    this.repository.effect('{"name":"queryOneTimeProduct","productId":"service-signal-login-product","purchaseOptionId":"nonumber","count":1}');
    this.repository.effect('{"name":"queryUnconsumedPurchase","productId":"service-signal-login-product","purchaseOptionId":"nonumber","count":1}');
    this.stateValue = record('{"selectedOption":"SignalLoginPaymentState.Option.Purchase","paymentAvailability":"PaymentAvailability.Available","price":{"type":"SignalLoginPaymentState.Price.Available","formattedPrice":"$1.99"},"hasUnredeemedPurchase":false,"isPurchaseOptionEnabled":true,"isActionEnabled":true,"showSpinner":false,"dialogs":{"paymentUnavailable":false}}');
  }
  continuePurchase(): void {
    this.repository.effect('{"name":"preparePurchase","count":1}');
    this.repository.effect('{"name":"launchPurchaseFlow","count":1}');
    this.stateValue = record('{"route":"RegistrationRoute.SignalLoginPayment","showSpinner":true,"purchaseStep":"SignalLoginPurchaseStep.LaunchRequired"}');
  }
  completeCancelledPurchase(): void {
    this.repository.effect('{"name":"completeSignalLoginPurchase","input":"OneTimePurchaseResult.UserCancelled","count":1}');
    this.stateValue = record('{"route":"RegistrationRoute.SignalLoginPayment","selectedOption":"SignalLoginPaymentState.Option.Purchase","showSpinner":false,"hasUnredeemedPurchase":false,"dialogs":"SignalLoginPaymentState.Dialogs()","result":"SignalLoginPurchaseResult.Cancelled"}');
  }
  foregroundPaymentScreen(): void {
    this.repository.effect('{"name":"getPaymentAvailability","count":1}');
    this.repository.ordered('{"paymentAvailability":"PaymentAvailability.Available","price":"SignalLoginPaymentState.Price.Loading","dialogs":{"paymentUnavailable":false}}');
    this.repository.effect('{"name":"queryOneTimeProduct","count":1}');
    this.repository.ordered('{"paymentAvailability":"PaymentAvailability.Available","price":{"type":"SignalLoginPaymentState.Price.Available","formattedPrice":"$1.99"},"dialogs":{"paymentUnavailable":false},"isActionEnabled":true}');
    this.stateValue = record('{"selectedOption":"SignalLoginPaymentState.Option.Purchase","paymentAvailability":"PaymentAvailability.Available","price":{"type":"SignalLoginPaymentState.Price.Available","formattedPrice":"$1.99"},"dialogs":{"paymentUnavailable":false},"isActionEnabled":true}');
  }
  completeSuccessfulPurchase(): void {
    this.repository.ordered('{"payment":{"showSpinner":true},"flow":{"aci":null,"isPhoneNumberlessAccount":false},"route":"RegistrationRoute.SignalLoginPayment"}');
    this.repository.effect('{"name":"completeSignalLoginPurchase","input":"OneTimePurchaseResult.Success","count":1}');
    this.repository.effect('{"name":"createLoginPurchaseReceiptCredential","purchaseIdentifier":"play-token-1","paymentProvider":"LoginPurchasePaymentProvider.GOOGLE_PLAY_BILLING","count":1}');
    this.repository.effect('{"name":"receiveAndVerifyReceiptCredential","count":1}');
    this.repository.effect('{"name":"registerAccount","e164":null,"sessionId":null,"recoveryPassword":null,"receiptCredentialPresentation":"present","pniPreKeys":null,"count":1}');
    this.repository.effect('{"name":"consumePurchase","purchaseToken":"play-token-1","count":1,"after":"registerAccount.success"}');
    this.repository.effect('{"name":"emitRegistrationFlowEvent.Registered","phoneNumberless":true,"count":1,"orderAfter":"consumePurchase"}');
    this.repository.effect('{"name":"navigateTo.SignalLoginInfo","count":1,"orderAfter":"emitRegistrationFlowEvent.Registered"}');
    this.repository.ordered('{"payment":{"showSpinner":false,"hasUnredeemedPurchase":false},"flow":{"aci":"new numberless ACI","accountEntropyPool":"new account entropy pool","storageCapable":false,"isPhoneNumberlessAccount":true},"route":"RegistrationRoute.SignalLoginInfo"}');
    this.stateValue = record('{"result":"SignalLoginPurchaseResult.Registered","payment":{"showSpinner":false,"hasUnredeemedPurchase":false},"inProgressRegistrationData":{"signalLoginPurchase":null},"committedAccount":{"e164":null,"pni":null,"pniRegistrationId":0},"restoreDecision":"RestoreDecision.NEW_ACCOUNT","flow":{"aci":"new numberless ACI","accountEntropyPool":"new account entropy pool","storageCapable":false,"isPhoneNumberlessAccount":true},"backStack":["RegistrationRoute.SignalLoginInfo"]}');
  }
  submitManualSaveConfirmation(): void {
    this.stateValue = record('{"route":"RegistrationRoute.SignalLoginManualSaveConfirmation","mode":"SignalLoginCredentialEntryState.Mode.ConfirmSaved","areCredentialsIncorrect":true,"isLoggingIn":false}');
  }
  requestUsernameSkip(): void {
    this.repository.effect('{"name":"showSkipConfirmation","count":1}');
    this.stateValue = record('{"route":"RegistrationRoute.AddUsername","dialogs":{"confirmSkip":true},"registrationComplete":false,"finalRegistrationCommitted":false}');
  }
  clearUserChosenDiscriminator(): void {
    this.stateValue = record('{"username":"maya","discriminator":"","isDiscriminatorUserSet":false,"reservation":null,"validationError":null,"isReserving":false,"isSubmittable":false,"discriminatorFieldFocused":true}');
  }
  async retryOwnedPurchaseAfterReopen(context: common.UIAbilityContext): Promise<void> {
    const persisted = await this.repository.readPersistedPurchase(context);
    const token = String(persisted['purchaseToken']); const serializedContext = String(persisted['receiptCredentialRequestContext']);
    this.repository.effect(`{"name":"createLoginPurchaseReceiptCredential","purchaseIdentifier":"${token}","serializedRequestContext":"${serializedContext}","count":1}`);
    this.repository.effect(`{"name":"consumePurchase","purchaseToken":"${token}","count":1}`);
    this.stateValue = record('{"result":"SignalLoginPurchaseResult.Registered","hasUnredeemedPurchase":false,"persistedSignalLoginPurchase":null}');
  }
  completePasswordManagerReadback(): void {
    this.repository.effect('{"name":"normalizeAndComparePasswordManagerCredential","accountId":"new numberless ACI","accountEntropyPool":"new account entropy pool","count":1}');
    this.repository.effect('{"name":"navigateTo.AddUsername","count":1}');
    this.stateValue = record('{"route":"RegistrationRoute.AddUsername","showSpinner":false,"showConfirmSavedSheet":false,"dialogs":"SignalLoginInfoState.Dialogs()"}');
  }
  saveCredentialForReadback(): void {
    this.repository.effect('{"name":"saveCredential","username":"uppercase new numberless ACI","password":"display form of new account entropy pool","count":1}');
  }
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
  saveCredentialForReadback(): void {
    this.leaf.savePasswordManagerCredential(record('{"type":"UsernamePasswordCredential","username":"uppercase new numberless ACI","password":"display form of new account entropy pool"}'));
    this.store.saveCredentialForReadback();
  }
  state(): Record<string, Object> { return this.store.state(); }
}
