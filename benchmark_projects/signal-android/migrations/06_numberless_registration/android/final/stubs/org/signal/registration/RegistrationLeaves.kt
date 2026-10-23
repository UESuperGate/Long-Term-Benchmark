package org.signal.registration

import org.signal.core.models.AccountEntropyPool
import org.signal.core.models.ServiceId.ACI
import org.signal.core.util.billing.OneTimePurchaseResult
import org.signal.core.util.billing.PurchaseLauncher
import org.signal.libsignal.net.RequestResult
import org.signal.libsignal.usernames.Username
import org.signal.libsignal.zkgroup.receipts.ReceiptCredential
import org.signal.libsignal.zkgroup.receipts.ReceiptCredentialPresentation
import org.signal.network.api.RegistrationApiV2.RegisterAccountError
import org.signal.network.api.RegistrationApiV2.RegisterAccountResponse
import org.signal.network.service.UsernameService.ConfirmUsernameError
import org.signal.network.service.UsernameService.ReserveUsernameError
import org.signal.registration.screens.signalloginpayment.PaymentAvailability

sealed interface RegistrationRoute {
  data object Welcome : RegistrationRoute
  data object SignalLoginPayment : RegistrationRoute
  data class SignalLoginCredentialEntry(val accountId: String = "") : RegistrationRoute
  data object SignalLoginInfo : RegistrationRoute
  data object SignalLoginViewDetails : RegistrationRoute
  data object SignalLoginViewDetailsForManualSave : RegistrationRoute
  data object SignalLoginManualSaveConfirmation : RegistrationRoute
  data object AddUsername : RegistrationRoute
}

class PreExistingRegistrationData
class PendingRestoreOption
class NetworkController { class ProvisioningMessage }

data class KeyMaterial(val accountEntropyPool: AccountEntropyPool)
data class RegisteredAccountData(val response: RegisterAccountResponse, val keyMaterial: KeyMaterial, val aci: ACI)

open class RegistrationRepository {
  var isDebugBuild: Boolean = false
  var hasPurchase: Boolean = false
  var availability: PaymentAvailability = PaymentAvailability.Available
  var priceResult: SignalLoginPriceResult = SignalLoginPriceResult.Available("$1.99")
  var purchaseStep: SignalLoginPurchaseStep = SignalLoginPurchaseStep.LaunchRequired(PurchaseLauncher())
  var completionResult: SignalLoginPurchaseResult = SignalLoginPurchaseResult.Cancelled
  var presentationResult: ReceiptCredentialResult<ReceiptCredentialPresentation> = ReceiptCredentialResult.Success(ReceiptCredentialPresentation())
  var registrationResult: RequestResult<RegisteredAccountData, RegisterAccountError> = RequestResult.ApplicationError()
  var reserveResult: RequestResult<Username, ReserveUsernameError> = RequestResult.Success(Username("maya.01"))
  var confirmResult: RequestResult<Unit, ConfirmUsernameError> = RequestResult.Success(Unit)
  val effects: MutableList<String> = mutableListOf()

  open suspend fun hasUnredeemedSignalLoginPurchase(): Boolean { effects += "queryUnconsumedPurchase"; return hasPurchase }
  open suspend fun getPaymentAvailability(): PaymentAvailability { effects += "getPaymentAvailability"; return availability }
  open suspend fun getSignalLoginPrice(): SignalLoginPriceResult { effects += "getLoginConfiguration"; effects += "queryOneTimeProduct"; return priceResult }
  open suspend fun startOrCompleteSignalLoginPurchase(): SignalLoginPurchaseStep { effects += "preparePurchase"; return purchaseStep }
  open suspend fun completeSignalLoginPurchase(result: OneTimePurchaseResult): SignalLoginPurchaseResult { effects += "completeSignalLoginPurchase"; return completionResult }
  open fun createReceiptCredentialPresentation(credential: ReceiptCredential): ReceiptCredentialResult<ReceiptCredentialPresentation> = presentationResult
  open suspend fun registerAccountWithoutPhoneNumber(presentation: ReceiptCredentialPresentation): RequestResult<RegisteredAccountData, RegisterAccountError> = registrationResult
  open suspend fun reserveUsername(nickname: String, discriminator: String?): RequestResult<Username, ReserveUsernameError> { effects += "reserveUsername"; return reserveResult }
  open suspend fun confirmUsername(username: Username): RequestResult<Unit, ConfirmUsernameError> { effects += "confirmUsername"; return confirmResult }
}
