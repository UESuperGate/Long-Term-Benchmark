package retrofit2.http

@Target(AnnotationTarget.FUNCTION)
annotation class GET(val value: String)

@Target(AnnotationTarget.VALUE_PARAMETER)
annotation class Query(val value: String)
