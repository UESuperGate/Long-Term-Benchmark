package org.signal.network.api

object RegistrationApiV2 {
  data class SessionMetadata(val nextSms: Long? = null, val nextCall: Long? = null)
  enum class VerificationCodeTransport { SMS, VOICE }
  sealed interface CreateLoginReceiptCredentialError { data object InvalidPurchase : CreateLoginReceiptCredentialError; data object Pending : CreateLoginReceiptCredentialError }
  sealed interface RegisterAccountError {
    data class InvalidReceiptCredentialPresentation(val message: String = "invalid") : RegisterAccountError
    data object DeviceTransferPossible : RegisterAccountError
    data class InvalidRequest(val message: String = "invalid") : RegisterAccountError
    data class RateLimited(val retryAfter: Long = 0) : RegisterAccountError
  }
  data class RegisterAccountResponse(val e164: String? = null, val storageCapable: Boolean = false)
}
