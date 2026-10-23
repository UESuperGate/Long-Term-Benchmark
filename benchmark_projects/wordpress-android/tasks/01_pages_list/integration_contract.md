# Pages List Integration Contract

This document defines the production API surface used by the runtime integration. Implementations may organize private helpers differently, but the symbols below must remain available with compatible signatures.

## Android production surface

- Target package: `org.wordpress.android.ui.pagesrs`
- Target source path: `WordPress/src/main/java/org/wordpress/android/ui/pagesrs/`
- Candidate production sources are discovered by that package or path. The runtime compiles them with the immutable WordPress production dependencies; test-source or evaluator-owned APIs are not part of the implementation contract.

The main APK owns a `PagesRuntimeOwnerActivity`. Instrumentation launches that entry and may only
dispatch case events through its owner methods. The owner acquires `PagesRsListViewModel` from its
`ViewModelStore` with `ViewModelProvider`; the evaluator does not retain or drive a detached presenter.

The owner dependency factory constructs these production classes:

```kotlin
internal class PageRsFluxCBridge(
    wpApiClientProvider: WpApiClientProvider,
    postStore: PostStore,
    postSqlUtils: PostSqlUtils,
    postMapper: PostRsToFluxCMapper,
)

internal class PageRsHomepageSettings(
    wpApiClientProvider: WpApiClientProvider,
    dispatcher: Dispatcher,
)

internal class PagesRsListViewModel(
    selectedSiteRepository: SelectedSiteRepository,
    serviceProvider: WpServiceProvider,
    dispatcher: Dispatcher,
    restClient: PostRsRestClient,
    resourceProvider: ResourceProvider,
    postStore: PostStore,
    homepageSettings: PageRsHomepageSettings,
    blazeFeatureUtils: BlazeFeatureUtils,
    fluxCBridge: PageRsFluxCBridge,
    networkUtilsWrapper: NetworkUtilsWrapper,
    accountStore: AccountStore,
    appPrefsWrapper: AppPrefsWrapper,
    analyticsTracker: AnalyticsTrackerWrapper,
)
```

The application owner exposes these evaluator-facing event methods:

```kotlin
fun PagesRuntimeOwnerActivity.open(tab: PageRsListTab = PageRsListTab.PUBLISHED)
fun PagesRuntimeOwnerActivity.refresh()
fun PagesRuntimeOwnerActivity.openSearch()
fun PagesRuntimeOwnerActivity.changeSearchQuery(query: String)
fun PagesRuntimeOwnerActivity.closeSearch()
fun PagesRuntimeOwnerActivity.selectAuthor(selection: AuthorFilterSelection)
fun PagesRuntimeOwnerActivity.openPage(pageId: Long)
fun PagesRuntimeOwnerActivity.chooseMenuAction(pageId: Long, action: PageRsMenuAction)
fun PagesRuntimeOwnerActivity.confirmPendingAction()
fun PagesRuntimeOwnerActivity.performSnackbarAction(message: SnackbarMessage)
fun PagesRuntimeOwnerActivity.renderHierarchy(pages: List<PageRsUiModel>)
fun PagesRuntimeOwnerActivity.renderMenu(...)
```

Those owner methods invoke these production methods and functions:

```kotlin
fun PagesRsListViewModel.initTab(tab: PageRsListTab)
fun PagesRsListViewModel.refreshTab(tab: PageRsListTab, isUserRefresh: Boolean = false)
fun PagesRsListViewModel.onSearchOpen()
fun PagesRsListViewModel.onSearchQueryChanged(query: String, activeTab: PageRsListTab)
fun PagesRsListViewModel.onSearchClose(activeTab: PageRsListTab)
fun PagesRsListViewModel.onAuthorFilterChanged(
    selection: AuthorFilterSelection,
    activeTab: PageRsListTab,
)
fun PagesRsListViewModel.openPage(remotePageId: Long, tab: PageRsListTab)
fun PagesRsListViewModel.onPageMenuAction(remotePageId: Long, action: PageRsMenuAction)
fun PagesRsListViewModel.onConfirmPendingAction()

fun buildRows(
    pages: List<PageRsUiModel>,
    applyHierarchy: Boolean,
    pageOnFront: Long,
    pageForPosts: Long,
): List<PageRsListItem>

fun computePageMenuActions(
    status: PostStatus?,
    isHomepage: Boolean,
    isPostsPage: Boolean,
    hasPassword: Boolean,
    isBlazeEligibleSite: Boolean,
    canManageHomepage: Boolean,
): List<PageRsMenuAction>
```

The runtime observes only owner-rendered values, production state, production events, persistent
preference storage, and controlled-leaf call logs:

```kotlin
val tabStates: StateFlow<Map<PageRsListTab, PageTabUiState>>
val isSearchActive: StateFlow<Boolean>
val searchQuery: StateFlow<String>
val authorFilter: StateFlow<AuthorFilterSelection>
val pendingConfirmation: StateFlow<PageRsListConfirmation?>
val snackbarMessages: Flow<SnackbarMessage>
```

`PageTabUiState`, `PageRsListItem`, `PageRsUiModel`, `PageRsListConfirmation`, `PageRsListTab`, and `PageRsMenuAction` are production model types in the same package. Their constructor properties must remain readable by code in that package.

## Android leaf boundaries

The runtime controls only external dependency leaves while executing the production bodies above. The relevant callable boundary is:

```kotlin
CollectionLeaf.factory:
    (PostEndpointType, PostListFilter, UInt) -> ObservableMetadataCollection

suspend fun ObservableMetadataCollection.refresh()
suspend fun ObservableMetadataCollection.loadItems(): List<MetadataItem>
suspend fun ObservableMetadataCollection.listInfo(): ListInfo
fun ObservableMetadataCollection.close()

suspend fun PostService.trashPost(endpointType: PostEndpointType, pageId: Long)
suspend fun PostRsRestClient.fetchMediaUrls(
    site: SiteModel,
    ids: List<Long>,
    size: Int,
): Map<Long, String>

fun WpApiClientProvider.getWpApiClient(site: SiteModel): WpApiClient
```

The `WpApiClient` returned to `PageRsFluxCBridge` supplies the normal production page-retrieval request path. No evaluator-specific interface is required in production code.

`given` may seed collection contents, service outcomes, media responses, bridge responses, and the
persisted author preference. It must not inject `PageTabUiState`, rendered rows, menu results, events,
or snackbar output. Trash observations are read after the production owner opens the real trashed tab;
the evaluator does not maintain a parallel `trashedRows` model.

The arbitrary-candidate harness always enters an application-owned Activity. An untouched 26.8
candidate executes the shared `PagesActivity` prefix and is scored from that runtime observation;
source discovery and adapter wiring metadata never determine a case verdict. Missing instrumentation,
missing runtime symbols, process crashes, invalid payloads, and install failures are infrastructure
errors and remain `not_scored`, never semantic failures.

## ArkTS controller surface

- Production source path: `entry/src/main/ets/features/PagesController.ets`
- The device runtime imports the following exports from that module.

```typescript
export interface PageRecord {
  id: number;
  parentId: number;
  title: string;
  status: string;
  featuredMediaId?: number;
  homepage?: boolean;
  postsPage?: boolean;
  passwordProtected?: boolean;
}

export interface PageRow {
  page: PageRecord;
  indent: number;
  thumbnailUrl?: string;
  statusLabel: string;
}

export interface PageRequest {
  entity: string;
  tab: string;
  statuses: string[];
  orderBy: string;
  order: string;
  pageSize: number;
  search: string;
  authorIds: number[];
}

export interface PagesServiceLeaf {
  fetch(request: PageRequest): Promise<PageRecord[]>;
  trash(pageId: number): Promise<void>;
  resolveMedia(mediaId: number): Promise<string>;
}
```

`PagesController` is constructed as `new PagesController(service: PagesServiceLeaf)` and exposes a readable `store: PagesStore`. The runtime calls:

```typescript
setSignedInAuthorId(id: number): void;
open(): Promise<void>;
loadTab(tab: string): Promise<boolean>;
refresh(): Promise<boolean>;
retryRefresh(): Promise<boolean>;
openSearch(): void;
updateSearch(query: string, settledForMs?: number): Promise<boolean>;
closeSearch(): Promise<void>;
selectAuthor(selection: string): Promise<void>;
menuActions(page: PageRecord, canManageHomepage: boolean, blazeEligible: boolean): string[];
chooseTrash(pageId: number): void;
confirmTrash(): Promise<boolean>;
retryTrash(): Promise<boolean>;
```

The readable `PagesStore` state is:

```typescript
surface: string;
tabs: string[];
selectedTab: string;
rows: PageRow[];
searchActive: boolean;
query: string;
authorSelection: string;
persistedAuthorSelection: string;
loading: boolean;
refreshing: boolean;
error: string;
feedback: string;
pendingTrash?: number;
trashedRows: number[];
requestCount: number;
closedSearchCollections: number;
```
