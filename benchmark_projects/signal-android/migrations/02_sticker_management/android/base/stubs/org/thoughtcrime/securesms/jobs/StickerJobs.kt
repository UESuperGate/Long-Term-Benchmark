package org.thoughtcrime.securesms.jobs

data class StickerPackDownloadJob(val packId: String, val packKey: String, val notify: Boolean, val kind: String) {
  companion object {
    @JvmStatic fun forReference(packId: String, packKey: String) = StickerPackDownloadJob(packId, packKey, false, "REFERENCE")
    @JvmStatic fun forInstall(packId: String, packKey: String, notify: Boolean) = StickerPackDownloadJob(packId, packKey, notify, "INSTALL")
  }
}

data class MultiDeviceStickerPackOperationJob(val packId: String, val packKey: String, val type: Type) {
  enum class Type { INSTALL, REMOVE }
}
