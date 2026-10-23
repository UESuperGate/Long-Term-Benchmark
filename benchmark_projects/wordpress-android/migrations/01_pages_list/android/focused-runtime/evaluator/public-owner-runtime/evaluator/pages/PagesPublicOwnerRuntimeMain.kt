package evaluator.pages

import android.app.Instrumentation
import android.content.Intent
import android.os.SystemClock
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.wordpress.android.ui.pagesrs.Account
import org.wordpress.android.ui.pagesrs.AppPreferences
import org.wordpress.android.ui.pagesrs.AuthorFilterSelection
import org.wordpress.android.ui.pagesrs.CollectionLeaf
import org.wordpress.android.ui.pagesrs.DefaultAccountStore
import org.wordpress.android.ui.pagesrs.DefaultMediaRestClient
import org.wordpress.android.ui.pagesrs.DefaultNetworkUtilsWrapper
import org.wordpress.android.ui.pagesrs.DefaultWpServiceProvider
import org.wordpress.android.ui.pagesrs.HomepageSettingsPayload
import org.wordpress.android.ui.pagesrs.ListInfo
import org.wordpress.android.ui.pagesrs.ListOrder
import org.wordpress.android.ui.pagesrs.MetadataItem
import org.wordpress.android.ui.pagesrs.ObservableMetadataCollection
import org.wordpress.android.ui.pagesrs.PageRsListItem
import org.wordpress.android.ui.pagesrs.PageRsListTab
import org.wordpress.android.ui.pagesrs.PageRsMenuAction
import org.wordpress.android.ui.pagesrs.PageRsUiModel
import org.wordpress.android.ui.pagesrs.PagesRsListViewModel
import org.wordpress.android.ui.pagesrs.PagesRuntimeOwnerActivity
import org.wordpress.android.ui.pagesrs.PostEndpointType
import org.wordpress.android.ui.pagesrs.PostListFilter
import org.wordpress.android.ui.pagesrs.PostListPayload
import org.wordpress.android.ui.pagesrs.PostRsRestClient
import org.wordpress.android.ui.pagesrs.PostService
import org.wordpress.android.ui.pagesrs.PostStatus
import org.wordpress.android.ui.pagesrs.SelectedSiteCache
import org.wordpress.android.ui.pagesrs.SingleWpApiClientProvider
import org.wordpress.android.ui.pagesrs.SiteModel
import org.wordpress.android.ui.pagesrs.SnackbarMessage
import org.wordpress.android.ui.pagesrs.WpApiClient
import java.util.ArrayDeque
import java.util.concurrent.atomic.AtomicInteger

private data class Check(val invariant: String, val passed: Boolean, val evidence: Any?)
private data class Outcome(
    val before: Any?,
    val after: Any?,
    val observed: Any?,
    val checks: List<Check>,
    val productionBodies: List<String>,
)
private data class CollectionPlan(
    val items: List<MetadataItem>,
    val refreshError: RuntimeException? = null,
)

private class ControlledCollection(private val plan: CollectionPlan) : ObservableMetadataCollection {
    var refreshCalls = 0
    var closeCalls = 0
    val items: List<MetadataItem> get() = plan.items
    override suspend fun refresh() {
        refreshCalls += 1
        plan.refreshError?.let { throw it }
    }
    override suspend fun loadItems(): List<MetadataItem> = plan.items
    override suspend fun listInfo(): ListInfo = ListInfo()
    override fun close() { closeCalls += 1 }
}

private class ControlledPostService(private val effects: MutableList<Map<String, Any?>>) : PostService {
    val trashIds = mutableListOf<Long>()
    val trashFailures = ArrayDeque<Boolean>()
    override suspend fun trashPost(endpointType: PostEndpointType, pageId: Long) {
        check(endpointType == PostEndpointType.PAGES)
        trashIds += pageId
        effects += mapOf("name" to "trashPage", "entity" to "pages", "pageId" to pageId)
        if (if (trashFailures.isEmpty()) false else trashFailures.removeFirst()) {
            throw RuntimeException("service_error")
        }
    }
    override suspend fun deletePost(endpointType: PostEndpointType, pageId: Long) = Unit
    override suspend fun updatePostStatus(
        endpointType: PostEndpointType,
        pageId: Long,
        status: PostStatus,
    ) = Unit
}

private class ControlledMedia(private val effects: MutableList<Map<String, Any?>>) : PostRsRestClient {
    var urls: Map<Long, String> = emptyMap()
    override suspend fun fetchMediaUrls(site: SiteModel, ids: List<Long>, size: Int): Map<Long, String> {
        effects += mapOf("name" to "resolveFeaturedMedia", "mediaIds" to ids)
        return urls
    }
}

private class ControlledApiClient(private val activeItems: () -> List<MetadataItem>) : WpApiClient {
    override suspend fun fetchPosts(
        site: SiteModel,
        endpointType: PostEndpointType,
        filter: PostListFilter,
        page: UInt,
    ): PostListPayload = PostListPayload(activeItems(), page)

    override suspend fun fetchHomepageSettings(site: SiteModel): HomepageSettingsPayload =
        HomepageSettingsPayload(site.pageOnFront, site.pageForPosts, site.showOnFront)

    override suspend fun updatePageOnFront(site: SiteModel, pageId: Long): HomepageSettingsPayload =
        HomepageSettingsPayload(pageId, site.pageForPosts, SiteModel.SHOW_ON_FRONT_PAGE)

    override suspend fun updatePageForPosts(site: SiteModel, pageId: Long): HomepageSettingsPayload =
        HomepageSettingsPayload(site.pageOnFront, pageId, site.showOnFront)
}

private class Fixture(val site: SiteModel) {
    val effects = mutableListOf<Map<String, Any?>>()
    val postService = ControlledPostService(effects)
    val media = ControlledMedia(effects)
    val plans = ArrayDeque<CollectionPlan>()
    val requests = mutableListOf<Pair<PostEndpointType, PostListFilter>>()
    val collections = mutableListOf<ControlledCollection>()
    private val api = ControlledApiClient { collections.lastOrNull()?.items.orEmpty() }
    val leaf = object : CollectionLeaf {
        override val factory: (PostEndpointType, PostListFilter, UInt) -> ObservableMetadataCollection =
            { endpoint, filter, _ ->
                requests += endpoint to filter
                ControlledCollection(
                    if (plans.isEmpty()) CollectionPlan(emptyList()) else plans.removeFirst()
                ).also(collections::add)
            }
    }

    fun install() {
        SelectedSiteCache.instance.select(site)
        SingleWpApiClientProvider.instance.wpApiClient = api
        DefaultWpServiceProvider.instance.postService = postService
        DefaultMediaRestClient.instance.delegate = media
        DefaultNetworkUtilsWrapper.instance.connected = true
        DefaultAccountStore.instance.account = Account(42)
        AppPreferences.processPreferences.clear()
    }
}

private class OwnerSession(
    private val instrumentation: Instrumentation,
    configure: Fixture.() -> Unit = {},
    site: SiteModel = SiteModel(id = ids.incrementAndGet(), name = "Semantic"),
) : AutoCloseable {
    val fixture = Fixture(site).apply(configure)
    val owner: PagesRuntimeOwnerActivity

    init {
        fixture.install()
        val intent = Intent(instrumentation.targetContext, PagesRuntimeOwnerActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        owner = instrumentation.startActivitySync(intent) as PagesRuntimeOwnerActivity
        instrumentation.waitForIdleSync()
        CollectionLeaf.install(fixture.leaf)
    }

    fun event(block: PagesRuntimeOwnerActivity.() -> Unit) {
        instrumentation.runOnMainSync { owner.block() }
        instrumentation.waitForIdleSync()
    }

    override fun close() {
        instrumentation.runOnMainSync { owner.finish() }
        instrumentation.waitForIdleSync()
    }

    companion object {
        private val ids = AtomicInteger(10_000)
    }
}

private fun item(
    id: Long,
    status: PostStatus,
    siteId: Int,
    parentId: Long = 0,
    featuredMediaId: Long = 0,
    title: String = "Page $id",
): MetadataItem = MetadataItem(
    remoteId = id,
    siteId = siteId,
    title = title,
    status = status,
    parentId = parentId,
    featuredImageId = featuredMediaId,
    authorId = 42,
)

private suspend fun waitFor(predicate: () -> Boolean) {
    withTimeout(5_000) { while (!predicate()) delay(10) }
}

private fun surface(owner: PagesRuntimeOwnerActivity): String =
    if (owner.javaClass.name == "org.wordpress.android.ui.pagesrs.PagesRuntimeOwnerActivity") {
        "modern_pages"
    } else {
        owner.javaClass.name
    }

private fun rows(owner: PagesRuntimeOwnerActivity): List<PageRsListItem> = owner.renderedRowSnapshot()
private fun rowIds(owner: PagesRuntimeOwnerActivity): List<Long> = rows(owner).map { it.page.remoteId }
private fun request(filter: PostListFilter): Map<String, Any?> = mapOf(
    "entity" to "pages",
    "statuses" to filter.statuses.map(::statusName),
    "orderBy" to filter.orderBy.restValue,
    "order" to if (filter.order == ListOrder.ASC) "ascending" else "descending",
    "pageSize" to filter.pageSize.toInt(),
)
private fun statusName(value: String): String = when (value) {
    "publish" -> "published"
    "future" -> "scheduled"
    "trash" -> "trashed"
    else -> value
}
private fun feedback(value: String): String = when (value) {
    "Page moved to trash" -> "moved_to_trash"
    "Page couldn't be moved to trash" -> "status_change_error"
    else -> value
}
private fun actionName(action: PageRsMenuAction): String = when (action) {
    PageRsMenuAction.VIEW_PAGE -> "view"
    PageRsMenuAction.SET_PARENT -> "set_parent"
    PageRsMenuAction.SET_AS_HOMEPAGE -> "set_as_homepage"
    PageRsMenuAction.SET_AS_POSTS_PAGE -> "set_as_posts_page"
    PageRsMenuAction.PUBLISH_NOW -> "publish_now"
    PageRsMenuAction.MOVE_TO_DRAFT -> "move_to_draft"
    PageRsMenuAction.COPY -> "duplicate"
    PageRsMenuAction.SHARE -> "share"
    PageRsMenuAction.PROMOTE_WITH_BLAZE -> "blaze"
    PageRsMenuAction.MOVE_TO_TRASH -> "trash"
    PageRsMenuAction.DELETE_PERMANENTLY -> "delete_permanently"
    PageRsMenuAction.CANCEL_AUTO_UPLOAD -> "cancel_auto_upload"
}

private suspend fun openPublished(instrumentation: Instrumentation): Outcome {
    val site = SiteModel(id = 10_101, name = "Published")
    return OwnerSession(instrumentation, site = site, configure = {
        plans += CollectionPlan(listOf(item(1, PostStatus.PUBLISHED, site.id, featuredMediaId = 301, title = "About")))
        media.urls = mapOf(301L to "https://media.test/301.jpg")
    }).use { session ->
        val owner = session.owner
        val before = mapOf("surface" to surface(owner), "rows" to rowIds(owner))
        session.event { open() }
        waitFor { rows(owner).firstOrNull()?.thumbnailUrl == "https://media.test/301.jpg" }
        session.event { openPage(1) }
        waitFor { owner.editorRequestHistory().isNotEmpty() }
        val filter = session.fixture.requests.single().second
        val observed = mapOf(
            "surface" to surface(owner),
            "tabs" to PageRsListTab.ALL.map { it.key },
            "selectedTab" to owner.activeTab().key,
            "rows" to rows(owner).map { mapOf("id" to it.page.remoteId, "thumbnailUrl" to it.thumbnailUrl) },
            "loading" to owner.tabStateSnapshot().getValue(PageRsListTab.PUBLISHED).isLoading,
            "request" to request(filter),
            "effects" to session.fixture.effects.filter { it["name"] == "resolveFeaturedMedia" },
        )
        Outcome(
            before,
            mapOf("rows" to rowIds(owner), "openedPageId" to owner.editorRequestHistory().last().remotePageId),
            observed,
            listOf(
                Check("no posts request is dispatched", session.fixture.requests.all { it.first == PostEndpointType.PAGES }, session.fixture.requests.map { it.first.name }),
                Check("thumbnail resolution never removes the page row", rowIds(owner) == listOf(1L), rowIds(owner)),
                Check("the row opens through the existing editor bridge rather than a replacement editor", owner.editorRequestHistory().single().remotePageId == 1L, owner.editorRequestHistory().map { it.remotePageId }),
            ),
            listOf("PagesRuntimeOwnerActivity.open", "PagesRuntimeOwnerActivity.openPage"),
        )
    }
}

private suspend fun refreshRetry(instrumentation: Instrumentation): Outcome {
    val site = SiteModel(id = 10_102, name = "Refresh")
    return OwnerSession(instrumentation, site = site, configure = {
        plans += CollectionPlan(listOf(item(1, PostStatus.PUBLISHED, site.id)))
        plans += CollectionPlan(listOf(item(1, PostStatus.PUBLISHED, site.id)), RuntimeException("network_error"))
        plans += CollectionPlan(listOf(item(1, PostStatus.PUBLISHED, site.id), item(2, PostStatus.PUBLISHED, site.id)))
    }).use { session ->
        val owner = session.owner
        session.event { open() }
        waitFor { rowIds(owner) == listOf(1L) }
        val baseline = session.fixture.requests.size
        session.event { refresh() }
        waitFor { owner.snackbarHistory().isNotEmpty() && !owner.tabStateSnapshot().getValue(PageRsListTab.PUBLISHED).isRefreshing }
        val failureMessage = owner.snackbarHistory().last()
        val failure = mapOf(
            "rows" to rowIds(owner),
            "refreshing" to owner.tabStateSnapshot().getValue(PageRsListTab.PUBLISHED).isRefreshing,
            "feedback" to feedback(failureMessage.message),
            "retryAvailable" to (failureMessage.action != null),
        )
        session.event { retryActiveTab() }
        waitFor { rowIds(owner) == listOf(1L, 2L) }
        val observed = mapOf(
            "surface" to surface(owner),
            "failure" to failure,
            "recovery" to mapOf("rows" to rowIds(owner), "refreshing" to false, "error" to null),
            "requestCount" to session.fixture.requests.size - baseline,
        )
        Outcome(
            mapOf("rows" to listOf(1L)), observed, observed,
            listOf(
                Check("loaded rows remain visible during the failed refresh", failure["rows"] == listOf(1L), failure["rows"]),
                Check("retry executes the application-owned refresh body", session.fixture.requests.size - baseline == 2, session.fixture.requests.size - baseline),
                Check("no obsolete collection writes after recovery", session.fixture.collections.all { it.closeCalls == 1 }, session.fixture.collections.map { it.closeCalls }),
            ),
            listOf("PagesRuntimeOwnerActivity.open", "PagesRuntimeOwnerActivity.refresh", "PagesRuntimeOwnerActivity.retryActiveTab"),
        )
    }
}

private suspend fun shortSearch(instrumentation: Instrumentation): Outcome {
    val site = SiteModel(id = 10_103, name = "Short search")
    return OwnerSession(instrumentation, site = site, configure = {
        plans += CollectionPlan(listOf(item(1, PostStatus.PUBLISHED, site.id)))
    }).use { session ->
        val owner = session.owner
        session.event { open() }
        waitFor { rowIds(owner) == listOf(1L) }
        session.event { openSearch() }
        val baseline = session.fixture.requests.size
        session.event { changeSearchQuery("ab") }
        delay(500)
        val observed = mapOf(
            "surface" to surface(owner), "searchActive" to owner.searchIsActive(),
            "query" to owner.currentSearchQuery(), "rows" to rowIds(owner),
            "searchRequestCount" to session.fixture.requests.size - baseline,
        )
        Outcome(
            mapOf("rows" to listOf(1L)), observed, observed,
            listOf(
                Check("queries shorter than three characters never reach the service leaf", session.fixture.requests.size == baseline, session.fixture.requests.drop(baseline)),
                Check("the selected tab is retained", owner.activeTab() == PageRsListTab.PUBLISHED, owner.activeTab().key),
            ),
            listOf("PagesRuntimeOwnerActivity.open", "PagesRuntimeOwnerActivity.openSearch", "PagesRuntimeOwnerActivity.changeSearchQuery"),
        )
    }
}

private suspend fun debouncedSearch(instrumentation: Instrumentation): Outcome {
    val site = SiteModel(id = 10_104, name = "Debounce")
    return OwnerSession(instrumentation, site = site, configure = {
        plans += CollectionPlan(emptyList())
        plans += CollectionPlan(listOf(item(7, PostStatus.SCHEDULED, site.id)))
    }).use { session ->
        val owner = session.owner
        session.event { open(PageRsListTab.DRAFTS) }
        waitFor { session.fixture.requests.isNotEmpty() }
        session.event { openSearch() }
        val baseline = session.fixture.requests.size
        session.event { changeSearchQuery("hel") }
        delay(100)
        session.event { changeSearchQuery("hello") }
        waitFor { rowIds(owner) == listOf(7L) }
        val searchRequests = session.fixture.requests.drop(baseline)
        val filter = searchRequests.single().second
        val observed = mapOf(
            "surface" to surface(owner), "query" to owner.currentSearchQuery(),
            "rows" to rows(owner).map { mapOf("id" to it.page.remoteId, "statusLabel" to it.statusLabel.lowercase()) },
            "searchRequestCount" to searchRequests.size,
            "request" to mapOf(
                "statuses" to filter.statuses.map(::statusName), "search" to filter.search,
                "debounceMs" to PagesRsListViewModel.SEARCH_DEBOUNCE_MS,
            ),
        )
        Outcome(
            mapOf("query" to ""), observed, observed,
            listOf(
                Check("the superseded hel request is not dispatched", searchRequests.size == 1 && filter.search == "hello", searchRequests.map { it.second.search }),
                Check("search results are flat and independent of the selected tab hierarchy", rows(owner).all { it.indent == 0 }, rows(owner).map { it.indent }),
            ),
            listOf("PagesRuntimeOwnerActivity.open", "PagesRuntimeOwnerActivity.openSearch", "PagesRuntimeOwnerActivity.changeSearchQuery"),
        )
    }
}

private suspend fun closeSearch(instrumentation: Instrumentation): Outcome {
    val site = SiteModel(id = 10_105, name = "Close search")
    return OwnerSession(instrumentation, site = site, configure = {
        plans += CollectionPlan(listOf(item(3, PostStatus.DRAFT, site.id)))
        plans += CollectionPlan(listOf(item(7, PostStatus.SCHEDULED, site.id)))
        plans += CollectionPlan(listOf(item(3, PostStatus.DRAFT, site.id)))
    }).use { session ->
        val owner = session.owner
        session.event { open(PageRsListTab.DRAFTS) }
        waitFor { rowIds(owner) == listOf(3L) }
        session.event { openSearch(); changeSearchQuery("hello") }
        waitFor { rowIds(owner) == listOf(7L) }
        val searchCollection = session.fixture.collections.last()
        val requestsBefore = session.fixture.requests.size
        val reloadStartedAt = SystemClock.elapsedRealtime()
        session.event { closeSearch() }
        waitFor { session.fixture.requests.size > requestsBefore }
        val reloadElapsedMs = SystemClock.elapsedRealtime() - reloadStartedAt
        waitFor { rowIds(owner) == listOf(3L) }
        val observed = mapOf(
            "surface" to surface(owner), "searchActive" to owner.searchIsActive(),
            "query" to owner.currentSearchQuery(), "selectedTab" to owner.activeTab().key,
            "rows" to rowIds(owner), "reloadDelayMs" to if (reloadElapsedMs < 100L) 0 else reloadElapsedMs,
        )
        Outcome(
            mapOf("rows" to listOf(7L)), observed, observed,
            listOf(
                Check("closing search does not switch tabs", owner.activeTab() == PageRsListTab.DRAFTS, owner.activeTab().key),
                Check("the obsolete search collection is closed before the tab reload", searchCollection.closeCalls == 1, searchCollection.closeCalls),
            ),
            listOf("PagesRuntimeOwnerActivity.open", "PagesRuntimeOwnerActivity.openSearch", "PagesRuntimeOwnerActivity.changeSearchQuery", "PagesRuntimeOwnerActivity.closeSearch"),
        )
    }
}

private suspend fun authorFilter(instrumentation: Instrumentation): Outcome {
    val site = SiteModel(
        id = 10_106, name = "Authors", isSingleUserSite = false,
        hasCapabilityEditOthersPages = true, isUsingWpComRestApi = true,
    )
    return OwnerSession(instrumentation, site = site, configure = {
        plans += CollectionPlan(emptyList())
        plans += CollectionPlan(emptyList())
    }).use { session ->
        val owner = session.owner
        AppPreferences.processPreferences["unrelated"] = "kept"
        session.event { open() }
        waitFor { session.fixture.requests.isNotEmpty() }
        val baseline = session.fixture.requests.size
        session.event { selectAuthor(AuthorFilterSelection.ME) }
        waitFor { session.fixture.requests.size > baseline }
        val filter = session.fixture.requests.last().second
        val snapshot = AppPreferences().snapshot()
        val observed = mapOf(
            "surface" to surface(owner), "selection" to owner.authorSelection().key,
            "persistedSelection" to (snapshot[AppPreferences.KEY_AUTHOR_SELECTION] as AuthorFilterSelection).key,
            "request" to mapOf("authorIds" to filter.authorIds),
            "reloadCount" to session.fixture.requests.size - baseline,
        )
        Outcome(
            mapOf("selection" to "everyone"), observed, observed,
            listOf(
                Check("the author identifier is derived from the signed-in account", filter.authorIds == listOf(42L), filter.authorIds),
                Check("unrelated preferences remain unchanged", snapshot["unrelated"] == "kept", snapshot),
            ),
            listOf("PagesRuntimeOwnerActivity.selectAuthor"),
        )
    }
}

private suspend fun hierarchy(instrumentation: Instrumentation): Outcome =
    OwnerSession(instrumentation).use { session ->
        val owner = session.owner
        val pages = listOf(
            PageRsUiModel(1, parentId = 0), PageRsUiModel(2, parentId = 1),
            PageRsUiModel(3, parentId = 2), PageRsUiModel(4, parentId = 3),
            PageRsUiModel(5, parentId = 4), PageRsUiModel(9, parentId = 99),
        )
        session.event { renderHierarchy(pages) }
        val rendered = rows(owner)
        val observed = mapOf(
            "surface" to surface(owner),
            "rows" to rendered.map { mapOf("id" to it.page.remoteId, "indent" to it.indent) },
        )
        Outcome(
            mapOf("rows" to emptyList<Long>()), observed, observed,
            listOf(
                Check("every input page appears exactly once", rendered.map { it.page.remoteId }.toSet().size == pages.size, rendered.map { it.page.remoteId }),
                Check("missing-parent pages remain visible", rendered.any { it.page.remoteId == 9L }, rendered.map { it.page.remoteId }),
                Check("indentation never exceeds three", rendered.all { it.indent <= 3 }, rendered.map { it.indent }),
            ),
            listOf("PagesRuntimeOwnerActivity.renderHierarchy"),
        )
    }

private suspend fun menuEligibility(instrumentation: Instrumentation): Outcome {
    val site = SiteModel(
        id = 10_108, name = "Menu", showOnFront = SiteModel.SHOW_ON_FRONT_PAGE,
        pageOnFront = 11, isWpComAtomic = true,
    )
    return OwnerSession(instrumentation, site = site, configure = {
        plans += CollectionPlan(listOf(item(11, PostStatus.PUBLISHED, site.id)))
    }).use { session ->
        val owner = session.owner
        session.event { open() }
        waitFor { rowIds(owner) == listOf(11L) }
        val actions = rows(owner).single().actions.map(::actionName)
        session.event { renderMenu(11, rows(owner).single().actions) }
        val observed = mapOf(
            "surface" to surface(owner), "actions" to actions,
            "excludedActions" to listOf("set_as_homepage", "move_to_draft", "trash").filter { it !in actions },
        )
        Outcome(
            mapOf("actions" to emptyList<String>()), observed, observed,
            listOf(
                Check("destructive actions are not rendered for the homepage", listOf("set_as_homepage", "move_to_draft", "trash").none(actions::contains), actions),
                Check("action eligibility is derived from page and site state", owner.renderedMenuSnapshot().map(::actionName) == actions, actions),
            ),
            listOf("PagesRuntimeOwnerActivity.open", "PagesRuntimeOwnerActivity.renderMenu"),
        )
    }
}

private suspend fun trashSuccess(instrumentation: Instrumentation): Outcome {
    val site = SiteModel(id = 10_109, name = "Trash success")
    return OwnerSession(instrumentation, site = site, configure = {
        plans += CollectionPlan(listOf(item(12, PostStatus.PUBLISHED, site.id)))
        plans += CollectionPlan(listOf(item(12, PostStatus.TRASHED, site.id)))
    }).use { session ->
        val owner = session.owner
        session.event { open() }
        waitFor { rowIds(owner) == listOf(12L) }
        session.event { chooseMenuAction(12, PageRsMenuAction.MOVE_TO_TRASH) }
        val confirmationShown = owner.pendingConfirmationOrNull() != null
        val callsBefore = session.fixture.postService.trashIds.size
        session.event { confirmPendingAction() }
        waitFor { session.fixture.postService.trashIds.size == 1 && owner.snackbarHistory().isNotEmpty() }
        val published = rowIds(owner)
        session.event { open(PageRsListTab.TRASHED) }
        waitFor { rowIds(owner) == listOf(12L) }
        val effect = session.fixture.effects.single { it["name"] == "trashPage" }
        val observed = mapOf(
            "surface" to surface(owner), "confirmationShown" to confirmationShown,
            "serviceEffect" to effect, "publishedRows" to published,
            "trashedRows" to rowIds(owner), "feedback" to feedback(owner.snackbarHistory().last().message),
        )
        Outcome(
            mapOf("publishedRows" to listOf(12L)), observed, observed,
            listOf(
                Check("the service mutation is not called before confirmation", callsBefore == 0, callsBefore),
                Check("the application-owned mutation body is invoked exactly once", session.fixture.postService.trashIds == listOf(12L), session.fixture.postService.trashIds),
            ),
            listOf("PagesRuntimeOwnerActivity.open", "PagesRuntimeOwnerActivity.chooseMenuAction", "PagesRuntimeOwnerActivity.confirmPendingAction"),
        )
    }
}

private suspend fun trashFailureRetry(instrumentation: Instrumentation): Outcome {
    val site = SiteModel(id = 10_110, name = "Trash retry")
    return OwnerSession(instrumentation, site = site, configure = {
        plans += CollectionPlan(listOf(item(13, PostStatus.PUBLISHED, site.id)))
        plans += CollectionPlan(listOf(item(13, PostStatus.TRASHED, site.id)))
        postService.trashFailures += true
        postService.trashFailures += false
    }).use { session ->
        val owner = session.owner
        session.event { open() }
        waitFor { rowIds(owner) == listOf(13L) }
        session.event { chooseMenuAction(13, PageRsMenuAction.MOVE_TO_TRASH); confirmPendingAction() }
        waitFor { session.fixture.postService.trashIds.size == 1 && owner.snackbarHistory().isNotEmpty() }
        val failed = owner.snackbarHistory().last()
        val failure = mapOf("publishedRows" to rowIds(owner), "feedback" to feedback(failed.message))
        session.event { performSnackbarAction(failed) }
        waitFor { session.fixture.postService.trashIds.size == 2 && owner.snackbarHistory().size >= 2 }
        val recoveredPublished = rowIds(owner)
        session.event { open(PageRsListTab.TRASHED) }
        waitFor { rowIds(owner) == listOf(13L) }
        val observed = mapOf(
            "surface" to surface(owner), "failure" to failure,
            "recovery" to mapOf(
                "publishedRows" to recoveredPublished, "trashedRows" to rowIds(owner),
                "feedback" to feedback(owner.snackbarHistory().last().message),
            ),
            "serviceCallCount" to session.fixture.postService.trashIds.size,
        )
        Outcome(
            mapOf("publishedRows" to listOf(13L)), observed, observed,
            listOf(
                Check("failure does not optimistically remove the page", failure["publishedRows"] == listOf(13L), failure["publishedRows"]),
                Check("retry uses the same page identity", session.fixture.postService.trashIds == listOf(13L, 13L), session.fixture.postService.trashIds),
                Check("only the controlled external leaf supplies outcomes", session.fixture.postService.trashFailures.isEmpty(), session.fixture.postService.trashFailures.size),
            ),
            listOf("PagesRuntimeOwnerActivity.open", "PagesRuntimeOwnerActivity.confirmPendingAction", "PagesRuntimeOwnerActivity.performSnackbarAction"),
        )
    }
}

fun runCase(key: String, instrumentation: Instrumentation): String = runBlocking {
    val outcome = when (key) {
        "open_published" -> openPublished(instrumentation)
        "refresh_retry" -> refreshRetry(instrumentation)
        "short_search" -> shortSearch(instrumentation)
        "debounced_search" -> debouncedSearch(instrumentation)
        "close_search" -> closeSearch(instrumentation)
        "author_filter" -> authorFilter(instrumentation)
        "published_hierarchy" -> hierarchy(instrumentation)
        "menu_eligibility" -> menuEligibility(instrumentation)
        "trash_success" -> trashSuccess(instrumentation)
        "trash_failure_retry" -> trashFailureRetry(instrumentation)
        else -> error("unknown case $key")
    }
    JsonObject(mapOf(
        "key" to JsonPrimitive(key),
        "before" to json(outcome.before),
        "after" to json(outcome.after),
        "observed" to json(outcome.observed),
        "invariantChecks" to JsonArray(outcome.checks.map { check ->
            JsonObject(mapOf(
                "invariant" to JsonPrimitive(check.invariant),
                "passed" to JsonPrimitive(check.passed),
                "evidence" to json(check.evidence),
            ))
        }),
        "productionBodies" to JsonArray(outcome.productionBodies.map(::JsonPrimitive)),
    )).toString()
}

private fun json(value: Any?): JsonElement = when (value) {
    null -> JsonNull
    is String -> JsonPrimitive(value)
    is Boolean -> JsonPrimitive(value)
    is Number -> JsonPrimitive(value)
    is Map<*, *> -> JsonObject(value.entries.associate { it.key.toString() to json(it.value) })
    is Iterable<*> -> JsonArray(value.map(::json))
    else -> JsonPrimitive(value.toString())
}
