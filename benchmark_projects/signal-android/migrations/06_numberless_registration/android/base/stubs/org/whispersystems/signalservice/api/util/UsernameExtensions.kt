package org.whispersystems.signalservice.api.util
val org.signal.libsignal.usernames.Username.discriminator: String get() = username.substringAfterLast('.', "")
