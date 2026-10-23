package org.wordpress.android.ui.mysite

import org.wordpress.android.fluxc.model.SiteModel

class SelectedSiteRepository(private var site: SiteModel? = SiteModel()) {
    fun getSelectedSite(): SiteModel? = site
}
