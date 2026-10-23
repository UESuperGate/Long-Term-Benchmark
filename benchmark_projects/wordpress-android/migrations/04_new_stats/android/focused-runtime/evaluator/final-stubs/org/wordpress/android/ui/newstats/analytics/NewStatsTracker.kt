package org.wordpress.android.ui.newstats.analytics

import org.wordpress.android.ui.newstats.StatsPeriod
import org.wordpress.android.ui.newstats.datasource.StatsUnit
import org.wordpress.android.ui.newstats.locations.LocationType
import org.wordpress.android.ui.newstats.viewsstats.ChartType
import org.wordpress.android.ui.newstats.viewsstats.StatsMetric
import java.time.LocalDate

class NewStatsTracker {
    enum class NavigationDirection { PREVIOUS, NEXT }
    val events = mutableListOf<String>()
    fun trackDateRangePresetSelected(period: StatsPeriod) { events += "preset:${period.toTypeString()}" }
    fun trackCustomDateRangeSelected(start: LocalDate, end: LocalDate) { events += "custom:$start:$end" }
    fun trackDateNavigationButtonTapped(direction: NavigationDirection, period: StatsPeriod) { events += "navigate:$direction:${period.toTypeString()}" }
    fun trackChartTypeChanged(from: ChartType, to: ChartType) { events += "chart:$from:$to" }
    fun trackChartMetricSelected(metric: StatsMetric) { events += "metric:${metric.storageKey}" }
    fun trackChartBarSelected(metric: StatsMetric, unit: StatsUnit, value: Long) { events += "bar:${metric.storageKey}:$unit:$value" }
    fun trackLocationLevelChanged(from: LocationType, to: LocationType) { events += "location:$from:$to" }
}
