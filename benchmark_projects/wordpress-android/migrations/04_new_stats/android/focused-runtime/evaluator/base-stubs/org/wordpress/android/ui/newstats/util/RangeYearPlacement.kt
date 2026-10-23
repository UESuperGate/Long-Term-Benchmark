package org.wordpress.android.ui.newstats.util

enum class RangeYearPlacement { BOTH, TRAILING }
fun rangeYearPlacement(startYear: Int, endYear: Int) = if (startYear == endYear) RangeYearPlacement.TRAILING else RangeYearPlacement.BOTH
