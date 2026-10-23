package android.app

import android.net.Uri
import evaluator.support.leaf.EvaluatorLeaf
import java.io.ByteArrayInputStream
import java.io.File
import java.io.InputStream

open class Application {
    val cacheDir: File = EvaluatorLeaf.cacheDir
    val contentResolver: ContentResolver = ContentResolver()
}

class ContentResolver {
    fun openInputStream(uri: Uri): InputStream? {
        EvaluatorLeaf.events += mapOf("name" to "createTempAttachments", "input" to uri.toString())
        return ByteArrayInputStream(EvaluatorLeaf.uriContents[uri.toString()] ?: byteArrayOf(1))
    }
    fun getType(uri: Uri): String? = EvaluatorLeaf.uriMimeTypes[uri.toString()]
}
