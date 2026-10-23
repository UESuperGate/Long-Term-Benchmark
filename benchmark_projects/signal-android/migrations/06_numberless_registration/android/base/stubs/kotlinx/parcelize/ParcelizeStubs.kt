package kotlinx.parcelize

import android.os.Parcel
import kotlin.reflect.KClass

@Target(AnnotationTarget.CLASS) annotation class Parcelize
@Target(AnnotationTarget.PROPERTY) annotation class IgnoredOnParcel
@Target(AnnotationTarget.TYPE) annotation class WriteWith<T : Parceler<*>>
@Target(AnnotationTarget.CLASS) @Repeatable annotation class TypeParceler<T, P : Parceler<T>>
interface Parceler<T> {
  fun create(parcel: Parcel): T
  fun T.write(parcel: Parcel, flags: Int)
}
