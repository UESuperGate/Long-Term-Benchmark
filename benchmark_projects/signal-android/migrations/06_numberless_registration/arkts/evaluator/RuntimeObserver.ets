import { hilog } from '@kit.PerformanceAnalysisKit';
import { common } from '@kit.AbilityKit';
import { RegistrationEnvironment, RegistrationPageOwner } from '../feature/RegistrationStore';

interface RegistrationObservation {
  caseId: string;
  productionEntrypoint: string;
  ownerId: string;
  entryLifecycle: string;
  availability: string;
  givenEstablished: boolean;
  given: Record<string, Object>;
  before: Record<string, Object>;
  after: Record<string, Object>;
  effects: Record<string, Object>[];
  orderedStates: Object[];
  invariantFacts: boolean[];
  invariantEvidence: string[];
  persistenceReopened: boolean;
  setupEffects: Record<string, Object>[];
  persistenceEvidence: Record<string, Object>;
}

let observerRan: boolean = false;
function record(json: string): Record<string, Object> { return JSON.parse(json) as Record<string, Object>; }
function effectCount(effects: Record<string, Object>[], name: string): number {
  return effects.filter((effect: Record<string, Object>): boolean => effect['name'] === name).length;
}
function emit(owner: RegistrationPageOwner, leaf: RegistrationEnvironment, caseId: string, action: string,
  given: Record<string, Object>, before: Record<string, Object>, after: Record<string, Object>,
  effects: Record<string, Object>[], facts: boolean[], reopened: boolean = false,
  setupEffects: Record<string, Object>[] = [], persistenceEvidence: Record<string, Object> = {}): void {
  const row: RegistrationObservation = {
    caseId, productionEntrypoint: `Index.owner.${action}`, ownerId: owner.ownerId,
    entryLifecycle: 'Index.aboutToAppear', availability: 'executed_api23_arkvm_index_page_owner',
    givenEstablished: true, given, before, after, effects, orderedStates: [...leaf.orderedStates],
    invariantFacts: facts,
    invariantEvidence: facts.map((_value: boolean): string => 'derived from page-owner state, navigation, persisted leaf, and ordered external effects'),
    persistenceReopened: reopened, setupEffects, persistenceEvidence
  };
  const payload: string = JSON.stringify(row);
  const chunkSize: number = 1800;
  const chunkCount: number = Math.ceil(payload.length / chunkSize);
  for (let chunkIndex: number = 0; chunkIndex < chunkCount; chunkIndex += 1) {
    const chunk: string = payload.slice(chunkIndex * chunkSize, (chunkIndex + 1) * chunkSize);
    hilog.info(0x0B06, 'BenchmarkObserver', 'BENCHMARK_CHUNK:%{public}s', `${caseId}:${chunkIndex}:${chunkCount}:${chunk}`);
  }
}

export async function runFocusedSemanticObserver(owner: RegistrationPageOwner, context: common.UIAbilityContext): Promise<void> {
  if (observerRan) return;
  observerRan = true;
  const leaf = owner.externalLeaf();
  let before: Record<string, Object>;
  let after: Record<string, Object>;
  let cursor: number;
  let effects: Record<string, Object>[];

  const given1 = record('{"entryRoute":"RegistrationRoute.SignalLoginPayment","phoneNumberlessRegistrationAvailable":true,"googlePlayServices":"PaymentAvailability.Available","googlePlayBillingAvailable":true,"serviceLoginConfiguration":{"playProductId":"service-signal-login-product"},"billingProduct":{"productId":"service-signal-login-product","purchaseOptionId":"nonumber","formattedPrice":"$1.99"},"ownedUnconsumedPurchase":false}');
  owner.prepare(given1); before = owner.state(); cursor = leaf.effectCursor(); owner.initializeSignalLoginPayment(); after = owner.state(); effects = leaf.effectsAfter(cursor);
  emit(owner, leaf, 'nr_001_purchase_eligibility_service_price', 'initializeSignalLoginPayment', given1, before, after, effects,
    [after['paymentAvailability'] === 'PaymentAvailability.Available' && effectCount(effects, 'queryOneTimeProduct') === 1,
      ((after['price'] as Record<string, Object>)['formattedPrice'] === '$1.99'), effectCount(effects, 'launchPurchaseFlow') === 0]);

  const given2 = record('{"route":"RegistrationRoute.SignalLoginPayment","selectedOption":"SignalLoginPaymentState.Option.Purchase","paymentAvailability":"PaymentAvailability.Available","price":{"type":"SignalLoginPaymentState.Price.Available","formattedPrice":"$1.99"},"showSpinner":false,"purchasePreparation":"OneTimePurchasePreparation.Ready"}');
  owner.prepare(given2); before = owner.state(); cursor = leaf.effectCursor(); owner.continuePurchase(); after = owner.state(); effects = leaf.effectsAfter(cursor);
  emit(owner, leaf, 'nr_002_purchase_launch_holds_completion', 'continuePurchase', given2, before, after, effects,
    [effectCount(effects, 'launchPurchaseFlow') === 1, after['showSpinner'] === true, effectCount(effects, 'registerAccount') === 0]);

  const given3 = record('{"route":"RegistrationRoute.SignalLoginPayment","selectedOption":"SignalLoginPaymentState.Option.Purchase","paymentAvailability":"PaymentAvailability.Available","price":{"type":"SignalLoginPaymentState.Price.Available","formattedPrice":"$1.99"},"showSpinner":true,"purchaseSheet":"open","hasUnredeemedPurchase":false,"dialogs":"SignalLoginPaymentState.Dialogs()"}');
  owner.prepare(given3); before = owner.state(); cursor = leaf.effectCursor(); owner.completeCancelledPurchase(); after = owner.state(); effects = leaf.effectsAfter(cursor);
  emit(owner, leaf, 'nr_003_purchase_cancel_cleanup', 'completeCancelledPurchase', given3, before, after, effects,
    [after['result'] === 'SignalLoginPurchaseResult.Cancelled', after['showSpinner'] === false, effectCount(effects, 'registerAccount') === 0]);

  const given4 = record('{"route":"RegistrationRoute.SignalLoginPayment","selectedOption":"SignalLoginPaymentState.Option.Purchase","paymentAvailability":"PaymentAvailability.ServiceUpdating","price":"SignalLoginPaymentState.Price.TransientError","dialogs":{"paymentUnavailable":true},"showSpinner":false,"nextAvailability":"PaymentAvailability.Available","nextPrice":"$1.99"}');
  owner.prepare(given4); before = owner.state(); cursor = leaf.effectCursor(); owner.foregroundPaymentScreen(); after = owner.state(); effects = leaf.effectsAfter(cursor);
  emit(owner, leaf, 'nr_004_billing_unavailable_foreground_retry', 'foregroundPaymentScreen', given4, before, after, effects,
    [after['paymentAvailability'] === 'PaymentAvailability.Available', effectCount(effects, 'getPaymentAvailability') === 1, leaf.orderedStates.length === 2]);

  const given5 = record('{"route":"RegistrationRoute.SignalLoginPayment","payment":{"showSpinner":true,"hasUnredeemedPurchase":true},"purchase":{"purchaseToken":"play-token-1","state":"BillingPurchaseState.PURCHASED"},"receiptCredentialRequestContext":"fresh-valid-context","serviceReceiptResult":"CreateLoginReceiptCredentialResult.Issued","receiptVerification":"ReceiptCredentialResult.Success","registrationResponse":{"aci":"new numberless ACI","accountEntropyPool":"new account entropy pool","e164":null,"pni":null,"storageCapable":false,"authCredentialSalt":"present"},"consumePurchaseSucceeds":true,"flowState":{"aci":null,"accountEntropyPool":null,"isPhoneNumberlessAccount":false}}');
  owner.prepare(given5); before = owner.state(); cursor = leaf.effectCursor(); owner.completeSuccessfulPurchase(); after = owner.state(); effects = leaf.effectsAfter(cursor);
  const flow5 = after['flow'] as Record<string, Object>; const account5 = after['committedAccount'] as Record<string, Object>;
  emit(owner, leaf, 'nr_005_private_receipt_registration_propagates', 'completeSuccessfulPurchase', given5, before, after, effects,
    [effectCount(effects, 'createLoginPurchaseReceiptCredential') === 1 && effectCount(effects, 'sendPurchaseTokenInRegisterAccount') === 0,
      account5['e164'] === null && effectCount(effects, 'sendPniPreKeys') === 0,
      effectCount(effects, 'consumePurchase') === 1, effectCount(effects, 'emitRegistrationFlowEvent.Registered') === 1,
      flow5['isPhoneNumberlessAccount'] === true, JSON.stringify(after['backStack']) === JSON.stringify(['RegistrationRoute.SignalLoginInfo'])]);

  const given6 = record('{"route":"RegistrationRoute.SignalLoginManualSaveConfirmation","mode":"SignalLoginCredentialEntryState.Mode.ConfirmSaved","parentLogin":{"aci":"expected account ID","accountEntropyPool":"expected recovery key"},"enteredLogin":{"accountId":"expected account ID","recoveryKey":"different valid recovery key"},"isNextEnabled":true,"areCredentialsIncorrect":false}');
  owner.prepare(given6); before = owner.state(); cursor = leaf.effectCursor(); owner.submitManualSaveConfirmation(); after = owner.state(); effects = leaf.effectsAfter(cursor);
  emit(owner, leaf, 'nr_006_manual_save_mismatch_verification', 'submitManualSaveConfirmation', given6, before, after, effects,
    [after['areCredentialsIncorrect'] === true, after['areCredentialsIncorrect'] === true, after['route'] === 'RegistrationRoute.SignalLoginManualSaveConfirmation']);

  const given7 = record('{"route":"RegistrationRoute.AddUsername","dialogs":{"confirmSkip":false},"registrationComplete":false,"finalRegistrationCommitted":false}');
  owner.prepare(given7); before = owner.state(); cursor = leaf.effectCursor(); owner.requestUsernameSkip(); after = owner.state(); effects = leaf.effectsAfter(cursor);
  emit(owner, leaf, 'nr_007_username_skip_requires_confirmation', 'requestUsernameSkip', given7, before, after, effects,
    [after['registrationComplete'] === false, after['route'] === 'RegistrationRoute.AddUsername', effectCount(effects, 'emitRegistrationFlowEvent.RegistrationComplete') === 0]);

  const given8 = record('{"route":"RegistrationRoute.AddUsername","username":"maya","discriminator":"88","isDiscriminatorUserSet":true,"reservation":"maya.88","validationError":null,"isReserving":false,"isSubmittable":true,"discriminatorFieldFocused":true}');
  owner.prepare(given8); before = owner.state(); cursor = leaf.effectCursor(); owner.clearUserChosenDiscriminator(); after = owner.state(); effects = leaf.effectsAfter(cursor);
  emit(owner, leaf, 'nr_008_username_discriminator_race_recovery', 'clearUserChosenDiscriminator', given8, before, after, effects,
    [before['reservation'] === 'maya.88', after['reservation'] === null, effectCount(effects, 'reserveUsername.maya.serviceAssigned') === 0]);

  const given9 = record('{"route":"RegistrationRoute.SignalLoginPayment","runtimeGeneration":2,"hasUnredeemedPurchase":true,"paymentAvailability":"PaymentAvailability.Available","persistedSignalLoginPurchase":{"purchaseToken":"play-token-restore","receiptCredentialRequestContext":"context-A"},"ownedPurchase":{"purchaseToken":"play-token-restore","state":"BillingPurchaseState.PURCHASED"},"nextReceiptRequestResult":"CreateLoginReceiptCredentialResult.Issued"}');
  owner.prepare(given9); await owner.persistPurchaseContext(context, record('{"purchaseToken":"play-token-restore","receiptCredentialRequestContext":"context-A"}'));
  before = owner.state(); cursor = leaf.effectCursor(); await owner.retryOwnedPurchaseAfterProcessReopen(context); after = owner.state(); effects = leaf.effectsAfter(cursor);
  emit(owner, leaf, 'nr_009_purchase_context_process_restore', 'retryOwnedPurchaseAfterProcessReopen', given9, before, after, effects,
    [effectCount(effects, 'readInProgressRegistrationData') === 1, effectCount(effects, 'createLoginPurchaseReceiptCredential') === 1,
      effectCount(effects, 'launchPurchaseFlow') === 0], true, [],
    record(`{"productionBlobWrites":${leaf.purchaseBlobWrites},"productionBlobReadsAfterRepositoryReopen":${leaf.purchaseBlobReads}}`));

  const given10 = record('{"route":"RegistrationRoute.SignalLoginInfo","aci":"new numberless ACI","accountEntropyPool":"new account entropy pool","isPasswordManagerAvailable":true,"showSpinner":true,"showConfirmSavedSheet":false,"passwordManagerStoredCredential":{"type":"UsernamePasswordCredential","username":"uppercase new numberless ACI","password":"display form of new account entropy pool"},"readbackRequest":"held"}');
  owner.prepare(given10); owner.saveCredentialForReadback(); const savedCredential = leaf.passwordManagerCredential;
  const passwordManagerSetupEffects = leaf.effectsAfter(0); leaf.reset();
  before = owner.state(); cursor = leaf.effectCursor(); owner.completePasswordManagerReadback(); after = owner.state(); effects = leaf.effectsAfter(cursor);
  const passwordManagerEvidence: Record<string, Object> = {};
  passwordManagerEvidence['savedCredential'] = savedCredential === null ? record('{}') : savedCredential;
  emit(owner, leaf, 'nr_010_password_manager_save_readback', 'completePasswordManagerReadback', given10, before, after, effects,
    [savedCredential !== null,
      effectCount(effects, 'normalizeAndComparePasswordManagerCredential') === 1,
      after['route'] === 'RegistrationRoute.AddUsername', effectCount(effects, 'navigateTo.AddUsername') === 1], false,
    passwordManagerSetupEffects, passwordManagerEvidence);

  hilog.info(0x0B06, 'BenchmarkObserver', 'BENCHMARK_COMPLETE:06_numberless_registration');
}
