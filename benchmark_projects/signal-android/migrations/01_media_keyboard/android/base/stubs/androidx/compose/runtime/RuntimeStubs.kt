package androidx.compose.runtime

import kotlin.reflect.KProperty

@Target(AnnotationTarget.CLASS, AnnotationTarget.FUNCTION)
annotation class Stable

@Target(AnnotationTarget.FUNCTION)
annotation class Composable

class MutableState<T>(var value: T)

fun <T> mutableStateOf(value: T): MutableState<T> = MutableState(value)
operator fun <T> MutableState<T>.getValue(thisRef: Any?, property: KProperty<*>): T = value
operator fun <T> MutableState<T>.setValue(thisRef: Any?, property: KProperty<*>, value: T) { this.value = value }
fun <T> remember(calculation: () -> T): T = calculation()
