package android.os

interface Parcelable

open class Parcel {
  fun readInt(): Int = 0
  fun writeInt(value: Int) = Unit
}

class Bundle {
  private val values = mutableMapOf<String, Any?>()
  fun putByte(key: String, value: Byte) { values[key] = value }
  fun getByte(key: String): Byte = values[key] as? Byte ?: 0
  fun putLong(key: String, value: Long) { values[key] = value }
  fun getLong(key: String): Long = values[key] as? Long ?: 0L
  fun putParcelable(key: String, value: Parcelable?) { values[key] = value }
  @Suppress("UNCHECKED_CAST") fun <T> get(key: String): T? = values[key] as? T
}
