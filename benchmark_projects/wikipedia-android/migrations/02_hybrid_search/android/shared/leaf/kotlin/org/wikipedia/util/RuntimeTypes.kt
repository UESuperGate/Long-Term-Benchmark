package org.wikipedia.util

sealed class UiState<out T> {
    data object Loading : UiState<Nothing>()
    data class Success<T>(val data: T) : UiState<T>()
    data class Error(val throwable: Throwable) : UiState<Nothing>()
}

object StringUtil {
    fun addUnderscores(value: String): String = value.replace(' ', '_')
}
