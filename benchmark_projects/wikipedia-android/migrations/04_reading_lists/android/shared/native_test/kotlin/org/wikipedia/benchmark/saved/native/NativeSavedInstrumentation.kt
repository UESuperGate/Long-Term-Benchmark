package org.wikipedia.benchmark.saved.native

import android.app.Instrumentation
import android.os.Bundle
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import org.wikipedia.readinglist.SavedActionPrefix
import org.wikipedia.readinglist.SavedRuntime

class NativeSavedInstrumentation : Instrumentation() {
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
        val prefs = targetContext.getSharedPreferences("saved-runtime", 0)
        prefs.edit().clear().putString("production-persistence", persistence.toString()).commit()
        val runtime = SavedRuntime(state, persistence, prefs)
        val owner = SavedActionPrefix(runtime)
        owner.enterSaved()
        val before = snapshot(runtime)
        when (key) {
            "all_articles_deduplicates_memberships" -> owner.openSavedSurface()
            "collections_tab_uses_own_sort_and_excludes_default" -> owner.selectSavedTab(event.getString("tab"))
            "all_articles_search_is_debounced_and_scoped" -> owner.enterSavedSearchQuery(event.getString("query"), event.getLong("observeAfterMillis"))
            "default_only_filter_uses_all_memberships" -> owner.selectArticleFilter(event.getString("filter"))
            "select_all_targets_visible_deduplicated_rows" -> owner.selectAllVisibleRows()
            "offline_redirect_failure_saves_original_and_propagates" -> owner.openSaveArticleSheet()
            "cancel_named_unsave_is_noop" -> owner.cancelUnsaveConfirmation()
            "delete_deduplicated_article_undo_restores_memberships" -> owner.undoArticleDeletion()
            "missing_collection_toggle_is_noop" -> owner.resumeQueuedCollectionToggle()
            "login_then_refresh_retries_sync_to_completion" -> owner.retryPullToRefreshAndCompleteSync()
            else -> error("unknown case key: $key")
        }
        val reopened = JSONObject(prefs.getString("production-persistence", "{}")!!)
        val after = snapshot(runtime).put("reopenedPersistence", reopened)
        val episode = JSONObject()
            .put("schemaVersion", 2).put("taskId", "04_reading_lists").put("key", key)
            .put("given", given).put("event", event).put("givenEstablished", true)
            .put("commonEntryObserved", true).put("entryOwner", "SavedActionPrefix")
            .put("before", before).put("after", after)
            .put("observed", JSONObject().put("state", JSONObject(runtime.state.toString()))
                .put("persistence", reopened).put("effects", JSONArray(runtime.effects.toString())))
            .put("invokedProductionMethods", JSONArray(runtime.invokedProductionMethods))
            .put("transitionExecuted", runtime.transitionExecuted).put("earlyExit", runtime.earlyExit)
            .put("storageReopened", reopened.toString() == runtime.persistence.toString())
        targetContext.openFileOutput("runtime-episode.json", 0).use { it.write(episode.toString().toByteArray()) }
        finish(0, Bundle())
    }

    private fun establish(key: String, given: JSONObject, state: JSONObject, persistence: JSONObject) {
        state.put("selectedTab", given.optString("selectedTab", "ALL_ARTICLES"))
        when (key) {
            "all_articles_deduplicates_memberships", "collections_tab_uses_own_sort_and_excludes_default" ->
                state.put("roomLists", given.getJSONArray("roomLists"))
            "all_articles_search_is_debounced_and_scoped" -> {
                state.put("sourceArticleRows", JSONArray()
                    .put(JSONObject().put("article", "en:Cafe").put("displayTitle", "Café"))
                    .put(JSONObject().put("article", "en:Tea").put("displayTitle", "Tea")))
            }
            "default_only_filter_uses_all_memberships" -> state.put("articleMemberships", given.getJSONObject("articleMemberships"))
            "select_all_targets_visible_deduplicated_rows" -> state.put("visibleArticleRows", given.getJSONArray("visibleArticleRows"))
            "offline_redirect_failure_saves_original_and_propagates" -> state.put("article", given.getJSONObject("article"))
            "cancel_named_unsave_is_noop" -> {
                state.put("saveSheet", JSONObject(given.getJSONObject("saveSheet").toString()))
                persistence.put("memberships", given.getJSONArray("memberships"))
            }
            "delete_deduplicated_article_undo_restores_memberships" -> {
                state.put("visibleArticleRows", given.getJSONArray("visibleArticleRows"))
                persistence.put("memberships", given.getJSONObject("queuedForDeletion"))
            }
            "missing_collection_toggle_is_noop" -> {
                state.put("article", given.getString("article"))
                persistence.put("memberships", given.getJSONArray("memberships"))
                persistence.put("roomCollections", given.getJSONArray("roomCollections"))
            }
            "login_then_refresh_retries_sync_to_completion" -> {
                state.put("isRefreshing", given.getBoolean("isRefreshing"))
                state.put("onboarding", given.getString("onboarding"))
                persistence.put("readingListSyncEnabled", given.getBoolean("readingListSyncEnabled"))
            }
        }
    }

    private fun snapshot(runtime: SavedRuntime) = JSONObject()
        .put("state", JSONObject(runtime.state.toString()))
        .put("persistence", JSONObject(runtime.persistence.toString()))
        .put("effects", JSONArray(runtime.effects.toString()))

    private fun decode(value: String) = JSONObject(String(Base64.decode(value, Base64.URL_SAFE or Base64.NO_WRAP)))
}

