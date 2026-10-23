package org.signal.imageeditor.core.model

import android.os.Parcelable

class ElementFlags { fun setSelectable(value: Boolean): ElementFlags = this; fun persist() = Unit }
open class EditorElement(val renderer: Any? = null) { val flags = ElementFlags() }
open class EditorModel : Parcelable {
  val elements: MutableList<EditorElement> = mutableListOf()
  fun addElement(element: EditorElement) { elements += element }
  companion object { fun create(value: Int) = EditorModel() }
}
