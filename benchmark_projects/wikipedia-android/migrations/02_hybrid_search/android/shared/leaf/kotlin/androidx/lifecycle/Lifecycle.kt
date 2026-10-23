package androidx.lifecycle

import java.util.WeakHashMap
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob

open class ViewModel

private val scopes = WeakHashMap<ViewModel, CoroutineScope>()

val ViewModel.viewModelScope: CoroutineScope
    get() = synchronized(scopes) {
        scopes.getOrPut(this) { CoroutineScope(SupervisorJob() + Dispatchers.Default) }
    }
