package androidx.lifecycle.serialization

import androidx.lifecycle.SavedDelegate
import androidx.lifecycle.SavedStateHandle

fun <T> SavedStateHandle.saved(serializer: Any?, key: String, init: () -> T): SavedDelegate<T> = SavedDelegate(get<T>(key) ?: init())
