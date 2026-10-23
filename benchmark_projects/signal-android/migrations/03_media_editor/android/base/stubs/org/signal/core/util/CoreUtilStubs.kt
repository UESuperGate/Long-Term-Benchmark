package org.signal.core.util

import android.os.Bundle

object ContentTypeUtil {
  fun isDocumentType(value: String?): Boolean = value == "application/pdf"
  fun isVideoType(value: String?): Boolean = value?.startsWith("video/") == true
  fun isGif(value: String?): Boolean = value == "image/gif"
  fun isImageType(value: String?): Boolean = value?.startsWith("image/") == true
}

object StringUtil {
  fun getGraphemeCount(value: CharSequence): Int = value.length
  fun trimSequence(value: CharSequence): CharSequence = value.trim()
}

inline fun <reified T> Bundle.getParcelableCompat(key: String, clazz: Class<T>): T? = get(key)
