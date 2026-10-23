package org.wordpress.android.fluxc.model

open class SiteModel {
    var id: Int = 1
    var siteId: Long = 1
    var pageOnFront: Long = 0
    var pageForPosts: Long = 0
    var showOnFront: String = "page"
    var isUsingWpComRestApi: Boolean = true
    var hasCapabilityEditOthersPages: Boolean = false
    var hasCapabilityManageOptions: Boolean = true
    var isSingleUserSite: Boolean? = true
}

object SiteHomepageSettings {
    enum class ShowOnFront(val value: String) { PAGE("page"), POSTS("posts") }
}

open class PostModel {
    var remotePostId: Long = 0
    var remoteLastModified: String? = null
    var isPage: Boolean = true
    var isLocallyChanged: Boolean = false
    var localSiteId: Int = 1
    var title: String = ""
    var content: String = ""
    var categoryIdList: String = ""
    var postFormat: String = ""
    fun setIsPage(value: Boolean) { isPage = value }
}
