package org.wikipedia.search

import org.wikipedia.Constants
import org.wikipedia.settings.Prefs
import org.wikipedia.util.UiState

interface HybridSearchPageEffects {
    fun submitFeedback(payload: Map<String, Any>)
    fun requestStandardSearch(query: String)
}

data class HybridSearchPageSnapshot(
    val featureAvailable: Boolean,
    val mode: String,
    val phase: String,
    val query: String,
    val sections: List<String>,
    val lexicalTitles: List<String>,
    val semanticTitles: List<String>,
    val retryAvailable: Boolean,
    val notice: String?
)

/** Focused application-owned action prefix for the hybrid results page. */
class HybridSearchPageActionPrefix(
    private val effects: HybridSearchPageEffects,
    private val viewModel: SearchResultsViewModel = SearchResultsViewModel()
) {
    private var mode = "standard"
    private var submitted = false

    init {
        viewModel.invokeSource = Constants.InvokeSource.SEARCH
        viewModel.updateLanguageCode("fr")
        viewModel.updateSearchTerm("Paris")
    }

    fun openHybridSearch() {
        if (Prefs.isHybridSearchEnabled && viewModel.isHybridSearchExperimentOn) {
            mode = "hybrid"
        }
    }

    fun submitSearch() {
        if (mode != "hybrid") return
        submitted = true
        viewModel.resetHybridSearchState()
        viewModel.loadHybridSearchResults()
    }

    fun retry() {
        submitSearch()
    }

    fun rateSemanticResult(position: Int, positive: Boolean) {
        val result = semanticResults().getOrNull(position) ?: error("semantic result $position missing")
        effects.submitFeedback(
            mapOf(
                "elementId" to if (positive) "thumb_up" else "thumb_down",
                "query" to viewModel.searchTerm.value.orEmpty(),
                "position" to position + 1,
                "title" to result.pageTitle.prefixedText
            )
        )
    }

    fun turnOffHybridSearch() {
        Prefs.isHybridSearchEnabled = false
        mode = "standard"
        effects.requestStandardSearch(viewModel.searchTerm.value.orEmpty())
    }

    fun snapshot(): HybridSearchPageSnapshot {
        val state = viewModel.hybridSearchResultState.value
        val results = (state as? UiState.Success<List<SearchResult>>)?.data.orEmpty()
        val lexical = results.filter { it.type == SearchResult.SearchResultType.SEARCH }
            .map { it.pageTitle.prefixedText }
        val semantic = results.filter { it.type == SearchResult.SearchResultType.SEMANTIC }
            .map { it.pageTitle.prefixedText }
        val phase = when {
            !submitted -> "idle"
            state is UiState.Success<*> -> "success"
            state is UiState.Error -> "error"
            else -> "loading"
        }
        val sections = when {
            lexical.isEmpty() -> if (semantic.isEmpty()) emptyList() else listOf("semantic")
            semantic.isEmpty() -> listOf("lexical")
            viewModel.getTestGroup == "semanticLexical" -> listOf("semantic", "lexical")
            else -> listOf("lexical", "semantic")
        }
        return HybridSearchPageSnapshot(
            featureAvailable = true,
            mode = mode,
            phase = phase,
            query = viewModel.searchTerm.value.orEmpty(),
            sections = sections,
            lexicalTitles = lexical,
            semanticTitles = semantic,
            retryAvailable = submitted && (phase == "error" || (phase == "success" && (lexical.isEmpty() || semantic.isEmpty()))),
            notice = when {
                phase != "success" -> null
                lexical.isEmpty() -> "lexical_empty"
                semantic.isEmpty() -> "semantic_empty"
                else -> null
            }
        )
    }

    private fun semanticResults(): List<SearchResult> =
        ((viewModel.hybridSearchResultState.value as? UiState.Success<List<SearchResult>>)?.data.orEmpty())
            .filter { it.type == SearchResult.SearchResultType.SEMANTIC }
}
