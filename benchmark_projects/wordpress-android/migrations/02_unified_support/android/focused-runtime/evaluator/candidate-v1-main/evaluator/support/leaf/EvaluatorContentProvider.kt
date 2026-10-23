package evaluator.support.leaf

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.net.Uri
import android.os.ParcelFileDescriptor
import java.io.File

class EvaluatorContentProvider : ContentProvider() {
    override fun onCreate(): Boolean = true
    override fun getType(uri: Uri): String? = EvaluatorLeaf.uriMimeTypes[uri.toString()]

    override fun openFile(uri: Uri, mode: String): ParcelFileDescriptor {
        EvaluatorLeaf.events += mapOf(
            "name" to "createTempAttachments",
            "inputs" to listOf(uri.lastPathSegment.orEmpty()),
        )
        val source = File(requireNotNull(context).cacheDir, "provider-${uri.lastPathSegment}")
        source.writeBytes(EvaluatorLeaf.uriContents[uri.toString()] ?: byteArrayOf(1))
        return ParcelFileDescriptor.open(source, ParcelFileDescriptor.MODE_READ_ONLY)
    }

    override fun query(uri: Uri, projection: Array<out String>?, selection: String?, selectionArgs: Array<out String>?, sortOrder: String?): Cursor? = null
    override fun insert(uri: Uri, values: ContentValues?): Uri? = null
    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = 0
    override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?): Int = 0
}
