package org.wordpress.android.ui.prefs.experimentalfeatures
open class ExperimentalFeatures {
    enum class Feature { NETWORK_DEBUGGING }
    open fun isEnabled(feature: Feature): Boolean = false
}
