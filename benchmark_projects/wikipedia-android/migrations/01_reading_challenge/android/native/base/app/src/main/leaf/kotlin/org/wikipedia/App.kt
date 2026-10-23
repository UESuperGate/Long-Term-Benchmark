package org.wikipedia

import android.content.Context

object R {
    object string {
        const val preference_key_reading_challenge_streak = 1
        const val preference_key_reading_challenge_enrolled = 2
        const val preference_key_reading_challenge_last_read_date = 3
    }
}

class WikipediaApp {
    companion object {
        lateinit var instance: Context
    }
}
