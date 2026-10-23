package org.thoughtcrime.securesms.mms

import android.net.Uri

object PartAuthority {
  @JvmStatic fun getStickerUri(rowId: Long): Uri = Uri.parse("sticker:$rowId")
}
