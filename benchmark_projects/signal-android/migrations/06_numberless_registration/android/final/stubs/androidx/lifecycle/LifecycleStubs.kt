package androidx.lifecycle

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlin.properties.ReadWriteProperty
import kotlin.reflect.KProperty

open class ViewModel {
  internal val benchmarkScope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
  protected open fun onCleared() = Unit
}

val ViewModel.viewModelScope: CoroutineScope
  get() = benchmarkScope

class ViewModelProvider {
  interface Factory {
    fun <T : ViewModel> create(modelClass: Class<T>): T = error("unsupported")
    fun <T : ViewModel> create(modelClass: Class<T>, extras: androidx.lifecycle.viewmodel.CreationExtras): T = create(modelClass)
  }
}

class SavedStateHandle(initial: Map<String, Any?> = emptyMap()) {
  private val values = initial.toMutableMap()
  @Suppress("UNCHECKED_CAST") operator fun <T> get(key: String): T? = values[key] as? T
  operator fun <T> set(key: String, value: T) { values[key] = value }
  fun contains(key: String): Boolean = values.containsKey(key)
  @Suppress("UNCHECKED_CAST") fun <T> getMutableStateFlow(key: String, initialValue: T): MutableStateFlow<T> {
    val existing = values[key]
    val flow = when (existing) {
      is MutableStateFlow<*> -> existing as MutableStateFlow<T>
      null -> MutableStateFlow(initialValue)
      else -> MutableStateFlow(existing as T)
    }.also { values[key] = it }
    return flow
  }
}

fun androidx.lifecycle.viewmodel.CreationExtras.createSavedStateHandle(): SavedStateHandle = SavedStateHandle()

class SavedDelegate<T>(private var value: T) : ReadWriteProperty<Any?, T> {
  override fun getValue(thisRef: Any?, property: KProperty<*>): T = value
  override fun setValue(thisRef: Any?, property: KProperty<*>, value: T) { this.value = value }
}
