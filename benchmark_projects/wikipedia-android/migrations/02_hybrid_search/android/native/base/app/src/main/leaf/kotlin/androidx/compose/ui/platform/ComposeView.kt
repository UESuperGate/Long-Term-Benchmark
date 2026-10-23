package androidx.compose.ui.platform

import android.content.Context
import android.view.View

class ComposeView(context: Context) : View(context) {
    fun setContent(content: () -> Unit) = content()
}
