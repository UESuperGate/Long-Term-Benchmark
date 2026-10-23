package org.wordpress.android.ui.prefs

import android.content.Context
import org.wordpress.android.WordPress

class AppPrefsWrapper {
    private val prefs get() = WordPress.instance.getSharedPreferences("site-picker-runtime", Context.MODE_PRIVATE)
    var pinnedSiteLocalIds: MutableSet<Int>
        get() = prefs.getStringSet("pinned", emptySet()).orEmpty().map(String::toInt).toMutableSet()
        set(value) { prefs.edit().putStringSet("pinned", value.map(Int::toString).toSet()).commit() }
    fun getRecentSiteLocalIds(): List<Int> = prefs.getString("recent", "").orEmpty().split(',').mapNotNull(String::toIntOrNull)
    fun addRecentSiteLocalId(id: Int) {
        val next = (listOf(id) + getRecentSiteLocalIds().filterNot { it == id }).take(10)
        prefs.edit().putString("recent", next.joinToString(",")).commit()
    }
    fun getSelectedSite(): Int = prefs.getInt("selected", -1)
    fun setSelectedSite(id: Int) { prefs.edit().putInt("selected", id).commit() }
    fun clear() { prefs.edit().clear().commit() }
}
