package benchmark.evaluator

import org.thoughtcrime.securesms.components.compose.mediakeyboard.MediaKeyboardController
import org.thoughtcrime.securesms.components.compose.mediakeyboard.MediaKeyboardKey

private fun json(value: Any?): String = when (value) {
  null -> "null"
  is String -> "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""
  is Number, is Boolean -> value.toString()
  is Map<*, *> -> value.entries.joinToString(prefix = "{", postfix = "}") { (key, item) -> "${json(key.toString())}:${json(item)}" }
  is Iterable<*> -> value.joinToString(prefix = "[", postfix = "]") { json(it) }
  else -> json(value.toString())
}

private fun state(controller: MediaKeyboardController): Map<String, Any?> = mapOf(
  "isShowing" to controller.isShowing,
  "current" to controller.current?.name,
  "keyboardHeightPx" to controller.keyboardHeightPx,
  "awaitingSystemKeyboard" to controller.awaitingSystemKeyboard
)

fun main() {
  val cases = listOf(
    "mk_state_001_initialize_tabs",
    "mk_state_002_restrict_fallback",
    "mk_state_003_lift_restriction",
    "mk_state_004_tab_clears_query",
    "mk_state_005_gif_initial_failure",
    "mk_state_006_gif_retry_recovery",
    "mk_state_007_gif_pagination",
    "mk_state_008_sticker_tap_defers_send",
    "mk_state_009_confirmation_cancel",
    "mk_state_010_confirmation_send_once"
  )

  for (caseId in cases) {
    val controller = MediaKeyboardController(320)
    val before = state(controller)
    controller.show(MediaKeyboardKey("media"))
    val after = state(controller)
    val prefixReached = after["isShowing"] == true && after["current"] == "media"
    println(json(mapOf(
      "caseId" to caseId,
      "productionEntrypoint" to "MediaKeyboardController.show",
      "before" to before,
      "after" to after,
      "effects" to emptyList<Any>(),
      "setup" to mapOf("initialKeyboardHeightPx" to 320, "keyboardKey" to "media"),
      "givenEstablished" to false,
      "terminalFailure" to mapOf(
        "kind" to "missing_canonical_transition_after_reachable_prefix",
        "prefixReached" to prefixReached,
        "prefix" to "MediaKeyboardController.show(media)"
      ),
      "availability" to "executed_legacy_production_prefix"
    )))
  }
}
