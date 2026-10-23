package androidx.annotation

@Target(AnnotationTarget.FUNCTION, AnnotationTarget.PROPERTY, AnnotationTarget.FIELD)
annotation class VisibleForTesting

@Target(AnnotationTarget.FIELD, AnnotationTarget.VALUE_PARAMETER, AnnotationTarget.PROPERTY)
annotation class StringRes

@Target(AnnotationTarget.FUNCTION, AnnotationTarget.CLASS) annotation class WorkerThread
@Target(AnnotationTarget.FUNCTION, AnnotationTarget.CLASS) annotation class RequiresApi(val value: Int)
@Target(AnnotationTarget.VALUE_PARAMETER, AnnotationTarget.FIELD, AnnotationTarget.FUNCTION) annotation class NonNull
@Target(AnnotationTarget.VALUE_PARAMETER, AnnotationTarget.FIELD, AnnotationTarget.FUNCTION) annotation class Nullable
@Target(AnnotationTarget.VALUE_PARAMETER) annotation class UiContext
