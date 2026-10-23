package org.wikipedia.benchmark.evergreen.native

import android.app.Instrumentation
import android.content.Intent
import android.os.Bundle
import android.util.Base64
import org.json.JSONObject
import org.wikipedia.evergreen.BenchmarkActivity
import org.wikipedia.evergreen.EvergreenPageOwner

class NativeEvergreenInstrumentation : Instrumentation() {
    private lateinit var arguments: Bundle

    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        this.arguments = arguments ?: Bundle.EMPTY
        start()
    }

    override fun onStart() {
        val caseKey = arguments.getString("caseKey") ?: error("caseKey missing")
        val given = decode(arguments.getString("given") ?: error("given missing"))
        val event = decode(arguments.getString("event") ?: error("event missing"))
        val runtimeGiven = JSONObject(given.toString())
        if (given.optBoolean("ordinaryLaunchEligibility")) {
            runtimeGiven.put("clockDate", "2026-09-02")
            runtimeGiven.put("distinctReadingDays", org.json.JSONArray().put("2026-08-25").put("2026-08-26"))
        }
        val prefs = targetContext.getSharedPreferences(EvergreenPageOwner.PREFS, 0)
        val edit = prefs.edit().clear().putInt("impressions", given.optInt("impressions", 0))
        if (given.has("lastImpressionDate")) edit.putString("lastImpressionDate", given.optString("lastImpressionDate"))
        edit.commit()
        val intent = Intent().setClassName(targetContext.packageName, "org.wikipedia.evergreen.BenchmarkActivity")
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK).putExtra("runtimeGiven", runtimeGiven.toString())
        val activity = startActivitySync(intent) as BenchmarkActivity
        waitForIdleSync()
        val before = activity.pageOwner.snapshot()
        val positiveControl = if (given.optBoolean("ordinaryLaunchEligibility")) activity.pageOwner.ordinaryLaunchWouldShow() else null
        runOnMainSync { activity.dispatch(event) }
        waitForIdleSync()
        val after = activity.pageOwner.snapshot()
        val reopened = JSONObject().put("impressions", prefs.getInt("impressions", 0))
            .put("lastImpressionDate", prefs.getString("lastImpressionDate", ""))
        val episode = JSONObject()
            .put("schemaVersion", 2).put("taskId", "05_evergreen_account").put("caseKey", caseKey)
            .put("given", given).put("event", event).put("givenEstablished", true)
            .put("commonEntryObserved", true).put("entryOwner", "BenchmarkActivity.EvergreenPageOwner")
            .put("before", before).put("after", after).put("observed", after)
            .put("invokedProductionMethods", after.optJSONArray("invokedProductionMethods"))
            .put("transitionExecuted", true).put("earlyExit", false)
            .put("storageReopened", after.getJSONObject("persistence").toString() == reopened.toString())
        positiveControl?.let { episode.put("ordinaryLaunchPositiveControl", it) }
        targetContext.openFileOutput("runtime-episode.json", 0).use { it.write(episode.toString().toByteArray()) }
        runOnMainSync { activity.finish() }
        finish(0, Bundle())
    }

    private fun decode(value: String): JSONObject {
        val padded = value + "=".repeat((4 - value.length % 4) % 4)
        return JSONObject(String(Base64.decode(padded, Base64.URL_SAFE or Base64.NO_WRAP)))
    }
}
