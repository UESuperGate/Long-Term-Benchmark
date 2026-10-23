package org.wikipedia.dataclient.mwapi

class MwQueryResponse(val query: Query? = null)
class Query(val pages: List<MwQueryPage> = emptyList())

class MwQueryPage(
    val title: String,
    val index: Int,
    val coordinates: Any? = null,
    private val thumbnail: String? = null,
    val description: String? = null
) {
    fun thumbUrl(): String? = thumbnail
}
