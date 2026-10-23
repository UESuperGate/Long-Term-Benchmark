package evaluator.newstats

import android.app.Instrumentation
import android.content.Intent
import evaluator.newstatsbase.NewStatsBaseOwnerActivity
import org.json.JSONObject
import java.util.concurrent.FutureTask

private val invariants = mapOf(
    "metric_replot_persist" to listOf("the persisted semantic choice remains visitors across restoration", "chart header and series represent the same selected metric", "switching metrics does not reload data already present in the period response"),
    "hourly_fallback_restore" to listOf("the hourly views fallback never overwrites the user's visitors preference", "returning to a multi-day period restores the compatible preference", "the bottom row and chart retain one coherent period"),
    "explicit_hourly_unavailable" to listOf("an explicit unsupported hourly metric receives an unavailable answer instead of appearing inert", "the independent bottom-stats row remains usable", "the explicit choice is retained for a compatible period"),
    "bar_soft_select" to listOf("soft selection freezes the Views chart on its committed period", "header, bottom row, highlight, top range, and other cards refer to the same selected bucket", "a bar tap reuses loaded per-bucket data"),
    "bar_drill_commit" to listOf("the given soft selection is established through the real bar-tap path", "committing clears the transient selection before the destination finishes loading", "every visible stats surface receives the committed day"),
    "future_bucket_noop" to listOf("future placeholders occupy chart slots but cannot be selected", "future placeholders are excluded from the elapsed-bucket average", "the chart and all other cards remain on the committed period"),
    "period_origin_restore" to listOf("the persisted configuration is read through the production repository after recreation", "a paged rolling window remains rolling even when its concrete dates form a calendar month", "forward navigation cannot pass the present edge"),
    "cached_revalidation_recovery" to listOf("the failed-revalidation precondition is established through the real screen-entry and refresh path", "request identity includes surface, site, current day, period, and variant", "only a complete successful retry replaces the cached value and marks it revalidated"),
    "pull_refresh_inflight_isolation" to listOf("cache invalidation happens synchronously before visible cards dispatch refreshes", "a result that started before invalidation cannot repopulate refreshed cached state", "the refresh indicator stops even when competing work completes later"),
    "plan_gate_presentation" to listOf("unauthorized is plan-gated only when the endpoint is gate-eligible and the user already has view-stats capability", "plan-gated and auth-error flags are mutually exclusive", "loading the gated surface does not discard the already loaded unrestricted surface")
)

fun runCase(key: String, instrumentation: Instrumentation): String {
    val intent = Intent().setClassName(instrumentation.targetContext.packageName, "evaluator.newstatsbase.NewStatsBaseOwnerActivity").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    val owner = instrumentation.startActivitySync(intent) as NewStatsBaseOwnerActivity
    val task = FutureTask { owner.reachCommonEntry() }
    owner.runOnUiThread(task)
    val after = task.get()
    owner.finish()
    return JSONObject(
        mapOf(
            "key" to key,
            "before" to emptyMap<String, Any>(),
            "after" to after,
            "observed" to JSONObject.NULL,
            "actionPrefix" to mapOf("reachedCommonEntry" to true, "targetActionReachable" to false),
            "invariantChecks" to requireNotNull(invariants[key]).map { mapOf("invariant" to it, "passed" to JSONObject.NULL, "status" to "unobserved_after_missing_action_prefix") },
            "productionBodies" to listOf("ViewsStatsViewModel.onChartTypeChanged", "StatsCardsConfigurationRepository.saveConfiguration")
        )
    ).toString()
}
