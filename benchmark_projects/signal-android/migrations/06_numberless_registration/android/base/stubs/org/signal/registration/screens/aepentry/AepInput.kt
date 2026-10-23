package org.signal.registration.screens.aepentry

import org.signal.core.models.AccountEntropyPool

data class AepInput(val enteredText: String = "", val error: Any? = null) {
  val normalized: String get() = AccountEntropyPool.removeIllegalCharacters(AccountEntropyPool.formatForStorage(enteredText)).lowercase()
  val isValid: Boolean get() = normalized.length == AccountEntropyPool.LENGTH
  companion object { fun from(value: String, error: Any? = null) = AepInput(value, error) }
}
