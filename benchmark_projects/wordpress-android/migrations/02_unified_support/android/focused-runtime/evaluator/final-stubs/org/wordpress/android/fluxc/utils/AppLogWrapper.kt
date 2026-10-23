package org.wordpress.android.fluxc.utils

import org.wordpress.android.util.AppLog

open class AppLogWrapper {
    val errors = mutableListOf<String>()
    open fun e(tag: AppLog.T, message: String) { errors += message }
    open fun d(tag: AppLog.T, message: String) {}
}
