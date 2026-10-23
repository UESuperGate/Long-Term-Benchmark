package org.wordpress.android.fluxc.network.rest.wpapi.rs

import org.wordpress.android.fluxc.model.SiteModel
import rs.wordpress.api.kotlin.WpRequestResult
import rs.wordpress.api.kotlin.WpResponse
import uniffi.wp_api.AnyPostWithEditContext
import uniffi.wp_api.PostEndpointType
import uniffi.wp_api.PostRetrieveParams
import uniffi.wp_api.SiteSettingsUpdateParams

data class SiteSettings(
    val showOnFront: String = "page",
    val pageOnFront: ULong = 0u,
    val pageForPosts: ULong = 0u,
)

open class PostsEndpoint(var page: AnyPostWithEditContext) {
    open fun retrieveWithEditContext(type: PostEndpointType, id: Long, params: PostRetrieveParams): AnyPostWithEditContext = page
}

open class SiteSettingsEndpoint(var current: SiteSettings = SiteSettings()) {
    open fun retrieveWithEditContext(): SiteSettings = current
    open fun update(params: SiteSettingsUpdateParams): SiteSettings {
        current = SiteSettings("page", params.pageOnFront, params.pageForPosts)
        return current
    }
}

class RequestBuilder(
    private val postsEndpoint: PostsEndpoint,
    private val settingsEndpoint: SiteSettingsEndpoint,
) {
    fun posts(): PostsEndpoint = postsEndpoint
    fun siteSettings(): SiteSettingsEndpoint = settingsEndpoint
}

open class WpApiClient(
    val builder: RequestBuilder,
    var failure: String? = null,
) {
    open suspend fun <T> request(block: (RequestBuilder) -> T): WpRequestResult<T> =
        failure?.let { WpRequestResult.WpError(it) } ?: WpRequestResult.Success(WpResponse(block(builder)))
}

open class WpApiClientProvider(var client: WpApiClient) {
    open fun getWpApiClient(site: SiteModel): WpApiClient = client
}
