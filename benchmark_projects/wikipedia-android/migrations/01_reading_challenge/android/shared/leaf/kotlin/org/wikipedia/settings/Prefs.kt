package org.wikipedia.settings

object Prefs {
    var readingChallengeStreak: Int = 0
    var readingChallengeEnrolled: Boolean = false
    var readingChallengeLastReadDate: String = ""
    var readingChallengeOnboardingShown: Boolean = false
    var readingChallengeInstallPromptShown: Boolean = false
    var readingChallengeEnrollmentDate: String = ""
    var readingChallengeEndDate: String = ""
    var readingChallengeStartDate: String = ""

    fun reset() {
        readingChallengeStreak = 0
        readingChallengeEnrolled = false
        readingChallengeLastReadDate = ""
        readingChallengeOnboardingShown = false
        readingChallengeInstallPromptShown = false
        readingChallengeEnrollmentDate = ""
        readingChallengeEndDate = ""
        readingChallengeStartDate = ""
    }
}
