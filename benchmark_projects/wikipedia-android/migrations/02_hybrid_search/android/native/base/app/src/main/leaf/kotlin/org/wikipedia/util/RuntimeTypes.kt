package org.wikipedia.util

import android.app.Activity

sealed class UiState<out T> {
    data object Loading : UiState<Nothing>()
    data class Success<T>(val data: T) : UiState<T>()
    data class Error(val throwable: Throwable) : UiState<Nothing>()
}

object StringUtil {
    fun addUnderscores(value: String): String = value.replace(' ', '_')
    fun fromHtml(value: String): String = value
}

object DeviceUtil {
    fun hideSoftKeyboard(activity: Activity) = Unit
    fun showSoftKeyboard(activity: Activity) = Unit
}

object FeedbackUtil {
    fun showMessage(activity: Activity, stringId: Int) = Unit
}

object UriUtil {
    fun visitInExternalBrowser(activity: Activity, uri: android.net.Uri) = Unit
}
