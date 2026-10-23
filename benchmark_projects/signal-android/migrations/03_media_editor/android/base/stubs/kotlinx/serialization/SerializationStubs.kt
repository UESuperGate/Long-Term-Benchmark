package kotlinx.serialization

import kotlin.reflect.KClass

@Target(AnnotationTarget.CLASS, AnnotationTarget.PROPERTY) annotation class Serializable(val with: KClass<*> = Nothing::class)
@Target(AnnotationTarget.PROPERTY) annotation class SerialName(val value: String)
@Target(AnnotationTarget.PROPERTY) annotation class EncodeDefault(val mode: Mode = Mode.ALWAYS) { enum class Mode { ALWAYS, NEVER } }
@RequiresOptIn annotation class ExperimentalSerializationApi
