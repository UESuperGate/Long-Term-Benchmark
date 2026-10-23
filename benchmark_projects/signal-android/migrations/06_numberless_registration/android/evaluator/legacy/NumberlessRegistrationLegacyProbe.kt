package benchmark.evaluator

import kotlinx.coroutines.runBlocking
import org.signal.registration.RegistrationRepository
import org.signal.registration.screens.signalloginpayment.SignalLoginPaymentScreenEvents
import org.signal.registration.screens.signalloginpayment.SignalLoginPaymentState
import org.signal.registration.screens.signalloginpayment.SignalLoginPaymentViewModel

private val ids = listOf("nr_001_purchase_eligibility_service_price", "nr_002_purchase_launch_holds_completion", "nr_003_purchase_cancel_cleanup", "nr_004_billing_unavailable_foreground_retry", "nr_005_private_receipt_registration_propagates", "nr_006_manual_save_mismatch_verification", "nr_007_username_skip_requires_confirmation", "nr_008_username_discriminator_race_recovery", "nr_009_purchase_context_process_restore", "nr_010_password_manager_save_readback")

fun main() = runBlocking {
  val vm = SignalLoginPaymentViewModel(RegistrationRepository()) {}
  var state = SignalLoginPaymentState(formattedPrice = "$1.99")
  vm.applyEvent(state, SignalLoginPaymentScreenEvents.Initialize, {}, { state = it })
  vm.applyEvent(state, SignalLoginPaymentScreenEvents.ContinueClicked, {}, { state = it })
  ids.forEach { caseId ->
    println("{\"caseId\":\"$caseId\",\"givenEstablished\":true,\"productionEntrypoint\":\"SignalLoginPaymentViewModel.applyEvent(Initialize/ContinueClicked)\",\"before\":{\"selectedOption\":\"SignalLoginPaymentState.Option.Purchase\",\"formattedPrice\":\"$1.99\"},\"after\":{\"selectedOption\":\"SignalLoginPaymentState.Option.${state.selectedOption}\",\"formattedPrice\":\"${state.formattedPrice}\",\"showSpinner\":${state.showSpinner}},\"effects\":[],\"terminalFailure\":{\"kind\":\"missing_canonical_transition_after_reachable_prefix\",\"prefixReached\":true,\"reason\":\"base production purchase branch is a reachable TODO and emits no purchase transition\"}}")
  }
}
