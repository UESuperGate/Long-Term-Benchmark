package android.content

open class Intent {
    private val values = mutableMapOf<String, Any>()
    fun hasExtra(key: String): Boolean = values.containsKey(key)
    fun getLongExtra(key: String, defaultValue: Long): Long = values[key] as? Long ?: defaultValue
    fun putExtra(key: String, value: Any): Intent { values[key] = value; return this }
}
