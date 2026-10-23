package org.wordpress.android.fluxc.model

class SiteModel {
    var id: Int = 0
    var siteId: Long = 0
    var name: String = ""
    var url: String = ""
    var isVisible: Boolean = true
    var isWpForTeamsSite: Boolean = false
    var isUsingWpComRestApi: Boolean = true
}
