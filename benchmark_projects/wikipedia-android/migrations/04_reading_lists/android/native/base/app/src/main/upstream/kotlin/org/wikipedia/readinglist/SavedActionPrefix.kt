package org.wikipedia.readinglist

import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject

class SavedRuntime(val state: JSONObject, val persistence: JSONObject, private val preferences: SharedPreferences) {
    val effects = JSONArray()
    val invokedProductionMethods = mutableListOf<String>()
    var transitionExecuted = false
    var earlyExit = ""
    fun effect(vararg values: Pair<String, Any?>) {
        effects.put(JSONObject().apply { values.forEach { (key, value) -> put(key, value) } })
    }
    fun complete() {
        preferences.edit().putString("production-persistence", persistence.toString()).commit()
        transitionExecuted = true
    }
}

/** Common legacy Saved entry retained at the immutable base boundary. */
class SavedActionPrefix(private val runtime: SavedRuntime) {
    fun enterSaved() { runtime.invokedProductionMethods += "ReadingListsFragment.onCreateView" }
    private fun unavailable(event: String) {
        runtime.invokedProductionMethods += "ReadingListsFragment.$event"
        runtime.earlyExit = "legacy_saved_has_no_collections_redesign_transition"
    }
    fun openSavedSurface() = unavailable("openSavedSurface")
    fun selectSavedTab(tab: String) = unavailable("selectSavedTab:$tab")
    fun enterSavedSearchQuery(query: String, elapsedMillis: Long) = unavailable("enterSavedSearchQuery:$query:$elapsedMillis")
    fun selectArticleFilter(filter: String) = unavailable("selectArticleFilter:$filter")
    fun selectAllVisibleRows() = unavailable("selectAllVisibleRows")
    fun openSaveArticleSheet() = unavailable("openSaveArticleSheet")
    fun cancelUnsaveConfirmation() = unavailable("cancelUnsaveConfirmation")
    fun undoArticleDeletion() = unavailable("undoArticleDeletion")
    fun resumeQueuedCollectionToggle() = unavailable("resumeQueuedCollectionToggle")
    fun retryPullToRefreshAndCompleteSync() = unavailable("retryPullToRefreshAndCompleteSync")
}

