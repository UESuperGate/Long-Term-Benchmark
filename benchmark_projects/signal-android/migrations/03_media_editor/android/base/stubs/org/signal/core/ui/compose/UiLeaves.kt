package org.signal.core.ui.compose

enum class DialogResult { POSITIVE, NEGATIVE, DISMISSED }

class DialogController<T> {
  var nextResult: DialogResult = DialogResult.NEGATIVE
  var showCount: Int = 0
  suspend fun show(value: T): DialogResult { showCount += 1; return nextResult }
}

class PermissionController(val permission: String, val permanentDenialMessage: Int) {
  suspend fun request(): Boolean = true
}

object SignalIcons { object SpeakerSlash; object QualityHigh; object QualityHighSlash; object ViewOnce }
