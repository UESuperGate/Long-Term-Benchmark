package org.wordpress.android.ui.newstats.repository

import android.content.Context

data class StatsCardsConfiguration(
    val selectedPeriodType: String? = null,
    val customPeriodStartDate: Long? = null,
    val customPeriodEndDate: Long? = null,
    val originPeriodType: String? = null,
    val originCustomStartDate: Long? = null,
    val originCustomEndDate: Long? = null,
    val selectedChartType: String? = null,
    val selectedMetric: String? = null
)

class StatsCardsConfigurationRepository(context: Context) {
    private val prefs = context.getSharedPreferences("new_stats_configuration", Context.MODE_PRIVATE)
    val writes = mutableListOf<Pair<Long, StatsCardsConfiguration>>()

    suspend fun getConfiguration(siteId: Long): StatsCardsConfiguration {
        fun text(name: String) = prefs.getString("$siteId:$name", null)
        fun number(name: String) = if (prefs.contains("$siteId:$name")) prefs.getLong("$siteId:$name", 0) else null
        return StatsCardsConfiguration(
            selectedPeriodType = text("period"),
            customPeriodStartDate = number("start"), customPeriodEndDate = number("end"),
            originPeriodType = text("origin"), originCustomStartDate = number("originStart"),
            originCustomEndDate = number("originEnd"), selectedChartType = text("chart"),
            selectedMetric = text("metric")
        )
    }

    suspend fun saveConfiguration(siteId: Long, configuration: StatsCardsConfiguration) {
        val edit = prefs.edit().clear()
        fun putText(name: String, value: String?) { if (value != null) edit.putString("$siteId:$name", value) }
        fun putLong(name: String, value: Long?) { if (value != null) edit.putLong("$siteId:$name", value) }
        putText("period", configuration.selectedPeriodType); putLong("start", configuration.customPeriodStartDate)
        putLong("end", configuration.customPeriodEndDate); putText("origin", configuration.originPeriodType)
        putLong("originStart", configuration.originCustomStartDate); putLong("originEnd", configuration.originCustomEndDate)
        putText("chart", configuration.selectedChartType); putText("metric", configuration.selectedMetric)
        check(edit.commit())
        writes += siteId to configuration
    }

    fun clear() { prefs.edit().clear().commit(); writes.clear() }
}
