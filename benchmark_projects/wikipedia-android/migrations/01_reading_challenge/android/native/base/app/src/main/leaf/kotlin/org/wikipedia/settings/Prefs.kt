package org.wikipedia.settings

import android.content.Context
import android.content.SharedPreferences

object Prefs {
    private const val STORE = "reading-challenge-native"
    private lateinit var storage: SharedPreferences

    fun attach(context: Context) { storage = context.applicationContext.getSharedPreferences(STORE, Context.MODE_PRIVATE) }
    fun reopen(context: Context) { attach(context) }

    var readingChallengeStreak: Int
        get() = storage.getInt("streak", 0)
        set(value) { check(storage.edit().putInt("streak", value).commit()) }
    var readingChallengeEnrolled: Boolean
        get() = storage.getBoolean("enrolled", false)
        set(value) { check(storage.edit().putBoolean("enrolled", value).commit()) }
    var readingChallengeLastReadDate: String
        get() = storage.getString("lastReadDate", "").orEmpty()
        set(value) { check(storage.edit().putString("lastReadDate", value).commit()) }
    var readingChallengeOnboardingShown: Boolean
        get() = storage.getBoolean("onboardingShown", false)
        set(value) { check(storage.edit().putBoolean("onboardingShown", value).commit()) }
    var readingChallengeInstallPromptShown: Boolean
        get() = storage.getBoolean("installPromptShown", false)
        set(value) { check(storage.edit().putBoolean("installPromptShown", value).commit()) }
    var readingChallengeEnrollmentDate: String
        get() = storage.getString("enrollmentDate", "").orEmpty()
        set(value) { check(storage.edit().putString("enrollmentDate", value).commit()) }
    var readingChallengeEndDate: String
        get() = storage.getString("endDate", "").orEmpty()
        set(value) { check(storage.edit().putString("endDate", value).commit()) }
    var readingChallengeStartDate: String
        get() = storage.getString("startDate", "").orEmpty()
        set(value) { check(storage.edit().putString("startDate", value).commit()) }

    fun reset() { check(storage.edit().clear().commit()) }
}
