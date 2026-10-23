package org.signal.libsignal.messagebackup

object AccountEntropyPool {
  fun generate(): String = "a".repeat(64)
  fun isValid(value: String): Boolean = value.length == 64
  fun deriveSvrKey(value: String): ByteArray = ByteArray(32)
  fun deriveBackupKey(value: String): BackupKey = BackupKey()
}
class BackupKey { fun serialize(): ByteArray = ByteArray(32) }
