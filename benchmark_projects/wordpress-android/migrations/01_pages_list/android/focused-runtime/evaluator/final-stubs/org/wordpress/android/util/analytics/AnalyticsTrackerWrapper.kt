package org.wordpress.android.util.analytics

import org.wordpress.android.analytics.AnalyticsTracker.Stat
import org.wordpress.android.fluxc.model.SiteModel
open class AnalyticsTrackerWrapper {
    open fun track(stat: Stat, site: SiteModel, properties: Map<String, *>? = null) {}
}
