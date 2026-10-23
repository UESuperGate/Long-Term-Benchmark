package org.wikipedia.widgets.readingchallenge

import android.content.Context
import java.time.LocalDate
import org.wikipedia.page.PageLoadCompleteActionPrefix
import org.wikipedia.settings.Prefs

data class ReadingChallengePageSnapshot(
    val featureAvailable: Boolean,
    val stateName: String,
    val streak: Int
)

/** Application-owned challenge surface and action prefix used by the native runtime harness. */
class ReadingChallengePageActionPrefix(context: Context) {
    private val repository = ReadingChallengeWidgetRepository(context)
    private val enrollment = ReadingChallengeEnrollmentAction(context)
    private val pageLoadComplete = PageLoadCompleteActionPrefix(context)

    fun refreshChallengeSurface(currentDate: LocalDate) {
        repository.recalculateStreakIfNeeded(currentDate)
    }

    suspend fun enroll(currentDate: LocalDate) {
        enrollment.enroll(currentDate)
    }

    suspend fun openArticle(currentDate: LocalDate) {
        pageLoadComplete.onPageLoadComplete(currentDate)
    }

    fun snapshot(currentDate: LocalDate): ReadingChallengePageSnapshot {
        val state = repository.resolveState(
            ReadingChallengeUserData(
                currentDate = currentDate,
                enabled = Prefs.readingChallengeEnrolled,
                currentStreak = Prefs.readingChallengeStreak,
                hasReadToday = repository.hasReadToday(currentDate),
                hasActiveStreak = repository.hasActiveStreak(currentDate)
            )
        )
        return ReadingChallengePageSnapshot(
            featureAvailable = true,
            stateName = when (state) {
                ReadingChallengeState.Loading -> "loading"
                ReadingChallengeState.NotLiveYet -> "not_live_yet"
                ReadingChallengeState.NotEnrolled -> "not_enrolled"
                ReadingChallengeState.EnrolledNotStarted -> "enrolled_not_started"
                is ReadingChallengeState.StreakOngoingNeedsReading -> "streak_needs_reading"
                is ReadingChallengeState.StreakOngoingReadToday -> "streak_read_today"
                ReadingChallengeState.ChallengeCompleted -> "challenge_completed"
                is ReadingChallengeState.ChallengeConcludedIncomplete -> "challenge_concluded_incomplete"
                ReadingChallengeState.ChallengeConcludedNoStreak -> "challenge_concluded_no_streak"
                ReadingChallengeState.ChallengeRemoved -> "challenge_removed"
            },
            streak = when (state) {
                is ReadingChallengeState.StreakOngoingNeedsReading -> state.streak
                is ReadingChallengeState.StreakOngoingReadToday -> state.streak
                is ReadingChallengeState.ChallengeConcludedIncomplete -> state.streak
                else -> Prefs.readingChallengeStreak
            }
        )
    }
}
