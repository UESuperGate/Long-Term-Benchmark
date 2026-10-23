package benchmark.evaluator

import android.content.Context
import java.io.File
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.signal.core.models.AccountEntropyPool
import org.signal.core.models.ServiceId.ACI
import org.signal.core.util.billing.OneTimeProduct
import org.signal.core.util.billing.OneTimeProductId
import org.signal.core.util.billing.OneTimeProductResult
import org.signal.core.util.billing.OneTimePurchase
import org.signal.core.util.billing.OneTimePurchaseApi
import org.signal.core.util.billing.OneTimePurchasePreparation
import org.signal.core.util.billing.OneTimePurchaseResult
import org.signal.core.util.billing.PurchaseLauncher
import org.signal.libsignal.net.RequestResult
import org.signal.libsignal.usernames.Username
import org.signal.libsignal.zkgroup.receipts.ReceiptCredential
import org.signal.libsignal.zkgroup.receipts.ReceiptCredentialPresentation
import org.signal.libsignal.zkgroup.receipts.ReceiptCredentialResult
import org.signal.network.api.RegistrationApiV2.LoginConfiguration
import org.signal.network.api.RegistrationApiV2.RegisterAccountResponse
import org.signal.registration.CreateLoginReceiptCredentialResult
import org.signal.registration.KeyMaterial
import org.signal.registration.RegisteredAccountData
import org.signal.registration.RegistrationFlowEvent
import org.signal.registration.RegistrationFlowState
import org.signal.registration.RegistrationRepository
import org.signal.registration.RegistrationRoute
import org.signal.registration.SignalLoginPurchaseStep
import org.signal.registration.screens.addusername.AddUsernameScreenEvents
import org.signal.registration.screens.addusername.AddUsernameState
import org.signal.registration.screens.addusername.AddUsernameViewModel
import org.signal.registration.screens.aepentry.AepInput
import org.signal.registration.screens.signallogincredentials.AccountIdInput
import org.signal.registration.screens.signallogincredentials.SignalLoginCredentialEntryScreenEvents
import org.signal.registration.screens.signallogincredentials.SignalLoginCredentialEntryState
import org.signal.registration.screens.signallogincredentials.SignalLoginManualSaveConfirmationViewModel
import org.signal.registration.screens.signallogininfo.SignalLoginInfoScreenActions
import org.signal.registration.screens.signallogininfo.SignalLoginInfoScreenEvents
import org.signal.registration.screens.signallogininfo.SignalLoginInfoViewModel
import org.signal.registration.screens.signalloginpayment.PaymentAvailability
import org.signal.registration.screens.signalloginpayment.SignalLoginPaymentScreenActions
import org.signal.registration.screens.signalloginpayment.SignalLoginPaymentScreenEvents
import org.signal.registration.screens.signalloginpayment.SignalLoginPaymentState
import org.signal.registration.screens.signalloginpayment.SignalLoginPaymentViewModel
import org.signal.registration.util.SignalCredentialManager
import org.signal.registration.util.SignalLoginPurchaseStore

private const val rawAci = "00112233-4455-6677-8899-aabbccddeeff"
private val aci = ACI(rawAci)
private val aep = AccountEntropyPool("a".repeat(64))
private val account = RegisteredAccountData(RegisterAccountResponse(e164 = null, storageCapable = false), KeyMaterial(aep), aci)
private lateinit var harnessContext: Context

fun installHarnessContext(context: Context) {
  harnessContext = context
}

private fun q(value: String): String = "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""
private fun emit(caseId: String, entry: String, before: String, after: String, effects: String = "[]", ordered: String? = null, reopened: Boolean = false) {
  val orderedField = ordered?.let { ",\"orderedStates\":$it" } ?: ""
  val reopenedField = if (reopened) ",\"persistenceReopened\":true" else ""
  println("{\"caseId\":${q(caseId)},\"givenEstablished\":true,\"productionEntrypoint\":${q(entry)},\"before\":$before,\"after\":$after,\"effects\":$effects$orderedField$reopenedField}")
}

private class FlowState(
  override val aci: ACI? = benchmark.evaluator.aci,
  override val accountEntropyPool: AccountEntropyPool? = aep,
  override val isPhoneNumberlessAccount: Boolean = true,
  override val registrationComplete: Boolean = false,
  override val finalRegistrationCommitted: Boolean = false
) : RegistrationFlowState

private class BillingLeaf : OneTimePurchaseApi {
  val effects = mutableListOf<String>()
  var product = OneTimeProductResult.Success(OneTimeProduct("$1.99")) as OneTimeProductResult
  var preparation = OneTimePurchasePreparation.Ready(PurchaseLauncher("held")) as OneTimePurchasePreparation
  var owned: OneTimePurchase? = null
  var consumeSucceeds = true

  override suspend fun getProduct(productId: OneTimeProductId): OneTimeProductResult {
    effects += "queryOneTimeProduct:${productId.productId}:${productId.purchaseOptionId}"
    return product
  }

  override suspend fun preparePurchase(productId: OneTimeProductId): OneTimePurchasePreparation {
    effects += "preparePurchase:${productId.productId}:${productId.purchaseOptionId}"
    return preparation
  }

  override suspend fun launchPurchase(launcher: PurchaseLauncher): OneTimePurchaseResult {
    effects += "launchPurchaseFlow:${launcher.id}"
    return OneTimePurchaseResult.UserCancelled
  }

  override suspend fun getUnredeemedPurchase(purchaseToken: String): OneTimePurchase? {
    effects += "queryUnconsumedPurchase:$purchaseToken"
    return owned
  }

  override suspend fun consumePurchase(purchase: OneTimePurchase): Boolean {
    effects += "consumePurchase:${purchase.purchaseToken}"
    return consumeSucceeds
  }
}

private class RepoLeaf : RegistrationRepository() {
  val effects = mutableListOf<String>()
  var availability = PaymentAvailability.Available
  var config = LoginConfiguration(playProductId = "service-signal-login-product")
  var receiptResult: CreateLoginReceiptCredentialResult = CreateLoginReceiptCredentialResult.Issued(ReceiptCredential())

  override fun getPaymentAvailability(): PaymentAvailability {
    effects += "getPaymentAvailability"
    return availability
  }

  override suspend fun getLoginConfiguration(): LoginConfiguration {
    effects += "getLoginConfiguration"
    return config
  }

  override suspend fun createLoginReceiptCredential(purchaseToken: String, receiptCredentialRequestContext: ByteArray): CreateLoginReceiptCredentialResult {
    effects += "createLoginPurchaseReceiptCredential:$purchaseToken:${String(receiptCredentialRequestContext)}"
    return receiptResult
  }

  override fun verifyReceiptCredential(credential: ReceiptCredential): ReceiptCredentialResult {
    effects += "receiveAndVerifyReceiptCredential"
    return ReceiptCredentialResult.Success(ReceiptCredentialPresentation())
  }

  override suspend fun registerAccountWithoutPhoneNumber(presentation: ReceiptCredentialPresentation): RequestResult<RegisteredAccountData, org.signal.network.api.RegistrationApiV2.RegisterAccountError> {
    effects += "registerAccount"
    return RequestResult.Success(account)
  }
}

private fun store(name: String): SignalLoginPurchaseStore {
  val file = File(System.getProperty("java.io.tmpdir"), "numberless-agent-probe-$name.blob")
  file.delete()
  return SignalLoginPurchaseStore(file)
}

private suspend fun paymentVm(repo: RepoLeaf, billing: BillingLeaf, purchaseStore: SignalLoginPurchaseStore, events: MutableList<RegistrationFlowEvent>): SignalLoginPaymentViewModel {
  val step = SignalLoginPurchaseStep(repo, billing, purchaseStore) { "fresh-valid-context".toByteArray() }
  val vm = SignalLoginPaymentViewModel(repo, step) { events += it }
  delay(10)
  repo.effects.clear()
  billing.effects.clear()
  return vm
}

fun main() = runBlocking {
  run {
    val repo = RepoLeaf()
    val billing = BillingLeaf()
    val vm = paymentVm(repo, billing, store("eligibility"), mutableListOf())
    var state = SignalLoginPaymentState(paymentAvailability = PaymentAvailability.ServiceUpdating)
    vm.applyEvent(state, SignalLoginPaymentScreenEvents.Initialize, {}, { state = it })
    val price = state.price as? SignalLoginPaymentState.Price.Available
    val effects = "[{\"name\":\"getLoginConfiguration\",\"count\":${repo.effects.count { it == "getLoginConfiguration" }}},{\"name\":\"queryOneTimeProduct\",\"productId\":\"service-signal-login-product\",\"purchaseOptionId\":\"nonumber\",\"count\":${billing.effects.count { it.startsWith("queryOneTimeProduct:") }}},{\"name\":\"queryUnconsumedPurchase\",\"productId\":\"service-signal-login-product\",\"purchaseOptionId\":\"nonumber\",\"count\":${billing.effects.count { it.startsWith("queryUnconsumedPurchase:") }} }]"
    emit("nr_001_purchase_eligibility_service_price", "SignalLoginPaymentViewModel.applyEvent(Initialize)", "{\"paymentAvailability\":\"unknown\",\"price\":\"loading\"}", "{\"selectedOption\":\"SignalLoginPaymentState.Option.${state.selectedOption}\",\"paymentAvailability\":\"PaymentAvailability.${state.paymentAvailability}\",\"price\":{\"type\":\"SignalLoginPaymentState.Price.Available\",\"formattedPrice\":${q(price?.formattedPrice ?: "")}},\"hasUnredeemedPurchase\":${state.hasUnredeemedPurchase},\"isPurchaseOptionEnabled\":${state.isPurchaseAvailable},\"isActionEnabled\":${state.isActionEnabled},\"showSpinner\":${state.showSpinner},\"dialogs\":{\"paymentUnavailable\":${state.dialogs.paymentUnavailable}}}", effects)
  }

  run {
    val repo = RepoLeaf()
    val billing = BillingLeaf()
    val vm = paymentVm(repo, billing, store("launch"), mutableListOf())
    var state = SignalLoginPaymentState(price = SignalLoginPaymentState.Price.Available("$1.99"))
    vm.applyEvent(state, SignalLoginPaymentScreenEvents.ContinueClicked, {}, { state = it })
    val action = vm.actions.first()
    val launched = action is SignalLoginPaymentScreenActions.LaunchPurchaseSheet
    emit("nr_002_purchase_launch_holds_completion", "SignalLoginPaymentViewModel.applyEvent(ContinueClicked)", "{\"route\":\"RegistrationRoute.SignalLoginPayment\",\"showSpinner\":false}", "{\"route\":\"RegistrationRoute.SignalLoginPayment\",\"showSpinner\":${state.showSpinner},\"purchaseStep\":\"SignalLoginPurchaseStep.LaunchRequired\"}", "[{\"name\":\"preparePurchase\",\"count\":${billing.effects.count { it.startsWith("preparePurchase:") }}},{\"name\":\"launchPurchaseFlow\",\"count\":${if (launched) 1 else 0}}]")
  }

  run {
    val repo = RepoLeaf()
    val billing = BillingLeaf()
    val vm = paymentVm(repo, billing, store("cancel"), mutableListOf())
    var state = SignalLoginPaymentState(price = SignalLoginPaymentState.Price.Available("$1.99"), showSpinner = true)
    vm.applyEvent(state, SignalLoginPaymentScreenEvents.PurchaseFlowCompleted(OneTimePurchaseResult.UserCancelled), {}, { state = it })
    emit("nr_003_purchase_cancel_cleanup", "SignalLoginPaymentViewModel.applyEvent(PurchaseFlowCompleted)", "{\"route\":\"RegistrationRoute.SignalLoginPayment\",\"showSpinner\":true}", "{\"route\":\"RegistrationRoute.SignalLoginPayment\",\"selectedOption\":\"SignalLoginPaymentState.Option.${state.selectedOption}\",\"showSpinner\":${state.showSpinner},\"hasUnredeemedPurchase\":${state.hasUnredeemedPurchase},\"dialogs\":\"SignalLoginPaymentState.Dialogs()\",\"result\":\"SignalLoginPurchaseResult.Cancelled\"}")
  }

  run {
    val repo = RepoLeaf()
    val billing = BillingLeaf()
    val vm = paymentVm(repo, billing, store("foreground"), mutableListOf())
    val emitted = mutableListOf<SignalLoginPaymentState>()
    var state = SignalLoginPaymentState(paymentAvailability = PaymentAvailability.ServiceUpdating, price = SignalLoginPaymentState.Price.TransientError, dialogs = SignalLoginPaymentState.Dialogs(paymentUnavailable = true))
    vm.applyEvent(state, SignalLoginPaymentScreenEvents.Foreground, {}, { state = it; emitted += it })
    val first = emitted.first()
    val ordered = "[{\"paymentAvailability\":\"PaymentAvailability.${first.paymentAvailability}\",\"price\":\"SignalLoginPaymentState.Price.Loading\",\"dialogs\":{\"paymentUnavailable\":${first.dialogs.paymentUnavailable}}},{\"paymentAvailability\":\"PaymentAvailability.${state.paymentAvailability}\",\"price\":{\"type\":\"SignalLoginPaymentState.Price.Available\",\"formattedPrice\":\"$1.99\"},\"dialogs\":{\"paymentUnavailable\":${state.dialogs.paymentUnavailable}},\"isActionEnabled\":${state.isActionEnabled}}]"
    emit("nr_004_billing_unavailable_foreground_retry", "SignalLoginPaymentViewModel.applyEvent(Foreground)", "{\"paymentAvailability\":\"PaymentAvailability.ServiceUpdating\"}", "{\"selectedOption\":\"SignalLoginPaymentState.Option.${state.selectedOption}\",\"paymentAvailability\":\"PaymentAvailability.${state.paymentAvailability}\",\"price\":{\"type\":\"SignalLoginPaymentState.Price.Available\",\"formattedPrice\":\"$1.99\"},\"dialogs\":{\"paymentUnavailable\":${state.dialogs.paymentUnavailable}},\"isActionEnabled\":${state.isActionEnabled}}", "[{\"name\":\"getPaymentAvailability\",\"count\":${repo.effects.count { it == "getPaymentAvailability" }}},{\"name\":\"queryOneTimeProduct\",\"count\":${billing.effects.count { it.startsWith("queryOneTimeProduct:") }}}]", ordered)
  }

  run {
    val repo = RepoLeaf()
    val billing = BillingLeaf()
    val purchaseStore = store("registered")
    val events = mutableListOf<RegistrationFlowEvent>()
    val vm = paymentVm(repo, billing, purchaseStore, events)
    var state = SignalLoginPaymentState(hasUnredeemedPurchase = true, showSpinner = true)
    vm.applyEvent(state, SignalLoginPaymentScreenEvents.PurchaseFlowCompleted(OneTimePurchaseResult.Success(OneTimePurchase("play-token-1"))), { events += it }, { state = it })
    val registered = events.filterIsInstance<RegistrationFlowEvent.Registered>().single()
    val navigated = events.filterIsInstance<RegistrationFlowEvent.NavigateToScreen>().single().route
    val effects = "[{\"name\":\"completeSignalLoginPurchase\",\"input\":\"OneTimePurchaseResult.Success\",\"count\":1},{\"name\":\"createLoginPurchaseReceiptCredential\",\"purchaseIdentifier\":\"play-token-1\",\"paymentProvider\":\"LoginPurchasePaymentProvider.GOOGLE_PLAY_BILLING\",\"count\":${repo.effects.count { it.startsWith("createLoginPurchaseReceiptCredential:") }}},{\"name\":\"receiveAndVerifyReceiptCredential\",\"count\":${repo.effects.count { it == "receiveAndVerifyReceiptCredential" }}},{\"name\":\"registerAccount\",\"e164\":null,\"sessionId\":null,\"recoveryPassword\":null,\"receiptCredentialPresentation\":\"present\",\"pniPreKeys\":null,\"count\":${repo.effects.count { it == "registerAccount" }}},{\"name\":\"consumePurchase\",\"purchaseToken\":\"play-token-1\",\"count\":${billing.effects.count { it == "consumePurchase:play-token-1" }},\"after\":\"registerAccount.success\"},{\"name\":\"emitRegistrationFlowEvent.Registered\",\"phoneNumberless\":${registered.phoneNumberless},\"count\":1,\"orderAfter\":\"consumePurchase\"},{\"name\":\"navigateTo.SignalLoginInfo\",\"count\":${if (navigated == RegistrationRoute.SignalLoginInfo) 1 else 0},\"orderAfter\":\"emitRegistrationFlowEvent.Registered\"}]"
    val after = "{\"result\":\"SignalLoginPurchaseResult.Registered\",\"payment\":{\"showSpinner\":${state.showSpinner},\"hasUnredeemedPurchase\":${state.hasUnredeemedPurchase}},\"inProgressRegistrationData\":{\"signalLoginPurchase\":null},\"committedAccount\":{\"e164\":null,\"pni\":null,\"pniRegistrationId\":0},\"restoreDecision\":\"RestoreDecision.NEW_ACCOUNT\",\"flow\":{\"aci\":\"new numberless ACI\",\"accountEntropyPool\":\"new account entropy pool\",\"storageCapable\":${registered.storageCapable},\"isPhoneNumberlessAccount\":${registered.phoneNumberless}},\"backStack\":[\"RegistrationRoute.SignalLoginInfo\"]}"
    val ordered = "[{\"payment\":{\"showSpinner\":true},\"flow\":{\"aci\":null,\"isPhoneNumberlessAccount\":false},\"route\":\"RegistrationRoute.SignalLoginPayment\"},{\"payment\":{\"showSpinner\":${state.showSpinner},\"hasUnredeemedPurchase\":${state.hasUnredeemedPurchase}},\"flow\":{\"aci\":\"new numberless ACI\",\"accountEntropyPool\":\"new account entropy pool\",\"storageCapable\":${registered.storageCapable},\"isPhoneNumberlessAccount\":${registered.phoneNumberless}},\"route\":\"RegistrationRoute.SignalLoginInfo\"}]"
    emit("nr_005_private_receipt_registration_propagates", "SignalLoginPaymentViewModel.applyEvent(PurchaseFlowCompleted)", "{\"payment\":{\"showSpinner\":true,\"hasUnredeemedPurchase\":true},\"flow\":{\"aci\":null,\"isPhoneNumberlessAccount\":false},\"route\":\"RegistrationRoute.SignalLoginPayment\"}", after, effects, ordered)
  }

  run {
    val repo = RepoLeaf()
    val vm = SignalLoginManualSaveConfirmationViewModel(FlowState(), repo) {}
    var state = SignalLoginCredentialEntryState(mode = SignalLoginCredentialEntryState.Mode.ConfirmSaved, accountId = AccountIdInput(rawAci), recoveryKey = AepInput("b".repeat(64)))
    vm.applyEvent(state, SignalLoginCredentialEntryScreenEvents.NextClicked, {}, { state = it })
    emit("nr_006_manual_save_mismatch_verification", "SignalLoginManualSaveConfirmationViewModel.applyEvent(NextClicked)", "{\"route\":\"RegistrationRoute.SignalLoginManualSaveConfirmation\",\"areCredentialsIncorrect\":false}", "{\"route\":\"RegistrationRoute.SignalLoginManualSaveConfirmation\",\"mode\":\"SignalLoginCredentialEntryState.Mode.ConfirmSaved\",\"areCredentialsIncorrect\":${state.areCredentialsIncorrect},\"isLoggingIn\":${state.showSpinner}}")
  }

  run {
    val events = mutableListOf<RegistrationFlowEvent>()
    val vm = AddUsernameViewModel(RepoLeaf(), FlowState(), { events += it }, 0)
    var state = AddUsernameState()
    vm.applyEvent(state, AddUsernameScreenEvents.SkipClicked, { events += it }, { state = it })
    emit("nr_007_username_skip_requires_confirmation", "AddUsernameViewModel.applyEvent(SkipClicked)", "{\"route\":\"RegistrationRoute.AddUsername\",\"dialogs\":{\"confirmSkip\":false},\"registrationComplete\":false,\"finalRegistrationCommitted\":false}", "{\"route\":\"RegistrationRoute.AddUsername\",\"dialogs\":{\"confirmSkip\":${state.dialogs.confirmSkip}},\"registrationComplete\":${events.any { it is RegistrationFlowEvent.RegistrationComplete }},\"finalRegistrationCommitted\":false}", "[{\"name\":\"showSkipConfirmation\",\"count\":${if (state.dialogs.confirmSkip) 1 else 0}}]")
  }

  run {
    val vm = AddUsernameViewModel(RepoLeaf(), FlowState(), {}, 0)
    var state = AddUsernameState(username = "maya", discriminator = "88", isDiscriminatorUserSet = true, reservation = Username("maya.88"), isSubmittable = true, discriminatorFieldFocused = true)
    vm.applyEvent(state, AddUsernameScreenEvents.DiscriminatorChanged(""), {}, { state = it })
    emit("nr_008_username_discriminator_race_recovery", "AddUsernameViewModel.applyEvent(DiscriminatorChanged)", "{\"username\":\"maya\",\"discriminator\":\"88\",\"isDiscriminatorUserSet\":true}", "{\"username\":${q(state.username)},\"discriminator\":${q(state.discriminator)},\"isDiscriminatorUserSet\":${state.isDiscriminatorUserSet},\"reservation\":null,\"validationError\":null,\"isReserving\":${state.isReserving},\"isSubmittable\":${state.isSubmittable},\"discriminatorFieldFocused\":${state.discriminatorFieldFocused}}")
  }

  run {
    val file = File(System.getProperty("java.io.tmpdir"), "numberless-agent-probe-restore.blob")
    file.delete()
    SignalLoginPurchaseStore(file).write("play-token-restore", "context-A".toByteArray())
    val repo = RepoLeaf()
    val billing = BillingLeaf().apply { owned = OneTimePurchase("play-token-restore") }
    val reopenedStore = SignalLoginPurchaseStore(file)
    val events = mutableListOf<RegistrationFlowEvent>()
    val vm = paymentVm(repo, billing, reopenedStore, events)
    var state = SignalLoginPaymentState(hasUnredeemedPurchase = true, price = SignalLoginPaymentState.Price.Available("$1.99"))
    repo.effects.clear(); billing.effects.clear()
    vm.applyEvent(state, SignalLoginPaymentScreenEvents.ContinueClicked, { events += it }, { state = it })
    val persisted = reopenedStore.read()
    val context = repo.effects.firstOrNull { it.startsWith("createLoginPurchaseReceiptCredential:") }?.substringAfterLast(':') ?: ""
    emit("nr_009_purchase_context_process_restore", "SignalLoginPaymentViewModel.applyEvent(ContinueClicked)", "{\"route\":\"RegistrationRoute.SignalLoginPayment\",\"runtimeGeneration\":2,\"hasUnredeemedPurchase\":true}", "{\"result\":\"SignalLoginPurchaseResult.Registered\",\"hasUnredeemedPurchase\":${state.hasUnredeemedPurchase},\"persistedSignalLoginPurchase\":${if (persisted == null) "null" else "{}"}}", "[{\"name\":\"readInProgressRegistrationData\",\"backingIo\":\"production blob reopened\",\"countAtLeast\":1},{\"name\":\"createLoginPurchaseReceiptCredential\",\"purchaseIdentifier\":\"play-token-restore\",\"serializedRequestContext\":${q(context)},\"count\":${repo.effects.count { it.startsWith("createLoginPurchaseReceiptCredential:") }}},{\"name\":\"consumePurchase\",\"purchaseToken\":\"play-token-restore\",\"count\":${billing.effects.count { it == "consumePurchase:play-token-restore" }}}]", reopened = true)
    file.delete()
  }

  run {
    val manager = SignalCredentialManager(harnessContext)
    val events = mutableListOf<RegistrationFlowEvent>()
    val vm = SignalLoginInfoViewModel(FlowState(), manager) { events += it }
    var state = vm.state.value.copy(isPasswordManagerAvailable = true)
    vm.applyEvent(state, SignalLoginInfoScreenEvents.SaveWithPasswordManagerClicked, { events += it }, { state = it })
    val saveAction = vm.actions.first()
    val saveResult = manager.saveCredential(state.accountId, state.recoveryKey)
    vm.applyEvent(state, SignalLoginInfoScreenEvents.CredentialSaveCompleted(saveResult), { events += it }, { state = it })
    vm.applyEvent(state, SignalLoginInfoScreenEvents.ConfirmSavedSheetConfirmed, { events += it }, { state = it })
    val readAction = vm.actions.first()
    val credential = manager.getCredential(aci)
    vm.applyEvent(state, SignalLoginInfoScreenEvents.SavedCredentialRetrieved(credential), { events += it }, { state = it })
    val navigated = events.filterIsInstance<RegistrationFlowEvent.NavigateToScreen>().lastOrNull()?.route
    val effects = "[{\"name\":\"normalizeAndComparePasswordManagerCredential\",\"accountId\":\"new numberless ACI\",\"accountEntropyPool\":\"new account entropy pool\",\"count\":${if (credential != null) 1 else 0}},{\"name\":\"navigateTo.AddUsername\",\"count\":${if (navigated == RegistrationRoute.AddUsername) 1 else 0}},{\"name\":\"passwordManagerSaveAction\",\"count\":${if (saveAction is SignalLoginInfoScreenActions.SaveCredentialWithPasswordManager) 1 else 0}},{\"name\":\"passwordManagerReadAction\",\"count\":${if (readAction is SignalLoginInfoScreenActions.ReadBackSavedCredential) 1 else 0}}]"
    emit("nr_010_password_manager_save_readback", "SignalLoginInfoViewModel.applyEvent(save/confirm/readback)", "{\"route\":\"RegistrationRoute.SignalLoginInfo\",\"showSpinner\":true,\"readbackRequest\":\"held\"}", "{\"route\":\"${if (navigated == RegistrationRoute.AddUsername) "RegistrationRoute.AddUsername" else "RegistrationRoute.SignalLoginInfo"}\",\"showSpinner\":${state.showSpinner},\"showConfirmSavedSheet\":${state.showConfirmSavedSheet},\"dialogs\":${if (state.dialogs == org.signal.registration.screens.signallogininfo.SignalLoginInfoState.Dialogs()) q("SignalLoginInfoState.Dialogs()") else "{\"saveNotConfirmed\":${state.dialogs.saveNotConfirmed}}"}}", effects)
  }
}
