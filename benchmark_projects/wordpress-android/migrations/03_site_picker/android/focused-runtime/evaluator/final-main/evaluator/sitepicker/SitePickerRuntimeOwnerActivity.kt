package evaluator.sitepicker

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import org.wordpress.android.ui.main.SiteViewModel

class SitePickerRuntimeOwnerActivity : ComponentActivity() {
    internal val viewModel: SiteViewModel by lazy {
        ViewModelProvider(this, requireNotNull(SitePickerRuntimeDependencies.factory))[SiteViewModel::class.java]
    }
    internal val calls = mutableListOf<String>()
    override fun onCreate(savedInstanceState: Bundle?) { super.onCreate(savedInstanceState); viewModel; current = this }
    override fun onDestroy() { if (current === this) current = null; super.onDestroy() }
    companion object { @Volatile internal var current: SitePickerRuntimeOwnerActivity? = null }
}

internal object SitePickerRuntimeDependencies { @Volatile var factory: ViewModelProvider.Factory? = null }
