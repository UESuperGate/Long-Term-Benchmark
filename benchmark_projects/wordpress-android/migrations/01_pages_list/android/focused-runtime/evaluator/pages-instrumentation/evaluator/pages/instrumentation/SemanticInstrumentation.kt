package evaluator.pages.instrumentation

import android.app.Instrumentation
import android.os.Bundle
import android.util.Base64
import evaluator.pages.runCase

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
}
