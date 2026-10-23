package org.wordpress.android.ui.newstats.util

import org.wordpress.android.fluxc.model.SiteModel
import org.wordpress.android.ui.newstats.StatsPeriod
import org.wordpress.android.viewmodel.ResourceProvider
import java.time.LocalDate
import java.time.format.DateTimeFormatter

enum class RangeYearPlacement { BOTH, TRAILING }

fun rangeYearPlacement(startYear: Int, endYear: Int): RangeYearPlacement =
    if (startYear == endYear) RangeYearPlacement.TRAILING else RangeYearPlacement.BOTH

fun StatsPeriod.toDateRangeString(formatter: DateTimeFormatter, today: LocalDate): String {
    val range = when (this) {
        StatsPeriod.Today -> today to today
        StatsPeriod.Last7Days -> today.minusDays(6) to today
        StatsPeriod.Last30Days -> today.minusDays(29) to today
        StatsPeriod.Last12Months -> today.minusMonths(12).plusDays(1) to today
        StatsPeriod.ThisWeek -> today.minusDays((today.dayOfWeek.value - 1).toLong()) to today
        StatsPeriod.ThisMonth -> today.withDayOfMonth(1) to today
        StatsPeriod.ThisYear -> today.withDayOfYear(1) to today
        is StatsPeriod.Custom -> startDate to endDate
    }
    return "${range.first.format(formatter)}:${range.second.format(formatter)}"
}

fun SiteModel.statsUpgradeUrl(): String = "https://wordpress.com/plans/$siteId"

fun StatsPeriod.toDateRangeString(resourceProvider: ResourceProvider): String = when (this) {
    StatsPeriod.Today -> "today"
    StatsPeriod.Last7Days -> "last_7_days"
    StatsPeriod.Last30Days -> "last_30_days"
    StatsPeriod.Last12Months -> "last_12_months"
    StatsPeriod.ThisWeek -> "this_week"
    StatsPeriod.ThisMonth -> "this_month"
    StatsPeriod.ThisYear -> "this_year"
    is StatsPeriod.Custom -> "$startDate:$endDate"
}
