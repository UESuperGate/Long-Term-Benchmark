package org.wordpress.android.fluxc.network

enum class NetworkRequestsRetentionPeriod(val value: Int) {
    ONE_HOUR(1), ONE_DAY(24);
    companion object { fun fromInt(value: Int) = entries.firstOrNull { it.value == value } ?: ONE_HOUR }
}
