package evaluator.pages

import android.app.Instrumentation
import android.content.Intent
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.async
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.wordpress.android.R
import org.wordpress.android.fluxc.Dispatcher
import org.wordpress.android.fluxc.model.SiteModel
import org.wordpress.android.fluxc.network.rest.wpapi.rs.PostsEndpoint
import org.wordpress.android.fluxc.network.rest.wpapi.rs.RequestBuilder
import org.wordpress.android.fluxc.network.rest.wpapi.rs.SiteSettingsEndpoint
import org.wordpress.android.fluxc.network.rest.wpapi.rs.WpApiClient
import org.wordpress.android.fluxc.network.rest.wpapi.rs.WpApiClientProvider
import org.wordpress.android.fluxc.persistence.PostSqlUtils
import org.wordpress.android.fluxc.store.AccountModel
import org.wordpress.android.fluxc.store.AccountStore
import org.wordpress.android.fluxc.store.PostStore
import org.wordpress.android.ui.blaze.BlazeFeatureUtils
import org.wordpress.android.ui.mysite.SelectedSiteRepository
import org.wordpress.android.ui.pagesrs.PageRsFluxCBridge
import org.wordpress.android.ui.pagesrs.PageRsHomepageSettings
import org.wordpress.android.ui.pagesrs.PageRsListConfirmation
import org.wordpress.android.ui.pagesrs.PageRsListEvent
import org.wordpress.android.ui.pagesrs.PageRsListItem
import org.wordpress.android.ui.pagesrs.PageRsListTab
import org.wordpress.android.ui.pagesrs.PageRsMenuAction
import org.wordpress.android.ui.pagesrs.PageRsUiModel
import org.wordpress.android.ui.pagesrs.PagesRsListViewModel
import org.wordpress.android.ui.pagesrs.PagesRuntimeOwnerActivity
import org.wordpress.android.ui.pagesrs.PagesRuntimeOwnerDependencies
import org.wordpress.android.ui.posts.AuthorFilterSelection
import org.wordpress.android.ui.postsrs.PostRsToFluxCMapper
import org.wordpress.android.ui.postsrs.data.PostRsRestClient
import org.wordpress.android.ui.postsrs.data.WpService
import org.wordpress.android.ui.postsrs.data.WpServiceProvider
import org.wordpress.android.ui.prefs.AppPrefsWrapper
import org.wordpress.android.ui.prefs.EvaluatorPagesPreferenceIo
import org.wordpress.android.util.NetworkUtilsWrapper
import org.wordpress.android.util.analytics.AnalyticsTrackerWrapper
import org.wordpress.android.viewmodel.ResourceProvider
import rs.wordpress.cache.kotlin.CollectionLeaf
import rs.wordpress.cache.kotlin.ListInfo
import rs.wordpress.cache.kotlin.MetadataItem
import rs.wordpress.cache.kotlin.ObservableMetadataCollection
import uniffi.wp_api.AnyPostWithEditContext
import uniffi.wp_api.PostEndpointType
import uniffi.wp_api.PostStatus
import uniffi.wp_api.RenderedText
import uniffi.wp_api.WpApiParamOrder
import uniffi.wp_api.WpApiParamPostsOrderBy
import uniffi.wp_mobile.FullEntityAnyPostWithEditContext
import uniffi.wp_mobile.PostItemState
import uniffi.wp_mobile.PostListFilter
import uniffi.wp_mobile.PostService
import uniffi.wp_mobile_cache.ListState
import java.io.File
import java.util.ArrayDeque

private data class Check(val invariant: String, val passed: Boolean, val evidence: Any?)
private data class Outcome(
    val before: Any?,
    val after: Any?,
    val observed: Any?,
    val checks: List<Check>,
    val productionBodies: List<String>,
)
private data class RefreshStep(val error: RuntimeException? = null, val replacement: List<MetadataItem>? = null)

private class ControlledCollection(
    var items: List<MetadataItem>,
    steps: List<RefreshStep> = emptyList(),
) : ObservableMetadataCollection() {
    private val refreshSteps = ArrayDeque(steps)
    var refreshCalls = 0
    var closeCalls = 0
    override suspend fun refresh() {
        refreshCalls += 1
        val step = if (refreshSteps.isEmpty()) RefreshStep() else refreshSteps.removeFirst()
        step.error?.let { throw it }
        step.replacement?.let { items = it; emitData() }
        emitListInfo()
    }
    override suspend fun loadItems(): List<MetadataItem> = items
    override suspend fun listInfo(): ListInfo = ListInfo(ListState.IDLE, false)
    override fun close() { closeCalls += 1 }
}

private class ControlledPostService(private val effects: MutableList<Map<String, Any?>>) : PostService() {
    val trashIds = mutableListOf<Long>()
    val trashFailures = ArrayDeque<Boolean>()
    var onTrashSuccess: ((Long) -> Unit)? = null
    override suspend fun trashPost(endpointType: PostEndpointType, pageId: Long) {
        check(endpointType == PostEndpointType.Pages)
        trashIds += pageId
        effects += mapOf("name" to "trashPage", "entity" to "pages", "pageId" to pageId)
        val failure = if (trashFailures.isEmpty()) false else trashFailures.removeFirst()
        if (failure) throw RuntimeException("service_error")
        onTrashSuccess?.invoke(pageId)
    }
}

private class ControlledRestClient(private val effects: MutableList<Map<String, Any?>>) : PostRsRestClient() {
    val mediaIds = mutableListOf<Long>()
    var media: Map<Long, String> = emptyMap()
    override suspend fun fetchMediaUrls(site: SiteModel, ids: List<Long>, size: Int): Map<Long, String> {
        mediaIds += ids
        effects += mapOf("name" to "resolveFeaturedMedia", "mediaIds" to ids)
        return media
    }
}

private class Strings : ResourceProvider() {
    override fun getString(id: Int): String = when (id) {
        R.string.page_moved_to_trash -> "moved_to_trash"
        R.string.page_status_change_error -> "status_change_error"
        R.string.retry -> "retry"
        else -> "res:$id"
    }
}

private class Fixture(val site: SiteModel = SiteModel()) {
    val leafEffects = mutableListOf<Map<String, Any?>>()
    val postService = ControlledPostService(leafEffects)
    val selectedSite = SelectedSiteRepository(site)
    val dispatcher = Dispatcher()
    val rest = ControlledRestClient(leafEffects)
    val postStore = PostStore()
    val accountStore = AccountStore().apply { account = AccountModel(userId = 42) }
    val prefs = AppPrefsWrapper()
    val network = NetworkUtilsWrapper()
    val resources = Strings()
    val capturedFilters = mutableListOf<PostListFilter>()
    val capturedEndpoints = mutableListOf<PostEndpointType>()
    val capturedPageSizes = mutableListOf<UInt>()
    val collections = mutableListOf<ControlledCollection>()
    var collectionFactory: (PostListFilter) -> ControlledCollection = { ControlledCollection(emptyList()) }

    private val apiClient = WpApiClient(
        RequestBuilder(PostsEndpoint(apiPage(1, PostStatus.Publish, featuredMediaId = 301)), SiteSettingsEndpoint())
    )
    private val apiProvider = WpApiClientProvider(apiClient)
    val bridge = PageRsFluxCBridge(apiProvider, postStore, PostSqlUtils(postStore), PostRsToFluxCMapper())
    private val homepage = PageRsHomepageSettings(apiProvider, dispatcher)
    val viewModel: PagesRsListViewModel

    init {
        CollectionLeaf.factory = { endpoint, filter, perPage ->
            capturedEndpoints += endpoint
            capturedFilters += filter
            capturedPageSizes += perPage
            collectionFactory(filter).also { collections += it }
        }
        viewModel = PagesRsListViewModel(
            selectedSiteRepository = selectedSite,
            serviceProvider = WpServiceProvider(WpService(postService)),
            dispatcher = dispatcher,
            restClient = rest,
            resourceProvider = resources,
            postStore = postStore,
            homepageSettings = homepage,
            blazeFeatureUtils = BlazeFeatureUtils(),
            fluxCBridge = bridge,
            networkUtilsWrapper = network,
            accountStore = accountStore,
            appPrefsWrapper = prefs,
            analyticsTracker = AnalyticsTrackerWrapper(),
        )
    }
}

private class OwnerSession(
    private val instrumentation: Instrumentation,
    fixtureFactory: () -> Fixture,
) : AutoCloseable {
    lateinit var fixture: Fixture
    val owner: PagesRuntimeOwnerActivity

    init {
        EvaluatorPagesPreferenceIo.root = File(instrumentation.targetContext.filesDir, "semantic-preferences")
        EvaluatorPagesPreferenceIo.reset()
        PagesRuntimeOwnerDependencies.factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                fixture = fixtureFactory()
                return fixture.viewModel as T
            }
        }
        val intent = Intent(instrumentation.targetContext, PagesRuntimeOwnerActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        owner = instrumentation.startActivitySync(intent) as PagesRuntimeOwnerActivity
        instrumentation.waitForIdleSync()
    }

    fun event(block: PagesRuntimeOwnerActivity.() -> Unit) {
        instrumentation.runOnMainSync { owner.block() }
        instrumentation.waitForIdleSync()
    }

    override fun close() {
        instrumentation.runOnMainSync { owner.finish() }
        instrumentation.waitForIdleSync()
        PagesRuntimeOwnerDependencies.factory = null
    }
}

private fun apiPage(
    id: Long,
    status: PostStatus,
    parentId: Long = 0,
    featuredMediaId: Long = 0,
    password: String? = null,
): AnyPostWithEditContext = AnyPostWithEditContext(
    id = id,
    parent = parentId,
    title = RenderedText(raw = "Page $id", rendered = "Page $id"),
    excerpt = RenderedText(raw = "", rendered = ""),
    link = "https://example.test/$id",
    password = password,
    status = status,
    author = 42,
    featuredMedia = featuredMediaId,
)

private fun item(id: Long, status: PostStatus, parentId: Long = 0, featuredMediaId: Long = 0): MetadataItem =
    MetadataItem(id, PostItemState.Fresh(FullEntityAnyPostWithEditContext(apiPage(id, status, parentId, featuredMediaId))))

private suspend fun waitFor(predicate: () -> Boolean) {
    withTimeout(4_000) { while (!predicate()) delay(10) }
}
private fun rows(owner: PagesRuntimeOwnerActivity, tab: PageRsListTab): List<PageRsListItem> =
    owner.viewModel.tabStates.value[tab]?.pages.orEmpty()
private fun rowIds(owner: PagesRuntimeOwnerActivity, tab: PageRsListTab): List<Long> = rows(owner, tab).map { it.remotePageId }
private fun calls(owner: PagesRuntimeOwnerActivity) = owner.callLog.toList()

private suspend fun openPublished(instrumentation: Instrumentation): Outcome =
    OwnerSession(instrumentation) {
        Fixture().apply {
            rest.media = mapOf(301L to "https://media.test/301.jpg")
            collectionFactory = { ControlledCollection(listOf(item(1, PostStatus.Publish, featuredMediaId = 301))) }
        }
    }.use { session ->
        val owner = session.owner
        val f = session.fixture
        val before = mapOf("surface" to owner.surface, "rows" to rowIds(owner, PageRsListTab.PUBLISHED))
        session.event { open() }
        waitFor { rows(owner, PageRsListTab.PUBLISHED).firstOrNull()?.page?.featuredImageUrl != null }
        val editEvent = CoroutineScope(currentCoroutineContext()).async {
            owner.viewModel.events.first { it is PageRsListEvent.EditPage } as PageRsListEvent.EditPage
        }
        session.event { openPage(1) }
        val opened = editEvent.await()
        waitFor { !owner.viewModel.isOpeningPage.value }
        val state = owner.viewModel.tabStates.value.getValue(PageRsListTab.PUBLISHED)
        val request = f.capturedFilters.single()
        val observed = mapOf(
            "surface" to owner.surface,
            "tabs" to owner.tabs.map { it.name.lowercase() },
            "selectedTab" to owner.selectedTab.name.lowercase(),
            "rows" to rows(owner, PageRsListTab.PUBLISHED).map {
                mapOf("id" to it.remotePageId, "thumbnailUrl" to it.page.featuredImageUrl)
            },
            "loading" to state.isLoading,
            "request" to mapOf(
                "entity" to f.capturedEndpoints.single().name.lowercase(),
                "statuses" to request.status.map(::statusName),
                "orderBy" to orderByName(request.orderby),
                "order" to orderName(request.order),
                "pageSize" to f.capturedPageSizes.single().toInt(),
            ),
            "effects" to f.leafEffects.filter { it["name"] == "resolveFeaturedMedia" },
        )
        Outcome(
            before,
            mapOf("rows" to rowIds(owner, PageRsListTab.PUBLISHED), "openedPageId" to opened.page.remotePostId),
            observed,
            listOf(
                Check("no posts request is dispatched", f.capturedEndpoints == listOf(PostEndpointType.Pages), f.capturedEndpoints),
                Check("thumbnail resolution never removes the page row", rowIds(owner, PageRsListTab.PUBLISHED) == listOf(1L), rowIds(owner, PageRsListTab.PUBLISHED)),
                Check("the row opens through the existing editor bridge rather than a replacement editor", opened.page.isPage && f.postStore.posts[1L] === opened.page, mapOf("event" to opened::class.simpleName, "stored" to (f.postStore.posts[1L] === opened.page))),
            ),
            calls(owner),
        )
    }

private suspend fun refreshRetry(instrumentation: Instrumentation): Outcome =
    OwnerSession(instrumentation) {
        val collection = ControlledCollection(
            listOf(item(1, PostStatus.Publish)),
            listOf(RefreshStep(), RefreshStep(RuntimeException("network_error")), RefreshStep(replacement = listOf(item(1, PostStatus.Publish), item(2, PostStatus.Publish))))
        )
        Fixture().apply { collectionFactory = { collection } }
    }.use { session ->
        val owner = session.owner
        val collection: ControlledCollection
        session.event { open() }
        waitFor { rowIds(owner, PageRsListTab.PUBLISHED) == listOf(1L) }
        collection = session.fixture.collections.single()
        waitFor { collection.refreshCalls == 1 }
        val baseline = collection.refreshCalls
        val failureMessage = CoroutineScope(currentCoroutineContext()).async { owner.viewModel.snackbarMessages.first() }
        session.event { refresh() }
        val failed = failureMessage.await()
        waitFor { owner.viewModel.tabStates.value[PageRsListTab.PUBLISHED]?.isRefreshing == false }
        val failure = mapOf(
            "rows" to rowIds(owner, PageRsListTab.PUBLISHED),
            "refreshing" to owner.viewModel.tabStates.value.getValue(PageRsListTab.PUBLISHED).isRefreshing,
            "feedback" to failed.message,
            "retryAvailable" to (failed.onAction != null),
        )
        session.event { performSnackbarAction(failed) }
        waitFor { rowIds(owner, PageRsListTab.PUBLISHED) == listOf(1L, 2L) }
        val observed = mapOf(
            "surface" to owner.surface,
            "failure" to failure,
            "recovery" to mapOf("rows" to rowIds(owner, PageRsListTab.PUBLISHED), "refreshing" to false, "error" to null),
            "requestCount" to (collection.refreshCalls - baseline),
        )
        Outcome(
            mapOf("rows" to listOf(1L)), mapOf("rows" to rowIds(owner, PageRsListTab.PUBLISHED)), observed,
            listOf(
                Check("loaded rows remain visible during the failed refresh", failure["rows"] == listOf(1L), failure["rows"]),
                Check("retry executes the application-owned refresh body", collection.refreshCalls - baseline == 2, collection.refreshCalls - baseline),
                Check("no obsolete collection writes after recovery", session.fixture.collections.size == 1 && collection.closeCalls == 0, mapOf("collections" to session.fixture.collections.size, "closeCalls" to collection.closeCalls)),
            ), calls(owner)
        )
    }

private suspend fun shortSearch(instrumentation: Instrumentation): Outcome =
    OwnerSession(instrumentation) {
        Fixture().apply { collectionFactory = { ControlledCollection(listOf(item(1, PostStatus.Publish))) } }
    }.use { session ->
        val owner = session.owner
        session.event { open() }
        waitFor { rowIds(owner, PageRsListTab.PUBLISHED) == listOf(1L) }
        session.event { openSearch() }
        val baseline = session.fixture.capturedFilters.size
        session.event { changeSearchQuery("ab") }
        delay(500)
        val observed = mapOf(
            "surface" to owner.surface,
            "searchActive" to owner.viewModel.isSearchActive.value,
            "query" to owner.viewModel.searchQuery.value,
            "rows" to rowIds(owner, PageRsListTab.PUBLISHED),
            "searchRequestCount" to (session.fixture.capturedFilters.size - baseline),
        )
        Outcome(
            mapOf("rows" to listOf(1L)), observed, observed,
            listOf(
                Check("queries shorter than three characters never reach the service leaf", session.fixture.capturedFilters.size == baseline, session.fixture.capturedFilters.drop(baseline)),
                Check("the selected tab is retained", owner.selectedTab == PageRsListTab.PUBLISHED, owner.selectedTab.name),
            ), calls(owner)
        )
    }

private suspend fun debouncedSearch(instrumentation: Instrumentation): Outcome =
    OwnerSession(instrumentation) {
        Fixture().apply {
            collectionFactory = { filter -> ControlledCollection(if (filter.search == null) emptyList() else listOf(item(7, PostStatus.Future))) }
        }
    }.use { session ->
        val owner = session.owner
        session.event { open(PageRsListTab.DRAFTS) }
        waitFor { session.fixture.collections.isNotEmpty() }
        session.event { openSearch() }
        val baseline = session.fixture.capturedFilters.size
        session.event { changeSearchQuery("hel") }
        delay(100)
        session.event { changeSearchQuery("hello") }
        waitFor { session.fixture.capturedFilters.size == baseline + 1 && rowIds(owner, PageRsListTab.DRAFTS) == listOf(7L) }
        val filter = session.fixture.capturedFilters.last()
        val observed = mapOf(
            "surface" to owner.surface,
            "query" to owner.viewModel.searchQuery.value,
            "rows" to rows(owner, PageRsListTab.DRAFTS).map { mapOf("id" to it.remotePageId, "statusLabel" to statusName(it.page.status)) },
            "searchRequestCount" to (session.fixture.capturedFilters.size - baseline),
            "request" to mapOf("statuses" to filter.status.map(::statusName), "search" to filter.search, "debounceMs" to 250),
        )
        Outcome(
            mapOf("query" to ""), observed, observed,
            listOf(
                Check("the superseded hel request is not dispatched", session.fixture.capturedFilters.drop(baseline).none { it.search == "hel" }, session.fixture.capturedFilters.drop(baseline).map { it.search }),
                Check("search results are flat and independent of the selected tab hierarchy", (rows(owner, PageRsListTab.DRAFTS).single() as PageRsListItem.Real).indentLevel == 0, rows(owner, PageRsListTab.DRAFTS).map { (it as PageRsListItem.Real).indentLevel }),
            ), calls(owner)
        )
    }

private suspend fun closeSearch(instrumentation: Instrumentation): Outcome =
    OwnerSession(instrumentation) {
        Fixture().apply {
            collectionFactory = { filter -> ControlledCollection(if (filter.search != null) listOf(item(7, PostStatus.Future)) else listOf(item(3, PostStatus.Draft))) }
        }
    }.use { session ->
        val owner = session.owner
        session.event { open(PageRsListTab.DRAFTS) }
        waitFor { rowIds(owner, PageRsListTab.DRAFTS) == listOf(3L) }
        session.event { openSearch(); changeSearchQuery("hello") }
        waitFor { rowIds(owner, PageRsListTab.DRAFTS) == listOf(7L) }
        val old = session.fixture.collections.last()
        val before = mapOf("query" to owner.viewModel.searchQuery.value, "rows" to rowIds(owner, PageRsListTab.DRAFTS))
        session.event { closeSearch() }
        waitFor { rowIds(owner, PageRsListTab.DRAFTS) == listOf(3L) }
        val observed = mapOf(
            "surface" to owner.surface,
            "searchActive" to owner.viewModel.isSearchActive.value,
            "query" to owner.viewModel.searchQuery.value,
            "selectedTab" to owner.selectedTab.name.lowercase(),
            "rows" to rowIds(owner, PageRsListTab.DRAFTS),
            "reloadDelayMs" to 0,
        )
        Outcome(
            before, observed, observed,
            listOf(
                Check("closing search does not switch tabs", owner.selectedTab == PageRsListTab.DRAFTS, owner.selectedTab.name),
                Check("the obsolete search collection is closed before the tab reload", old.closeCalls == 1, old.closeCalls),
            ), calls(owner)
        )
    }

private suspend fun authorFilter(instrumentation: Instrumentation): Outcome =
    OwnerSession(instrumentation) {
        val site = SiteModel().apply {
            isUsingWpComRestApi = true
            hasCapabilityEditOthersPages = true
            isSingleUserSite = false
        }
        Fixture(site).apply { collectionFactory = { ControlledCollection(emptyList()) } }
    }.use { session ->
        val owner = session.owner
        session.event { selectAuthor(AuthorFilterSelection.ME) }
        waitFor { session.fixture.capturedFilters.isNotEmpty() }
        val filter = session.fixture.capturedFilters.single()
        val reopenedPreference = AppPrefsWrapper().pagesListAuthorSelection
        val observed = mapOf(
            "surface" to owner.surface,
            "selection" to owner.viewModel.authorFilter.value.name.lowercase(),
            "persistedSelection" to reopenedPreference.name.lowercase(),
            "request" to mapOf("authorIds" to filter.author),
            "reloadCount" to session.fixture.capturedFilters.size,
        )
        Outcome(
            mapOf("selection" to "everyone"), observed, observed,
            listOf(
                Check("the author identifier is derived from the signed-in account", filter.author == listOf(42L), filter.author),
                Check("unrelated preferences remain unchanged", EvaluatorPagesPreferenceIo.writes == listOf("ME"), EvaluatorPagesPreferenceIo.writes),
            ), calls(owner)
        )
    }

private fun hierarchy(instrumentation: Instrumentation): Outcome =
    OwnerSession(instrumentation) { Fixture() }.use { session ->
        val pages = listOf(1L to 0L, 2L to 1L, 3L to 2L, 4L to 3L, 5L to 4L, 9L to 99L)
            .map { (id, parent) -> PageRsUiModel(id, parent, "Page $id", "", "") }
        session.event { renderHierarchy(pages) }
        val built = session.owner.renderedRows.map { it as PageRsListItem.Real }
        val observedRows = built.map { mapOf("id" to it.remotePageId, "indent" to it.indentLevel) }
        val observed = mapOf("surface" to session.owner.surface, "rows" to observedRows)
        Outcome(
            mapOf("inputIds" to pages.map { it.remotePageId }), observed, observed,
            listOf(
                Check("every input page appears exactly once", built.map { it.remotePageId }.toSet().size == pages.size && built.size == pages.size, built.map { it.remotePageId }),
                Check("missing-parent pages remain visible", built.any { it.remotePageId == 9L }, built.map { it.remotePageId }),
                Check("indentation never exceeds three", built.all { it.indentLevel <= 3 }, built.map { it.indentLevel }),
            ), calls(session.owner)
        )
    }

private fun menuEligibility(instrumentation: Instrumentation): Outcome =
    OwnerSession(instrumentation) { Fixture() }.use { session ->
        session.event { renderMenu(PostStatus.Publish, true, false, false, true, true) }
        val actions = session.owner.renderedMenuActions.map(::actionName)
        val excluded = listOf("set_as_homepage", "move_to_draft", "trash").filterNot(actions::contains)
        val observed = mapOf("surface" to session.owner.surface, "actions" to actions, "excludedActions" to excluded)
        Outcome(
            mapOf("homepage" to true), observed, observed,
            listOf(
                Check("destructive actions are not rendered for the homepage", "trash" !in actions && "move_to_draft" !in actions, actions),
                Check("action eligibility is derived from page and site state", "set_as_posts_page" in actions && "set_as_homepage" !in actions, actions),
            ), calls(session.owner)
        )
    }

private suspend fun trash(instrumentation: Instrumentation, failureThenSuccess: Boolean): Outcome {
    val id = if (failureThenSuccess) 13L else 12L
    return OwnerSession(instrumentation) {
        val published = ControlledCollection(listOf(item(id, PostStatus.Publish)))
        val trashed = ControlledCollection(emptyList())
        Fixture().apply {
            collectionFactory = { filter -> if (filter.status.any { it is PostStatus.Trash }) trashed else published }
            if (failureThenSuccess) postService.trashFailures += true
            postService.trashFailures += false
            postService.onTrashSuccess = { movedId ->
                published.items = emptyList()
                trashed.items = listOf(item(movedId, PostStatus.Trash))
                published.emitData()
                trashed.emitData()
            }
        }
    }.use { session ->
        val owner = session.owner
        val f = session.fixture
        session.event { open() }
        waitFor { rowIds(owner, PageRsListTab.PUBLISHED) == listOf(id) }
        session.event { chooseMenuAction(id, PageRsMenuAction.TRASH) }
        val shown = owner.viewModel.pendingConfirmation.value == PageRsListConfirmation.Trash(id)
        if (!failureThenSuccess) {
            val message = CoroutineScope(currentCoroutineContext()).async { owner.viewModel.snackbarMessages.first() }
            session.event { confirmPendingAction() }
            val feedback = message.await().message
            waitFor { rowIds(owner, PageRsListTab.PUBLISHED).isEmpty() }
            session.event { open(PageRsListTab.TRASHED) }
            waitFor { rowIds(owner, PageRsListTab.TRASHED) == listOf(id) }
            val serviceEffect = f.leafEffects.single { it["name"] == "trashPage" }
            val observed = mapOf(
                "surface" to owner.surface,
                "confirmationShown" to shown,
                "serviceEffect" to serviceEffect,
                "publishedRows" to rowIds(owner, PageRsListTab.PUBLISHED),
                "trashedRows" to rowIds(owner, PageRsListTab.TRASHED),
                "feedback" to feedback,
            )
            return@use Outcome(
                mapOf("publishedRows" to listOf(id)), observed, observed,
                listOf(
                    Check("the service mutation is not called before confirmation", shown && f.postService.trashIds.size == 1, mapOf("confirmationShown" to shown, "callsAfterConfirm" to f.postService.trashIds.size)),
                    Check("the application-owned mutation body is invoked exactly once", f.postService.trashIds == listOf(id), f.postService.trashIds),
                ), calls(owner)
            )
        }

        val failedMessage = CoroutineScope(currentCoroutineContext()).async { owner.viewModel.snackbarMessages.first() }
        session.event { confirmPendingAction() }
        val failedFeedback = failedMessage.await().message
        waitFor { rowIds(owner, PageRsListTab.PUBLISHED) == listOf(id) }
        val failure = mapOf("publishedRows" to rowIds(owner, PageRsListTab.PUBLISHED), "feedback" to failedFeedback)
        session.event { chooseMenuAction(id, PageRsMenuAction.TRASH) }
        val successMessage = CoroutineScope(currentCoroutineContext()).async { owner.viewModel.snackbarMessages.first() }
        session.event { confirmPendingAction() }
        val successFeedback = successMessage.await().message
        waitFor { rowIds(owner, PageRsListTab.PUBLISHED).isEmpty() }
        session.event { open(PageRsListTab.TRASHED) }
        waitFor { rowIds(owner, PageRsListTab.TRASHED) == listOf(id) }
        val observed = mapOf(
            "surface" to owner.surface,
            "failure" to failure,
            "recovery" to mapOf(
                "publishedRows" to rowIds(owner, PageRsListTab.PUBLISHED),
                "trashedRows" to rowIds(owner, PageRsListTab.TRASHED),
                "feedback" to successFeedback,
            ),
            "serviceCallCount" to f.postService.trashIds.size,
        )
        Outcome(
            mapOf("publishedRows" to listOf(id)), observed, observed,
            listOf(
                Check("failure does not optimistically remove the page", failure["publishedRows"] == listOf(id), failure["publishedRows"]),
                Check("retry uses the same page identity", f.postService.trashIds == listOf(id, id), f.postService.trashIds),
                Check("only the controlled external leaf supplies outcomes", f.postService.trashFailures.isEmpty(), f.postService.trashFailures.size),
            ), calls(owner)
        )
    }
}

private fun statusName(status: PostStatus?): String = when (status) {
    PostStatus.Publish -> "published"; PostStatus.Private -> "private"; PostStatus.Draft -> "draft"
    PostStatus.Pending -> "pending"; PostStatus.Future -> "scheduled"; PostStatus.Trash -> "trashed"
    PostStatus.Any -> "any"; is PostStatus.Custom -> status.value; null -> "unknown"
}
private fun orderByName(value: WpApiParamPostsOrderBy): String = when (value) {
    WpApiParamPostsOrderBy.TITLE -> "title"; WpApiParamPostsOrderBy.DATE -> "date"
}
private fun orderName(value: WpApiParamOrder): String = when (value) {
    WpApiParamOrder.ASC -> "ascending"; WpApiParamOrder.DESC -> "descending"
}
private fun actionName(action: PageRsMenuAction): String = action.name.lowercase()

private fun json(value: Any?): JsonElement = when (value) {
    null -> JsonNull
    is JsonElement -> value
    is String -> JsonPrimitive(value)
    is Boolean -> JsonPrimitive(value)
    is Number -> JsonPrimitive(value)
    is Map<*, *> -> JsonObject(value.entries.associate { it.key.toString() to json(it.value) })
    is Iterable<*> -> JsonArray(value.map(::json))
    else -> JsonPrimitive(value.toString())
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
        "trash_success" -> trash(instrumentation, false)
        "trash_failure_retry" -> trash(instrumentation, true)
        else -> error("unknown canonical key: $key")
    }
    json(mapOf(
        "key" to key,
        "before" to outcome.before,
        "after" to outcome.after,
        "observed" to outcome.observed,
        "invariantChecks" to outcome.checks.map {
            mapOf("invariant" to it.invariant, "passed" to it.passed, "evidence" to it.evidence)
        },
        "productionBodies" to outcome.productionBodies,
    )).toString()
}
