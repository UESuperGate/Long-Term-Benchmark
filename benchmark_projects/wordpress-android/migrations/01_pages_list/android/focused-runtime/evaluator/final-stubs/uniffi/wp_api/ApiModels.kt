package uniffi.wp_api

import java.util.Date

sealed interface PostStatus {
    data object Publish : PostStatus
    data object Private : PostStatus
    data object Draft : PostStatus
    data object Pending : PostStatus
    data object Future : PostStatus
    data object Trash : PostStatus
    data object Any : PostStatus
    data class Custom(val value: String) : PostStatus
}

enum class PostEndpointType { Pages, Posts }
enum class WpApiParamOrder { ASC, DESC }
enum class WpApiParamPostsOrderBy { TITLE, DATE }
data class PostRetrieveParams(val unused: Boolean = false)
data class PostUpdateParams(val status: PostStatus? = null, val parent: Long? = null, val meta: Any? = null)
data class SiteSettingsUpdateParams(val pageOnFront: ULong = 0u, val pageForPosts: ULong = 0u)
data class RenderedText(val raw: String? = null, val rendered: String? = null)
data class AnyPostWithEditContext(
    val id: Long,
    val parent: Long? = null,
    val title: RenderedText? = null,
    val excerpt: RenderedText? = null,
    val dateGmt: Date = Date(0),
    val modifiedGmt: Date = Date(0),
    val link: String = "",
    val password: String? = null,
    val status: PostStatus? = null,
    val author: Long? = null,
    val featuredMedia: Long? = null,
)
