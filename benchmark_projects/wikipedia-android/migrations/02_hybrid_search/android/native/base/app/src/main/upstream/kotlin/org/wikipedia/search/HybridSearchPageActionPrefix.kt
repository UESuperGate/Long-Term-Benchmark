package org.wikipedia.search

import org.wikipedia.Constants

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

/** Same application entry ABI as final, backed by the pre-feature search page. */
class HybridSearchPageActionPrefix(
    private val effects: HybridSearchPageEffects,
    private val viewModel: SearchResultsViewModel = SearchResultsViewModel()
) {
    init {
        viewModel.invokeSource = Constants.InvokeSource.SEARCH
        viewModel.updateLanguageCode("fr")
        viewModel.updateSearchTerm("Paris")
    }

    fun openHybridSearch() = Unit
    fun submitSearch() = viewModel.refreshSearchResults()
    fun retry() = viewModel.refreshSearchResults()
    fun rateSemanticResult(position: Int, positive: Boolean) = Unit
    fun turnOffHybridSearch() = Unit

    fun snapshot() = HybridSearchPageSnapshot(
        featureAvailable = false,
        mode = "standard",
        phase = "idle",
        query = viewModel.searchTerm.value.orEmpty(),
        sections = listOf("lexical"),
        lexicalTitles = emptyList(),
        semanticTitles = emptyList(),
        retryAvailable = false,
        notice = null
    )
}
