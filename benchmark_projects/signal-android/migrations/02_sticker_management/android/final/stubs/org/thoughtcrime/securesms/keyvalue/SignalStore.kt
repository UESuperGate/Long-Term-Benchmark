package org.thoughtcrime.securesms.keyvalue

object SignalStore {
  @JvmField val account = Account()
  @JvmStatic fun account(): Account = account

  class Account {
    @JvmField var hasLinkedDevices: Boolean = false
    fun hasLinkedDevices(): Boolean = hasLinkedDevices
    fun setLinkedDevices(value: Boolean) { hasLinkedDevices = value }
  }
}
