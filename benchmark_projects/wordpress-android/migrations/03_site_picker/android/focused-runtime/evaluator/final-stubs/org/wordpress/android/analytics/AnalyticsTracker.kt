package org.wordpress.android.analytics

object AnalyticsTracker {
    enum class Stat { SITE_SWITCHER_PIN_UPDATED }
    val events = mutableListOf<Pair<Stat, Map<String, Any>>>()
    fun track(stat: Stat, properties: Map<String, Any> = emptyMap()) { events += stat to properties }
}
