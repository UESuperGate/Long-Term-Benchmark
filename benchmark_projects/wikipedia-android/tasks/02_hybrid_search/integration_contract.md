# Hybrid Search Integration Contract

This document contains only stable production API shape and integration boundaries. Evaluator-owned data is intentionally excluded.

## Runtime integration rule

Semantic tests must execute the real production entry path. On Android, mode changes, submission, retry, semantic feedback, opt-out, and rendered state are owned by `HybridSearchPageActionPrefix`; dispatch and merge behavior then run through the page-owned `SearchResultsViewModel`. On ArkTS, the ArkUI page must own a real `HybridSearchPageStore`, which in turn owns a real `HybridSearchViewModel`. Controlled HTTP, feedback, standard-search, preferences, and experiment services may terminate the call graph only at the external leaves listed below. A harness implementation of concurrency, fallback, merge, retry, mapping, or opt-out is not valid production evidence.

## Android production sources

- `app/src/main/java/org/wikipedia/search/SearchResultsViewModel.kt`
- `app/src/main/java/org/wikipedia/search/SearchResultsFragment.kt`
- `app/src/main/java/org/wikipedia/search/HybridSearchResultsScreen.kt`
- `app/src/main/java/org/wikipedia/search/SemanticSearchService.kt`
- `app/src/main/java/org/wikipedia/search/HybridSearchAbCTest.kt`
- `app/src/main/java/org/wikipedia/settings/Prefs.kt`

Package: `org.wikipedia.search`

```kotlin
class SearchResultsViewModel() : ViewModel() {
    var countsPerLanguageCode: MutableList<Pair<String, Int>>
    lateinit var invokeSource: Constants.InvokeSource
    var searchTerm: StateFlow<String?>
    var searchTermForLogging: SharedFlow<String?>
    var lexicalResultsForLogging: StateFlow<List<SearchResult>?>
    var languageCode: StateFlow<String>
    val hybridSearchResultState: StateFlow<UiState<List<SearchResult>>>
    val getTestGroup: String
    val isHybridSearchExperimentOn: Boolean

    fun loadHybridSearchResults(): Unit
    fun updateSearchTerm(term: String?): Unit
    fun updateLanguageCode(code: String): Unit
    fun refreshSearchResults(): Unit
    fun resetHybridSearchState(): Unit
    fun getEventActionContext(): Map<String, Any>
    fun getBreadcrumbActionContext(): Map<String, String>
}

class SearchResultsFragment() : Fragment() {
    var showHybridSearch: Boolean
    val isShowing: Boolean

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View

    fun show(): Unit
    fun hide(): Unit
    fun startSearch(term: String?, force: Boolean, resetHybridSearch: Boolean): Unit
    fun setInvokeSource(invokeSource: Constants.InvokeSource): Unit
}

interface SemanticSearchService {
    suspend fun search(
        query: String,
        count: Int,
        table: String,
        includeText: Boolean
    ): SemanticSearchResults

    companion object {
        const val BASE_URL: String
    }
}

class HybridSearchPageActionPrefix(effects: HybridSearchPageEffects) {
    fun openHybridSearch(): Unit
    fun submitSearch(): Unit
    fun retry(): Unit
    fun rateSemanticResult(position: Int, positive: Boolean): Unit
    fun turnOffHybridSearch(): Unit
    fun snapshot(): HybridSearchPageSnapshot
}

class SemanticSearchResults() {
    val languageCode: String
    val query: String
    val results: List<SemanticSearchResult>
}

class SemanticSearchResult() {
    val title: String
    val sectionHeader: String
    val sectionIndex: Int
    val sectionText: String
    val url: String
}
```

Package: `org.wikipedia.settings`

```kotlin
object Prefs {
    var isHybridSearchEnabled: Boolean
}
```

The native episode strongly links one application-owned page action prefix and observes that owner's snapshot, reopened preference storage, and real HTTP/page leaf logs. It never constructs or invokes `SearchResultsViewModel` directly. `enable` and `retry` execute only in their event phase. Missing owner APIs are compile/runtime binding failures, never base-like verdicts.

## Android external leaf boundaries

- Lexical HTTP: the MediaWiki service calls reached through `ServiceFactory.get(wikiSite)` are controlled leaves:

```kotlin
suspend fun prefixSearchResponse(term: String, count: Int, offset: Int): HttpResponse<MwQueryResponse>
suspend fun fullTextSearch(term: String, count: Int, offset: Int): MwQueryResponse
suspend fun fullTextSearchResponse(
    term: String,
    count: Int,
    offset: Int,
    isSemantic: Boolean
): HttpResponse<MwQueryResponse>
suspend fun getInfoByPageIdsOrTitles(titles: String): MwQueryResponse
```

- Semantic HTTP: `SemanticSearchService.search(...)` is a controlled transport leaf. Production request selection and response mapping remain application-owned.
- Experiment assignment: `HybridSearchAbCTest.getGroupName(): String` and `HybridSearchAbCTest.isHybridSearchEnabled(languageCode: String): Boolean` may be controlled inputs. Production eligibility checks remain in the application path.
- Persistence: the backing store behind `Prefs.isHybridSearchEnabled` is controllable. Opt-out must still execute the production Fragment body that updates the preference and page mode.
- Feedback/analytics transport and `SearchResultCallback` navigation are leaves. The Fragment must still construct feedback metadata, convert positions, select the target result, and return the active query to standard search.
- Android lifecycle, Compose rendering primitives, keyboard, and browser/navigation services are leaves. They may expose callbacks but must not recreate page mode or retry logic.

## ArkTS production sources

- `entry/src/main/ets/pages/Index.ets`
- `entry/src/main/ets/model/HybridSearchModels.ets`
- `entry/src/main/ets/model/HybridSearchViewModel.ets`
- `entry/src/main/ets/model/HybridSearchPageStore.ets`
- `entry/src/main/ets/model/HttpSearchLeaf.ets`

### Model API

```ts
export interface SearchHttpLeaf {
  prefix(query: string, language: string): Promise<string[]>;
  fullText(query: string, language: string): Promise<string[]>;
  semantic(query: string, language: string): Promise<string[]>;
}

export interface FeedbackPayload {
  elementId: string;
  query: string;
  position: number;
  title: string;
}

export interface FeedbackLeaf {
  submit(payload: FeedbackPayload): Promise<void>;
}

export interface StandardSearchLeaf {
  request(query: string): void;
}

export interface HybridSearchState {
  phase: string;
  lexicalTitles: string[];
  semanticTitles: string[];
  notice?: string;
  retryAvailable: boolean;
}

export interface HybridSearchSettings {
  language: string;
  experimentGroup: string;
  remoteEnabled: boolean;
  hybridEnabled: boolean;
  query: string;
}

export class HybridSearchViewModel {
  state: HybridSearchState;

  constructor(http: SearchHttpLeaf);
  search(query: string, language: string): Promise<HybridSearchState>;
  retry(): Promise<HybridSearchState>;
}

export class HybridSearchPageStore {
  readonly viewModel: HybridSearchViewModel;
  mode: string;

  static create(
    context: common.UIAbilityContext,
    settings: HybridSearchSettings,
    http: SearchHttpLeaf,
    feedback: FeedbackLeaf,
    standardSearch: StandardSearchLeaf
  ): Promise<HybridSearchPageStore>;

  openHybrid(): void;
  submit(): Promise<HybridSearchState>;
  retry(): Promise<HybridSearchState>;
  rate(title: string, position: number, positive: boolean): Promise<void>;
  optOut(): Promise<void>;
  updateQuery(query: string): void;
  sections(): string[];
}

export class HttpSearchLeaf implements SearchHttpLeaf {
  prefix(query: string, language: string): Promise<string[]>;
  fullText(query: string, language: string): Promise<string[]>;
  semantic(query: string, language: string): Promise<string[]>;
}
```

`Index.aboutToAppear()` is the ArkUI production composition entry. It creates `HybridSearchPageStore` with the production `HttpSearchLeaf` and page-owned feedback and standard-search leaves. The rendered Open hybrid, Search, Retry, rating, Opt out, and query controls call the public store API above. Deterministic tests may substitute only the declared leaf interfaces and ArkData backing store; they must keep `HybridSearchPageStore` and `HybridSearchViewModel` in the executed call path and observe their state, persistence, and emitted leaf calls.
