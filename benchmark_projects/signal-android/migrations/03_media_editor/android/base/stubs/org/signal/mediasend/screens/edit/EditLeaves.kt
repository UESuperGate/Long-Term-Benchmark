package org.signal.mediasend.screens.edit

sealed interface ScheduleSendOption {
  data class PresetTime(val timeMs: Long) : ScheduleSendOption
  data object PickTime : ScheduleSendOption
}

class ImageController {
  fun insertSticker(value: Any) = Unit
  fun cancelStickerInsertion() = Unit
  suspend fun blurFaces(context: android.content.Context) = Unit
  fun clearFaceBlurs() = Unit
  class Container(state: org.signal.mediasend.screens.edit.image.BrushWidthsState) {
    fun getOrCreate(uri: android.net.Uri, model: org.signal.imageeditor.core.model.EditorModel): ImageController = ImageController()
    fun remove(uri: android.net.Uri) = Unit
  }
}
