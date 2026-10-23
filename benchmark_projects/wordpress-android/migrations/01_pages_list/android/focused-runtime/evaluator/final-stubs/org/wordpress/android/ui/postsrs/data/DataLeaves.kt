package org.wordpress.android.ui.postsrs.data

import org.wordpress.android.fluxc.model.SiteModel
import uniffi.wp_mobile.PostService

open class WpService(private val postService: PostService = PostService()) { open fun posts(): PostService = postService }
open class WpServiceProvider(var service: WpService = WpService()) { open fun getService(site: SiteModel): WpService = service }
open class PostRsRestClient {
    var clearCount: Int = 0
    open fun clearCaches() { clearCount += 1 }
    open suspend fun fetchMediaUrls(site: SiteModel, ids: List<Long>, size: Int): Map<Long, String> = emptyMap()
    open suspend fun fetchUserDisplayNames(site: SiteModel, ids: List<Long>): Map<Long, String> = emptyMap()
}
