package com.squareup.anvil.annotations

import kotlin.reflect.KClass

// Compile-only DI metadata. No generated DI or production behavior is replaced.
@Target(AnnotationTarget.CLASS)
@Retention(AnnotationRetention.BINARY)
annotation class ContributesTo(val scope: KClass<*>)
