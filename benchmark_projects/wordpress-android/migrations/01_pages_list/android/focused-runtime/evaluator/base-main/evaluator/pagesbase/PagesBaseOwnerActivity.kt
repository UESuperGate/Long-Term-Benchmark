package evaluator.pagesbase

import android.os.Bundle
import android.view.View
import androidx.activity.ComponentActivity
import org.wordpress.android.ui.pages.PagesActivity

class PagesBaseOwnerActivity : ComponentActivity() {
    private lateinit var legacyOwner: PagesActivity
    private lateinit var surfaceView: View

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        legacyOwner = PagesActivity().also { it.performCreate() }
        surfaceView = View(this).apply { contentDescription = "legacy_pages" }
        setContentView(surfaceView)
        current = this
    }

    override fun onDestroy() {
        if (current === this) current = null
        super.onDestroy()
    }

    fun dispatchOpenPages() = legacyOwner.performNewIntent(legacyOwner.intent)
    val surface: String get() = surfaceView.contentDescription.toString()
    val legacyContentView: String get() = legacyOwner.lastContentView.toString()

    companion object {
        @Volatile var current: PagesBaseOwnerActivity? = null
    }
}
