package org.wikipedia.evergreen

import android.app.Activity
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import org.json.JSONObject

class BenchmarkActivity : Activity() {
    lateinit var pageOwner: EvergreenPageOwner
        private set
    private lateinit var status: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        pageOwner = EvergreenPageOwner(this)
        pageOwner.mount(JSONObject(intent.getStringExtra("runtimeGiven") ?: "{}"))
        status = TextView(this).apply { textSize = 22f }
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 32, 32, 32)
            addView(TextView(this@BenchmarkActivity).apply { text = "Wikipedia"; textSize = 30f })
            addView(status)
            addView(Button(this@BenchmarkActivity).apply {
                text = "Create account"
                setOnClickListener { dispatch(JSONObject().put("name", "createAccountAndCompleteSuccessfully").put("authenticationLeafResult", "success_permanent_account")) }
            })
            addView(Button(this@BenchmarkActivity).apply {
                text = "Maybe later"
                setOnClickListener { dispatch(JSONObject().put("name", "maybeLater")) }
            })
            addView(Button(this@BenchmarkActivity).apply {
                text = "Close"
                setOnClickListener { dispatch(JSONObject().put("name", "pressPermanentCloseAndRelaunch")) }
            })
        }
        setContentView(layout)
        render()
    }

    fun dispatch(event: JSONObject) {
        pageOwner.dispatch(event)
        render()
    }

    private fun render() {
        val state = pageOwner.snapshot().optJSONObject("state") ?: JSONObject()
        status.text = if (state.optBoolean("visible")) "Create your account" else state.optString("surface", "main")
    }
}
