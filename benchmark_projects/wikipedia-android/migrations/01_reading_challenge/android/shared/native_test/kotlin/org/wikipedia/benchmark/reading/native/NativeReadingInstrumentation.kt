package org.wikipedia.benchmark.reading.native

import android.app.Activity
import android.app.Instrumentation
import android.os.Bundle
import java.io.PrintWriter
import java.io.StringWriter

class NativeReadingInstrumentation : Instrumentation() {
    private lateinit var arguments: Bundle

    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        this.arguments = arguments ?: Bundle.EMPTY
        start()
    }

    override fun onStart() {
        val result = Bundle()
        try {
            val episode = NativeReadingEpisode.run(arguments, targetContext)
            targetContext.openFileOutput(REPORT, 0).bufferedWriter().use { it.write(episode) }
            result.putString("reportPath", targetContext.filesDir.resolve(REPORT).absolutePath)
            finish(Activity.RESULT_OK, result)
        } catch (error: Throwable) {
            val trace = StringWriter().also { error.printStackTrace(PrintWriter(it)) }.toString()
            result.putString("error", trace)
            finish(Activity.RESULT_CANCELED, result)
        }
    }

    companion object {
        const val REPORT = "runtime-episode.json"
    }
}
