package androidx.lifecycle

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job

class Lifecycle {
    enum class State { CREATED }
}

class LifecycleOwner

val LifecycleOwner.lifecycleScope: CoroutineScope
    get() = CoroutineScope(Job().also { it.cancel() })

suspend fun CoroutineScope.repeatOnLifecycle(state: Lifecycle.State, block: suspend () -> Unit) = Unit
