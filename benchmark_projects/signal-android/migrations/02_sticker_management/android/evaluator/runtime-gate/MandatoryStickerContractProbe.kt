package benchmark.evaluator

import android.app.Application

private var harnessApplication: Application? = null

fun installHarnessApplication(application: Application) {
  harnessApplication = application
}

private fun json(value: Any?): String = when (value) {
  null -> "null"
  is String -> "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""
  is Number, is Boolean -> value.toString()
  is Map<*, *> -> value.entries.joinToString(prefix = "{", postfix = "}") { (key, item) -> "${json(key.toString())}:${json(item)}" }
  is Iterable<*> -> value.joinToString(prefix = "[", postfix = "]") { json(it) }
  else -> json(value.toString())
}

private data class MethodContract(val owner: String, val name: String, val parameterCount: Int)

private val classes = listOf(
  "org.thoughtcrime.securesms.database.model.StickerPackId",
  "org.thoughtcrime.securesms.database.model.StickerPackKey",
  "org.thoughtcrime.securesms.stickers.StickerManagementRepository",
  "org.thoughtcrime.securesms.stickers.StickerManagementUiState",
  "org.thoughtcrime.securesms.stickers.StickerManagementViewModel"
)

private val methods = listOf(
  MethodContract("org.thoughtcrime.securesms.stickers.StickerManagementViewModel", "installStickerPack", 1),
  MethodContract("org.thoughtcrime.securesms.stickers.StickerManagementViewModel", "onUninstallStickerPacksRequested", 1),
  MethodContract("org.thoughtcrime.securesms.stickers.StickerManagementViewModel", "onUninstallStickerPacksConfirmed", 1),
  MethodContract("org.thoughtcrime.securesms.stickers.StickerManagementViewModel", "onUninstallStickerPacksCanceled", 0),
  MethodContract("org.thoughtcrime.securesms.stickers.StickerManagementViewModel", "updatePosition", 2),
  MethodContract("org.thoughtcrime.securesms.stickers.StickerManagementViewModel", "saveInstalledPacksSortOrder", 0),
  MethodContract("org.thoughtcrime.securesms.stickers.StickerManagementViewModel", "toggleSelection", 1),
  MethodContract("org.thoughtcrime.securesms.stickers.StickerManagementViewModel", "toggleSelectAll", 0),
  MethodContract("org.thoughtcrime.securesms.stickers.StickerManagementViewModel", "setMultiSelectEnabled", 1),
  MethodContract("org.thoughtcrime.securesms.stickers.StickerManagementViewModel", "getUiState", 0)
)

private val caseIds = listOf(
  "sm_state_001_exit_multiselect",
  "sm_state_002_install_lifecycle",
  "sm_state_003_install_status_settles",
  "sm_state_004_drag_reorder",
  "sm_state_005_drop_persists_order",
  "sm_state_006_select_enters_multiselect",
  "sm_state_007_select_all_toggle",
  "sm_state_008_request_multi_delete",
  "sm_state_009_cancel_multi_delete",
  "sm_state_010_confirm_multi_delete"
)

fun main() {
  val application = checkNotNull(harnessApplication) { "Android Application was not installed by HarnessActivity" }
  val loader = checkNotNull(application.javaClass.classLoader) { "Android application ClassLoader is unavailable" }
  val missing = mutableListOf<String>()

  for (className in classes) {
    try {
      Class.forName(className, false, loader)
    } catch (_: ClassNotFoundException) {
      missing += className
    }
  }
  for (contract in methods) {
    val owner = try {
      Class.forName(contract.owner, false, loader)
    } catch (_: ClassNotFoundException) {
      continue
    }
    if (owner.methods.none { it.name == contract.name && it.parameterCount == contract.parameterCount }) {
      missing += "${contract.owner}#${contract.name}/${contract.parameterCount}"
    }
  }

  check(missing.isNotEmpty()) {
    "The public sticker integration ABI is present; the executable state bridge must handle this candidate"
  }

  for (caseId in caseIds) {
    println(json(mapOf(
      "caseId" to caseId,
      "productionEntrypoint" to "Android application ClassLoader public integration gate",
      "before" to null,
      "after" to null,
      "effects" to emptyList<Any>(),
      "givenEstablished" to false,
      "terminalFailure" to mapOf(
        "kind" to "mandatory_public_integration_contract_unavailable_after_app_launch",
        "appRuntimeReached" to true,
        "missingDeclarations" to missing
      ),
      "availability" to "executed_android_application_runtime_capability_gate"
    )))
  }
}
