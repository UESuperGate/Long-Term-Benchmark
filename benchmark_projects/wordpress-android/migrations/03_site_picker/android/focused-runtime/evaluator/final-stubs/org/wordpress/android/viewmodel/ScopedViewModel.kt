package org.wordpress.android.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.launch

open class ScopedViewModel(private val dispatcher: CoroutineDispatcher) : ViewModel() {
    protected fun launch(block: suspend () -> Unit) = viewModelScope.launch(dispatcher) { block() }
}
