package org.wikipedia.activity

import androidx.fragment.app.Fragment
import org.wikipedia.search.RuntimeFragmentLeaves

object FragmentUtil {
    fun <T> getCallback(fragment: Fragment, type: Class<T>): T? = type.cast(RuntimeFragmentLeaves.callback)
}
