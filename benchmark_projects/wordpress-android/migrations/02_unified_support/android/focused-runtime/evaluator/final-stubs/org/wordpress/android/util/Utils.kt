package org.wordpress.android.util

import evaluator.support.leaf.EvaluatorLeaf
import java.io.File

object AppLog {
    enum class T { SUPPORT }
    fun d(tag: T, message: String) {}
    fun e(tag: T, message: String) {}
}

open class NetworkUtilsWrapper { open fun isNetworkAvailable(): Boolean = EvaluatorLeaf.networkAvailable }

open class EncryptedLogging {
    open fun encryptAndUploadLogFile(logFile: File, shouldStartUploadImmediately: Boolean): String? {
        EvaluatorLeaf.events += mapOf("name" to "uploadEncryptedLogs", "file" to logFile.name)
        return EvaluatorLeaf.logIds.removeFirstOrNull()
    }
}

open class LogFileProviderWrapper { open fun getLogFiles(): List<File> = EvaluatorLeaf.logFiles }

object WPUrlUtils { fun safeToAddWordPressComAuthToken(url: String): Boolean = url.contains("wordpress.com") }
