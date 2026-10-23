package org.wikipedia.settings

import android.content.Context
import android.content.SharedPreferences

object Prefs {
    private const val STORE = "hybrid-search-native"
    private lateinit var storage: SharedPreferences

    fun attach(context: Context) { storage = context.applicationContext.getSharedPreferences(STORE, Context.MODE_PRIVATE) }
    fun reopen(context: Context) { attach(context) }
    var isHybridSearchEnabled: Boolean
        get() = storage.getBoolean("hybridEnabled", true)
        set(value) { check(storage.edit().putBoolean("hybridEnabled", value).commit()) }
    fun reset() { check(storage.edit().clear().commit()) }
}
