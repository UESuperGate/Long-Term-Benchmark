package org.wikipedia.dataclient

import java.lang.reflect.Proxy
import org.wikipedia.dataclient.mwapi.MwQueryPage
import org.wikipedia.dataclient.mwapi.MwQueryResponse
import org.wikipedia.dataclient.mwapi.Query
import org.wikipedia.search.RuntimeSearchLeaves

class WikiSite(val url: String = "", val languageCode: String = "fr") {
    fun dbName(): String = "${languageCode}wiki"

    companion object {
        fun forLanguageCode(languageCode: String): WikiSite = WikiSite(languageCode = languageCode)
    }
}

class HttpResponse<T>(private val value: T, private val responseHeaders: Map<String, String>) {
    fun body(): T = value
    fun headers(): Map<String, String> = responseHeaders
}

class WikiSearchService {
    suspend fun prefixSearchResponse(term: String, count: Int, offset: Int): HttpResponse<MwQueryResponse> =
        RuntimeSearchLeaves.prefix()

    suspend fun fullTextSearch(term: String, count: Int, offset: Int): MwQueryResponse =
        RuntimeSearchLeaves.fullText()

    suspend fun fullTextSearchResponse(
        term: String,
        count: Int,
        offset: Int,
        isSemantic: Boolean = false
    ): HttpResponse<MwQueryResponse> = if (isSemantic) {
        RuntimeSearchLeaves.semantic()
    } else {
        HttpResponse(RuntimeSearchLeaves.fullText(), mapOf("x-search-id" to "lex-full"))
    }

    suspend fun getInfoByPageIdsOrTitles(titles: String): MwQueryResponse = MwQueryResponse(Query(emptyList()))
}

object ServiceFactory {
    fun get(wikiSite: WikiSite): WikiSearchService = WikiSearchService()

    @Suppress("UNCHECKED_CAST")
    operator fun <T> get(wikiSite: WikiSite, baseUrl: String, service: Class<T>): T {
        return Proxy.newProxyInstance(service.classLoader, arrayOf(service)) { _, method, _ ->
            if (method.name == "search") RuntimeSearchLeaves.emptySemanticSearchResult(service.classLoader)
            else error("Unexpected service method ${method.name}")
        } as T
    }
}
