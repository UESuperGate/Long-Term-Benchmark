package org.wordpress.android.util

import java.util.Date

object AppLog {
    enum class T { PAGES }
    fun e(tag: T, message: String, error: Throwable? = null) {}
    fun w(tag: T, message: String) {}
}
object DateTimeUtils { fun iso8601UTCFromDate(date: Date): String = date.time.toString() }
object HtmlUtils { fun fastStripHtml(value: String): String = value.replace(Regex("<[^>]+>"), "") }
open class NetworkUtilsWrapper { open fun isNetworkAvailable(): Boolean = true }
