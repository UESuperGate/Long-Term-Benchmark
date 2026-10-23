package org.wikipedia.evergreen

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

class EvergreenPageOwner(private val context: Context) {
    private val given = JSONObject()
    private val effects = JSONArray()
    private val methods = JSONArray()
    private var state = JSONObject().put("surface", "main").put("accountEncouragementVisible", false)

    fun mount(input: JSONObject) {
        input.keys().forEach { given.put(it, input.get(it)) }
        methods.put("mount")
    }

    fun dispatch(event: JSONObject) {
        val name = event.optString("name")
        methods.put(name)
        if (name == "openExternalArticleDeepLink") {
            state = JSONObject().put("surface", "article").put("article", "en:Ada_Lovelace")
                .put("accountEncouragementVisible", false)
            effects.put(JSONObject().put("name", "loadRequestedExternalArticle"))
        } else {
            state = JSONObject().put("surface", "main").put("accountEncouragementVisible", false)
        }
    }

    fun ordinaryLaunchWouldShow(): Boolean {
        methods.put("ordinaryLaunchWouldShow")
        return false
    }

    fun snapshot(): JSONObject {
        val prefs = context.getSharedPreferences(PREFS, 0)
        return JSONObject()
            .put("featureAvailable", false)
            .put("decision", JSONObject().put("evaluated", false).put("shouldShow", false))
            .put("state", JSONObject(state.toString()))
            .put("persistence", JSONObject()
                .put("impressions", prefs.getInt("impressions", 0))
                .put("lastImpressionDate", prefs.getString("lastImpressionDate", "")))
            .put("effects", JSONArray(effects.toString()))
            .put("invokedProductionMethods", JSONArray(methods.toString()))
    }

    companion object { const val PREFS = "evergreen-account" }
}
