package org.wikipedia.feed

import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject

class ExploreRuntime(
    val state: JSONObject,
    val persistence: JSONObject,
    private val preferences: SharedPreferences,
) {
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

/** Common legacy Explore entry retained at the immutable base boundary. */
class ExploreActionPrefix(private val runtime: ExploreRuntime) {
    fun enterHome() {
        runtime.invokedProductionMethods += "FeedFragment.onCreateView"
    }

    private fun unavailable(event: String) {
        runtime.invokedProductionMethods += "FeedFragment.$event"
        runtime.earlyExit = "legacy_explore_has_no_home_redesign_transition"
    }

    fun recreateHomeSurface() = unavailable("recreateHomeSurface")
    fun selectHomeTab(tab: String) = unavailable("selectHomeTab:$tab")
    fun retryCommunityLoad() = unavailable("retryCommunityLoad")
    fun retryCommunityLoadMore() = unavailable("retryCommunityLoadMore")
    fun resumeHomeSurface() = unavailable("resumeHomeSurface")
    fun finishInterestEditing() = unavailable("finishInterestEditing")
    fun retryForYouLoad() = unavailable("retryForYouLoad")
    fun confirmAllModulesOff() = unavailable("confirmAllModulesOff")
}

