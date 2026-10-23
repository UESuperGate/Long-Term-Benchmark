package evaluator.support.leaf

import android.app.Application
import android.os.FileObserver
import kotlinx.coroutines.CompletableDeferred
import uniffi.wp_api.BotConversation
import uniffi.wp_api.UnifiedConversation
import uniffi.wp_api.UnifiedConversationSummary
import java.io.File
import java.util.Collections

object EvaluatorLeaf {
    lateinit var application: Application
    val cacheDir: File get() = application.cacheDir
    var networkAvailable = true
    var failuresRemaining = 0
    var requestCount = 0
    var requestEntered = CompletableDeferred<Unit>()
    var requestRelease: CompletableDeferred<Unit>? = null
    var conversationList: List<UnifiedConversationSummary> = emptyList()
    var conversationDetails: Map<Long, UnifiedConversation> = emptyMap()
    var replyResult: UnifiedConversation? = null
    var botResult: BotConversation? = null
    var lastReplyAttachments: List<String> = emptyList()
    val sentMessages = Collections.synchronizedList(mutableListOf<String>())
    val events = Collections.synchronizedList(mutableListOf<Map<String, Any?>>())
    val uriContents = mutableMapOf<String, ByteArray>()
    val uriMimeTypes = mutableMapOf<String, String>()
    val uriSizes = mutableMapOf<String, Long>()
    val logIds = ArrayDeque<String>()
    var logFiles: List<File> = emptyList()
    private var cacheObserver: FileObserver? = null

    fun reset() {
        cacheObserver?.stopWatching()
        cacheDir.mkdirs()
        cacheDir.listFiles()?.forEach { it.delete() }
        networkAvailable = true
        failuresRemaining = 0
        requestCount = 0
        requestEntered = CompletableDeferred()
        requestRelease = null
        conversationList = emptyList()
        conversationDetails = emptyMap()
        replyResult = null
        botResult = null
        lastReplyAttachments = emptyList()
        sentMessages.clear()
        events.clear()
        uriContents.clear()
        uriMimeTypes.clear()
        uriSizes.clear()
        logIds.clear()
        logFiles = emptyList()
        cacheObserver = object : FileObserver(cacheDir, DELETE) {
            override fun onEvent(event: Int, path: String?) {
                if (path != null && lastReplyAttachments.any { File(it).name == path }) {
                    events += mapOf("name" to "removeTempAttachments", "path" to path)
                }
            }
        }.also { it.startWatching() }
    }
}
