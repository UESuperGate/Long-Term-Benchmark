package org.wordpress.android.ui.mysite

import org.wordpress.android.fluxc.model.SiteModel
open class SelectedSiteRepository(private var selected: SiteModel? = SiteModel()) {
    open fun getSelectedSite(): SiteModel? = selected
    fun setSelectedSite(site: SiteModel?) { selected = site }
}
