package org.wikipedia.extensions

import android.app.Activity
import org.wikipedia.search.RuntimeFragmentLeaves

val Activity.instrument: RuntimeInstrument?
    get() = RuntimeFragmentLeaves.instrument

class RuntimeInstrument {
    fun setDefaultMediaWikiData(value: String) = Unit

    fun submitInteraction(
        name: String,
        elementId: String? = null,
        pageData: Any? = null,
        actionContext: Map<String, Any> = emptyMap(),
        actionSubtype: String? = null
    ) {
        RuntimeFragmentLeaves.recordInteraction(name, elementId, pageData, actionContext)
    }
}
