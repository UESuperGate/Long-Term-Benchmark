package org.thoughtcrime.securesms.stickers

import android.app.Application
import org.thoughtcrime.securesms.database.SignalDatabase
import org.thoughtcrime.securesms.database.model.StickerPackRecord
import org.thoughtcrime.securesms.database.model.StickerRecord
import org.thoughtcrime.securesms.dependencies.AppDependencies
import org.thoughtcrime.securesms.jobs.MultiDeviceStickerPackOperationJob
import org.thoughtcrime.securesms.jobs.StickerPackDownloadJob
import org.thoughtcrime.securesms.keyvalue.SignalStore
import java.io.File

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

private fun record(id: String, installed: Boolean, title: String = id): StickerPackRecord = StickerPackRecord(
  id,
  "key-$id",
  title,
  "fixture",
  StickerRecord(1, id, "key-$id", 1, "", "image/webp", 1, true),
  installed
)

private fun reset(caseId: String, records: List<StickerPackRecord>, linked: Boolean = false) {
  val application = checkNotNull(harnessApplication) { "Android Application was not installed by HarnessActivity" }
  val backing = File(application.filesDir, "$caseId-stickers.bin")
  if (backing.exists()) check(backing.delete()) { "could not reset $backing" }
  SignalDatabase.stickers.resetBacking(backing, records)
  AppDependencies.jobManager.jobs.clear()
  SignalStore.account.hasLinkedDevices = linked
}

private fun viewModel(): StickerManagementViewModel {
  val application = checkNotNull(harnessApplication)
  val repository = StickerManagementRepository(application)
  return StickerManagementViewModel.Factory(application, repository).create(StickerManagementViewModel::class.java)
}

private fun packs(vm: StickerManagementViewModel): Map<String, Any?> {
  val result = vm.stickerPacks.getValue()
  return mapOf(
    "installedPackIds" to (result?.installedPacks?.map { it.packId } ?: emptyList<String>()),
    "availableOfficialIds" to (result?.blessedPacks?.map { it.packId } ?: emptyList<String>()),
    "availableOtherIds" to (result?.availablePacks?.map { it.packId } ?: emptyList<String>()),
    "availablePackIds" to ((result?.blessedPacks.orEmpty() + result?.availablePacks.orEmpty()).map { it.packId })
  )
}

private fun leafEffects(): List<Map<String, Any?>> {
  val values = SignalDatabase.stickers.effects.toMutableList()
  for (job in AppDependencies.jobManager.jobs) {
    when (job) {
      is StickerPackDownloadJob -> if (job.kind == "INSTALL") values += mapOf("name" to "installStickerPack", "packId" to job.packId, "notify" to job.notify, "count" to 1)
      is MultiDeviceStickerPackOperationJob -> values += mapOf("name" to "enqueueLinkedOperation", "packId" to job.packId, "operation" to job.type.name, "count" to 1)
    }
  }
  return values
}

private fun emitTerminal(caseId: String, entrypoint: String, before: Map<String, Any?>, after: Map<String, Any?>, setup: Map<String, Any?>) {
  val prefixReached = after.containsKey("installedPackIds") && after.containsKey("availablePackIds")
  println(json(mapOf(
    "caseId" to caseId,
    "productionEntrypoint" to entrypoint,
    "before" to before,
    "after" to after,
    "effects" to leafEffects(),
    "setup" to setup,
    "orderedStates" to emptyList<String>(),
    "givenEstablished" to false,
    "terminalFailure" to mapOf(
      "kind" to "missing_canonical_transition_after_reachable_prefix",
      "prefixReached" to prefixReached,
      "prefix" to entrypoint
    ),
    "availability" to "executed_legacy_production_prefix"
  )))
}

fun main() {
  run {
    reset("sm-base-001", listOf(record("a", true), record("b", true)))
    val vm = viewModel()
    val before = packs(vm)
    emitTerminal("sm_state_001_exit_multiselect", "StickerManagementViewModel.getStickerPacks", before, packs(vm), mapOf("backingInstalledIds" to listOf("a", "b")))
  }

  run {
    reset("sm-base-002", listOf(record("p1", false, "One")))
    val vm = viewModel()
    val before = packs(vm)
    vm.onStickerPackInstallClicked("p1", "key-p1")
    emitTerminal("sm_state_002_install_lifecycle", "StickerManagementViewModel.onStickerPackInstallClicked/StickerManagementRepository.installStickerPack", before, packs(vm), mapOf("availablePackLoadedFrom" to "StickerManagementRepository.getStickerPacks"))
  }

  run {
    reset("sm-base-003", listOf(record("p1", false, "One")))
    val vm = viewModel()
    val before = packs(vm)
    vm.onStickerPackInstallClicked("p1", "key-p1")
    emitTerminal("sm_state_003_install_status_settles", "StickerManagementViewModel.onStickerPackInstallClicked", before, packs(vm), mapOf("installPrefixReached" to true))
  }

  for (caseId in listOf(
    "sm_state_004_drag_reorder",
    "sm_state_005_drop_persists_order",
    "sm_state_006_select_enters_multiselect",
    "sm_state_007_select_all_toggle",
    "sm_state_008_request_multi_delete",
    "sm_state_009_cancel_multi_delete",
    "sm_state_010_confirm_multi_delete"
  )) {
    reset("sm-base-$caseId", listOf(record("a", true), record("b", true), record("c", true)), linked = caseId == "sm_state_010_confirm_multi_delete")
    val vm = viewModel()
    val before = packs(vm)
    emitTerminal(caseId, "StickerManagementViewModel.getStickerPacks", before, packs(vm), mapOf("backingInstalledIds" to listOf("a", "b", "c")))
  }
}
