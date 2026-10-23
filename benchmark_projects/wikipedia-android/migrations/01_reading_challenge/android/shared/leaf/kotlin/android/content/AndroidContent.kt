package android.content

open class Context {
    open fun getString(id: Int): String = id.toString()
}

class ComponentName(context: Context, type: Class<*>)

class Intent {
    private val extras = mutableSetOf<String>()
    fun hasExtra(name: String): Boolean = name in extras
    fun putExtra(name: String, value: Boolean): Intent = apply { extras += name }
}

interface SharedPreferences {
    fun interface OnSharedPreferenceChangeListener {
        fun onSharedPreferenceChanged(preferences: SharedPreferences, key: String?)
    }

    fun registerOnSharedPreferenceChangeListener(listener: OnSharedPreferenceChangeListener)
    fun unregisterOnSharedPreferenceChangeListener(listener: OnSharedPreferenceChangeListener)
}

class RuntimeSharedPreferences : SharedPreferences {
    override fun registerOnSharedPreferenceChangeListener(listener: SharedPreferences.OnSharedPreferenceChangeListener) = Unit
    override fun unregisterOnSharedPreferenceChangeListener(listener: SharedPreferences.OnSharedPreferenceChangeListener) = Unit
}
