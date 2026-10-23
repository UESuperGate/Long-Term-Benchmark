package org.wikipedia.widgets.readingchallenge

import android.content.Context
import java.time.LocalDate
import org.wikipedia.page.PageLoadCompleteActionPrefix

data class ReadingChallengePageSnapshot(
    val featureAvailable: Boolean,
    val stateName: String,
    val streak: Int
)

/** Same application entry ABI as final, backed by the pre-feature page behavior. */
class ReadingChallengePageActionPrefix(context: Context) {
    private val pageLoadComplete = PageLoadCompleteActionPrefix(context)

    fun refreshChallengeSurface(currentDate: LocalDate) = Unit
    suspend fun enroll(currentDate: LocalDate) = Unit
    suspend fun openArticle(currentDate: LocalDate) = pageLoadComplete.onPageLoadComplete(currentDate)

    fun snapshot(currentDate: LocalDate) = ReadingChallengePageSnapshot(
        featureAvailable = false,
        stateName = "common_page_loaded",
        streak = 0
    )
}
