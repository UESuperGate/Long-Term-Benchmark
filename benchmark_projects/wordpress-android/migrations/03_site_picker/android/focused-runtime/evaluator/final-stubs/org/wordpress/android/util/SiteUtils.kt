package org.wordpress.android.util

import org.wordpress.android.fluxc.model.SiteModel
import org.wordpress.android.util.image.BlavatarShape
import org.wordpress.android.util.image.ImageType

object SiteUtils {
    fun getSiteNameOrHomeURL(site: SiteModel): String = site.name.ifEmpty { site.url }
    fun getHomeURLOrHostName(site: SiteModel): String = site.url
    fun getSiteIconUrl(site: SiteModel, size: Int): String = "https://icon.invalid/${site.id}?s=$size"
    fun getSiteImageType(value: Boolean, shape: BlavatarShape): ImageType = ImageType.BLAVATAR
}
