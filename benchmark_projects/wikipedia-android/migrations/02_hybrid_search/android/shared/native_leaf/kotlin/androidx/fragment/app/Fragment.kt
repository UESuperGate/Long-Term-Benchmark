package androidx.fragment.app

import android.app.Activity
import android.content.Context
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.lifecycle.LifecycleOwner
import org.wikipedia.search.RuntimeFragmentLeaves

open class Fragment {
    val viewLifecycleOwner = LifecycleOwner()
    val isAdded: Boolean get() = true
    open fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View? = null
    open fun onDestroyView() = Unit
    fun requireActivity(): Activity = RuntimeFragmentLeaves.activity
    fun requireContext(): Context = RuntimeFragmentLeaves.activity
    fun requireParentFragment(): Fragment = RuntimeFragmentLeaves.parent
    fun getString(id: Int): String = "string-$id"
}

inline fun <reified T : Any> Fragment.viewModels(): Lazy<T> = lazy {
    @Suppress("UNCHECKED_CAST")
    RuntimeFragmentLeaves.viewModel as T
}
