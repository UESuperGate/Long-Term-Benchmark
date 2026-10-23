package org.signal.core.util.logging

object Log {
  fun tag(type: kotlin.reflect.KClass<*>): String = type.qualifiedName ?: type.simpleName ?: "unknown"
  fun d(tag: String, message: String) = Unit
  fun w(tag: String, message: String) = Unit
}
