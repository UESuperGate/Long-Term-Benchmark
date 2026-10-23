package org.signal.network.service

object UsernameService {
  sealed interface ReserveUsernameError {
    data object NicknameInvalid : ReserveUsernameError
    data object NotAvailable : ReserveUsernameError
    data object RateLimited : ReserveUsernameError
  }
  sealed interface ConfirmUsernameError {
    data object NotAvailable : ConfirmUsernameError
    data object ReservationInvalid : ConfirmUsernameError
    data object BadRequest : ConfirmUsernameError
    data object GenerationFailed : ConfirmUsernameError
    data object RateLimited : ConfirmUsernameError
  }
}
