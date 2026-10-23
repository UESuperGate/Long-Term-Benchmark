package android.database

interface Cursor : AutoCloseable {
  fun moveToNext(): Boolean
  fun getColumnIndexOrThrow(column: String): Int
  fun getString(index: Int): String
  override fun close() = Unit
}
