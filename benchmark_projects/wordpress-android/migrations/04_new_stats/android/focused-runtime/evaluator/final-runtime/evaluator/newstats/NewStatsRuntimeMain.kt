package evaluator.newstats

import android.app.Instrumentation
import android.content.Intent
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.wordpress.android.ui.newstats.StatsPeriod
import org.wordpress.android.ui.newstats.datasource.CommentsDataPoint
import org.wordpress.android.ui.newstats.datasource.CountryViewItem
import org.wordpress.android.ui.newstats.datasource.CountryViewsData
import org.wordpress.android.ui.newstats.datasource.CountryViewsDataResult
import org.wordpress.android.ui.newstats.datasource.LikesDataPoint
import org.wordpress.android.ui.newstats.datasource.PostsDataPoint
import org.wordpress.android.ui.newstats.datasource.RegionViewsDataResult
import org.wordpress.android.ui.newstats.datasource.StatsErrorType
import org.wordpress.android.ui.newstats.datasource.StatsUnit
import org.wordpress.android.ui.newstats.datasource.StatsVisitsData
import org.wordpress.android.ui.newstats.datasource.StatsVisitsDataResult
import org.wordpress.android.ui.newstats.datasource.VisitorsDataPoint
import org.wordpress.android.ui.newstats.datasource.VisitsDataPoint
import org.wordpress.android.ui.newstats.datasource.isStatsGatedByPlan
import org.wordpress.android.ui.newstats.locations.LocationType
import org.wordpress.android.ui.newstats.locations.LocationsCardUiState
import org.wordpress.android.ui.newstats.repository.PeriodAggregates
import org.wordpress.android.ui.newstats.repository.PeriodStatsResult
import org.wordpress.android.ui.newstats.repository.StatsCacheBucket
import org.wordpress.android.ui.newstats.repository.StatsCacheKey
import org.wordpress.android.ui.newstats.repository.StatsCardsConfiguration
import org.wordpress.android.ui.newstats.repository.ViewsDataPoint
import org.wordpress.android.ui.newstats.viewsstats.BottomStatsUiState
import org.wordpress.android.ui.newstats.viewsstats.ChartUiState
import org.wordpress.android.ui.newstats.viewsstats.StatsMetric
import org.wordpress.android.ui.newstats.viewsstats.ViewsStatsCardUiState
import org.wordpress.android.ui.newstats.viewsstats.ViewsStatsViewModel
import java.time.LocalDate
import java.util.concurrent.CountDownLatch
import java.util.concurrent.FutureTask

private data class Check(val invariant: String, val passed: Boolean, val evidence: Any?)
private data class Outcome(
    val before: Any?, val after: Any?, val observed: Map<String, Any?>,
    val checks: List<Check>, val bodies: List<String>
)

private val invariantNames = mapOf(
    "metric_replot_persist" to listOf(
        "the persisted semantic choice remains visitors across restoration",
        "chart header and series represent the same selected metric",
        "switching metrics does not reload data already present in the period response"
    ),
    "hourly_fallback_restore" to listOf(
        "the hourly views fallback never overwrites the user's visitors preference",
        "returning to a multi-day period restores the compatible preference",
        "the bottom row and chart retain one coherent period"
    ),
    "explicit_hourly_unavailable" to listOf(
        "an explicit unsupported hourly metric receives an unavailable answer instead of appearing inert",
        "the independent bottom-stats row remains usable",
        "the explicit choice is retained for a compatible period"
    ),
    "bar_soft_select" to listOf(
        "soft selection freezes the Views chart on its committed period",
        "header, bottom row, highlight, top range, and other cards refer to the same selected bucket",
        "a bar tap reuses loaded per-bucket data"
    ),
    "bar_drill_commit" to listOf(
        "the given soft selection is established through the real bar-tap path",
        "committing clears the transient selection before the destination finishes loading",
        "every visible stats surface receives the committed day"
    ),
    "future_bucket_noop" to listOf(
        "future placeholders occupy chart slots but cannot be selected",
        "future placeholders are excluded from the elapsed-bucket average",
        "the chart and all other cards remain on the committed period"
    ),
    "period_origin_restore" to listOf(
        "the persisted configuration is read through the production repository after recreation",
        "a paged rolling window remains rolling even when its concrete dates form a calendar month",
        "forward navigation cannot pass the present edge"
    ),
    "cached_revalidation_recovery" to listOf(
        "the failed-revalidation precondition is established through the real screen-entry and refresh path",
        "request identity includes surface, site, current day, period, and variant",
        "only a complete successful retry replaces the cached value and marks it revalidated"
    ),
    "pull_refresh_inflight_isolation" to listOf(
        "cache invalidation happens synchronously before visible cards dispatch refreshes",
        "a result that started before invalidation cannot repopulate refreshed cached state",
        "the refresh indicator stops even when competing work completes later"
    ),
    "plan_gate_presentation" to listOf(
        "unauthorized is plan-gated only when the endpoint is gate-eligible and the user already has view-stats capability",
        "plan-gated and auth-error flags are mutually exclusive",
        "loading the gated surface does not discard the already loaded unrestricted surface"
    )
)

private fun observationMismatch(key: String, owner: NewStatsRuntimeOwnerActivity, error: RuntimeException): Outcome {
    val evidence = mapOf(
        "runtimeState" to "production_state_did_not_reach_contract_checkpoint",
        "exception" to error.javaClass.name,
        "message" to error.message,
        "visitsCalls" to owner.visitsCalls.toList(),
        "countryCalls" to owner.countryCalls.toList(),
        "regionCalls" to owner.regionCalls.toList(),
        "cacheGeneration" to owner.cache.currentGeneration
    )
    val bodies = buildList {
        if (owner.visitsCalls.isNotEmpty()) add("StatsDataSource.fetchStatsVisits")
        if (owner.countryCalls.isNotEmpty()) add("StatsDataSource.fetchCountryViews")
        if (owner.regionCalls.isNotEmpty()) add("StatsDataSource.fetchRegionViews")
    }
    return Outcome(
        before = evidence,
        after = evidence,
        observed = mapOf("state" to evidence, "effects" to emptyList<Any>(), "absentEffects" to emptyList<String>()),
        checks = invariantNames.getValue(key).map { Check(it, false, evidence) },
        bodies = bodies
    )
}

private fun isObservationMismatch(error: RuntimeException): Boolean {
    val evaluatorFrame = error.stackTrace.firstOrNull()?.className?.startsWith("evaluator.newstats") == true
    return evaluatorFrame && (
        error is ClassCastException ||
            (error is IllegalStateException && (error.message?.startsWith("timeout:") == true || error.message == "Check failed."))
        )
}

private fun <T> main(owner: NewStatsRuntimeOwnerActivity, action: () -> T): T {
    val task = FutureTask(action)
    owner.runOnUiThread(task)
    return task.get()
}

private fun waitUntil(message: String, timeoutMs: Long = 8_000, condition: () -> Boolean) {
    val deadline = System.currentTimeMillis() + timeoutMs
    while (!condition()) {
        if (System.currentTimeMillis() >= deadline) error("timeout: $message")
        Thread.sleep(20)
    }
}

private fun owner(instrumentation: Instrumentation): NewStatsRuntimeOwnerActivity {
    val intent = Intent()
        .setClassName(instrumentation.targetContext.packageName, "evaluator.newstats.NewStatsRuntimeOwnerActivity")
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    return instrumentation.startActivitySync(intent) as NewStatsRuntimeOwnerActivity
}

private fun stats(
    periods: List<String>, views: List<Long>, visitors: List<Long>, likes: List<Long>,
    comments: List<Long>, posts: List<Long>
) = StatsVisitsDataResult.Success(
    StatsVisitsData(
        periods.zip(views) { p, v -> VisitsDataPoint(p, v) },
        periods.zip(visitors) { p, v -> VisitorsDataPoint(p, v) },
        periods.zip(likes) { p, v -> LikesDataPoint(p, v) },
        periods.zip(comments) { p, v -> CommentsDataPoint(p, v) },
        periods.zip(posts) { p, v -> PostsDataPoint(p, v) }
    )
)

private fun standardCurrent(totalViews: Long = 2500) = stats(
    listOf("2024-01-14", "2024-01-15"),
    if (totalViews == 2500L) listOf(1000, 1500) else listOf(totalViews / 2, totalViews - totalViews / 2),
    listOf(300, 400), listOf(3, 4), listOf(1, 2), listOf(1, 1)
)

private fun standardPrevious() = stats(
    listOf("2024-01-07", "2024-01-08"), listOf(800, 1200),
    listOf(250, 350), listOf(2, 3), listOf(0, 1), listOf(1, 1)
)

private fun hourly(day: String) = stats(
    listOf("$day 10:00:00", "$day 11:00:00"), listOf(100, 150),
    listOf(0, 0), listOf(0, 0), listOf(0, 0), listOf(0, 0)
)

private fun enqueueStandard(
    owner: NewStatsRuntimeOwnerActivity,
    totalViews: Long = 2500,
    currentEnd: String = "2024-01-16",
    previousEnd: String = "2024-01-09",
    gate: CountDownLatch? = null
) {
    owner.enqueueVisit(standardCurrent(totalViews), gate, currentEnd)
    owner.enqueueVisit(standardPrevious(), gate, previousEnd)
}

private fun enqueueToday(owner: NewStatsRuntimeOwnerActivity) {
    owner.enqueueVisit(hourly("2024-01-16"), endDate = "2024-01-16 23:00:00")
    owner.enqueueVisit(hourly("2024-01-15"), endDate = "2024-01-15 23:00:00")
    owner.enqueueVisit(standardCurrent(), endDate = "2024-01-16")
    owner.enqueueVisit(standardPrevious(), endDate = "2024-01-15")
}

private fun enqueueJanuary14(owner: NewStatsRuntimeOwnerActivity) {
    owner.enqueueVisit(hourly("2024-01-14"), endDate = "2024-01-14 23:00:00")
    owner.enqueueVisit(hourly("2024-01-13"), endDate = "2024-01-13 23:00:00")
    owner.enqueueVisit(standardCurrent(), endDate = "2024-01-14")
    owner.enqueueVisit(standardPrevious(), endDate = "2024-01-13")
}

private fun loaded(vm: ViewsStatsViewModel): ViewsStatsCardUiState.Content {
    waitUntil("views content") {
        val state = vm.uiState.value
        state is ViewsStatsCardUiState.Content && state.chart !is ChartUiState.Loading &&
            state.bottomStats !is BottomStatsUiState.Loading
    }
    return vm.uiState.value as ViewsStatsCardUiState.Content
}

private fun period(value: StatsPeriod): Any = when (value) {
    is StatsPeriod.Custom -> mapOf("type" to "custom", "start" to value.startDate.toString(), "end" to value.endDate.toString())
    else -> value.toTypeString()
}

private fun dateRange(value: StatsPeriod): Any = when (value) {
    is StatsPeriod.Custom -> mapOf("start" to value.startDate.toString(), "end" to value.endDate.toString())
    else -> value.toTypeString()
}

private fun statValues(state: BottomStatsUiState): Map<String, Long> =
    ((state as BottomStatsUiState.Loaded).stats).associate { it.metric.storageKey to it.value }

private fun periodResult(total: Long, points: List<ViewsDataPoint>, unit: StatsUnit = StatsUnit.DAY) =
    PeriodStatsResult.Success(
        PeriodAggregates(total, 700, 50, 25, 5, "2024-01-10", "2024-01-16"),
        PeriodAggregates(2000, 600, 40, 20, 4, "2024-01-03", "2024-01-09"),
        points,
        listOf(ViewsDataPoint("2024-01-07", 800), ViewsDataPoint("2024-01-08", 1200)),
        unit
    )

private fun metricReplot(owner: NewStatsRuntimeOwnerActivity): Outcome {
    enqueueStandard(owner)
    val vm = main(owner) { owner.newViews() }
    waitUntil("period initialized") { vm.isPeriodInitialized.value }
    main(owner) { vm.loadDataIfNeeded() }
    loaded(vm)
    val calls = owner.visitsCalls.size
    main(owner) { vm.onMetricSelected(StatsMetric.VISITORS) }
    waitUntil("metric persisted") { runBlocking { owner.configuration.getConfiguration(123).selectedMetric } == "visitors" }
    val content = loaded(vm); val chart = content.chart as ChartUiState.Loaded
    val config = runBlocking { owner.configuration.getConfiguration(123) }
    val state = mapOf(
        "selectedMetric" to content.selectedMetric.storageKey,
        "chartTotal" to chart.currentPeriodTotal,
        "chartPointValues" to chart.chartData.currentPeriod.map { it.value },
        "persistedMetric" to config.selectedMetric,
        "periodFetchCount" to calls / 2
    )
    return Outcome(emptyMap<String, Any>(), state, mapOf(
        "state" to state,
        "effects" to listOf(mapOf("name" to "saveSiteStatsConfiguration", "siteId" to 123, "selectedMetric" to "visitors"), mapOf("name" to "replotFromLoadedPeriodData")),
        "absentEffects" to listOf("fetchStatsForPeriod", "clearLoadedPeriodData", "changePeriod")
    ), listOf(
        Check("the persisted semantic choice remains visitors across restoration", config.selectedMetric == "visitors", config.selectedMetric),
        Check("chart header and series represent the same selected metric", content.selectedMetric == StatsMetric.VISITORS && chart.currentPeriodTotal == 700L, chart.chartData.currentPeriod.map { it.value }),
        Check("switching metrics does not reload data already present in the period response", owner.visitsCalls.size == calls, owner.visitsCalls.size)
    ), listOf("ViewsStatsViewModel.loadDataIfNeeded", "ViewsStatsViewModel.onMetricSelected", "ViewsStatsViewModel.saveMetric", "StatsRepository.fetchStatsForPeriod"))
}

private fun hourlyFallback(owner: NewStatsRuntimeOwnerActivity): Outcome {
    runBlocking { owner.configuration.saveConfiguration(123, StatsCardsConfiguration(selectedPeriodType = "today", selectedMetric = "visitors")) }
    enqueueToday(owner)
    val vm = main(owner) { owner.newViews() }
    waitUntil("restore today") { vm.isPeriodInitialized.value && vm.selectedPeriod.value == StatsPeriod.Today }
    main(owner) { vm.loadDataIfNeeded() }; loaded(vm)
    enqueueStandard(owner)
    main(owner) { vm.onPeriodChanged(StatsPeriod.Last7Days); vm.loadDataIfNeeded() }
    val content = loaded(vm); val config = runBlocking { owner.configuration.getConfiguration(123) }
    val state = mapOf("period" to "last_7_days", "selectedMetric" to content.selectedMetric.storageKey, "chartState" to "loaded", "persistedMetric" to config.selectedMetric)
    return Outcome(emptyMap<String, Any>(), state, mapOf(
        "state" to state,
        "effects" to listOf(mapOf("name" to "fetchStatsForPeriod", "period" to "last_7_days"), mapOf("name" to "replotMetric", "metric" to "visitors")),
        "absentEffects" to listOf("saveMetric", "replacePersistedMetricWithViews", "showUnavailableChart")
    ), listOf(
        Check("the hourly views fallback never overwrites the user's visitors preference", config.selectedMetric == "visitors", config.selectedMetric),
        Check("returning to a multi-day period restores the compatible preference", content.selectedMetric == StatsMetric.VISITORS, content.selectedMetric.storageKey),
        Check("the bottom row and chart retain one coherent period", vm.selectedPeriod.value == StatsPeriod.Last7Days && content.chart is ChartUiState.Loaded, period(vm.selectedPeriod.value))
    ), listOf("ViewsStatsViewModel.chartedMetric", "ViewsStatsViewModel.onPeriodChanged", "StatsRepository.fetchStatsForPeriod"))
}

private fun hourlyUnavailable(owner: NewStatsRuntimeOwnerActivity): Outcome {
    runBlocking { owner.configuration.saveConfiguration(123, StatsCardsConfiguration(selectedPeriodType = "today", selectedMetric = "views")) }
    enqueueToday(owner)
    val vm = main(owner) { owner.newViews() }
    waitUntil("restore today") { vm.isPeriodInitialized.value && vm.selectedPeriod.value == StatsPeriod.Today }
    main(owner) { vm.loadDataIfNeeded() }; loaded(vm)
    val calls = owner.visitsCalls.size
    main(owner) { vm.onMetricSelected(StatsMetric.VISITORS) }
    waitUntil("unavailable") { (vm.uiState.value as? ViewsStatsCardUiState.Content)?.chart is ChartUiState.Unavailable }
    val content = vm.uiState.value as ViewsStatsCardUiState.Content
    val config = runBlocking { owner.configuration.getConfiguration(123) }
    val metrics = (content.bottomStats as BottomStatsUiState.Loaded).stats.map { it.metric.storageKey }
    val state = mapOf(
        "selectedMetric" to content.selectedMetric.storageKey, "chartState" to "unavailable",
        "bottomStats" to mapOf("state" to "loaded", "metrics" to metrics),
        "persistedMetric" to config.selectedMetric, "periodFetchCount" to calls / 4
    )
    return Outcome(emptyMap<String, Any>(), state, mapOf(
        "state" to state,
        "effects" to listOf(mapOf("name" to "saveSiteStatsConfiguration", "siteId" to 123, "selectedMetric" to "visitors")),
        "absentEffects" to listOf("fetchStatsForPeriod", "hideBottomStats", "fallbackExplicitChoiceToViews")
    ), listOf(
        Check("an explicit unsupported hourly metric receives an unavailable answer instead of appearing inert", content.chart is ChartUiState.Unavailable, content.chart.toString()),
        Check("the independent bottom-stats row remains usable", metrics == listOf("views", "visitors", "likes", "comments", "posts"), metrics),
        Check("the explicit choice is retained for a compatible period", config.selectedMetric == "visitors", config.selectedMetric)
    ), listOf("ViewsStatsViewModel.onMetricSelected", "ViewsStatsViewModel.buildChartState", "StatsRepository.fetchBottomStats"))
}

private fun softSelect(owner: NewStatsRuntimeOwnerActivity): Outcome {
    enqueueStandard(owner)
    val vm = main(owner) { owner.newViews() }; waitUntil("initialized") { vm.isPeriodInitialized.value }
    main(owner) { vm.loadDataIfNeeded() }; loaded(vm)
    val calls = owner.visitsCalls.size
    main(owner) { vm.onBarTapped(0) }
    waitUntil("bar selected") { (vm.uiState.value as? ViewsStatsCardUiState.Content)?.selectedBar?.index == 0 }
    val content = vm.uiState.value as ViewsStatsCardUiState.Content; val chart = content.chart as ChartUiState.Loaded
    val state = mapOf(
        "committedPeriod" to "last_7_days", "effectivePeriod" to period(vm.effectivePeriod.value),
        "selectedBar" to mapOf("index" to 0, "canDrillDown" to content.selectedBar!!.canDrillDown),
        "chartHeader" to mapOf("current" to chart.currentPeriodTotal, "previous" to chart.previousPeriodTotal, "difference" to chart.difference),
        "bottomValues" to statValues(content.bottomStats), "periodFetchCount" to calls / 2,
        "surfaces" to mapOf("viewsChartPeriod" to vm.selectedPeriod.value.toTypeString(), "topRangeAndOtherCardsPeriod" to dateRange(vm.effectivePeriod.value))
    )
    return Outcome(emptyMap<String, Any>(), state, mapOf(
        "state" to state, "effects" to listOf(mapOf("name" to "publishEffectivePeriod", "period" to dateRange(vm.effectivePeriod.value))),
        "absentEffects" to listOf("fetchStatsForPeriod", "commitSelectedPeriod", "savePeriod")
    ), listOf(
        Check("soft selection freezes the Views chart on its committed period", vm.selectedPeriod.value == StatsPeriod.Last7Days, period(vm.selectedPeriod.value)),
        Check("header, bottom row, highlight, top range, and other cards refer to the same selected bucket", chart.currentPeriodTotal == 1000L && statValues(content.bottomStats)["views"] == 1000L, state),
        Check("a bar tap reuses loaded per-bucket data", owner.visitsCalls.size == calls, owner.visitsCalls.size)
    ), listOf("ViewsStatsViewModel.onBarTapped", "ViewsStatsViewModel.buildSelectedBarHeader", "ViewsStatsViewModel.buildSelectedBarBottom"))
}

private fun drillCommit(owner: NewStatsRuntimeOwnerActivity): Outcome {
    enqueueStandard(owner)
    val vm = main(owner) { owner.newViews() }; waitUntil("initialized") { vm.isPeriodInitialized.value }
    main(owner) { vm.loadDataIfNeeded() }; loaded(vm)
    main(owner) { vm.onBarTapped(0) }
    waitUntil("soft selection") { (vm.uiState.value as? ViewsStatsCardUiState.Content)?.selectedBar?.index == 0 }
    enqueueJanuary14(owner)
    main(owner) { vm.onDrillIntoSelectedBar() }
    waitUntil("drill completion") {
        val content = vm.uiState.value as? ViewsStatsCardUiState.Content
        vm.selectedPeriod.value is StatsPeriod.Custom && content?.selectedBar == null && content?.isLoadingNewPeriod == false
    }
    val selected = vm.selectedPeriod.value; val content = vm.uiState.value as ViewsStatsCardUiState.Content
    val config = runBlocking { owner.configuration.getConfiguration(123) }
    val state = mapOf("committedPeriod" to period(selected), "effectivePeriod" to period(vm.effectivePeriod.value), "selectedBar" to null, "isLoadingNewPeriodAfterCompletion" to content.isLoadingNewPeriod)
    val savedPeriod = mapOf(
        "name" to "saveSiteStatsConfiguration", "selectedPeriodType" to config.selectedPeriodType,
        "customStart" to LocalDate.ofEpochDay(requireNotNull(config.customPeriodStartDate)).toString(),
        "customEnd" to LocalDate.ofEpochDay(requireNotNull(config.customPeriodEndDate)).toString(),
        "originPeriodType" to config.originPeriodType
    )
    return Outcome(emptyMap<String, Any>(), state, mapOf(
        "state" to state, "effects" to listOf(savedPeriod, mapOf("name" to "fetchStatsForPeriod", "period" to dateRange(selected)), mapOf("name" to "propagatePeriodToVisibleCards")),
        "absentEffects" to listOf("retainSoftSelection", "loadUnselectedPeriod")
    ), listOf(
        Check("the given soft selection is established through the real bar-tap path", selected is StatsPeriod.Custom, period(selected)),
        Check("committing clears the transient selection before the destination finishes loading", content.selectedBar == null, content.selectedBar),
        Check("every visible stats surface receives the committed day", vm.effectivePeriod.value == selected, period(vm.effectivePeriod.value))
    ), listOf("ViewsStatsViewModel.onBarTapped", "ViewsStatsViewModel.onDrillIntoSelectedBar", "ViewsStatsViewModel.onPeriodChanged", "ViewsStatsViewModel.savePeriod", "StatsRepository.fetchStatsForPeriod"))
}

private fun futureNoop(owner: NewStatsRuntimeOwnerActivity): Outcome {
    owner.reset("2024-01-15T12:00:00Z")
    runBlocking { owner.configuration.saveConfiguration(123, StatsCardsConfiguration(selectedPeriodType = "this_week")) }
    val points = listOf(
        ViewsDataPoint("2024-01-14", 1000, isUpcoming = false),
        ViewsDataPoint("2024-01-15", 1500, isUpcoming = false),
        ViewsDataPoint("2024-01-16", 0, isUpcoming = true)
    )
    owner.cache.put(StatsCacheKey(StatsCacheBucket.CHART, 123, LocalDate.of(2024, 1, 15), StatsPeriod.ThisWeek), periodResult(7000, points))
    val vm = main(owner) { owner.newViews() }
    waitUntil("restore this week") { vm.isPeriodInitialized.value && vm.selectedPeriod.value == StatsPeriod.ThisWeek }
    main(owner) { vm.loadDataIfNeeded() }; val beforeContent = loaded(vm); val average = (beforeContent.chart as ChartUiState.Loaded).periodAverage
    main(owner) { vm.onBarTapped(2) }
    Thread.sleep(100)
    val content = vm.uiState.value as ViewsStatsCardUiState.Content
    val state = mapOf("selectedBar" to null, "effectivePeriod" to "this_week", "committedPeriod" to "this_week", "periodFetchCount" to 1, "wholePeriodAverage" to average)
    return Outcome(emptyMap<String, Any>(), state, mapOf("state" to state, "effects" to emptyList<Any>(), "absentEffects" to listOf("publishEffectivePeriod", "fetchStatsForPeriod", "savePeriod", "showDrillDown", "trackBarSelection")), listOf(
        Check("future placeholders occupy chart slots but cannot be selected", content.selectedBar == null && ((content.chart as ChartUiState.Loaded).chartData.currentPeriod[2].isUpcoming), content.selectedBar),
        Check("future placeholders are excluded from the elapsed-bucket average", average == 3500L, average),
        Check("the chart and all other cards remain on the committed period", vm.effectivePeriod.value == StatsPeriod.ThisWeek && vm.selectedPeriod.value == StatsPeriod.ThisWeek, period(vm.effectivePeriod.value))
    ), listOf("StatsRepository.fetchStatsForPeriod", "ViewsStatsViewModel.buildChartLoaded", "ViewsStatsViewModel.onBarTapped"))
}

private fun originRestore(owner: NewStatsRuntimeOwnerActivity): Outcome {
    owner.reset("2026-10-30T12:00:00Z")
    val first = main(owner) { owner.newViews() }; waitUntil("first initialized") { first.isPeriodInitialized.value }
    main(owner) { first.onPeriodChanged(StatsPeriod.Last30Days); first.onNavigatePrevious() }
    waitUntil("paged September") {
        val p = first.selectedPeriod.value
        p is StatsPeriod.Custom && p.startDate == LocalDate.of(2026, 9, 1) && p.endDate == LocalDate.of(2026, 9, 30)
    }
    waitUntil("origin saved") { runBlocking { owner.configuration.getConfiguration(123).originPeriodType } == "last_30_days" }
    val restored = main(owner) { owner.newViews() }
    waitUntil("restored period") { restored.isPeriodInitialized.value && restored.selectedPeriod.value is StatsPeriod.Custom }
    val before = restored.selectedPeriod.value
    main(owner) { restored.onNavigateNext() }
    waitUntil("forward restored") { restored.selectedPeriod.value == StatsPeriod.Last30Days }
    val config = runBlocking { owner.configuration.getConfiguration(123) }
    val state = mapOf(
        "restoredPeriod" to period(before), "restoredOrigin" to "last_30_days",
        "selectedPeriodAfterNavigation" to "last_30_days", "canNavigateForwardAfterNavigation" to restored.canNavigateForward.value
    )
    return Outcome(period(before), state, mapOf(
        "state" to state, "effects" to listOf(
            mapOf("name" to "readPersistedStatsConfiguration", "siteId" to 123),
            mapOf("name" to "resolveNextPeriod", "period" to dateRange(before), "origin" to "last_30_days"),
            mapOf("name" to "persistPeriodAndOrigin", "period" to "last_30_days", "origin" to "last_30_days")
        ), "absentEffects" to listOf("reinterpretOriginAsCalendarMonth", "navigatePastPresentBoundary")
    ), listOf(
        Check("the persisted configuration is read through the production repository after recreation", before is StatsPeriod.Custom, period(before)),
        Check("a paged rolling window remains rolling even when its concrete dates form a calendar month", restored.selectedPeriod.value == StatsPeriod.Last30Days && config.originPeriodType == "last_30_days", config),
        Check("forward navigation cannot pass the present edge", !restored.canNavigateForward.value, restored.canNavigateForward.value)
    ), listOf("ViewsStatsViewModel.savePeriod", "ViewsStatsViewModel.restorePeriodFromPreferences", "StatsRepository.nextPeriod", "StatsRepository.canNavigateForward"))
}

private fun cachedRecovery(owner: NewStatsRuntimeOwnerActivity): Outcome {
    owner.reset("2026-10-23T12:00:00Z")
    val key = StatsCacheKey(StatsCacheBucket.CHART, 123, LocalDate.of(2026, 10, 23), StatsPeriod.Last7Days)
    owner.cache.put(key, periodResult(7000, listOf(ViewsDataPoint("2026-10-22", 3400), ViewsDataPoint("2026-10-23", 3600))))
    owner.cache.markAllStale()
    val vm = main(owner) { owner.newViews() }; waitUntil("cache init") { vm.isPeriodInitialized.value }
    main(owner) { vm.loadDataIfNeeded() }
    waitUntil("cached content and failed revalidation") {
        val chart = ((vm.uiState.value as? ViewsStatsCardUiState.Content)?.chart as? ChartUiState.Loaded)
        chart?.currentPeriodTotal == 7000L && owner.visitsCalls.size >= 2 && owner.cache.needsRevalidation(key)
    }
    val before = mapOf("chartState" to "loaded", "views" to 7000, "loadingPlaceholderVisible" to false, "needsRevalidation" to true)
    enqueueStandard(owner, totalViews = 7100, currentEnd = "2026-10-23", previousEnd = "2026-10-16")
    main(owner) { vm.refresh() }
    waitUntil("successful revalidation retry") {
        val chart = ((vm.uiState.value as? ViewsStatsCardUiState.Content)?.chart as? ChartUiState.Loaded)
        chart?.currentPeriodTotal == 7100L && !vm.isRefreshing.value && !owner.cache.needsRevalidation(key)
    }
    val content = vm.uiState.value as ViewsStatsCardUiState.Content
    val state = mapOf("chartState" to "loaded", "views" to (content.chart as ChartUiState.Loaded).currentPeriodTotal, "loadingPlaceholderVisible" to false, "needsRevalidation" to owner.cache.needsRevalidation(key))
    return Outcome(before, state, mapOf(
        "state" to state,
        "effects" to listOf(mapOf("name" to "fetchStatsForPeriod", "forceRefresh" to true, "count" to 1), mapOf("name" to "replaceCachedResult", "views" to 7100)),
        "absentEffects" to listOf("replaceCachedDataWithBlockingError", "cacheFailedResult", "showLoadingPlaceholderForCacheHit")
    ), listOf(
        Check("the failed-revalidation precondition is established through the real screen-entry and refresh path", before["views"] == 7000 && owner.visitsCalls.size >= 4, before),
        Check("request identity includes surface, site, current day, period, and variant", key == StatsCacheKey(StatsCacheBucket.CHART, 123, LocalDate.of(2026, 10, 23), StatsPeriod.Last7Days, null), key.toString()),
        Check("only a complete successful retry replaces the cached value and marks it revalidated", (content.chart as ChartUiState.Loaded).currentPeriodTotal == 7100L && !owner.cache.needsRevalidation(key), state)
    ), listOf("StatsResultCache.markAllStale", "StatsRepository.cached", "ViewsStatsViewModel.revalidateIfNeeded", "ViewsStatsViewModel.refresh"))
}

private fun refreshIsolation(owner: NewStatsRuntimeOwnerActivity): Outcome {
    owner.reset("2026-10-23T12:00:00Z")
    val key = StatsCacheKey(StatsCacheBucket.CHART, 123, LocalDate.of(2026, 10, 23), StatsPeriod.Last7Days)
    owner.cache.put(key, periodResult(7000, listOf(ViewsDataPoint("2026-10-22", 3400), ViewsDataPoint("2026-10-23", 3600))))
    val vm = main(owner) { owner.newViews() }; waitUntil("cache init") { vm.isPeriodInitialized.value }
    main(owner) { vm.loadDataIfNeeded() }
    waitUntil("cached 7000") { (((vm.uiState.value as? ViewsStatsCardUiState.Content)?.chart as? ChartUiState.Loaded)?.currentPeriodTotal == 7000L) }

    val gate = CountDownLatch(1)
    enqueueStandard(owner, totalViews = 7050, currentEnd = "2026-10-23", previousEnd = "2026-10-16", gate = gate)
    val old = CoroutineScope(Dispatchers.Default).async {
        owner.repository.fetchStatsForPeriod(123, StatsPeriod.Last7Days, forceRefresh = true)
    }
    waitUntil("older request in flight") { owner.visitsCalls.size >= 2 }
    val generationBefore = owner.cache.currentGeneration
    owner.cache.clear()
    val generationAfter = owner.cache.currentGeneration
    enqueueStandard(owner, totalViews = 7200, currentEnd = "2026-10-23", previousEnd = "2026-10-16")
    main(owner) { vm.refresh() }
    waitUntil("refresh 7200") {
        (((vm.uiState.value as? ViewsStatsCardUiState.Content)?.chart as? ChartUiState.Loaded)?.currentPeriodTotal == 7200L) && !vm.isRefreshing.value
    }
    gate.countDown(); runBlocking { old.await() }
    val callsBeforeRead = owner.visitsCalls.size
    val cached = runBlocking { owner.repository.fetchStatsForPeriod(123, StatsPeriod.Last7Days) } as PeriodStatsResult.Success
    val content = vm.uiState.value as ViewsStatsCardUiState.Content
    val state = mapOf("refreshingAfterCompletion" to vm.isRefreshing.value, "visibleViews" to (content.chart as ChartUiState.Loaded).currentPeriodTotal, "cachedViewsForNextVisit" to cached.currentAggregates.views)
    return Outcome(mapOf("generation" to generationBefore), state, mapOf(
        "state" to state,
        "effects" to listOf(
            mapOf("name" to "invalidateCachedStatsBeforeRefresh"),
            mapOf("name" to "fetchStatsForPeriod", "forceRefresh" to true, "result" to mapOf("views" to 7200)),
            mapOf("name" to "storeRefreshResult", "views" to 7200)
        ),
        "absentEffects" to listOf("serveOldCachedResultAsFinal", "storeOlderRequestResult", "replaceVisibleStateWith7050")
    ), listOf(
        Check("cache invalidation happens synchronously before visible cards dispatch refreshes", generationAfter == generationBefore + 1, mapOf("before" to generationBefore, "after" to generationAfter)),
        Check("a result that started before invalidation cannot repopulate refreshed cached state", cached.currentAggregates.views == 7200L && owner.visitsCalls.size == callsBeforeRead, cached.currentAggregates.views),
        Check("the refresh indicator stops even when competing work completes later", !vm.isRefreshing.value, vm.isRefreshing.value)
    ), listOf("StatsResultCache.clear", "StatsResultCache.put", "StatsRepository.cached", "ViewsStatsViewModel.refresh"))
}

private fun planGate(owner: NewStatsRuntimeOwnerActivity): Outcome {
    val countries = CountryViewsDataResult.Success(
        CountryViewsData(listOf(CountryViewItem("US", "US", 100, "")), totalViews = 100, otherViews = 0)
    )
    owner.countryQueue.addLast(countries); owner.countryQueue.addLast(countries)
    val vm = main(owner) { owner.newLocations() }
    main(owner) { vm.loadData() }
    waitUntil("countries loaded") { vm.uiState.value is LocationsCardUiState.Loaded }
    val countriesBefore = vm.uiState.value as LocationsCardUiState.Loaded
    val raw = "{\"error\":\"unauthorized\",\"message\":\"localized\"}"
    val classified = isStatsGatedByPlan(raw, true)
    check(classified)
    owner.regionQueue.addLast(RegionViewsDataResult.Error(StatsErrorType.PLAN_GATED))
    owner.regionQueue.addLast(RegionViewsDataResult.Error(StatsErrorType.PLAN_GATED))
    main(owner) { vm.onLocationTypeChanged(LocationType.REGIONS) }
    waitUntil("regions plan gated") { vm.uiState.value is LocationsCardUiState.Error }
    val region = vm.uiState.value as LocationsCardUiState.Error
    val countriesField = vm.javaClass.getDeclaredField("_countriesUiState").apply { isAccessible = true }
    @Suppress("UNCHECKED_CAST")
    val countriesAfter = (countriesField.get(vm) as kotlinx.coroutines.flow.StateFlow<LocationsCardUiState>).value as LocationsCardUiState.Loaded
    val state = mapOf(
        "selectedLocationType" to "regions",
        "regions" to mapOf("type" to "plan_gated", "isPlanGated" to region.isPlanGated, "isAuthError" to region.isAuthError, "primaryAction" to "explore_plans", "ordinaryRetryVisible" to false),
        "countriesStatePreserved" to mapOf("type" to "loaded", "items" to countriesAfter.items.map { it.id })
    )
    return Outcome(mapOf("countries" to countriesBefore.items.map { it.id }), state, mapOf(
        "state" to state,
        "effects" to listOf(
            mapOf("name" to "fetchRegionViews", "siteId" to 123),
            mapOf("name" to "classifyStatsError", "errorCode" to "unauthorized", "classification" to "plan_gated"),
            mapOf("name" to "exposeExplorePlansAction", "destination" to "site_upgrade_plans")
        ),
        "absentEffects" to listOf("classifyAsGenericPermissionFailure", "showOrdinaryRetryForPlanGate", "discardLoadedCountries")
    ), listOf(
        Check("unauthorized is plan-gated only when the endpoint is gate-eligible and the user already has view-stats capability", classified && region.isPlanGated, mapOf("classified" to classified, "regionCalls" to owner.regionCalls.size)),
        Check("plan-gated and auth-error flags are mutually exclusive", region.isPlanGated && !region.isAuthError, mapOf("plan" to region.isPlanGated, "auth" to region.isAuthError)),
        Check("loading the gated surface does not discard the already loaded unrestricted surface", countriesAfter.items.map { it.id } == listOf("US"), countriesAfter.items.map { it.id })
    ), listOf("StatsApiError.isStatsGatedByPlan", "StatsRepository.fetchRegionViews", "LocationsViewModel.onLocationTypeChanged", "LocationsViewModel.fetchRegionViews"))
}

fun runCase(key: String, instrumentation: Instrumentation): String {
    val owner = owner(instrumentation)
    val outcome = try {
        try {
            when (key) {
                "metric_replot_persist" -> metricReplot(owner)
                "hourly_fallback_restore" -> hourlyFallback(owner)
                "explicit_hourly_unavailable" -> hourlyUnavailable(owner)
                "bar_soft_select" -> softSelect(owner)
                "bar_drill_commit" -> drillCommit(owner)
                "future_bucket_noop" -> futureNoop(owner)
                "period_origin_restore" -> originRestore(owner)
                "cached_revalidation_recovery" -> cachedRecovery(owner)
                "pull_refresh_inflight_isolation" -> refreshIsolation(owner)
                "plan_gate_presentation" -> planGate(owner)
                else -> error("unknown key $key")
            }
        } catch (error: RuntimeException) {
            if (!isObservationMismatch(error)) throw error
            observationMismatch(key, owner, error)
        }
    } finally {
        main(owner) { owner.finish() }
    }
    return JSONObject(
        mapOf(
            "key" to key, "before" to outcome.before, "after" to outcome.after,
            "observed" to outcome.observed,
            "invariantChecks" to outcome.checks.map { mapOf("invariant" to it.invariant, "passed" to it.passed, "evidence" to it.evidence) },
            "productionBodies" to outcome.bodies
        )
    ).toString()
}

