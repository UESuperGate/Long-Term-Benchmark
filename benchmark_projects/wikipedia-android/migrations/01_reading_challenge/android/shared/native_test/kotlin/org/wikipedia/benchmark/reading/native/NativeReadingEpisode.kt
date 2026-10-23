package org.wikipedia.benchmark.reading.native

import android.content.Context
import android.os.Bundle
import java.time.LocalDate
import kotlinx.coroutines.runBlocking
import org.wikipedia.settings.Prefs
import org.wikipedia.widgets.readingchallenge.ReadingChallengePageActionPrefix
import org.wikipedia.widgets.readingchallenge.ReadingChallengePageSnapshot
import org.wikipedia.widgets.readingchallenge.RuntimeChallengeEffects

object NativeReadingEpisode {
    fun run(options: Bundle, context: Context): String = runBlocking {
        val date = LocalDate.parse(options.getString("date"))
        Prefs.attach(context)
        Prefs.reset()
        Prefs.readingChallengeEnrolled = options.getString("enrolled")?.toBoolean() ?: false
        Prefs.readingChallengeStreak = options.getString("streak")?.toInt() ?: 0
        Prefs.readingChallengeLastReadDate = nullable(options.getString("lastReadDate"))
        Prefs.readingChallengeEnrollmentDate = nullable(options.getString("enrollmentDate"))
        Prefs.reopen(context)
        RuntimeChallengeEffects.clear()

        val page = ReadingChallengePageActionPrefix(context)
        val invoked = mutableListOf<String>()
        if (options.getString("setupRefresh") == "true") {
            page.refreshChallengeSurface(date)
            invoked += "ReadingChallengePageActionPrefix.refreshChallengeSurface"
        }
        Prefs.reopen(context)
        val beforePersistence = persistence()
        val before = snapshot(page.snapshot(date), date)

        when (options.getString("event")) {
            "refreshChallengeSurface" -> {
                page.refreshChallengeSurface(date)
                invoked += "ReadingChallengePageActionPrefix.refreshChallengeSurface"
            }
            "enroll" -> {
                page.enroll(date)
                invoked += "ReadingChallengePageActionPrefix.enroll"
            }
            "openArticle" -> {
                page.openArticle(date)
                invoked += "ReadingChallengePageActionPrefix.openArticle>PageLoadCompleteActionPrefix.onPageLoadComplete"
            }
            else -> error("unknown event ${options.getString("event")}")
        }

        Prefs.reopen(context)
        val after = snapshot(page.snapshot(date), date)
        val persistedAfter = persistence()
        val observed = after.toMutableMap().also {
            it["persistence"] = persistedAfter.toMutableMap().also { values ->
                values["unchanged"] = beforePersistence == persistedAfter
            }
            it["effects"] = RuntimeChallengeEffects.snapshot()
        }
        json(
            mapOf(
                "before" to before,
                "after" to after,
                "observed" to observed,
                "entryOwner" to "ReadingChallengePageActionPrefix",
                "invokedProductionMethods" to invoked,
                "transitionExecuted" to true,
                "storageReopened" to true
            )
        )
    }

    private fun nullable(value: String?): String = value.orEmpty().takeUnless { it == "null" }.orEmpty()

    private fun snapshot(value: ReadingChallengePageSnapshot, date: LocalDate): Map<String, Any> = mapOf(
        "featureAvailable" to value.featureAvailable,
        "clockDate" to date.toString(),
        "state" to mapOf("name" to value.stateName, "streak" to value.streak),
        "persistence" to persistence()
    )

    private fun persistence(): Map<String, Any?> = linkedMapOf(
        "enrolled" to Prefs.readingChallengeEnrolled,
        "streak" to Prefs.readingChallengeStreak,
        "lastReadDate" to Prefs.readingChallengeLastReadDate.ifEmpty { null },
        "enrollmentDate" to Prefs.readingChallengeEnrollmentDate.ifEmpty { null }
    )

    private fun json(value: Any?): String = when (value) {
        null -> "null"
        is String -> "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""
        is Number, is Boolean -> value.toString()
        is Map<*, *> -> value.entries.joinToString(prefix = "{", postfix = "}") { "${json(it.key.toString())}:${json(it.value)}" }
        is Iterable<*> -> value.joinToString(prefix = "[", postfix = "]") { json(it) }
        else -> error("unsupported JSON value ${value.javaClass}")
    }
}
