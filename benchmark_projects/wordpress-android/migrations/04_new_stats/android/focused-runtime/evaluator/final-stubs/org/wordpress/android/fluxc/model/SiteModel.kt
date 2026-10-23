package org.wordpress.android.fluxc.model

data class SiteModel(
    var siteId: Long = 123,
    var url: String = "https://example.test",
    var adminUrl: String = "https://example.test/wp-admin/"
)
