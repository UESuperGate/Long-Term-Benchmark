package io.element.android.libraries.di
import kotlin.reflect.KClass
abstract class RoomScope
annotation class SingleIn(val scope: KClass<*>)
