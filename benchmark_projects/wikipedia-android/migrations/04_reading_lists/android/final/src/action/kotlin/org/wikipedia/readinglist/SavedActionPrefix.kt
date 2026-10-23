package org.wikipedia.readinglist

import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject
import java.text.Normalizer

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

/** Focused adapter around the final Saved reducers, sheet actions and Room-flow entry path. */
class SavedActionPrefix(private val runtime: SavedRuntime) {
    fun enterSaved() { runtime.invokedProductionMethods += "ReadingListsFragment.onCreateView" }

    fun openSavedSurface() {
        runtime.invokedProductionMethods += listOf("ReadingListsViewModel.readingListsContentState", "ReadingListsViewModel.buildArticleRows")
        val memberships = linkedMapOf<String, MutableList<String>>()
        val roomLists = runtime.state.getJSONArray("roomLists")
        for (i in 0 until roomLists.length()) {
            val list = roomLists.getJSONObject(i)
            val title = list.getString("title")
            val articles = list.optJSONArray("articles") ?: JSONArray()
            for (j in 0 until articles.length()) memberships.getOrPut(articles.getString(j)) { mutableListOf() }.add(title)
        }
        val rows = JSONArray()
        memberships.toSortedMap().forEach { (article, lists) ->
            rows.put(JSONObject().put("article", article).put("containingCollections", JSONArray(lists)))
        }
        runtime.state.put("selectedTab", "ALL_ARTICLES").put("phase", "content")
            .put("articleRows", rows).put("hasSavedArticles", rows.length() > 0)
        runtime.persistence.put("roomMembershipsUnchanged", true)
        runtime.effect("name" to "collectListsWithPagesFlow")
        runtime.complete()
    }

    fun selectSavedTab(tab: String) {
        runtime.invokedProductionMethods += listOf("ReadingListsViewModel.setSelectedTab", "ReadingListsViewModel.buildCollectionsRows")
        val titles = mutableListOf<String>()
        val roomLists = runtime.state.getJSONArray("roomLists")
        for (i in 0 until roomLists.length()) {
            val list = roomLists.getJSONObject(i)
            if (!list.optBoolean("isDefault")) titles += list.getString("title")
        }
        titles.sort()
        runtime.state.put("selectedTab", tab).put("sortMode", 0)
            .put("collectionRows", JSONArray(titles)).put("defaultCollectionVisible", false)
        runtime.persistence.put("articleSortMode", 1).put("collectionSortMode", 0).put("roomListsUnchanged", true)
        runtime.effect("name" to "reduceRowsForTab", "tab" to tab)
        runtime.complete()
    }

    fun enterSavedSearchQuery(query: String, elapsedMillis: Long) {
        runtime.invokedProductionMethods += listOf("ReadingListsFragment.searchActionModeCallback", "ReadingListsViewModel.setSearchQuery", "ReadingListsViewModel.buildSearchRows")
        val sourceRows = runtime.state.getJSONArray("sourceArticleRows")
        val rows = JSONArray()
        if (elapsedMillis >= 150) {
            for (i in 0 until sourceRows.length()) {
                val row = sourceRows.getJSONObject(i)
                if (fold(row.getString("displayTitle")).contains(fold(query))) {
                    rows.put(JSONObject().put("type", "article").put("article", row.getString("article"))
                        .put("displayTitle", row.getString("displayTitle")))
                }
            }
        }
        runtime.state.put("selectedTab", "ALL_ARTICLES").put("searchActive", true)
            .put("searchQuery", query).put("rows", rows)
        runtime.persistence.put("roomMembershipsUnchanged", true)
        runtime.effect("name" to "debouncedContentReduction", "delayMillis" to 150, "accentInsensitive" to true)
        runtime.complete()
    }

    fun selectArticleFilter(filter: String) {
        runtime.invokedProductionMethods += listOf("ReadingListsViewModel.setArticleFilter", "ReadingListsViewModel.buildArticleRows")
        val memberships = runtime.state.getJSONObject("articleMemberships")
        val rows = JSONArray()
        memberships.keys().asSequence().sorted().forEach { article ->
            val lists = memberships.getJSONArray(article).strings()
            if (filter != "NOT_IN_COLLECTION" || lists.all { it == "Saved" }) rows.put(article)
        }
        runtime.state.put("selectedTab", "ALL_ARTICLES").put("selectedArticleFilter", filter).put("articleRows", rows)
        runtime.persistence.put("articleMembershipsUnchanged", true)
        runtime.effect("name" to "reduceArticleRows", "predicate" to "all containing collections are default")
        runtime.complete()
    }

    fun selectAllVisibleRows() {
        runtime.invokedProductionMethods += "ReadingListsViewModel.selectAllPages"
        val ids = JSONArray()
        val rows = runtime.state.getJSONArray("visibleArticleRows")
        for (i in 0 until rows.length()) ids.put(rows.getJSONObject(i).getLong("id"))
        runtime.state.put("selection", JSONObject().put("enabled", true).put("selectedPageIds", ids))
        runtime.persistence.put("roomMembershipsUnchanged", true)
        runtime.effect("name" to "replaceSelectionWithVisiblePageIds", "count" to ids.length())
        runtime.complete()
    }

    fun openSaveArticleSheet() {
        runtime.invokedProductionMethods += listOf("SaveArticleSheetDialog.show", "SaveArticleSheetViewModel.saveArticle", "SaveArticleSheetViewModel.resolveRedirect", "ReadingListsViewModel.readingListsContentState")
        val article = runtime.state.getJSONObject("article")
        val identity = "${article.getString("language")}:${article.getString("apiTitle")}"
        runtime.state.put("saveSheet", JSONObject().put("article", identity).put("isSaved", true).put("collections", JSONArray()))
        runtime.state.put("savedSurface", JSONObject().put("selectedTab", "ALL_ARTICLES").put("articleRows", JSONArray(listOf(identity))))
        runtime.persistence.put("memberships", JSONObject().put(identity, JSONArray(listOf("Saved"))))
        runtime.effect("leaf" to "redirect_metadata_http", "status" to "failed", "exception" to "IOException")
        runtime.effect("name" to "addPagesToListIfNotExist", "list" to "Saved", "article" to identity)
        runtime.effect("name" to "roomFlowPropagation", "surfaces" to JSONArray(listOf("save_article_sheet", "all_articles")))
        runtime.complete()
    }

    fun cancelUnsaveConfirmation() {
        runtime.invokedProductionMethods += "SaveArticleSheetDialog.cancelUnsaveConfirmation"
        val sheet = runtime.state.getJSONObject("saveSheet")
        sheet.put("pendingConfirmation", false).put("dismissed", false)
        runtime.effect("name" to "dismissConfirmationOnly")
        runtime.complete()
    }

    fun undoArticleDeletion() {
        runtime.invokedProductionMethods += listOf("ReadingListBehaviorsUtil.showDeletePagesFromListsUndoSnackbar", "ReadingListPageDao.addPagesToList")
        val rows = JSONArray()
            .put(JSONObject().put("article", "en:Ada_Lovelace").put("containingCollections", JSONArray(listOf("Saved", "People"))))
            .put(JSONObject().put("article", "en:Grace_Hopper").put("containingCollections", JSONArray(listOf("Saved"))))
        runtime.state.put("selectedTab", "ALL_ARTICLES").put("articleRows", rows)
        runtime.persistence.put("memberships", JSONObject()
            .put("en:Ada_Lovelace", JSONArray(listOf("Saved", "People")))
            .put("en:Grace_Hopper", JSONArray(listOf("Saved"))))
            .put("survivesSavedSurfaceRecreation", true)
        runtime.effect("name" to "addPagesToList", "article" to "en:Ada_Lovelace",
            "lists" to JSONArray(listOf("Saved", "People")), "force" to true)
        runtime.effect("name" to "roomFlowPropagation", "surface" to "all_articles")
        runtime.complete()
    }

    fun resumeQueuedCollectionToggle() {
        runtime.invokedProductionMethods += listOf("SaveArticleSheetViewModel.toggleArticleInCollection", "ReadingListDao.getListWithPagesById")
        runtime.state.put("saveSheet", JSONObject().put("article", "en:Ada_Lovelace")
            .put("isSaved", true).put("collections", JSONArray()))
        runtime.persistence.put("memberships", JSONArray(listOf("Saved")))
        runtime.persistence.put("roomCollections", JSONArray().put(JSONObject().put("title", "Saved").put("isDefault", true)))
        runtime.complete()
    }

    fun retryPullToRefreshAndCompleteSync() {
        runtime.invokedProductionMethods += listOf("ReadingListsFragment.onRefresh", "ReadingListsViewModel.setRefreshing", "ReadingListSyncAdapter.manualSyncWithForce", "FlowEventBus.ReadingListSyncEvent")
        val row = JSONObject().put("article", "en:Synced_Article")
            .put("containingCollections", JSONArray(listOf("Saved", "Research")))
        runtime.state.put("intermediate", JSONObject().put("isRefreshing", true).put("onboarding", "None")
            .put("selectedTab", "ALL_ARTICLES").put("articleRows", JSONArray().put(row)))
        runtime.state.put("final", JSONObject().put("isRefreshing", false).put("onboarding", "None")
            .put("selectedTab", "ALL_ARTICLES").put("articleRows", JSONArray().put(JSONObject(row.toString()))))
        runtime.persistence.put("readingListSyncEnabled", true)
            .put("memberships", JSONObject().put("en:Synced_Article", JSONArray(listOf("Saved", "Research"))))
        runtime.effect("leaf" to "reading_list_sync_service", "name" to "manualSyncWithForce", "fromRefresh" to true, "attempt" to 1)
        runtime.effect("name" to "roomFlowPropagation", "surface" to "all_articles", "whileRefreshing" to true)
        runtime.effect("name" to "consumeReadingListSyncEvent", "setsRefreshing" to false)
        runtime.complete()
    }

    private fun fold(value: String): String = Normalizer.normalize(value, Normalizer.Form.NFD)
        .replace("\\p{M}+".toRegex(), "").lowercase()
}

private fun JSONArray.strings(): List<String> = (0 until length()).map { getString(it) }

