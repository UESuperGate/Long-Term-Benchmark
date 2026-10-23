package rs.wordpress.api.kotlin

data class WpResponse<T>(val data: T)
data class WpResponseEnvelope<T>(val response: WpResponse<T>)

sealed class WpRequestResult<out T> {
    data class Success<T>(val response: WpResponse<T>) : WpRequestResult<T>()
    data class WpError<T>(val errorMessage: String) : WpRequestResult<T>()
}
