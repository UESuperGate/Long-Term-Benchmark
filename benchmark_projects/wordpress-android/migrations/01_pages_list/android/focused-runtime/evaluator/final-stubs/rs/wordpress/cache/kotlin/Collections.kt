package rs.wordpress.cache.kotlin

import uniffi.wp_api.PostEndpointType
import uniffi.wp_mobile.PostItemState
import uniffi.wp_mobile.PostListFilter
import uniffi.wp_mobile.PostService
import uniffi.wp_mobile_cache.ListState

data class MetadataItem(val id: Long, val state: PostItemState)
data class ListInfo(val state: ListState = ListState.IDLE, val morePages: Boolean = false)
val ListInfo.hasMorePages: Boolean get() = morePages

open class ObservableMetadataCollection {
    private var dataObserver: (() -> Unit)? = null
    private var listObserver: (() -> Unit)? = null
    open fun addDataObserver(observer: () -> Unit) { dataObserver = observer }
    open fun addListInfoObserver(observer: () -> Unit) { listObserver = observer }
    open suspend fun refresh() {}
    open suspend fun loadNextPage() {}
    open suspend fun loadItems(): List<MetadataItem> = emptyList()
    open suspend fun listInfo(): ListInfo? = ListInfo()
    open fun close() {}
    fun emitData() { dataObserver?.invoke() }
    fun emitListInfo() { listObserver?.invoke() }
}

object CollectionLeaf {
    var factory: (PostEndpointType, PostListFilter, UInt) -> ObservableMetadataCollection = { _, _, _ -> ObservableMetadataCollection() }
}

fun PostService.getObservablePostMetadataCollectionWithEditContext(
    endpointType: PostEndpointType,
    filter: PostListFilter,
    perPage: UInt,
): ObservableMetadataCollection = CollectionLeaf.factory(endpointType, filter, perPage)
