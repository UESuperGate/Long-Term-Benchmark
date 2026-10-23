package android.webkit

class MimeTypeMap private constructor() {
    fun getExtensionFromMimeType(type: String): String? = when (type) {
        "image/jpeg" -> "jpg"
        "image/png" -> "png"
        "video/mp4" -> "mp4"
        else -> null
    }
    companion object {
        private val instance = MimeTypeMap()
        fun getSingleton(): MimeTypeMap = instance
    }
}
