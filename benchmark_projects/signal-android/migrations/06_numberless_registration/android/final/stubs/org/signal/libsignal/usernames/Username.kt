package org.signal.libsignal.usernames

data class Username(val username: String) {
  val discriminator: String get() = username.substringAfterLast('.', "")
}
