package evaluator.supportbase

import android.os.Bundle
import android.view.View
import androidx.activity.ComponentActivity
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import org.wordpress.android.support.main.ui.SupportViewModel

class SupportBaseOwnerActivity : ComponentActivity() {
    private lateinit var surfaceView: View
    internal val viewModel: SupportViewModel by lazy {
        ViewModelProvider(this, requireNotNull(SupportBaseOwnerDependencies.factory))[SupportViewModel::class.java]
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        surfaceView = View(this).apply { contentDescription = "legacy_support" }
        setContentView(surfaceView)
        viewModel.init()
        current = this
    }

    override fun onDestroy() {
        if (current === this) current = null
        super.onDestroy()
    }

    internal val surface: String get() = surfaceView.contentDescription.toString()

    companion object {
        @Volatile internal var current: SupportBaseOwnerActivity? = null
    }
}

internal object SupportBaseOwnerDependencies {
    @Volatile var factory: ViewModelProvider.Factory? = null
}
