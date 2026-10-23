package androidx.core.content
inline fun <reified T> android.content.Context.getSystemService(): T? = when (T::class) { android.view.autofill.AutofillManager::class -> android.view.autofill.AutofillManager() as T; else -> null }
