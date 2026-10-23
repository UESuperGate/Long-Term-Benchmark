package androidx.preference

import android.content.Context
import android.content.SharedPreferences

object PreferenceManager {
    fun getDefaultSharedPreferences(context: Context): SharedPreferences =
        context.getSharedPreferences("reading-challenge-native", Context.MODE_PRIVATE)
}
