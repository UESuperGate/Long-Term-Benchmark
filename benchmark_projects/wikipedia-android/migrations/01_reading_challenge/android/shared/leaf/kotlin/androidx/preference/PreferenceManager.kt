package androidx.preference

import android.content.Context
import android.content.RuntimeSharedPreferences
import android.content.SharedPreferences

object PreferenceManager {
    fun getDefaultSharedPreferences(context: Context): SharedPreferences = RuntimeSharedPreferences()
}
