package evaluator.sitepicker

import android.app.Instrumentation
import android.content.Intent
import evaluator.sitepickerbase.SitePickerBaseOwnerActivity
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

private val invariants = mapOf(
    "grouped_open" to listOf("each available site appears exactly once", "a pinned site is excluded from the recent section even when its id is in recent preferences", "opening the picker does not change the active site"),
    "search_clear" to listOf("the search precondition is established through the real query input", "clearing search restores the complete pinned, recent, and remaining grouping", "a site present in both preferences appears only in the pinned section"),
    "pin_mode_row_noop" to listOf("the pin-mode precondition is established through the real edit-pins action", "row-body clicks and long presses are ineligible while pin mode is active", "only an explicit pin control may change the pinned set"),
    "pin_persist_reopen" to listOf("the persisted pin was created through the real pin control before reopening", "reopening observes the pin from durable application state", "the pinned site appears exactly once and remains outside the recent section"),
    "unpin_regroup" to listOf("unpinning does not erase the site's existing recent membership", "the site appears exactly once after regrouping", "editing remains active until the user explicitly finishes it"),
    "select_recent_propagation" to listOf("the recent-state precondition is established through the real selection flow", "the selected site is the first recent site on the next open even with fewer than 11 sites", "pinned sites remain excluded from recent grouping"),
    "refresh_failure_retry" to listOf("the failure precondition is established through the real refresh input and leaves refreshing false", "retry rebuilds groups from the successful store contents", "neither failure nor retry changes the active site"),
    "wpcom_long_press_noop" to listOf("a long press on a WordPress.com-accessible site is a no-op in the redesigned picker", "the row remains visible and selectable", "the active site is unchanged"),
    "restore_search_pin_mode" to listOf("recreation restores both the active query and pin-editing semantics", "restoration does not mutate persistent pin or recent state", "the restored row remains ineligible for site selection until pin mode ends"),
    "restricted_mode_selection" to listOf("management restrictions do not prevent selection of an otherwise valid self-hosted site", "restricted mode hides both pin editing and site creation", "selection uses the same result contract as default mode"),
)

fun runCase(key:String,instrumentation:Instrumentation):String {
    val owner=instrumentation.startActivitySync(Intent(instrumentation.targetContext,SitePickerBaseOwnerActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as SitePickerBaseOwnerActivity
    val common=mapOf("activityClass" to owner::class.java.name,"legacyAction" to owner.viewModel.onActionTriggered.value?.peekContent()?.javaClass?.simpleName,"redesignedPickerEntryPresent" to false)
    owner.finish()
    val checks=JsonArray(invariants.getValue(key).map{JsonObject(mapOf("invariant" to JsonPrimitive(it),"passed" to JsonNull,"status" to JsonPrimitive("unobserved_after_missing_action_prefix")))})
    return JsonObject(mapOf("key" to JsonPrimitive(key),"before" to JsonObject(emptyMap()),"after" to JsonObject(common.mapValues{JsonPrimitive(it.value.toString())}),"observed" to JsonNull,"invariantChecks" to checks,"productionBodies" to JsonArray(listOf(JsonPrimitive("SitePickerViewModel.onContinueFlowSelected"))),"actionPrefix" to JsonObject(mapOf("reachedCommonEntry" to JsonPrimitive(true),"targetActionReachable" to JsonPrimitive(false))))).toString()
}
