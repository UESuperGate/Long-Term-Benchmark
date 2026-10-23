package evaluator.support

import android.app.Instrumentation
import android.content.Intent
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import evaluator.supportbase.SupportBaseOwnerActivity
import evaluator.supportbase.SupportBaseOwnerDependencies
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.wordpress.android.fluxc.store.AccountStore
import org.wordpress.android.fluxc.utils.AppLogWrapper
import org.wordpress.android.support.main.ui.SupportViewModel
import org.wordpress.android.ui.prefs.AppPrefsWrapper
import org.wordpress.android.ui.prefs.experimentalfeatures.ExperimentalFeatures

fun runCase(key: String, instrumentation: Instrumentation): String {
    SupportBaseOwnerDependencies.factory = object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T = SupportViewModel(
            AccountStore(), AppLogWrapper(), AppPrefsWrapper(), ExperimentalFeatures()
        ) as T
    }
    val intent = Intent(instrumentation.targetContext, SupportBaseOwnerActivity::class.java)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    val owner = instrumentation.startActivitySync(intent) as SupportBaseOwnerActivity
    instrumentation.waitForIdleSync()
    val visibility = owner.viewModel.optionsVisibility.value
    val observed = JsonObject(mapOf(
        "surface" to JsonPrimitive(owner.surface),
        "legacyEntries" to JsonArray(listOf(
            JsonPrimitive(if (visibility.showAskTheBots) "ask_the_bots" else "hidden_bots"),
            JsonPrimitive(if (visibility.showAskHappinessEngineers) "ask_happiness_engineers" else "hidden_engineers"),
        )),
        "unifiedEntryPresent" to JsonPrimitive(false),
    ))
    instrumentation.runOnMainSync { owner.finish() }
    instrumentation.waitForIdleSync()
    SupportBaseOwnerDependencies.factory = null
    return JsonObject(mapOf(
        "key" to JsonPrimitive(key),
        "before" to JsonObject(mapOf("initialized" to JsonPrimitive(false))),
        "after" to JsonObject(mapOf("initialized" to JsonPrimitive(true))),
        "observed" to observed,
        "invariantChecks" to JsonArray(emptyList()),
        "productionBodies" to JsonArray(listOf(
            JsonPrimitive("SupportBaseOwnerActivity.onCreate"),
            JsonPrimitive("SupportViewModel.init"),
        )),
    )).toString()
}
