package evaluator.support.instrumentation

import android.app.Application
import android.app.Instrumentation
import android.os.Bundle
import android.util.Base64
import evaluator.support.runCase

class SemanticInstrumentation : Instrumentation() {
    private var launchArguments: Bundle? = null

    override fun onCreate(arguments: Bundle?) {
        launchArguments = arguments
        super.onCreate(arguments)
        start()
    }

    override fun onStart() {
        val result = Bundle()
        try {
            configureFinalRuntimeWhenPresent()
            val key = requireNotNull(launchArguments?.getString("case")) { "missing case argument" }
            val json = runCase(key, this)
            result.putString("runtime_state_transition_b64", Base64.encodeToString(json.toByteArray(), Base64.NO_WRAP))
            sendStatus(0, result)
            finish(0, result)
        } catch (error: Throwable) {
            result.putString("runtime_error", error.stackTraceToString())
            sendStatus(-1, result)
            finish(-1, result)
        }
    }

    private fun configureFinalRuntimeWhenPresent() {
        try {
            val leafClass = Class.forName("evaluator.support.leaf.EvaluatorLeaf")
            val instance = leafClass.getField("INSTANCE").get(null)
            leafClass.getMethod("setApplication", Application::class.java)
                .invoke(instance, targetContext.applicationContext as Application)
        } catch (_: ClassNotFoundException) {
            // The exact 26.8 base has no unified evaluator leaf.
        }
    }
}
