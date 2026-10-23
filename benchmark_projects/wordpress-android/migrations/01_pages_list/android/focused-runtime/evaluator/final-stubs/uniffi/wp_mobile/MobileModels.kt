package uniffi.wp_mobile

import uniffi.wp_api.AnyPostWithEditContext
import uniffi.wp_api.PostEndpointType
import uniffi.wp_api.PostStatus
import uniffi.wp_api.PostUpdateParams
import uniffi.wp_api.WpApiParamOrder
import uniffi.wp_api.WpApiParamPostsOrderBy

data class FullEntityAnyPostWithEditContext(val data: AnyPostWithEditContext)

sealed interface PostItemState {
    data class Fresh(val data: FullEntityAnyPostWithEditContext) : PostItemState
    data class Stale(val data: FullEntityAnyPostWithEditContext) : PostItemState
    data class FetchingWithData(val data: FullEntityAnyPostWithEditContext) : PostItemState
    data class FailedWithData(val data: FullEntityAnyPostWithEditContext) : PostItemState
    data object Missing : PostItemState
    data object Fetching : PostItemState
    data object Failed : PostItemState
}

data class PostListFilter(
    val status: List<PostStatus>,
    val order: WpApiParamOrder,
    val orderby: WpApiParamPostsOrderBy,
    val search: String?,
    val author: List<Long>,
)

open class PostService {
    open suspend fun trashPost(endpointType: PostEndpointType, pageId: Long) {}
    open suspend fun deletePostPermanently(endpointType: PostEndpointType, pageId: Long) {}
    open suspend fun updatePost(endpointType: PostEndpointType, pageId: Long, params: PostUpdateParams) {}
}
