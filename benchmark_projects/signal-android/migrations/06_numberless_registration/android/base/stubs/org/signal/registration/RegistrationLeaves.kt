package org.signal.registration

import org.signal.core.models.AccountEntropyPool
import org.signal.core.models.ServiceId.ACI
import org.signal.libsignal.net.RequestResult
import org.signal.libsignal.zkgroup.receipts.ReceiptCredential
import org.signal.libsignal.zkgroup.receipts.ReceiptCredentialPresentation
import org.signal.network.api.RegistrationApiV2.RegisterAccountError
import org.signal.network.api.RegistrationApiV2.RegisterAccountResponse

sealed interface RegistrationRoute {
  data object Welcome : RegistrationRoute
  data class SignalLoginCredentialEntry(val accountId: String = "") : RegistrationRoute
  data object SignalLoginInfo : RegistrationRoute
}
class PreExistingRegistrationData
class PendingRestoreOption
class NetworkController { class ProvisioningMessage }
data class KeyMaterial(val accountEntropyPool: AccountEntropyPool)
data class RegisteredAccountData(val response: RegisterAccountResponse, val keyMaterial: KeyMaterial, val aci: ACI)

open class RegistrationRepository {
  var isDebugBuild: Boolean = false
  open fun createReceiptCredentialPresentation(credential: ReceiptCredential): ReceiptCredentialPresentation = ReceiptCredentialPresentation()
  open suspend fun registerAccountWithoutPhoneNumber(presentation: ReceiptCredentialPresentation): RequestResult<RegisteredAccountData, RegisterAccountError> = RequestResult.ApplicationError()
}
