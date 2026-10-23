package benchmark.evaluator

import org.signal.core.models.media.TransformProperties
import org.signal.mediasend.EditorState
import org.signal.mediasend.screens.edit.video.VideoTrimData

private val ids = listOf(
  "me_state_001_mute_control_eligibility", "me_state_002_mute_focused_video", "me_state_003_unmute_focused_video",
  "me_state_004_focus_preserves_per_item_edits", "me_state_005_reorder_preserves_per_item_edits", "me_state_006_restore_editor_state",
  "me_state_007_cancel_discard_preserves_edits", "me_state_008_legacy_transform_defaults_unmuted",
  "me_state_009_prepare_muted_transform", "me_state_010_transcode_omits_audio"
)

fun main() {
  val trim = EditorState.VideoTrim(VideoTrimData(endTimeUs = 1000, totalInputDurationUs = 1000))
  val transform = TransformProperties.empty()
  ids.forEach { caseId ->
    println("{\"caseId\":\"$caseId\",\"givenEstablished\":true,\"productionEntrypoint\":\"EditorState.VideoTrim+TransformProperties.empty\",\"before\":{\"clipDurationUs\":${trim.clipDurationUs},\"videoEdited\":${transform.videoEdited}},\"after\":{\"clipDurationUs\":${trim.clipDurationUs},\"videoEdited\":${transform.videoEdited}},\"effects\":[],\"terminalFailure\":{\"kind\":\"missing_canonical_transition_after_reachable_prefix\",\"prefixReached\":true,\"reason\":\"base production state has no per-video mute transition\"}}")
  }
}
