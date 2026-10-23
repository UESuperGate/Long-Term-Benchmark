package org.wordpress.android.ui.pagesrs

import android.os.Bundle
import android.view.View
import androidx.activity.ComponentActivity
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelStoreOwner
import java.util.concurrent.atomic.AtomicInteger

/** Application-owned runtime entry used by the semantic instrumentation. */
class PagesRuntimeOwnerActivity : ComponentActivity() {
    private lateinit var surfaceView: View

    internal val viewModel: PagesRsListViewModel by lazy {
        ViewModelProvider(this, requireNotNull(PagesRuntimeOwnerDependencies.factory))[PagesRsListViewModel::class.java]
    }

    internal var selectedTab: PageRsListTab = PageRsListTab.PUBLISHED
        private set
    internal var renderedRows: List<PageRsListItem> = emptyList()
        private set
    internal var renderedMenuActions: List<PageRsMenuAction> = emptyList()
        private set
    internal val callLog = mutableListOf<String>()
    internal val tabs: List<PageRsListTab> get() = PageRsListTab.entries

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        surfaceView = View(this).apply { contentDescription = SURFACE }
        setContentView(surfaceView)
        viewModel
        generation = generations.incrementAndGet()
        current = this
    }

    override fun onDestroy() {
        if (current === this) current = null
        super.onDestroy()
    }

    internal fun open(tab: PageRsListTab = PageRsListTab.PUBLISHED) {
        callLog += "PagesRuntimeOwnerActivity.open"
        selectedTab = tab
        viewModel.initTab(tab)
    }

    internal fun refresh() {
        callLog += "PagesRuntimeOwnerActivity.refresh"
        viewModel.refreshTab(selectedTab, isUserRefresh = true)
    }
    internal fun openSearch() {
        callLog += "PagesRuntimeOwnerActivity.openSearch"
        viewModel.onSearchOpen()
    }
    internal fun changeSearchQuery(query: String) {
        callLog += "PagesRuntimeOwnerActivity.changeSearchQuery"
        viewModel.onSearchQueryChanged(query, selectedTab)
    }
    internal fun closeSearch() {
        callLog += "PagesRuntimeOwnerActivity.closeSearch"
        viewModel.onSearchClose(selectedTab)
    }
    internal fun selectAuthor(selection: org.wordpress.android.ui.posts.AuthorFilterSelection) {
        callLog += "PagesRuntimeOwnerActivity.selectAuthor"
        viewModel.onAuthorFilterChanged(selection, selectedTab)
    }
    internal fun openPage(pageId: Long) {
        callLog += "PagesRuntimeOwnerActivity.openPage"
        viewModel.openPage(pageId, selectedTab)
    }
    internal fun chooseMenuAction(pageId: Long, action: PageRsMenuAction) {
        callLog += "PagesRuntimeOwnerActivity.chooseMenuAction"
        viewModel.onPageMenuAction(pageId, action)
    }
    internal fun confirmPendingAction() {
        callLog += "PagesRuntimeOwnerActivity.confirmPendingAction"
        viewModel.onConfirmPendingAction()
    }
    internal fun performSnackbarAction(message: org.wordpress.android.ui.postsrs.SnackbarMessage) {
        callLog += "PagesRuntimeOwnerActivity.performSnackbarAction"
        message.onAction?.invoke()
    }

    internal fun renderHierarchy(pages: List<PageRsUiModel>) {
        callLog += "PagesRuntimeOwnerActivity.renderHierarchy"
        renderedRows = buildRows(pages, applyHierarchy = true, pageOnFront = 0, pageForPosts = 0)
    }

    internal fun renderMenu(
        status: uniffi.wp_api.PostStatus?,
        isHomepage: Boolean,
        isPostsPage: Boolean,
        hasPassword: Boolean,
        isBlazeEligibleSite: Boolean,
        canManageHomepage: Boolean,
    ) {
        callLog += "PagesRuntimeOwnerActivity.renderMenu"
        renderedMenuActions = computePageMenuActions(
            status, isHomepage, isPostsPage, hasPassword, isBlazeEligibleSite, canManageHomepage
        )
    }

    internal val surface: String get() = surfaceView.contentDescription.toString()
    internal val owner: ViewModelStoreOwner get() = this

    companion object {
        const val SURFACE = "modern_pages"
        private val generations = AtomicInteger()
        @Volatile internal var current: PagesRuntimeOwnerActivity? = null
        @Volatile internal var generation: Int = 0
    }
}

internal object PagesRuntimeOwnerDependencies {
    @Volatile var factory: ViewModelProvider.Factory? = null
}
