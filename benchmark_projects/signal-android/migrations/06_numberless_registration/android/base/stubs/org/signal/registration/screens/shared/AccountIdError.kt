package org.signal.registration.screens.shared
sealed interface AccountIdError { data class TooLong(val length: Int) : AccountIdError; data object Invalid : AccountIdError }
