package evaluator.sitepicker.instrumentation

import android.app.Instrumentation
import android.os.Bundle
import android.util.Base64
import evaluator.sitepicker.runCase

class SemanticInstrumentation : Instrumentation() {
    private var arguments: Bundle? = null
    override fun onCreate(arguments: Bundle?) { this.arguments = arguments; super.onCreate(arguments); start() }
    override fun onStart() {
        val result = Bundle()
        try {
            val key = requireNotNull(arguments?.getString("case"))
            val payload = runCase(key, this)
            result.putString("runtime_state_transition_b64", Base64.encodeToString(payload.toByteArray(), Base64.NO_WRAP))
            sendStatus(0, result); finish(0, result)
        } catch (error: Throwable) {
            result.putString("runtime_error", error.stackTraceToString()); sendStatus(-1, result); finish(-1, result)
        }
    }
}
