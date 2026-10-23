package org.wikipedia.search

import org.wikipedia.Constants
import org.wikipedia.dataclient.WikiSite
import org.wikipedia.dataclient.mwapi.MwQueryPage
import org.wikipedia.page.PageTitle

class SearchResult {
    enum class SearchResultType { SEARCH, SEMANTIC }

    val pageTitle: PageTitle
    val location: Any?
    val type: SearchResultType
    val snippet: String

    constructor(
        page: MwQueryPage,
        wikiSite: WikiSite,
        location: Any?,
        type: SearchResultType
    ) {
        pageTitle = PageTitle(page.title, wikiSite)
        this.location = location
        this.type = type
        snippet = ""
    }

    constructor(
        pageTitle: PageTitle,
        searchResultType: SearchResultType = SearchResultType.SEARCH,
        snippet: String = ""
    ) {
        this.pageTitle = pageTitle
        location = null
        type = searchResultType
        this.snippet = snippet
    }
}

class StandardSearchResults(
    val results: List<SearchResult> = emptyList(),
    val continuation: Int? = null
)

interface SearchRepository<T> {
    suspend fun search(
        searchTerm: String,
        languageCode: String,
        invokeSource: Constants.InvokeSource,
        continuation: Int?,
        batchSize: Int,
        isPrefixSearch: Boolean,
        countsPerLanguageCode: MutableList<Pair<String, Int>>
    ): StandardSearchResults
}

class StandardSearchRepository : SearchRepository<StandardSearchResults> {
    override suspend fun search(
        searchTerm: String,
        languageCode: String,
        invokeSource: Constants.InvokeSource,
        continuation: Int?,
        batchSize: Int,
        isPrefixSearch: Boolean,
        countsPerLanguageCode: MutableList<Pair<String, Int>>
    ): StandardSearchResults = StandardSearchResults()
}

class HybridSearchAbCTest {
    fun getGroupName(): String = RuntimeSearchLeaves.group
    fun isHybridSearchEnabled(languageCode: String): Boolean = RuntimeSearchLeaves.enabled
}
