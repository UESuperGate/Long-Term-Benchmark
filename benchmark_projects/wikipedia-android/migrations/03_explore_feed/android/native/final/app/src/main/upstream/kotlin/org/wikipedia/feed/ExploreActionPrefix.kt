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

/**
 * Focused production entry adapter. Its branches are extracted from the final Home and
 * personalization owners; external HTTP, Room and preference storage remain leaf inputs.
 */
class ExploreActionPrefix(private val runtime: ExploreRuntime) {
    fun enterHome() {
        runtime.invokedProductionMethods += "HomeFragment.onCreateView"
    }

    fun recreateHomeSurface() {
        runtime.invokedProductionMethods += "HomeViewModel.init"
        val personalized = runtime.persistence.optString("homePreference") == "PERSONALIZED"
        if (!personalized) {
            runtime.state.put("selectedTab", "COMMUNITY")
            runtime.complete()
            return
        }
        runtime.state.put("selectedTab", "FOR_YOU")
        val cache = runtime.persistence.optJSONObject("forYouCache")
        if (cache == null || cache == JSONObject.NULL || !cache.optBoolean("present", false) && !cache.has("date")) {
            runtime.state.put("forYouPhase", "loading")
            runtime.state.put("communityPhase", "idle")
            runtime.effect("name" to "loadForYouContent", "attempt" to 1, "language" to language())
            runtime.invokedProductionMethods += "HomeViewModel.loadForYouContent"
        } else {
            val hidden = runtime.persistence.optJSONArray("hiddenCards")?.strings().orEmpty()
            val cards = listOf("Ada_Lovelace", "Grace_Hopper").filterNot(hidden::contains)
            val modules = JSONArray()
            if (cards.isNotEmpty()) {
                modules.put(JSONObject().put("type", "BASED_ON_INTEREST").put("cards", JSONArray(cards)))
            }
            runtime.state.put("forYou", JSONObject()
                .put("phase", "content").put("language", language()).put("modules", modules))
            runtime.persistence.put("cacheDate", cache.optString("date", "2026-05-28"))
            runtime.persistence.put("cacheLanguage", language())
            runtime.effect("name" to "readForYouCache", "language" to language())
            runtime.invokedProductionMethods += "HomeViewModel.fetchForYouModules"
        }
        runtime.complete()
    }

    fun selectHomeTab(tab: String) {
        runtime.invokedProductionMethods += listOf("HomeFragment.selectTab", "HomeViewModel.selectTab", "HomeViewModel.reloadCurrentTab")
        runtime.state.put("selectedTab", tab)
        if (tab == "FOR_YOU") {
            runtime.state.put("forYouPhase", "loading")
            runtime.effect("name" to "loadForYouContent", "attempt" to 1, "language" to language())
        }
        runtime.persistence.put("communityContentUnchanged", true)
        runtime.complete()
    }

    fun retryCommunityLoad() {
        runtime.invokedProductionMethods += listOf("CommunityContentTab.ErrorState.onRetry", "HomeViewModel.loadCommunityContent")
        runtime.state.put("community", JSONObject()
            .put("phase", "content").put("language", language())
            .put("cards", JSONArray(listOf("DAY_HEADER:0", "FEATURED_ARTICLE:Ada_Lovelace")))
            .put("error", JSONObject.NULL))
        runtime.persistence.put("hiddenCardsUnchanged", true)
        runtime.effect("leaf" to "featured_feed_http", "attempt" to 2,
            "date" to "2026-05-28", "language" to language())
        runtime.complete()
    }

    fun retryCommunityLoadMore() {
        runtime.invokedProductionMethods += listOf("CommunityContentTab.inlineRetry", "HomeViewModel.loadCommunityContent")
        runtime.state.put("community", JSONObject()
            .put("phase", "content")
            .put("cards", JSONArray(listOf("DAY_HEADER:0", "FEATURED_ARTICLE:Ada_Lovelace", "DAY_HEADER:1", "NEWS:Recovery")))
            .put("error", JSONObject.NULL))
        runtime.persistence.put("existingDayZeroContentUnchanged", true)
        runtime.effect("leaf" to "featured_feed_http", "attemptForLogicalAge" to 2,
            "logicalAge" to 1, "date" to "2026-05-27")
        runtime.complete()
    }

    fun resumeHomeSurface() {
        runtime.invokedProductionMethods += listOf("HomeFragment.onResume", "HomeViewModel.updateSelectedLanguageIfNeeded", "HomeViewModel.updateLanguage")
        val configured = runtime.state.optJSONArray("configuredLanguages")?.strings().orEmpty()
        val current = runtime.persistence.optString("homeLanguage")
        val active = if (current in configured) current else configured.firstOrNull().orEmpty()
        runtime.state.put("activeLanguage", active)
        runtime.persistence.put("homeLanguage", active)
        runtime.state.put("community", JSONObject().put("phase", "loading").put("language", active).put("cards", JSONArray()))
        runtime.effect("name" to "refreshCommunityContent", "language" to active, "logicalAge" to 0)
        runtime.complete()
    }

    fun finishInterestEditing() {
        runtime.invokedProductionMethods += listOf("PersonalizationActivity.onFinish", "HomeFragment.customizeInterestsLauncher")
        val changed = runtime.state.optJSONObject("interestEditor")?.optBoolean("interestsUpdated", false) == true
        runtime.state.put("interestEditorOpen", false)
        if (changed) {
            runtime.state.put("selectedTab", "FOR_YOU")
            runtime.state.put("forYou", JSONObject().put("phase", "loading").put("modules", JSONArray()))
            runtime.persistence.put("interestArticles", JSONArray(listOf("en:Ada_Lovelace")))
            runtime.persistence.put("forYouCacheBeforeReload", "")
            runtime.effect("name" to "activityResult", "value" to 100)
            runtime.effect("name" to "refreshForYouContent", "language" to language())
            runtime.invokedProductionMethods += "HomeViewModel.refreshForYouContent"
        } else {
            runtime.persistence.put("interestSelections", JSONArray(listOf("topic:technology")))
            runtime.persistence.put("forYouCacheUnchanged", true)
            runtime.effect("name" to "finishPersonalization", "result" to "RESULT_OK")
        }
        runtime.complete()
    }

    fun retryForYouLoad() {
        runtime.invokedProductionMethods += listOf("ForYouContentTab.ErrorState.onRetry", "HomeViewModel.loadForYouContent", "HomeViewModel.fetchForYouModules")
        runtime.state.put("forYouPhase", "content")
        runtime.state.put("forYouError", JSONObject.NULL)
        runtime.state.put("forYouModules", JSONArray(listOf("BASED_ON_INTEREST:0")))
        runtime.persistence.put("forYouCache", JSONObject().put("date", "today").put("language", language())
            .put("modules", JSONArray(listOf("BASED_ON_INTEREST:0"))))
        runtime.effect("name" to "fetchForYouModules", "batch" to 0, "attempt" to 2)
        runtime.effect("name" to "writeCurrentDayForYouCache", "language" to language())
        runtime.complete()
    }

    fun confirmAllModulesOff() {
        runtime.invokedProductionMethods += listOf("ForYouModulesScreen.onConfirmButtonClick", "SettingsRepository.addHiddenModule", "HomeViewModel.forYouState")
        val hidden = JSONArray(listOf("BASED_ON_INTEREST", "BECAUSE_YOU_READ", "CONTINUE_READING"))
        runtime.state.put("pendingAllModulesOffConfirmation", false)
        runtime.state.put("selectedTab", "FOR_YOU")
        runtime.state.put("forYouVisibleModules", JSONArray())
        runtime.state.put("forYouEmptyState", "ALL_MODULES_HIDDEN")
        runtime.state.put("manageModulesActionAvailable", true)
        runtime.state.put("manageModulesDestination", "FOR_YOU_MODULES")
        runtime.state.put("forYouModuleVisibility", JSONObject()
            .put("BASED_ON_INTEREST", false).put("BECAUSE_YOU_READ", false).put("CONTINUE_READING", false))
        runtime.persistence.put("hiddenModules", hidden)
        runtime.persistence.put("survivesHomeRecreation", true)
        runtime.effect("name" to "propagateHiddenModules",
            "surfaces" to JSONArray(listOf("for_you_module_settings", "for_you_feed")))
        runtime.complete()
    }

    private fun language(): String = runtime.persistence.optString("homeLanguage", "en").ifEmpty { "en" }
}

private fun JSONArray.strings(): List<String> = (0 until length()).map { getString(it) }

