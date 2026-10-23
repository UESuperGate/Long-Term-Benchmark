package evaluator.pages

import android.app.Instrumentation
import android.content.Intent
import evaluator.pagesbase.PagesBaseOwnerActivity
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

fun runCase(key: String, instrumentation: Instrumentation): String {
    val intent = Intent(instrumentation.targetContext, PagesBaseOwnerActivity::class.java)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    val owner = instrumentation.startActivitySync(intent) as PagesBaseOwnerActivity
    val before = mapOf("surface" to owner.surface, "ownerClass" to owner.javaClass.name)
    instrumentation.runOnMainSync { owner.dispatchOpenPages() }
    instrumentation.waitForIdleSync()
    val after = mapOf(
        "surface" to owner.surface,
        "legacyContentView" to owner.legacyContentView,
    )
    instrumentation.runOnMainSync { owner.finish() }
    return JsonObject(mapOf(
        "key" to JsonPrimitive(key),
        "before" to json(before),
        "after" to json(after),
        "observed" to json(after),
        "invariantChecks" to JsonArray(emptyList()),
        "productionBodies" to JsonArray(listOf(
            JsonPrimitive("PagesBaseOwnerActivity.onCreate"),
            JsonPrimitive("PagesActivity.onCreate"),
            JsonPrimitive("PagesActivity.onNewIntent"),
        )),
    )).toString()
}

private fun json(value: Any?): JsonElement = when (value) {
    null -> JsonNull
    is String -> JsonPrimitive(value)
    is Boolean -> JsonPrimitive(value)
    is Number -> JsonPrimitive(value)
    is Map<*, *> -> JsonObject(value.entries.associate { it.key.toString() to json(it.value) })
    is Iterable<*> -> JsonArray(value.map(::json))
    else -> JsonPrimitive(value.toString())
}
