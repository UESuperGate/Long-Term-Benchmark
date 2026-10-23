package androidx.lifecycle

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob

open class ViewModel {
    internal val evaluatorScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    public open fun onCleared() {}
}

val ViewModel.viewModelScope: CoroutineScope get() = evaluatorScope
