package androidx.navigation3.runtime

interface NavKey

class NavBackStack<T : NavKey>(initial: T) : ArrayList<T>() {
  init { add(initial) }
  fun resetTo(value: T) { clear(); add(value) }
  fun pop(): T? = if (isEmpty()) null else removeAt(lastIndex)
}
