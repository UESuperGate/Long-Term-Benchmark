package org.signal.core.models

class MasterKey(val bytes: ByteArray = ByteArray(32))

sealed class ServiceId {
  data class ACI(val raw: String) : ServiceId() {
    override fun toString(): String = raw.lowercase()
    fun logString(): String = raw
    companion object {
      fun parseOrNull(value: String): ACI? = value.takeIf { Regex("[0-9a-fA-F-]{36}").matches(it) }?.lowercase()?.let(::ACI)
    }
  }
  data class PNI(val raw: String) : ServiceId()
}
