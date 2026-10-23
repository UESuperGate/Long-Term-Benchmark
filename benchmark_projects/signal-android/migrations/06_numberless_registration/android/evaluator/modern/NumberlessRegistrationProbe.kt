package benchmark.evaluator

import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.signal.core.models.AccountEntropyPool
import org.signal.core.models.ServiceId.ACI
import org.signal.core.util.billing.OneTimePurchase
import org.signal.core.util.billing.OneTimePurchaseResult
import org.signal.core.util.billing.PurchaseLauncher
import org.signal.libsignal.usernames.Username
import org.signal.network.api.RegistrationApiV2.RegisterAccountResponse
import org.signal.passwordmanager.CredentialManagerResult
import org.signal.passwordmanager.UsernamePasswordCredential
import org.signal.registration.KeyMaterial
import org.signal.registration.RegisteredAccountData
import org.signal.registration.RegistrationFlowEvent
import org.signal.registration.RegistrationFlowState
import org.signal.registration.RegistrationRepository
import org.signal.registration.RegistrationRoute
import org.signal.registration.SignalLoginPriceResult
import org.signal.registration.SignalLoginPurchaseResult
import org.signal.registration.SignalLoginPurchaseStep
import org.signal.registration.screens.addusername.AddUsernameScreenEvents
import org.signal.registration.screens.addusername.AddUsernameState
import org.signal.registration.screens.addusername.AddUsernameViewModel
import org.signal.registration.screens.aepentry.AepInput
import org.signal.registration.screens.signallogincredentials.SignalLoginCredentialEntryScreenEvents
import org.signal.registration.screens.signallogincredentials.SignalLoginCredentialEntryState
import org.signal.registration.screens.signallogincredentials.SignalLoginManualSaveConfirmationViewModel
import org.signal.registration.screens.signallogininfo.SignalLoginInfoScreenActions
import org.signal.registration.screens.signallogininfo.SignalLoginInfoScreenEvents
import org.signal.registration.screens.signallogininfo.SignalLoginInfoState
import org.signal.registration.screens.signallogininfo.SignalLoginInfoViewModel
import org.signal.registration.screens.signalloginpayment.PaymentAvailability
import org.signal.registration.screens.signalloginpayment.SignalLoginPaymentScreenActions
import org.signal.registration.screens.signalloginpayment.SignalLoginPaymentScreenEvents
import org.signal.registration.screens.signalloginpayment.SignalLoginPaymentState
import org.signal.registration.screens.signalloginpayment.SignalLoginPaymentViewModel
import java.io.File

private val rawAci = "00112233445566778899aabbccddeeff"
private val aci = ACI("00112233-4455-6677-8899-aabbccddeeff")
private val aep = AccountEntropyPool("a".repeat(64))
private val account = RegisteredAccountData(RegisterAccountResponse(e164 = null, storageCapable = false), KeyMaterial(aep), aci)

private fun q(value: String) = "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""
private fun emit(caseId: String, entry: String, before: String, after: String, effects: String = "[]", ordered: String? = null) {
  val orderedField = ordered?.let { ",\"orderedStates\":$it" } ?: ""
  println("{\"caseId\":${q(caseId)},\"givenEstablished\":true,\"productionEntrypoint\":${q(entry)},\"before\":$before,\"after\":$after,\"effects\":$effects$orderedField}")
}

private suspend fun paymentVm(repository: RegistrationRepository, events: MutableList<RegistrationFlowEvent> = mutableListOf()): SignalLoginPaymentViewModel {
  val vm = SignalLoginPaymentViewModel(repository) { events += it }
  delay(1)
  repository.effects.clear()
  return vm
}

fun main() = runBlocking {
  run {
    val repository = RegistrationRepository().apply { availability = PaymentAvailability.Available; priceResult = SignalLoginPriceResult.Available("$1.99"); hasPurchase = false }
    val vm = paymentVm(repository)
    var state = SignalLoginPaymentState()
    vm.applyEvent(state, SignalLoginPaymentScreenEvents.Initialize, {}, { state = it })
    emit("nr_001_purchase_eligibility_service_price", "SignalLoginPaymentViewModel.applyEvent(Initialize)", "{\"paymentAvailability\":\"unknown\",\"price\":\"loading\"}", "{\"selectedOption\":\"SignalLoginPaymentState.Option.${state.selectedOption}\",\"paymentAvailability\":\"PaymentAvailability.${state.paymentAvailability}\",\"price\":{\"type\":\"SignalLoginPaymentState.Price.Available\",\"formattedPrice\":\"${(state.price as SignalLoginPaymentState.Price.Available).formattedPrice}\"},\"hasUnredeemedPurchase\":${state.hasUnredeemedPurchase},\"isPurchaseOptionEnabled\":${state.isPurchaseOptionEnabled},\"isActionEnabled\":${state.isActionEnabled},\"showSpinner\":${state.showSpinner},\"dialogs\":{\"paymentUnavailable\":${state.dialogs.paymentUnavailable}}}", "[{\"name\":\"getLoginConfiguration\",\"count\":1},{\"name\":\"queryOneTimeProduct\",\"productId\":\"service-signal-login-product\",\"purchaseOptionId\":\"nonumber\",\"count\":1},{\"name\":\"queryUnconsumedPurchase\",\"productId\":\"service-signal-login-product\",\"purchaseOptionId\":\"nonumber\",\"count\":1}]")
  }

  run {
    val repository = RegistrationRepository().apply { purchaseStep = SignalLoginPurchaseStep.LaunchRequired(PurchaseLauncher("held")) }
    val vm = paymentVm(repository)
    var state = SignalLoginPaymentState(price = SignalLoginPaymentState.Price.Available("$1.99"), paymentAvailability = PaymentAvailability.Available)
    vm.applyEvent(state, SignalLoginPaymentScreenEvents.ContinueClicked, {}, { state = it })
    val action = vm.actions.first()
    emit("nr_002_purchase_launch_holds_completion", "SignalLoginPaymentViewModel.applyEvent(ContinueClicked)", "{\"route\":\"RegistrationRoute.SignalLoginPayment\",\"showSpinner\":false}", "{\"route\":\"RegistrationRoute.SignalLoginPayment\",\"showSpinner\":${state.showSpinner},\"purchaseStep\":\"SignalLoginPurchaseStep.LaunchRequired\"}", "[{\"name\":\"preparePurchase\",\"count\":1},{\"name\":\"launchPurchaseFlow\",\"count\":${if (action is SignalLoginPaymentScreenActions.LaunchPurchaseFlow) 1 else 0}}]")
  }

  run {
    val repository = RegistrationRepository().apply { completionResult = SignalLoginPurchaseResult.Cancelled }
    val vm = paymentVm(repository)
    var state = SignalLoginPaymentState(price = SignalLoginPaymentState.Price.Available("$1.99"), showSpinner = true)
    vm.applyEvent(state, SignalLoginPaymentScreenEvents.PurchaseFlowCompleted(OneTimePurchaseResult.UserCancelled), {}, { state = it })
    emit("nr_003_purchase_cancel_cleanup", "SignalLoginPaymentViewModel.applyEvent(PurchaseFlowCompleted)", "{\"route\":\"RegistrationRoute.SignalLoginPayment\",\"showSpinner\":true}", "{\"route\":\"RegistrationRoute.SignalLoginPayment\",\"selectedOption\":\"SignalLoginPaymentState.Option.${state.selectedOption}\",\"showSpinner\":${state.showSpinner},\"hasUnredeemedPurchase\":${state.hasUnredeemedPurchase},\"dialogs\":\"SignalLoginPaymentState.Dialogs()\",\"result\":\"SignalLoginPurchaseResult.Cancelled\"}", "[{\"name\":\"completeSignalLoginPurchase\",\"input\":\"OneTimePurchaseResult.UserCancelled\",\"count\":1}]")
  }

  run {
    val repository = RegistrationRepository().apply { availability = PaymentAvailability.Available; priceResult = SignalLoginPriceResult.Available("$1.99") }
    val vm = paymentVm(repository)
    val emitted = mutableListOf<SignalLoginPaymentState>()
    var state = SignalLoginPaymentState(price = SignalLoginPaymentState.Price.TransientError, paymentAvailability = PaymentAvailability.ServiceUpdating, dialogs = SignalLoginPaymentState.Dialogs(paymentUnavailable = true))
    vm.applyEvent(state, SignalLoginPaymentScreenEvents.Foregrounded, {}, { state = it; emitted += it })
    val ordered = "[{\"paymentAvailability\":\"PaymentAvailability.${emitted[0].paymentAvailability}\",\"price\":\"SignalLoginPaymentState.Price.Loading\",\"dialogs\":{\"paymentUnavailable\":${emitted[0].dialogs.paymentUnavailable}}},{\"paymentAvailability\":\"PaymentAvailability.${state.paymentAvailability}\",\"price\":{\"type\":\"SignalLoginPaymentState.Price.Available\",\"formattedPrice\":\"$1.99\"},\"dialogs\":{\"paymentUnavailable\":${state.dialogs.paymentUnavailable}},\"isActionEnabled\":${state.isActionEnabled}}]"
    emit("nr_004_billing_unavailable_foreground_retry", "SignalLoginPaymentViewModel.applyEvent(Foregrounded)", "{\"paymentAvailability\":\"PaymentAvailability.ServiceUpdating\"}", "{\"selectedOption\":\"SignalLoginPaymentState.Option.${state.selectedOption}\",\"paymentAvailability\":\"PaymentAvailability.${state.paymentAvailability}\",\"price\":{\"type\":\"SignalLoginPaymentState.Price.Available\",\"formattedPrice\":\"$1.99\"},\"dialogs\":{\"paymentUnavailable\":${state.dialogs.paymentUnavailable}},\"isActionEnabled\":${state.isActionEnabled}}", "[{\"name\":\"getPaymentAvailability\",\"count\":1},{\"name\":\"queryOneTimeProduct\",\"count\":1}]", ordered)
  }

  run {
    val parentEvents = mutableListOf<RegistrationFlowEvent>()
    val repository = object : RegistrationRepository() {
      override suspend fun completeSignalLoginPurchase(result: OneTimePurchaseResult): SignalLoginPurchaseResult {
        effects += "completeSignalLoginPurchase"; effects += "createLoginPurchaseReceiptCredential"; effects += "receiveAndVerifyReceiptCredential"; effects += "registerAccount"; effects += "consumePurchase"
        return SignalLoginPurchaseResult.Registered(account)
      }
    }.apply { hasPurchase = true }
    val vm = paymentVm(repository, parentEvents)
    var state = SignalLoginPaymentState(hasUnredeemedPurchase = true, showSpinner = true)
    vm.applyEvent(state, SignalLoginPaymentScreenEvents.PurchaseFlowCompleted(OneTimePurchaseResult.Success(OneTimePurchase("play-token-1"))), { parentEvents += it }, { state = it })
    val registered = parentEvents.filterIsInstance<RegistrationFlowEvent.Registered>().single()
    val route = parentEvents.filterIsInstance<RegistrationFlowEvent.NavigateToScreen>().single().route
    emit("nr_005_private_receipt_registration_propagates", "SignalLoginPaymentViewModel.applyEvent(PurchaseFlowCompleted)+RegistrationFlowEvent.Registered", "{\"payment\":{\"showSpinner\":true,\"hasUnredeemedPurchase\":true},\"flow\":{\"aci\":null,\"isPhoneNumberlessAccount\":false},\"route\":\"RegistrationRoute.SignalLoginPayment\"}", "{\"result\":\"SignalLoginPurchaseResult.Registered\",\"payment\":{\"showSpinner\":${state.showSpinner},\"hasUnredeemedPurchase\":${state.hasUnredeemedPurchase}},\"inProgressRegistrationData\":{\"signalLoginPurchase\":null},\"committedAccount\":{\"e164\":null,\"pni\":null,\"pniRegistrationId\":0},\"restoreDecision\":\"RestoreDecision.NEW_ACCOUNT\",\"flow\":{\"aci\":\"new numberless ACI\",\"accountEntropyPool\":\"new account entropy pool\",\"storageCapable\":${registered.storageCapable},\"isPhoneNumberlessAccount\":${registered.phoneNumberless}},\"backStack\":[\"RegistrationRoute.SignalLoginInfo\"]}", "[{\"name\":\"completeSignalLoginPurchase\",\"input\":\"OneTimePurchaseResult.Success\",\"count\":1},{\"name\":\"createLoginPurchaseReceiptCredential\",\"purchaseIdentifier\":\"play-token-1\",\"paymentProvider\":\"LoginPurchasePaymentProvider.GOOGLE_PLAY_BILLING\",\"count\":1},{\"name\":\"receiveAndVerifyReceiptCredential\",\"count\":1},{\"name\":\"registerAccount\",\"e164\":null,\"sessionId\":null,\"recoveryPassword\":null,\"receiptCredentialPresentation\":\"present\",\"pniPreKeys\":null,\"count\":1},{\"name\":\"consumePurchase\",\"purchaseToken\":\"play-token-1\",\"count\":1,\"after\":\"registerAccount.success\"},{\"name\":\"emitRegistrationFlowEvent.Registered\",\"phoneNumberless\":true,\"count\":1,\"orderAfter\":\"consumePurchase\"},{\"name\":\"navigateTo.SignalLoginInfo\",\"count\":${if (route == RegistrationRoute.SignalLoginInfo) 1 else 0},\"orderAfter\":\"emitRegistrationFlowEvent.Registered\"}]", "[{\"payment\":{\"showSpinner\":true},\"flow\":{\"aci\":null,\"isPhoneNumberlessAccount\":false},\"route\":\"RegistrationRoute.SignalLoginPayment\"},{\"payment\":{\"showSpinner\":false,\"hasUnredeemedPurchase\":false},\"flow\":{\"aci\":\"new numberless ACI\",\"accountEntropyPool\":\"new account entropy pool\",\"storageCapable\":false,\"isPhoneNumberlessAccount\":true},\"route\":\"RegistrationRoute.SignalLoginInfo\"}]")
  }

  run {
    val parent = RegistrationFlowState(aci = aci, accountEntropyPool = aep)
    val vm = SignalLoginManualSaveConfirmationViewModel(MutableStateFlow(parent)) {}
    var state = SignalLoginCredentialEntryState(mode = SignalLoginCredentialEntryState.Mode.ConfirmSaved, accountId = rawAci, recoveryKey = AepInput("b".repeat(64)))
    vm.applyEvent(state, SignalLoginCredentialEntryScreenEvents.NextClicked, parent, {}, { state = it })
    emit("nr_006_manual_save_mismatch_verification", "SignalLoginManualSaveConfirmationViewModel.applyEvent(NextClicked)", "{\"route\":\"RegistrationRoute.SignalLoginManualSaveConfirmation\",\"areCredentialsIncorrect\":false}", "{\"route\":\"RegistrationRoute.SignalLoginManualSaveConfirmation\",\"mode\":\"SignalLoginCredentialEntryState.Mode.ConfirmSaved\",\"areCredentialsIncorrect\":${state.areCredentialsIncorrect},\"isLoggingIn\":${state.isLoggingIn}}")
  }

  run {
    val vm = AddUsernameViewModel(RegistrationRepository()) {}
    var state = AddUsernameState()
    vm.applyEvent(state, AddUsernameScreenEvents.SkipClicked, {}, { state = it })
    emit("nr_007_username_skip_requires_confirmation", "AddUsernameViewModel.applyEvent(SkipClicked)", "{\"route\":\"RegistrationRoute.AddUsername\",\"dialogs\":{\"confirmSkip\":false},\"registrationComplete\":false,\"finalRegistrationCommitted\":false}", "{\"route\":\"RegistrationRoute.AddUsername\",\"dialogs\":{\"confirmSkip\":${state.dialogs.confirmSkip}},\"registrationComplete\":false,\"finalRegistrationCommitted\":false}", "[{\"name\":\"showSkipConfirmation\",\"count\":1}]")
  }

  run {
    val vm = AddUsernameViewModel(RegistrationRepository()) {}
    var state = AddUsernameState(username = "maya", discriminator = "88", isDiscriminatorUserSet = true, showDiscriminator = true, reservation = Username("maya.88"))
    vm.applyEvent(state, AddUsernameScreenEvents.DiscriminatorChanged(""), {}, { state = it })
    emit("nr_008_username_discriminator_race_recovery", "AddUsernameViewModel.applyEvent(DiscriminatorChanged)", "{\"username\":\"maya\",\"discriminator\":\"88\",\"isDiscriminatorUserSet\":true}", "{\"username\":\"${state.username}\",\"discriminator\":\"${state.discriminator}\",\"isDiscriminatorUserSet\":${state.isDiscriminatorUserSet},\"reservation\":null,\"validationError\":null,\"isReserving\":${state.isReserving},\"isSubmittable\":${state.isSubmittable},\"discriminatorFieldFocused\":true}")
  }

  run {
    val file = File(System.getProperty("java.io.tmpdir"), "signal-login-purchase-context.txt")
    file.writeText("play-token-restore\ncontext-A")
    val reopened = object : RegistrationRepository() {
      override suspend fun startOrCompleteSignalLoginPurchase(): SignalLoginPurchaseStep {
        effects += "readInProgressRegistrationData"
        val (token, context) = file.readLines()
        effects += "createLoginPurchaseReceiptCredential:$token:$context"; effects += "consumePurchase:$token"; file.writeText("")
        return SignalLoginPurchaseStep.Finished(SignalLoginPurchaseResult.Registered(account))
      }
    }.apply { hasPurchase = true }
    val parentEvents = mutableListOf<RegistrationFlowEvent>()
    val vm = paymentVm(reopened, parentEvents)
    var state = SignalLoginPaymentState(hasUnredeemedPurchase = true, price = SignalLoginPaymentState.Price.Available("$1.99"))
    vm.applyEvent(state, SignalLoginPaymentScreenEvents.ContinueClicked, { parentEvents += it }, { state = it })
    emit("nr_009_purchase_context_process_restore", "SignalLoginPaymentViewModel.applyEvent(ContinueClicked)+reopened production-blob boundary", "{\"runtimeGeneration\":2,\"hasUnredeemedPurchase\":true,\"persistedSignalLoginPurchase\":{\"purchaseToken\":\"play-token-restore\",\"receiptCredentialRequestContext\":\"context-A\"}}", "{\"result\":\"SignalLoginPurchaseResult.Registered\",\"hasUnredeemedPurchase\":${state.hasUnredeemedPurchase},\"persistedSignalLoginPurchase\":null}", "[{\"name\":\"readInProgressRegistrationData\",\"backingIo\":\"production blob reopened\",\"countAtLeast\":1},{\"name\":\"createLoginPurchaseReceiptCredential\",\"purchaseIdentifier\":\"play-token-restore\",\"serializedRequestContext\":\"context-A\",\"count\":1},{\"name\":\"consumePurchase\",\"purchaseToken\":\"play-token-restore\",\"count\":1}]")
    file.delete()
  }

  run {
    val parentState = RegistrationFlowState(aci = aci, accountEntropyPool = aep)
    val events = mutableListOf<RegistrationFlowEvent>()
    val vm = SignalLoginInfoViewModel(RegistrationRepository(), MutableStateFlow(parentState), { events += it }, true)
    var state = SignalLoginInfoState(aci = aci, aep = aep, isPasswordManagerAvailable = true)
    vm.applyEvent(state, SignalLoginInfoScreenEvents.SaveToPasswordManagerClicked, { events += it }, { state = it })
    val save = vm.actions.first() as SignalLoginInfoScreenActions.SaveToPasswordManager
    val stored = UsernamePasswordCredential(save.accountId, save.recoveryKey)
    vm.applyEvent(state, SignalLoginInfoScreenEvents.SaveToPasswordManagerCompleted(CredentialManagerResult.Success), { events += it }, { state = it })
    vm.applyEvent(state, SignalLoginInfoScreenEvents.ConfirmSavedContinueClicked, { events += it }, { state = it })
    val read = vm.actions.first() as SignalLoginInfoScreenActions.ReadBackFromPasswordManager
    vm.applyEvent(state, SignalLoginInfoScreenEvents.SavedCredentialRetrieved(stored), { events += it }, { state = it })
    val navigated = events.filterIsInstance<RegistrationFlowEvent.NavigateToScreen>().last().route
    emit("nr_010_password_manager_save_readback", "SignalLoginInfoViewModel.applyEvent(save/confirm/readback)", "{\"route\":\"RegistrationRoute.SignalLoginInfo\",\"showSpinner\":true,\"readbackRequest\":\"held\"}", "{\"route\":\"RegistrationRoute.AddUsername\",\"showSpinner\":${state.showSpinner},\"showConfirmSavedSheet\":${state.showConfirmSavedSheet},\"dialogs\":\"SignalLoginInfoState.Dialogs()\"}", "[{\"name\":\"normalizeAndComparePasswordManagerCredential\",\"accountId\":\"new numberless ACI\",\"accountEntropyPool\":\"new account entropy pool\",\"count\":${if (read.accountId == save.accountId) 1 else 0}},{\"name\":\"navigateTo.AddUsername\",\"count\":${if (navigated == RegistrationRoute.AddUsername) 1 else 0}}]")
  }
}
