package androidx.paging

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf

class PagingConfig(val pageSize: Int, val initialLoadSize: Int = pageSize)
class PagingData<T>
class PagingState<Key : Any, Value : Any>

abstract class PagingSource<Key : Any, Value : Any> {
    abstract suspend fun load(params: LoadParams<Key>): LoadResult<Key, Value>
    abstract fun getRefreshKey(state: PagingState<Key, Value>): Key?

    open class LoadParams<Key : Any>(val key: Key?, val loadSize: Int)

    sealed class LoadResult<Key : Any, Value : Any> {
        class Page<Key : Any, Value : Any>(
            val data: List<Value>,
            val prevKey: Key?,
            val nextKey: Key?
        ) : LoadResult<Key, Value>()

        class Error<Key : Any, Value : Any>(val throwable: Throwable) : LoadResult<Key, Value>()
    }
}

class Pager<Key : Any, Value : Any>(
    config: PagingConfig,
    pagingSourceFactory: () -> PagingSource<Key, Value>
) {
    val flow: Flow<PagingData<Value>> = flowOf(PagingData())
}

fun <T> Flow<PagingData<T>>.cachedIn(scope: CoroutineScope): Flow<PagingData<T>> = this
