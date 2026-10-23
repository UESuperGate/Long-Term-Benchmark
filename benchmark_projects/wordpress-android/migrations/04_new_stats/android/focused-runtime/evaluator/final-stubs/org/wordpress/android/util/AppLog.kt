package org.wordpress.android.util

object AppLog {
    enum class T { STATS }
    fun e(tag: T, message: String, error: Throwable? = null) = Unit
    fun w(tag: T, message: String) = Unit
}
