package coil.request

import android.content.Context

class ImageRequest private constructor() {
    class Builder(context: Context) {
        fun data(value: Any?) = this
        fun crossfade(enabled: Boolean) = this
        fun decoderFactory(factory: Any) = this
        fun addHeader(name: String, value: String) = this
        fun build(): ImageRequest = ImageRequest()
    }
}

fun ImageRequest.Builder.videoFrameMillis(value: Long): ImageRequest.Builder = this
