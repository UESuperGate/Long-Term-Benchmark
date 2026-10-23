package org.wikipedia.benchmark.explore.native

import android.app.Instrumentation
import android.os.Bundle
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import org.wikipedia.feed.ExploreActionPrefix
import org.wikipedia.feed.ExploreRuntime

class NativeExploreInstrumentation : Instrumentation() {
    private lateinit var arguments: Bundle

    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        this.arguments = arguments ?: Bundle.EMPTY
        start()
    }

    override fun onStart() {
        val key = arguments.getString("caseKey") ?: error("caseKey missing")
        val given = decode(arguments.getString("given") ?: error("given missing"))
        val event = decode(arguments.getString("event") ?: error("event missing"))
        val state = JSONObject()
        val persistence = JSONObject()
        establish(key, given, state, persistence)
        val prefs = targetContext.getSharedPreferences("explore-runtime", 0)
        prefs.edit().clear().putString("production-persistence", persistence.toString()).commit()
        val runtime = ExploreRuntime(state, persistence, prefs)
        val owner = ExploreActionPrefix(runtime)
        owner.enterHome()
        val before = snapshot(runtime)
        when (key) {
            "personalized_preference_restored", "foryou_same_day_cache_restored_and_filtered" -> owner.recreateHomeSurface()
            "switch_tab_lazy_load_preserves_community" -> owner.selectHomeTab(event.getString("tab"))
            "community_initial_retry_same_day" -> owner.retryCommunityLoad()
            "community_inline_retry_preserves_content" -> owner.retryCommunityLoadMore()
            "unavailable_language_falls_back" -> owner.resumeHomeSurface()
            "interest_edit_refreshes_foryou", "unchanged_interest_edit_is_noop" -> owner.finishInterestEditing()
            "foryou_initial_retry_same_batch" -> owner.retryForYouLoad()
            "foryou_all_modules_hidden_propagates" -> owner.confirmAllModulesOff()
            else -> error("unknown case key: $key")
        }
        val reopened = JSONObject(prefs.getString("production-persistence", "{}")!!)
        val after = snapshot(runtime).put("reopenedPersistence", reopened)
        val episode = JSONObject()
            .put("schemaVersion", 2)
            .put("taskId", "03_explore_feed")
            .put("key", key)
            .put("given", given)
            .put("event", event)
            .put("givenEstablished", true)
            .put("commonEntryObserved", true)
            .put("entryOwner", "ExploreActionPrefix")
            .put("before", before)
            .put("after", after)
            .put("observed", JSONObject().put("state", JSONObject(runtime.state.toString()))
                .put("persistence", reopened).put("effects", JSONArray(runtime.effects.toString())))
            .put("invokedProductionMethods", JSONArray(runtime.invokedProductionMethods))
            .put("transitionExecuted", runtime.transitionExecuted)
            .put("earlyExit", runtime.earlyExit)
            .put("storageReopened", reopened.toString() == runtime.persistence.toString())
        targetContext.openFileOutput("runtime-episode.json", 0).use { it.write(episode.toString().toByteArray()) }
        finish(0, Bundle())
    }

    private fun establish(key: String, given: JSONObject, state: JSONObject, persistence: JSONObject) {
        persistence.put("homeLanguage", given.optString("homeLanguage", given.optString("persistedHomeLanguage", "en")))
        state.put("selectedTab", given.optString("selectedTab", "COMMUNITY"))
        when (key) {
            "personalized_preference_restored" -> {
                persistence.put("homePreference", given.getString("homePreference"))
                state.put("configuredLanguages", given.getJSONArray("configuredLanguages"))
            }
            "switch_tab_lazy_load_preserves_community" -> {
                state.put("community", given.getJSONObject("community"))
                state.put("forYou", given.getJSONObject("forYou"))
            }
            "community_initial_retry_same_day", "community_inline_retry_preserves_content" ->
                state.put("community", given.getJSONObject("community"))
            "unavailable_language_falls_back" -> {
                state.put("configuredLanguages", given.getJSONArray("configuredLanguages"))
                state.put("community", given.getJSONObject("community"))
                state.put("forYou", given.getJSONObject("forYou"))
            }
            "foryou_same_day_cache_restored_and_filtered" -> {
                persistence.put("homePreference", given.getString("homePreference"))
                persistence.put("forYouCache", given.getJSONObject("persistedForYouCache"))
                persistence.put("hiddenCards", given.getJSONArray("persistedHiddenCards"))
            }
            "interest_edit_refreshes_foryou", "unchanged_interest_edit_is_noop" -> {
                state.put("interestEditor", given.getJSONObject("interestEditor"))
                if (given.has("forYouModules")) state.put("forYouModules", given.getJSONArray("forYouModules"))
                if (given.has("forYouState")) state.put("forYouState", given.getJSONObject("forYouState"))
                given.optJSONObject("forYouCache")?.let { persistence.put("forYouCache", it) }
                if (key == "unchanged_interest_edit_is_noop") state.put("forYouPhase", "content")
            }
            "foryou_initial_retry_same_batch" -> {
                state.put("forYouModules", given.getJSONArray("forYouModules"))
                state.put("forYouPhase", given.getString("forYouPhase"))
                state.put("forYouError", given.getString("forYouError"))
                state.put("communityPhase", given.getString("communityPhase"))
            }
            "foryou_all_modules_hidden_propagates" -> {
                state.put("pendingAllModulesOffConfirmation", true)
                persistence.put("hiddenModules", given.getJSONArray("hiddenModules"))
            }
        }
    }

    private fun snapshot(runtime: ExploreRuntime) = JSONObject()
        .put("state", JSONObject(runtime.state.toString()))
        .put("persistence", JSONObject(runtime.persistence.toString()))
        .put("effects", JSONArray(runtime.effects.toString()))

    private fun decode(value: String) = JSONObject(String(Base64.decode(value, Base64.URL_SAFE or Base64.NO_WRAP)))
}

