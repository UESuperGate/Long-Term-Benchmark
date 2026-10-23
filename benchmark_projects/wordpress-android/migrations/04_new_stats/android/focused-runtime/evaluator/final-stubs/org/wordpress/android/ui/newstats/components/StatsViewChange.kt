package org.wordpress.android.ui.newstats.components

import android.os.Parcelable
import kotlinx.parcelize.Parcelize

@Parcelize
sealed class StatsViewChange : Parcelable {
    @Parcelize
    data class Positive(val value: Long, val percentage: Double) : StatsViewChange()
    @Parcelize
    data class Negative(val value: Long, val percentage: Double) : StatsViewChange()
    @Parcelize
    data object NoChange : StatsViewChange()
}
