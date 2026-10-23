package org.wikipedia.evergreen

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.format.DateTimeParseException
import kotlin.math.abs

private class ReadingHistoryStore(context: Context) : SQLiteOpenHelper(context, "evergreen-history.db", null, 1) {
    override fun onCreate(db: SQLiteDatabase) { db.execSQL("CREATE TABLE history(day TEXT PRIMARY KEY)") }
    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit
    fun replace(days: List<String>) {
        writableDatabase.beginTransaction()
        try {
            writableDatabase.delete("history", null, null)
            days.distinct().forEach { writableDatabase.execSQL("INSERT INTO history(day) VALUES(?)", arrayOf(it)) }
            writableDatabase.setTransactionSuccessful()
        } finally { writableDatabase.endTransaction() }
    }
    fun days(): List<LocalDate> {
        val result = mutableListOf<LocalDate>()
        readableDatabase.rawQuery("SELECT day FROM history ORDER BY day", null).use { cursor ->
            while (cursor.moveToNext()) runCatching { result += LocalDate.parse(cursor.getString(0)) }
        }
        return result
    }
}

class EvergreenPageOwner(private val context: Context) {
    private val prefs = context.getSharedPreferences(PREFS, 0)
    private val history = ReadingHistoryStore(context)
    private val effects = JSONArray()
    private val methods = JSONArray()
    private var account = "logged_out"
    private var clock = LocalDate.of(2026, 9, 2)
    private var state = JSONObject().put("surface", "main").put("accountEncouragementVisible", false)
    private var decision = JSONObject().put("evaluated", false).put("shouldShow", false)
    private var decisionAfterRelaunch: JSONObject? = null
    private var routing: JSONObject? = null

    fun mount(input: JSONObject) {
        methods.put("mount")
        account = input.optString("account", "logged_out")
        runCatching { clock = LocalDate.parse(input.optString("clockDate", "2026-09-02")) }
        val days = mutableListOf<String>()
        listOf("distinctReadingDays", "distinctReadingDaysAfterLastImpression", "distinctRecentReadingDays").forEach { key ->
            input.optJSONArray(key)?.let { array -> for (i in 0 until array.length()) days += array.getString(i) }
        }
        history.replace(days)
        if (input.optBoolean("visible", false) || input.optString("surface") == "account_encouragement") {
            state = JSONObject().put("surface", "account_encouragement").put("visible", true).put("pageIndex", 0)
        }
    }

    fun dispatch(event: JSONObject) {
        when (event.optString("name")) {
            "resumeApplication" -> resumeApplication(false)
            "openExternalArticleDeepLink" -> openExternalArticleDeepLink()
            "pressPermanentCloseAndRelaunch" -> permanentCloseAndRelaunch()
            "createAccountAndCompleteSuccessfully" -> createAccountAndComplete(event.optString("authenticationLeafResult"))
            "maybeLater" -> maybeLater()
        }
    }

    fun ordinaryLaunchWouldShow(): Boolean {
        methods.put("ordinaryLaunchWouldShow")
        return evaluateEligibility().optBoolean("shouldShow")
    }

    private fun resumeApplication(afterAction: Boolean) {
        methods.put("resumeApplication")
        val result = evaluateEligibility()
        if (afterAction) decisionAfterRelaunch = result else decision = result
        if (result.optBoolean("shouldShow")) showEncouragement() else showMain()
    }

    private fun evaluateEligibility(): JSONObject {
        if (account == "registered") {
            effects.put(JSONObject().put("name", "readPermanentAccountState"))
            return JSONObject().put("evaluated", true).put("shouldShow", false)
        }
        val impressions = prefs.getInt("impressions", 0)
        if (impressions >= 2) {
            effects.put(JSONObject().put("name", "applyMaximumOrdinaryImpressions").put("maximum", 2))
            return JSONObject().put("evaluated", true).put("shouldShow", false)
        }
        if (impressions == 1) {
            val persisted = prefs.getString("lastImpressionDate", "") ?: ""
            val last = try { LocalDate.parse(persisted) } catch (_: DateTimeParseException) {
                effects.put(JSONObject().put("name", "parsePersistedLastImpressionDate").put("result", "invalid"))
                return JSONObject().put("evaluated", true).put("shouldShow", false).put("completedWithoutException", true)
            }
            val count = history.days().count { it.isAfter(last) }
            effects.put(JSONObject().put("name", "countDistinctReturnReadingDays").put("count", count))
            return JSONObject().put("evaluated", true).put("shouldShow", count >= 2)
        }
        val recent = history.days().filter { !it.isBefore(clock.minusDays(365)) && !it.isAfter(clock) }
        effects.put(JSONObject().put("name", "queryDistinctReadingDaysWithinHistoryCutoff")
            .put("historyCutoffDays", 365).put("qualifyingDays", recent.size))
        val eligible = recent.any { earlier ->
            val age = clock.toEpochDay() - earlier.toEpochDay()
            age >= 7 && recent.any { later -> later.isAfter(earlier) && abs(later.toEpochDay() - earlier.toEpochDay()) < 14 }
        }
        return JSONObject().put("evaluated", true).put("shouldShow", eligible)
    }

    private fun showEncouragement() {
        methods.put("showEncouragement")
        val next = prefs.getInt("impressions", 0) + 1
        prefs.edit().putInt("impressions", next).putString("lastImpressionDate", clock.toString()).commit()
        state = JSONObject().put("surface", "account_encouragement").put("visible", true)
            .put("accountEncouragementVisible", true).put("pageIndex", 0)
        effects.put(JSONObject().put("name", "loadPersonalizedCountsFromApplicationData"))
        effects.put(JSONObject().put("name", "startAuthenticationEncouragementFunnel").put("interaction", "impression"))
    }

    private fun showMain() {
        state = JSONObject().put("surface", "main").put("accountEncouragementVisible", false)
        if (account == "registered") state.put("account", "registered")
    }

    private fun permanentCloseAndRelaunch() {
        methods.put("pressPermanentClose")
        prefs.edit().putInt("impressions", 100).commit()
        effects.put(JSONObject().put("name", "finishAccountEncouragement"))
        decisionAfterRelaunch = JSONObject().put("evaluated", true).put("shouldShow", false)
        showMain()
    }

    private fun maybeLater() {
        methods.put("maybeLater")
        effects.put(JSONObject().put("name", "finishAccountEncouragement"))
        showMain()
    }

    private fun createAccountAndComplete(result: String) {
        methods.put("createAccountAndCompleteSuccessfully")
        effects.put(JSONObject().put("name", "launchRegistrationFirstAuthentication")
            .put("source", "encourage").put("createAccountFirst", true))
        if (result == "success_permanent_account") {
            account = "registered"
            effects.put(JSONObject().put("name", "finishAccountEncouragementAfterLoginResult").put("result", "success"))
        }
        decisionAfterRelaunch = evaluateEligibility()
        showMain()
    }

    private fun openExternalArticleDeepLink() {
        methods.put("openExternalArticleDeepLink")
        routing = JSONObject().put("externalArticleLinkDetected", true).put("encouragementConsidered", false)
        state = JSONObject().put("surface", "article").put("article", "en:Ada_Lovelace")
            .put("accountEncouragementVisible", false)
        effects.put(JSONObject().put("name", "loadRequestedExternalArticle"))
    }

    fun snapshot(): JSONObject {
        val result = JSONObject().put("featureAvailable", true).put("decision", decision)
            .put("state", JSONObject(state.toString()))
            .put("persistence", JSONObject().put("impressions", prefs.getInt("impressions", 0))
                .put("lastImpressionDate", prefs.getString("lastImpressionDate", "")))
            .put("effects", JSONArray(effects.toString()))
            .put("historyDays", JSONArray(history.days().map { it.toString() }))
            .put("invokedProductionMethods", JSONArray(methods.toString()))
        decisionAfterRelaunch?.let { result.put("decisionAfterRelaunch", it) }
        routing?.let { result.put("routing", it) }
        return result
    }

    companion object { const val PREFS = "evergreen-account" }
}
