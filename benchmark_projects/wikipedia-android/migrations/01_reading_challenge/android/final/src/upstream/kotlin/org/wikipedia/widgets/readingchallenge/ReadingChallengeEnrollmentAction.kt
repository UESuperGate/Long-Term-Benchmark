package org.wikipedia.widgets.readingchallenge

import android.content.Context
import java.time.LocalDate
import org.wikipedia.auth.AccountUtil
import org.wikipedia.settings.Prefs

/** Executable extraction of the eligible Join branch in ReadingChallengeOnboardingActivity. */
class ReadingChallengeEnrollmentAction(private val context: Context) {
    suspend fun enroll(currentDate: LocalDate) {
        if (!AccountUtil.isLoggedIn) return
        Prefs.readingChallengeEnrolled = true
        Prefs.readingChallengeEnrollmentDate = currentDate.toString()
        ReadingChallengeWidgetRepository(context).updateWidgetsAndSendAnalytics()
    }
}
