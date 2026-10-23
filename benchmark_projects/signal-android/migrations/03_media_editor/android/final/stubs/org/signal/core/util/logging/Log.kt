package org.signal.core.util.logging

object Log {
  @JvmStatic fun tag(type: Class<*>): String = type.name
  fun tag(type: kotlin.reflect.KClass<*>): String = type.qualifiedName ?: type.simpleName ?: "unknown"
  @JvmStatic fun d(tag: String, message: String) = Unit
  @JvmStatic fun i(tag: String, message: String) = Unit
  @JvmStatic fun w(tag: String, message: String) = Unit
  @JvmStatic fun w(tag: String, message: String, error: Throwable) = Unit
}
