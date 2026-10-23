package org.signal.core.util

fun String.censor(): String = "***"
object Base64 { fun decode(value: String): ByteArray = java.util.Base64.getDecoder().decode(value) }

object UsernameUtil {
  fun checkNickname(value: String): InvalidReason? = null
  fun checkDiscriminator(value: String): InvalidReason? = null
  enum class InvalidReason { TOO_SHORT, TOO_LONG, STARTS_WITH_NUMBER, INVALID_NUMBER_00, INVALID_NUMBER_PREFIX_0, INVALID_CHARACTERS }
}
