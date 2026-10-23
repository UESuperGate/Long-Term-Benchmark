package org.wordpress.android.fluxc.store

import org.wordpress.android.fluxc.model.SiteModel

open class SiteStore {
    open var sites: List<SiteModel> = emptyList()
    open var sitesAccessedViaWPComRest: List<SiteModel> = emptyList()
    open fun getSiteByLocalId(id: Int): SiteModel? = sites.firstOrNull { it.id == id }
}
