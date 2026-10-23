package org.wikipedia.page

import android.content.Context
import java.time.LocalDate
import org.wikipedia.widgets.readingchallenge.ReadingChallengeWidgetRepository

/** Focused application-owned prefix of the production page-load completion path. */
class PageLoadCompleteActionPrefix(context: Context) {
    private val challengeRepository = ReadingChallengeWidgetRepository(context)

    suspend fun onPageLoadComplete(currentDate: LocalDate) {
        challengeRepository.updateOnArticleRead(currentDate)
    }
}
