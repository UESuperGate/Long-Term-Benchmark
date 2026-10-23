package org.signal.core.util
object PlayServicesUtil { enum class PlayServicesStatus { SUCCESS, MISSING }; fun getPlayServicesStatus(context: android.content.Context) = PlayServicesStatus.SUCCESS }
