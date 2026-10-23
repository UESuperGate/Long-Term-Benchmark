package org.wordpress.android.networking.restapi

import rs.wordpress.api.kotlin.WpComApiClient

open class WpComApiClientProvider(private val client: WpComApiClient = WpComApiClient()) {
    open fun getWpComApiClient(accessToken: String): WpComApiClient = client
}
