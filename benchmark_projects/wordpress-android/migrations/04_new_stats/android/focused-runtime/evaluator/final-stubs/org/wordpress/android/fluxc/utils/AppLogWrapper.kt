package org.wordpress.android.fluxc.utils

import org.wordpress.android.util.AppLog

class AppLogWrapper {
    fun e(tag: AppLog.T, message: String) = Unit
    fun d(tag: AppLog.T, message: String) = Unit
}
