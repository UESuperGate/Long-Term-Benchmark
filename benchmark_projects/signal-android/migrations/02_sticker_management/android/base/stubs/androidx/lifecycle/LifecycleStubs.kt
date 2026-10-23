package androidx.lifecycle

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob

open class ViewModel {
  internal val benchmarkScope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
  protected open fun onCleared() = Unit
}

val ViewModel.viewModelScope: CoroutineScope
  get() = benchmarkScope

open class LiveData<T> {
  protected var stored: T? = null
  fun getValue(): T? = stored
}

class MutableLiveData<T> : LiveData<T>() {
  fun postValue(value: T) { stored = value }
}

class ViewModelProvider {
  open class NewInstanceFactory {
    open fun <T : ViewModel> create(modelClass: Class<T>): T = modelClass.getDeclaredConstructor().newInstance()
  }
}
