package org.signal.libsignal.net

sealed interface RequestResult<out T, out E> {
  data class Success<T>(val result: T) : RequestResult<T, Nothing>
  data class NonSuccess<E>(val error: E) : RequestResult<Nothing, E>
  data class RetryableNetworkError(val networkError: Throwable = Exception("network")) : RequestResult<Nothing, Nothing>
  data class ApplicationError(val cause: Throwable = Exception("application")) : RequestResult<Nothing, Nothing>
}
