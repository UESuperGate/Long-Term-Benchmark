package evaluator.sitepickerbase

import android.os.Bundle
import androidx.activity.ComponentActivity
import org.wordpress.android.ui.jetpackoverlay.individualplugin.WPJetpackIndividualPluginHelper
import org.wordpress.android.viewmodel.main.SitePickerViewModel

class SitePickerBaseOwnerActivity : ComponentActivity() {
    internal lateinit var viewModel: SitePickerViewModel
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        viewModel = SitePickerViewModel(WPJetpackIndividualPluginHelper())
        viewModel.onContinueFlowSelected()
        current = this
    }
    override fun onDestroy() { if (current === this) current = null; super.onDestroy() }
    companion object { @Volatile internal var current: SitePickerBaseOwnerActivity? = null }
}
