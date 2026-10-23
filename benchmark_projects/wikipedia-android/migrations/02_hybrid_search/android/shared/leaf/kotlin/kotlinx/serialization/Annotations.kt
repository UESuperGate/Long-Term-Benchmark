package kotlinx.serialization

@Target(AnnotationTarget.CLASS)
annotation class Serializable

@Target(AnnotationTarget.PROPERTY)
annotation class SerialName(val value: String)
