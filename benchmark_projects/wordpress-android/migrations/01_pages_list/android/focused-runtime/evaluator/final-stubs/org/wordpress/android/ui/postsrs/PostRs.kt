package org.wordpress.android.ui.postsrs

import org.wordpress.android.R
import org.wordpress.android.fluxc.model.PostModel
import org.wordpress.android.fluxc.model.SiteModel
import org.wordpress.android.util.NetworkUtilsWrapper
import org.wordpress.android.viewmodel.ResourceProvider
import uniffi.wp_api.AnyPostWithEditContext
import uniffi.wp_api.PostStatus
import java.util.Date

object PostRsDateFormatter { fun format(date: Date, status: PostStatus?): String = date.time.toString() }
fun PostStatus?.toLabel(): Int = when (this) {
    is PostStatus.Pending -> R.string.post_status_pending_review
    else -> 0
}
data class SnackbarMessage(val message: String, val actionLabel: String? = null, val onAction: (() -> Unit)? = null)
object PostRsErrorUtils {
    fun isAuthError(error: Exception): Boolean = false
    fun friendlyErrorMessage(error: Exception?, defaultResId: Int?, resources: ResourceProvider, network: NetworkUtilsWrapper): String =
        defaultResId?.let(resources::getString) ?: error?.message ?: "general"
}
open class PostRsToFluxCMapper {
    open fun map(page: AnyPostWithEditContext, site: SiteModel): PostModel =
        PostModel().apply { remotePostId = page.id }
}
