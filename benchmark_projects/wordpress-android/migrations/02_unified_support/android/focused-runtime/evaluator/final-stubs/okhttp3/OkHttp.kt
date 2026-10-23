package okhttp3

import java.io.ByteArrayInputStream
import java.io.Closeable
import java.util.concurrent.TimeUnit

class Request private constructor(val url: String, val headers: Map<String, String>) {
    class Builder {
        private var url: String = ""
        private val headers = mutableMapOf<String, String>()
        fun url(value: String) = apply { url = value }
        fun addHeader(name: String, value: String) = apply { headers[name] = value }
        fun build(): Request = Request(url, headers)
    }
}

open class OkHttpClient {
    open fun newBuilder(): Builder = Builder()
    open fun newCall(request: Request): Call = Call()
    class Builder {
        fun connectTimeout(value: Long, unit: TimeUnit) = this
        fun readTimeout(value: Long, unit: TimeUnit) = this
        fun build(): OkHttpClient = OkHttpClient()
    }
}

class Call { fun execute(): Response = Response() }
class ResponseBody { fun byteStream() = ByteArrayInputStream(byteArrayOf()) }
class Response : Closeable {
    val code: Int = 200
    val isSuccessful: Boolean = true
    val body: ResponseBody = ResponseBody()
    override fun close() {}
}
