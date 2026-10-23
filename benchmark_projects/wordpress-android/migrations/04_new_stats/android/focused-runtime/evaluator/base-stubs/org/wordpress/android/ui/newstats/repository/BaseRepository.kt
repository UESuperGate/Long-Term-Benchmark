package org.wordpress.android.ui.newstats.repository

import android.content.Context
import org.wordpress.android.ui.newstats.StatsPeriod
import org.wordpress.android.ui.newstats.datasource.StatsUnit
import java.time.LocalDate

data class StatsCardsConfiguration(
    val selectedPeriodType: String? = null,
    val customPeriodStartDate: Long? = null,
    val customPeriodEndDate: Long? = null,
    val selectedChartType: String? = null
)

class StatsCardsConfigurationRepository(context: Context) {
    private val prefs = context.getSharedPreferences("new_stats_base_configuration", Context.MODE_PRIVATE)
    suspend fun getConfiguration(siteId: Long) = StatsCardsConfiguration(
        selectedPeriodType = prefs.getString("period", null),
        selectedChartType = prefs.getString("chart", null)
    )
    suspend fun saveConfiguration(siteId: Long, value: StatsCardsConfiguration) {
        prefs.edit().putString("period", value.selectedPeriodType).putString("chart", value.selectedChartType).commit()
    }
}

data class PeriodAggregates(val views: Long, val visitors: Long, val likes: Long, val comments: Long, val posts: Long, val startDate: String, val endDate: String)
data class ViewsDataPoint(val period: String, val views: Long, val visitors: Long = 0, val likes: Long = 0, val comments: Long = 0, val posts: Long = 0)
sealed class PeriodStatsResult {
    data class Success(val currentAggregates: PeriodAggregates, val previousAggregates: PeriodAggregates, val currentPeriodData: List<ViewsDataPoint>, val previousPeriodData: List<ViewsDataPoint>, val unit: StatsUnit) : PeriodStatsResult()
    data class Error(val message: String) : PeriodStatsResult()
}
data class BottomStatsAggregates(val views: Long, val visitors: Long, val likes: Long, val comments: Long, val posts: Long)
sealed class BottomStatsResult {
    data class Success(val current: BottomStatsAggregates, val previous: BottomStatsAggregates) : BottomStatsResult()
    data object Error : BottomStatsResult()
}

class StatsRepository {
    fun init(accessToken: String) = Unit
    fun canNavigateBackward(period: StatsPeriod) = true
    fun canNavigateForward(period: StatsPeriod) = false
    fun previousPeriod(period: StatsPeriod): StatsPeriod = StatsPeriod.Custom(LocalDate.of(2024, 1, 1), LocalDate.of(2024, 1, 7))
    fun nextPeriod(period: StatsPeriod): StatsPeriod = period
    suspend fun fetchStatsForPeriod(siteId: Long, period: StatsPeriod): PeriodStatsResult = PeriodStatsResult.Error("base")
    suspend fun fetchBottomStats(siteId: Long, period: StatsPeriod): BottomStatsResult = BottomStatsResult.Error
}
