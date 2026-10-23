package org.wikipedia.benchmark.hybrid.native

import android.app.Activity
import android.app.Instrumentation
import android.content.Intent
import android.os.Bundle
import java.io.PrintWriter
import java.io.StringWriter
import org.wikipedia.search.HybridHarnessActivity
import org.wikipedia.search.RuntimeFragmentLeaves

class NativeHybridInstrumentation : Instrumentation() {
    private lateinit var arguments: Bundle

    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        this.arguments = arguments ?: Bundle.EMPTY
        start()
    }

    override fun onStart() {
        val result = Bundle()
        var activity: Activity? = null
        try {
            val intent = Intent(targetContext, HybridHarnessActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            activity = startActivitySync(intent)
            RuntimeFragmentLeaves.activity = activity
            val episode = NativeHybridEpisode.run(arguments, targetContext)
            targetContext.openFileOutput(REPORT, 0).bufferedWriter().use { it.write(episode) }
            result.putString("reportPath", targetContext.filesDir.resolve(REPORT).absolutePath)
            finish(Activity.RESULT_OK, result)
        } catch (error: Throwable) {
            val trace = StringWriter().also { error.printStackTrace(PrintWriter(it)) }.toString()
            result.putString("error", trace)
            finish(Activity.RESULT_CANCELED, result)
        } finally {
            activity?.finish()
        }
    }

    companion object { const val REPORT = "runtime-episode.json" }
}
