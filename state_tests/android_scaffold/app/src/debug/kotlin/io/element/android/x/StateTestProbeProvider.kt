package io.element.android.x

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject

/** Transport-only provider. Expected testcase facts intentionally do not live here. */
class StateTestProbeProvider : ContentProvider() {
    override fun onCreate(): Boolean = true

    override fun query(
        uri: Uri,
        projection: Array<out String>?,
        selection: String?,
        selectionArgs: Array<out String>?,
        sortOrder: String?,
    ): Cursor {
        val caseId = uri.getQueryParameter("caseId") ?: selectionArgs?.firstOrNull().orEmpty()
        val stateEvent = uri.getQueryParameter("stateEvent").orEmpty()
        val snapshot = runCatching {
            val observation = StateTestScenario.capture(caseId, stateEvent)
            JSONObject()
                .put("caseId", caseId)
                .put("ready", true)
                .put("semanticFacts", JSONArray(observation.semanticFacts.map(String::trim).filter(String::isNotEmpty).distinct()))
                .apply {
                    if (observation.appliedEvent.isNotEmpty()) {
                        put("lastEvent", observation.appliedEvent)
                    }
                }
        }.getOrElse { error ->
            JSONObject()
                .put("caseId", caseId)
                .put("ready", true)
                .put("semanticFacts", JSONArray())
                .put("adapterError", error.javaClass.simpleName)
        }
        return MatrixCursor(arrayOf("case_id", "snapshot")).apply {
            addRow(arrayOf(caseId, snapshot.toString()))
        }
    }

    override fun getType(uri: Uri): String? = null
    override fun insert(uri: Uri, values: ContentValues?): Uri? = null
    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = 0
    override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?): Int = 0
}
