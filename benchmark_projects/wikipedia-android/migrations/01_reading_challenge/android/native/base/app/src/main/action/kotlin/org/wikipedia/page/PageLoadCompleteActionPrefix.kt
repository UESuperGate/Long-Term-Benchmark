package org.wikipedia.page

import android.content.Context
import java.time.LocalDate

/** The pre-feature page-load prefix has no reading-challenge dispatch. */
class PageLoadCompleteActionPrefix(context: Context) {
    suspend fun onPageLoadComplete(currentDate: LocalDate) = Unit
}
