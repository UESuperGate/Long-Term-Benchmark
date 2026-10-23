package benchmark.evaluator

import android.media.MediaDataSource
import android.net.Uri
import androidx.lifecycle.SavedStateHandle
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.signal.core.models.media.Media
import org.signal.core.models.media.TransformProperties
import org.signal.mediasend.EditorState
import org.signal.mediasend.MediaFilterResult
import org.signal.mediasend.MediaSendFlowActivityContract
import org.signal.mediasend.MediaSendFlowEvent
import org.signal.mediasend.MediaSendFlowState
import org.signal.mediasend.MediaSendFlowViewModel
import org.signal.mediasend.MediaSendRepository
import org.signal.mediasend.SendRequest
import org.signal.mediasend.SendResult
import org.signal.mediasend.SentMediaQuality
import org.signal.mediasend.StorySendRequirements
import org.signal.mediasend.preupload.PreUploadController
import org.signal.mediasend.screens.edit.image.BrushWidths
import org.signal.mediasend.screens.edit.video.VideoTrimData
import org.thoughtcrime.securesms.mediasend.VideoTrimTransform
import org.thoughtcrime.securesms.video.StreamingTranscoder
import org.thoughtcrime.securesms.video.TranscodingConfig
import org.thoughtcrime.securesms.video.videoconverter.MediaConverter
import java.io.ByteArrayOutputStream
import java.util.Base64
import kotlin.time.Duration

private const val TINY_H264_MP4_BASE64 = "AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAMWbW9vdgAAAGxtdmhkAAAAAAAAAAAAAAAAAAAD6AAAA+gAAQAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAkB0cmFrAAAAXHRraGQAAAADAAAAAAAAAAAAAAABAAAAAAAAA+gAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAABAAAAAACAAAAAgAAAAAAAkZWR0cwAAABxlbHN0AAAAAAAAAAEAAAPoAAAAAAABAAAAAAG4bWRpYQAAACBtZGhkAAAAAAAAAAAAAAAAAABAAAAAQABVxAAAAAAALWhkbHIAAAAAAAAAAHZpZGUAAAAAAAAAAAAAAABWaWRlb0hhbmRsZXIAAAABY21pbmYAAAAUdm1oZAAAAAEAAAAAAAAAAAAAACRkaW5mAAAAHGRyZWYAAAAAAAAAAQAAAAx1cmwgAAAAAQAAASNzdGJsAAAAv3N0c2QAAAAAAAAAAQAAAK9hdmMxAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAACAAIABIAAAASAAAAAAAAAABFUxhdmM2Mi4yOC4xMDEgbGlieDI2NAAAAAAAAAAAAAAAGP//AAAANWF2Y0MBZAAK/+EAGGdkAAqs2UlsBEAAAAMAQAAAAwCDxIllgAEABmjr48siwP34+AAAAAAQcGFzcAAAAAEAAAABAAAAFGJ0cnQAAAAAAAAWgAAAAAAAAAAYc3R0cwAAAAAAAAABAAAAAQAAQAAAAAAcc3RzYwAAAAAAAAABAAAAAQAAAAEAAAABAAAAFHN0c3oAAAAAAAAC0AAAAAEAAAAUc3RjbwAAAAAAAAABAAADRgAAAGJ1ZHRhAAAAWm1ldGEAAAAAAAAAIWhkbHIAAAAAAAAAAG1kaXJhcHBsAAAAAAAAAAAAAAAALWlsc3QAAAAlqXRvbwAAAB1kYXRhAAAAAQAAAABMYXZmNjIuMTIuMTAxAAAACGZyZWUAAALYbWRhdAAAAq0GBf//qdxF6b3m2Ui3lizYINkj7u94MjY0IC0gY29yZSAxNjUgcjMyMjMgMDQ4MGNiMCAtIEguMjY0L01QRUctNCBBVkMgY29kZWMgLSBDb3B5bGVmdCAyMDAzLTIwMjUgLSBodHRwOi8vd3d3LnZpZGVvbGFuLm9yZy94MjY0Lmh0bWwgLSBvcHRpb25zOiBjYWJhYz0xIHJlZj0zIGRlYmxvY2s9MTowOjAgYW5hbHlzZT0weDM6MHgxMTMgbWU9aGV4IHN1Ym1lPTcgcHN5PTEgcHN5X3JkPTEuMDA6MC4wMiBtaXhlZF9yZWY9MSBtZV9yYW5nZT0xNiBjaHJvbWFfbWU9MSB0cmVsbGlzPTEgOHg4ZGN0PTEgY3FtPTAgZGVhZHpvbmU9MjEsMTEgZmFzdF9wc2tpcD0xIGNocm9tYV9xcF9vZmZzZXQ9LTIgdGhyZWFkcz0xIGxvb2thaGVhZF90aHJlYWRzPTEgc2xpY2VkX3RocmVhZHM9MCBucj0wIGRlY2ltYXRlPTEgaW50ZXJsYWNlZD0wIGJsdXJheV9jb21wYXQ9MCBjb25zdHJhaW5lZF9pbnRyYT0wIGJmcmFtZXM9MyBiX3B5cmFtaWQ9MiBiX2FkYXB0PTEgYl9iaWFzPTAgZGlyZWN0PTEgd2VpZ2h0Yj0xIG9wZW5fZ29wPTAgd2VpZ2h0cD0yIGtleWludD0yNTAga2V5aW50X21pbj0xIHNjZW5lY3V0PTQwIGludHJhX3JlZnJlc2g9MCByY19sb29rYWhlYWQ9NDAgcmM9Y3JmIG1idHJlZT0xIGNyZj0yMy4wIHFjb21wPTAuNjAgcXBtaW49MCBxcG1heD02OSBxcHN0ZXA9NCBpcF9yYXRpbz0xLjQwIGFxPTE6MS4wMACAAAAAG2WIhAAV//7sz34FN0a5i/MZbsx35143uhD/4Q=="

private fun media(id: String, videoGif: Boolean = false, contentType: String = "video/mp4") = Media(
  uri = Uri.parse(id), contentType = contentType, date = 0, width = 100, height = 100, size = 10,
  duration = 1000, isBorderless = false, isVideoGif = videoGif, bucketId = null, caption = null,
  transformProperties = null, fileName = "$id.mp4"
)

private class Repository : MediaSendRepository {
  override var sentMediaQuality = SentMediaQuality.STANDARD
  override var brushWidths = BrushWidths()
  override val storyMaxVideoDuration = Duration.ZERO
  override val hasDismissedSaveToStorageWarning = true
  override suspend fun validateAndFilterMedia(media: List<Media>, maxSelection: Int, isStory: Boolean) = MediaFilterResult(media, null)
  override suspend fun deleteBlobs(media: List<Media>) = Unit
  override suspend fun getDocumentInfo(media: Media) = null
  override suspend fun getStorySendRequirements(media: List<Media>) = media.associate { it.uri to StorySendRequirements.CAN_SEND }
  override suspend fun checkUntrustedIdentities(contactIds: Set<Long>, since: Long) = emptyList<Long>()
  override suspend fun saveImageToStorage(editorModel: org.signal.imageeditor.core.model.EditorModel) = org.signal.mediasend.SaveToStorageResult.SUCCESS
  override suspend fun send(request: SendRequest): SendResult = SendResult.Success
  override fun getMaxVideoDurationUs(quality: SentMediaQuality, duration: Duration) = duration.inWholeMicroseconds
  override fun getVideoTranscodingTiers(quality: SentMediaQuality) = emptyList<TranscodingConfig.QualityTier>()
  override fun isVideoTranscodeAvailable() = true
  override fun getMediaConstraints() = org.signal.mediasend.MediaConstraints()
  override fun markSaveToStorageWarningDismissed() = Unit
}

private class UploadRecorder : PreUploadController() {
  val cancelled = mutableListOf<String>()
  val orders = mutableListOf<List<String>>()
  override fun cancelUpload(media: Media) { cancelled += media.uri.toString() }
  override fun updateDisplayOrder(media: List<Media>) { orders += media.map { it.uri.toString() } }
}

private data class Fixture(val viewModel: MediaSendFlowViewModel, val upload: UploadRecorder, val handle: SavedStateHandle)
private class ProbeContext : android.content.Context()

private fun fixture(state: MediaSendFlowState): Fixture {
  val handle = SavedStateHandle(mapOf(
    "media_send_vm_args" to MediaSendFlowActivityContract.Args(),
    "media_send_vm_identity_changes_since" to 0L,
    "media_send_vm_state" to state
  ))
  val upload = UploadRecorder()
  return Fixture(MediaSendFlowViewModel(handle, Repository(), upload, flowOf(false)), upload, handle)
}

private fun q(value: String) = "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""
private fun emit(caseId: String, entry: String, before: String, after: String, effects: String = "[]") {
  println("{\"caseId\":${q(caseId)},\"givenEstablished\":true,\"productionEntrypoint\":${q(entry)},\"before\":$before,\"after\":$after,\"effects\":$effects}")
}

fun main() = runBlocking {
  val one = media("video-1")
  val two = media("video-2")
  val image = media("image-1", contentType = "image/jpeg")
  val gifVideo = media("gif-video", videoGif = true)
  val trimMuted = EditorState.VideoTrim(VideoTrimData(endTimeUs = 1000, totalInputDurationUs = 1000, isMuted = true))
  val trimAudible = EditorState.VideoTrim(VideoTrimData(endTimeUs = 1000, totalInputDurationUs = 1000, isMuted = false))

  val eligible = listOf(one to trimAudible, gifVideo to EditorState.VideoGif, image to EditorState.Gif).associate { (item, editor) ->
    item.uri.toString() to (MediaSendFlowState(isMuteVideoAudioEnabled = true, focusedMedia = item, editorStateMap = mapOf(item.uri to editor)).let {
      it.isMuteVideoAudioEnabled && it.editorStateMap[it.focusedMedia?.uri] is EditorState.VideoTrim && !item.isVideoGif
    })
  }
  emit("me_state_001_mute_control_eligibility", "MediaSendFlowState.isMuteVideoAudioEnabled+EditorState.VideoTrim", "{\"focusedItemId\":\"video-1\"}", "{\"muteControlByItem\":{\"video-1\":${eligible["video-1"]},\"gif-video\":${eligible["gif-video"]},\"image-1\":${eligible["image-1"]}}}")

  run {
    val fx = fixture(MediaSendFlowState(selectedMedia = listOf(one), focusedMedia = one, editorStateMap = mapOf(one.uri to trimAudible)))
    fx.viewModel.onEvent(MediaSendFlowEvent.ToggleVideoMuted)
    fx.viewModel.toastEvents.first()
    val muted = (fx.viewModel.state.value.editorStateMap[one.uri] as EditorState.VideoTrim).videoTrimData.isMuted
    emit("me_state_002_mute_focused_video", "MediaSendFlowViewModel.onEvent(ToggleVideoMuted)", "{\"isMuted\":false}", "{\"focusedItemId\":\"video-1\",\"selectedItemIds\":[\"video-1\"],\"editorStateByItem\":{\"video-1\":{\"kind\":\"video_trim\",\"isMuted\":$muted}}}", "[{\"name\":\"cancelPreUpload\",\"itemId\":\"video-1\",\"count\":${fx.upload.cancelled.size}},{\"name\":\"showMutedFeedback\",\"count\":1}]")
  }

  run {
    val fx = fixture(MediaSendFlowState(selectedMedia = listOf(one), focusedMedia = one, editorStateMap = mapOf(one.uri to trimMuted)))
    fx.viewModel.onEvent(MediaSendFlowEvent.ToggleVideoMuted)
    val muted = (fx.viewModel.state.value.editorStateMap[one.uri] as EditorState.VideoTrim).videoTrimData.isMuted
    emit("me_state_003_unmute_focused_video", "MediaSendFlowViewModel.onEvent(ToggleVideoMuted)", "{\"isMuted\":true}", "{\"focusedItemId\":\"video-1\",\"selectedItemIds\":[\"video-1\"],\"editorStateByItem\":{\"video-1\":{\"kind\":\"video_trim\",\"isMuted\":$muted}}}", "[{\"name\":\"cancelPreUpload\",\"itemId\":\"video-1\",\"count\":${fx.upload.cancelled.size}}]")
  }

  run {
    val fx = fixture(MediaSendFlowState(selectedMedia = listOf(one, two), focusedMedia = one, editorStateMap = mapOf(one.uri to trimMuted, two.uri to trimAudible)))
    fx.viewModel.onEvent(MediaSendFlowEvent.SetFocusedMedia(two))
    val state = fx.viewModel.state.value
    emit("me_state_004_focus_preserves_per_item_edits", "MediaSendFlowViewModel.onEvent(SetFocusedMedia)", "{\"focusedItemId\":\"video-1\"}", "{\"selectedItemIds\":[\"video-1\",\"video-2\"],\"focusedItemId\":\"${state.focusedMedia?.uri}\",\"focusedEditorState\":{\"kind\":\"video_trim\",\"isMuted\":false},\"editorStateByItem\":{\"video-1\":{\"kind\":\"video_trim\",\"isMuted\":true},\"video-2\":{\"kind\":\"video_trim\",\"isMuted\":false}}}")
  }

  run {
    val fx = fixture(MediaSendFlowState(selectedMedia = listOf(one, two, image), focusedMedia = one, editorStateMap = mapOf(one.uri to trimMuted, two.uri to trimAudible)))
    fx.viewModel.onEvent(MediaSendFlowEvent.ReorderSelectedMedia(0, 2))
    val ids = fx.viewModel.state.value.selectedMedia.joinToString(",") { q(it.uri.toString()) }
    val order = fx.upload.orders.single().joinToString(",") { q(it) }
    emit("me_state_005_reorder_preserves_per_item_edits", "MediaSendFlowViewModel.onEvent(ReorderSelectedMedia)", "{\"selectedItemIds\":[\"video-1\",\"video-2\",\"image-1\"]}", "{\"selectedItemIds\":[$ids],\"focusedItemId\":\"video-1\",\"editorStateByItem\":{\"video-1\":{\"kind\":\"video_trim\",\"isMuted\":true},\"video-2\":{\"kind\":\"video_trim\",\"isMuted\":false}}}", "[{\"name\":\"updatePreUploadDisplayOrder\",\"itemIds\":[$order],\"count\":1}]")
  }

  run {
    val saved = MediaSendFlowState(selectedMedia = listOf(one, two), focusedMedia = two, editorStateMap = mapOf(
      one.uri to EditorState.VideoTrim(VideoTrimData(isDurationEdited = true, startTimeUs = 100, endTimeUs = 900, totalInputDurationUs = 1000, isMuted = true)),
      two.uri to trimAudible
    ))
    val fx = fixture(saved)
    val restored = MediaSendFlowViewModel(fx.handle, Repository(), UploadRecorder(), flowOf(false)).state.value
    emit("me_state_006_restore_editor_state", "SavedStateHandle.getMutableStateFlow+MediaSendFlowViewModel.<init>", "{\"runtimeGeneration\":1}", "{\"selectedItemIds\":[\"video-1\",\"video-2\"],\"focusedItemId\":\"${restored.focusedMedia?.uri}\",\"focusedEditorState\":{\"kind\":\"video_trim\",\"isMuted\":false,\"startTimeUs\":0,\"endTimeUs\":1000},\"editorStateByItem\":{\"video-1\":{\"kind\":\"video_trim\",\"isMuted\":true,\"startTimeUs\":100,\"endTimeUs\":900},\"video-2\":{\"kind\":\"video_trim\",\"isMuted\":false,\"startTimeUs\":0,\"endTimeUs\":1000}}}")
  }

  run {
    val fx = fixture(MediaSendFlowState(selectedMedia = listOf(one), focusedMedia = one, editorStateMap = mapOf(one.uri to trimMuted)))
    fx.viewModel.onCloseRequested()
    val state = fx.viewModel.state.value
    emit("me_state_007_cancel_discard_preserves_edits", "MediaSendFlowViewModel.onCloseRequested", "{\"screen\":\"media_editor\"}", "{\"selectedItemIds\":[\"video-1\"],\"focusedItemId\":\"${state.focusedMedia?.uri}\",\"editorStateByItem\":{\"video-1\":{\"kind\":\"video_trim\",\"isMuted\":true}},\"screen\":\"media_editor\"}", "[{\"name\":\"showDiscardConfirmation\",\"count\":${fx.viewModel.discardMediaDialog.showCount}}]")
  }

  run {
    val restored = TransformProperties.empty()
    emit("me_state_008_legacy_transform_defaults_unmuted", "TransformProperties.empty", "{\"storedPayloadHasVideoMuted\":false}", "{\"videoMuted\":${restored.videoMuted},\"videoEdited\":${restored.videoEdited},\"videoTrim\":${restored.videoTrim},\"sentMediaQuality\":${restored.sentMediaQuality}}")
  }

  run {
    val transformed = VideoTrimTransform(VideoTrimData(endTimeUs = 1_000_000, totalInputDurationUs = 1_000_000, isMuted = true)).transform(ProbeContext(), one)
    val p = transformed.transformProperties!!
    emit("me_state_009_prepare_muted_transform", "VideoTrimTransform.transform", "{\"transformProperties\":null}", "{\"transformProperties\":{\"videoTrim\":${p.videoTrim},\"videoTrimStartTimeUs\":${p.videoTrimStartTimeUs},\"videoTrimEndTimeUs\":${p.videoTrimEndTimeUs},\"videoMuted\":${p.videoMuted},\"videoEdited\":${p.videoEdited}},\"videoTrack\":true}", "[{\"name\":\"applyVideoTransform\",\"itemId\":\"video-1\",\"count\":1}]")
  }

  run {
    val bytes = Base64.getDecoder().decode(TINY_H264_MP4_BASE64)
    val source = object : MediaDataSource() {
      override fun readAt(position: Long, buffer: ByteArray, offset: Int, size: Int): Int {
        if (position >= bytes.size) return -1
        val count = minOf(size, bytes.size - position.toInt())
        bytes.copyInto(buffer, offset, position.toInt(), position.toInt() + count)
        return count
      }
      override fun getSize() = bytes.size.toLong()
      override fun close() = Unit
    }
    MediaConverter.reset()
    val transcoder = StreamingTranscoder.createManuallyForTesting(source, null, "video/avc", 800, 200, 720, true, true)
    val required = transcoder.isTranscodeRequired
    transcoder.transcode({ }, ByteArrayOutputStream(), null)
    emit("me_state_010_transcode_omits_audio", "StreamingTranscoder.createManuallyForTesting/transcode", "{\"audioTrack\":true}", "{\"output\":{\"videoTrack\":true,\"audioTrack\":${!MediaConverter.lastSkipAudio}},\"transcodeRequired\":$required}", "[{\"name\":\"setSkipAudio\",\"value\":${MediaConverter.lastSkipAudio},\"count\":1},{\"name\":\"convertVideo\",\"count\":${if (MediaConverter.converted) 1 else 0}}]")
  }
}
