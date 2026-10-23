package benchmark.evaluator

import android.app.Application
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withTimeoutOrNull
import org.thoughtcrime.securesms.database.SignalDatabase
import org.thoughtcrime.securesms.database.model.StickerPackId
import org.thoughtcrime.securesms.database.model.StickerPackRecord
import org.thoughtcrime.securesms.database.model.StickerRecord
import org.thoughtcrime.securesms.dependencies.AppDependencies
import org.thoughtcrime.securesms.jobs.MultiDeviceStickerPackOperationJob
import org.thoughtcrime.securesms.jobs.StickerPackDownloadJob
import org.thoughtcrime.securesms.keyvalue.SignalStore
import org.thoughtcrime.securesms.stickers.AvailableStickerPack
import org.thoughtcrime.securesms.stickers.StickerManagementConfirmation
import org.thoughtcrime.securesms.stickers.StickerManagementUiState
import org.thoughtcrime.securesms.stickers.StickerManagementViewModel
import java.io.File
import java.lang.reflect.Field
import java.util.Collections
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

private var harnessApplication: Application? = null

private class BeforeAddList(
  private val delegate: MutableList<Any>,
  private val beforeAdd: (Any) -> Unit
) : MutableList<Any> by delegate {
  override fun add(element: Any): Boolean {
    beforeAdd(element)
    return delegate.add(element)
  }
}

private fun installBeforeJobAddHook(
  asynchronousLeafHook: (Any) -> Unit,
  inlineLeafHook: (Any) -> Unit
): () -> Unit {
  val jobManager = AppDependencies.jobManager
  val setter = jobManager.javaClass.methods.firstOrNull { method ->
    method.name == "setBeforeAdd" && method.parameterCount == 1
  }
  if (setter != null) {
    setter.invoke(jobManager, asynchronousLeafHook)
    return { setter.invoke(jobManager, null) }
  }

  val jobsField: Field = jobManager.javaClass.declaredFields.singleOrNull { field ->
    field.name == "jobs" && MutableList::class.java.isAssignableFrom(field.type)
  } ?: error("JobManager exposes neither setBeforeAdd nor the scaffold jobs leaf")
  jobsField.isAccessible = true
  @Suppress("UNCHECKED_CAST")
  val original = jobsField.get(jobManager) as MutableList<Any>
  jobsField.set(jobManager, BeforeAddList(original, inlineLeafHook))
  return { jobsField.set(jobManager, original) }
}

private fun clearBeforeJobAddHook() {
  val jobManager = AppDependencies.jobManager
  jobManager.javaClass.methods.firstOrNull { method ->
    method.name == "setBeforeAdd" && method.parameterCount == 1
  }?.invoke(jobManager, null)
}

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
  packId = id,
  packKey = "key-$id",
  title = title,
  author = "fixture",
  cover = StickerRecord(1, id, "key-$id", 1, "", "image/webp", 1, true),
  isInstalled = installed
)

private fun reset(caseId: String, records: List<StickerPackRecord>, linkedDevices: Boolean = false): File {
  val application = checkNotNull(harnessApplication) { "Android Application was not installed by HarnessActivity" }
  val backingFile = File(application.filesDir, "$caseId-stickers.bin")
  if (backingFile.exists()) check(backingFile.delete()) { "could not reset $backingFile" }
  SignalDatabase.stickers.resetBacking(backingFile, records)
  SignalDatabase.attachments.unavailable = emptyList()
  AppDependencies.jobManager.jobs.clear()
  clearBeforeJobAddHook()
  SignalStore.account.hasLinkedDevices = linkedDevices
  return backingFile
}

private suspend fun waitUntil(predicate: () -> Boolean) {
  withTimeout(5_000) {
    while (!predicate()) delay(10)
  }
}

private suspend fun waitUntilObserved(timeoutMillis: Long = 2_000, predicate: () -> Boolean): Boolean {
  return withTimeoutOrNull(timeoutMillis) {
    while (!predicate()) delay(10)
    true
  } == true
}

private fun confirmation(value: StickerManagementConfirmation?): Any? = when (value) {
  null -> null
  is StickerManagementConfirmation.InstalledPack -> mapOf("type" to "INSTALLED", "title" to value.packTitle)
  is StickerManagementConfirmation.UninstalledPack -> mapOf("type" to "UNINSTALLED", "title" to value.packTitle)
  is StickerManagementConfirmation.UninstalledPacks -> mapOf("type" to "UNINSTALLED_MULTIPLE", "count" to value.numPacksUninstalled)
}

private fun downloadStatus(value: StickerManagementUiState, packId: String): String? {
  return (value.availableBlessedPacks + value.availableNotBlessedPacks)
    .firstOrNull { it.id.value == packId }
    ?.downloadStatus
    ?.let {
      when (it) {
        AvailableStickerPack.DownloadStatus.NotDownloaded -> "NOT_DOWNLOADED"
        AvailableStickerPack.DownloadStatus.InProgress -> "IN_PROGRESS"
        AvailableStickerPack.DownloadStatus.Downloaded -> "DOWNLOADED"
      }
    }
}

private fun state(value: StickerManagementUiState, packId: String? = null): Map<String, Any?> = mapOf(
  "installedPackIds" to value.installedPacks.map { it.id.value },
  "availableOfficialIds" to value.availableBlessedPacks.map { it.id.value },
  "availableOtherIds" to value.availableNotBlessedPacks.map { it.id.value },
  "availablePackIds" to (value.availableBlessedPacks + value.availableNotBlessedPacks).map { it.id.value },
  "selectedPackIds" to value.selectedPackIds.map { it.value },
  "multiSelectEnabled" to value.multiSelectEnabled,
  "prompt" to value.userPrompt?.let { mapOf("numItemsToDelete" to it.numItemsToDelete) },
  "confirmation" to confirmation(value.actionConfirmation),
  "downloadStatus" to packId?.let { downloadStatus(value, it) }
)

private class DownloadStatusObservationLeaf(private val packId: String) {
  val calls = mutableListOf<Map<String, Any?>>()
  private var sawDownloaded = false

  fun onState(value: StickerManagementUiState) {
    val status = downloadStatus(value, packId)
    if (status == "DOWNLOADED") sawDownloaded = true
    if (sawDownloaded && status == null && value.installedPacks.any { it.id.value == packId } && calls.isEmpty()) {
      calls += mapOf("name" to "clearTransientDownloadStatus", "packId" to packId, "count" to 1)
    }
  }
}

private fun leafEffects(): List<Map<String, Any?>> {
  val effects = SignalDatabase.stickers.effects.toMutableList()
  for (job in AppDependencies.jobManager.jobs) {
    when (job) {
      is StickerPackDownloadJob -> if (job.kind == "INSTALL") effects += mapOf("name" to "installStickerPack", "packId" to job.packId, "notify" to job.notify, "count" to 1)
      is MultiDeviceStickerPackOperationJob -> effects += mapOf("name" to "enqueueLinkedOperation", "packId" to job.packId, "operation" to job.type.name, "count" to 1)
    }
  }
  return effects
}

private fun emit(
  caseId: String,
  entrypoint: String,
  before: Map<String, Any?>,
  after: Map<String, Any?>,
  effects: List<Map<String, Any?>>,
  setup: Map<String, Any?>,
  orderedStates: List<String> = emptyList(),
  orderedTimeline: List<String> = emptyList()
) {
  println(json(mapOf(
    "caseId" to caseId,
    "productionEntrypoint" to entrypoint,
    "before" to before,
    "after" to after,
    "effects" to effects,
    "setup" to setup,
    "orderedStates" to orderedStates,
    "orderedTimeline" to orderedTimeline,
    "givenEstablished" to true,
    "availability" to "executed_production_owner"
  )))
}

private fun emitReachableTransitionFailure(
  caseId: String,
  entrypoint: String,
  observedState: Map<String, Any?>,
  effects: List<Map<String, Any?>>,
  detail: String
) {
  println(json(mapOf(
    "caseId" to caseId,
    "productionEntrypoint" to entrypoint,
    "before" to observedState,
    "after" to observedState,
    "effects" to effects,
    "setup" to emptyMap<String, Any?>(),
    "orderedStates" to emptyList<String>(),
    "orderedTimeline" to emptyList<String>(),
    "givenEstablished" to false,
    "terminalFailure" to mapOf(
      "kind" to "canonical_given_unreachable_after_executed_production_prefix",
      "prefixReached" to true,
      "detail" to detail
    ),
    "availability" to "executed_production_owner"
  )))
}

fun main() = runBlocking {
  run {
    reset("sm-001", listOf(record("a", true), record("b", true)))
    val vm = StickerManagementViewModel()
    waitUntil { vm.uiState.value.installedPacks.size == 2 }
    vm.toggleSelection(vm.uiState.value.installedPacks.first())
    val before = state(vm.uiState.value)
    vm.setMultiSelectEnabled(false)
    emit("sm_state_001_exit_multiselect", "StickerManagementViewModel.setMultiSelectEnabled", before, state(vm.uiState.value), emptyList(), mapOf("selectionEstablishedBy" to "StickerManagementViewModel.toggleSelection", "backingInstalledIds" to listOf("a", "b")))
  }

  run {
    reset("sm-002", listOf(record("p1", false, "One")))
    val vm = StickerManagementViewModel()
    waitUntil { vm.uiState.value.availableNotBlessedPacks.isNotEmpty() }
    delay(25) // callbackFlow emits its first row before registering the database observer.
    val before = state(vm.uiState.value, "p1")
    val statuses = mutableListOf<String>()
    val timeline = Collections.synchronizedList(mutableListOf<String>())
    val inProgressObserved = CountDownLatch(1)
    val collection = launch(start = CoroutineStart.UNDISPATCHED) {
      vm.uiState.map { value -> downloadStatus(value, "p1") }
        .distinctUntilChanged()
        .collect { status ->
          if (status != null) timeline += "STATE:$status"
          if (status != null && status in setOf("IN_PROGRESS", "DOWNLOADED") && statuses.lastOrNull() != status) statuses += status
          if (status == "IN_PROGRESS") inProgressObserved.countDown()
        }
    }
    val recordAsynchronousEffect: (Any) -> Unit = { job ->
      if (job is StickerPackDownloadJob && job.kind == "INSTALL") {
        check(inProgressObserved.await(5, TimeUnit.SECONDS)) { "production IN_PROGRESS state was not observable before install leaf call" }
        timeline += "EFFECT:installStickerPack"
      }
    }
    val recordInlineEffect: (Any) -> Unit = { job ->
      if (job is StickerPackDownloadJob && job.kind == "INSTALL") {
        val statusAtEffect = downloadStatus(vm.uiState.value, "p1")
        check(statusAtEffect == "IN_PROGRESS") { "production state at install leaf was $statusAtEffect instead of IN_PROGRESS" }
        if (statuses.lastOrNull() != statusAtEffect) statuses += statusAtEffect
        if (timeline.lastOrNull() != "STATE:$statusAtEffect") timeline += "STATE:$statusAtEffect"
        timeline += "EFFECT:installStickerPack"
      }
    }
    val restoreJobHook = installBeforeJobAddHook(recordAsynchronousEffect, recordInlineEffect)
    try {
      vm.installStickerPack(vm.uiState.value.availableNotBlessedPacks.single())
      waitUntil { vm.uiState.value.actionConfirmation is StickerManagementConfirmation.InstalledPack }
      waitUntil { statuses == listOf("IN_PROGRESS", "DOWNLOADED") }
      emit("sm_state_002_install_lifecycle", "StickerManagementViewModel.installStickerPack/StickerManagementRepository.installStickerPack", before, state(vm.uiState.value, "p1"), leafEffects(), mapOf("availablePackLoadedFrom" to "StickerManagementRepository.getStickerPacks", "linkedDevices" to false), statuses.toList(), timeline.toList())
    } finally {
      restoreJobHook()
      collection.cancel()
    }
  }

  run {
    reset("sm-003", listOf(record("p1", false, "One")))
    val vm = StickerManagementViewModel()
    waitUntil { vm.uiState.value.availableNotBlessedPacks.isNotEmpty() }
    delay(25) // Ensure the production repository owns the external database notification leaf.
    val observationLeaf = DownloadStatusObservationLeaf("p1")
    val collection = launch(start = CoroutineStart.UNDISPATCHED) { vm.uiState.collect(observationLeaf::onState) }
    vm.installStickerPack(vm.uiState.value.availableNotBlessedPacks.single())
    waitUntil {
      vm.uiState.value.actionConfirmation is StickerManagementConfirmation.InstalledPack &&
        downloadStatus(vm.uiState.value, "p1") == "DOWNLOADED"
    }
    val canonicalGivenReached = waitUntilObserved {
      downloadStatus(vm.uiState.value, "p1") == "DOWNLOADED" &&
        vm.uiState.value.installedPacks.any { it.id.value == "p1" }
    }
    val before = state(vm.uiState.value, "p1")
    if (!canonicalGivenReached) {
      emitReachableTransitionFailure(
        "sm_state_003_install_status_settles",
        "StickerManagementViewModel.installStickerPack",
        before,
        leafEffects(),
        "install completed but the production owner did not establish the installed-pack portion of the canonical given"
      )
      collection.cancel()
      return@run
    }
    waitUntil { vm.uiState.value.availableNotBlessedPacks.none { it.id.value == "p1" } }
    waitUntil { observationLeaf.calls.isNotEmpty() }
    emit("sm_state_003_install_status_settles", "StickerManagementViewModel.installStickerPack delay/updatePackDownloadStatus", before, state(vm.uiState.value, "p1"), observationLeaf.calls.toList(), mapOf("downloadedStateEstablishedBy" to "StickerManagementViewModel.installStickerPack", "repositoryInstalledIds" to listOf("p1")))
    collection.cancel()
  }

  run {
    reset("sm-004", listOf(record("a", true), record("b", true), record("c", true)))
    val vm = StickerManagementViewModel()
    waitUntil { vm.uiState.value.installedPacks.size == 3 }
    val before = state(vm.uiState.value)
    vm.updatePosition(0, 2)
    emit("sm_state_004_drag_reorder", "StickerManagementViewModel.updatePosition", before, state(vm.uiState.value), emptyList(), mapOf("installedPacksLoadedFrom" to "StickerManagementRepository.getStickerPacks"))
  }

  run {
    val backing = reset("sm-005", listOf(record("a", true), record("b", true), record("c", true)))
    val vm = StickerManagementViewModel()
    waitUntil { vm.uiState.value.installedPacks.size == 3 }
    val before = state(vm.uiState.value)
    vm.updatePosition(0, 2)
    vm.saveInstalledPacksSortOrder()
    waitUntil { SignalDatabase.stickers.effects.any { it["name"] == "setStickerPacksOrder" } }
    val after = state(vm.uiState.value).toMutableMap()
    after["reopenedInstalledPackIds"] = SignalDatabase.stickers.reopenBacking().getAllStickerPacks().filter { it.isInstalled }.map { it.packId }
    emit("sm_state_005_drop_persists_order", "StickerManagementViewModel.updatePosition+saveInstalledPacksSortOrder/StickerManagementRepository.setStickerPacksOrder", before, after, leafEffects(), mapOf("installedPacksLoadedFrom" to "StickerManagementRepository.getStickerPacks", "backingStore" to backing.name, "reopened" to true))
  }

  run {
    reset("sm-006", listOf(record("a", true), record("b", true)))
    val vm = StickerManagementViewModel()
    waitUntil { vm.uiState.value.installedPacks.size == 2 }
    val before = state(vm.uiState.value)
    vm.toggleSelection(vm.uiState.value.installedPacks.first())
    emit("sm_state_006_select_enters_multiselect", "StickerManagementViewModel.toggleSelection", before, state(vm.uiState.value), emptyList(), mapOf("installedPacksLoadedFrom" to "StickerManagementRepository.getStickerPacks"))
  }

  run {
    reset("sm-007", listOf(record("a", true), record("b", true), record("c", true)))
    val vm = StickerManagementViewModel()
    waitUntil { vm.uiState.value.installedPacks.size == 3 }
    vm.toggleSelection(vm.uiState.value.installedPacks.first())
    val before = state(vm.uiState.value)
    vm.toggleSelectAll()
    emit("sm_state_007_select_all_toggle", "StickerManagementViewModel.toggleSelectAll", before, state(vm.uiState.value), emptyList(), mapOf("selectionEstablishedBy" to "StickerManagementViewModel.toggleSelection"))
  }

  run {
    reset("sm-008", listOf(record("a", true), record("b", true), record("c", true)))
    val vm = StickerManagementViewModel()
    waitUntil { vm.uiState.value.installedPacks.size == 3 }
    vm.toggleSelection(vm.uiState.value.installedPacks[0])
    vm.toggleSelection(vm.uiState.value.installedPacks[2])
    val ids = setOf(StickerPackId("a"), StickerPackId("c"))
    val before = state(vm.uiState.value)
    vm.onUninstallStickerPacksRequested(ids)
    emit("sm_state_008_request_multi_delete", "StickerManagementViewModel.onUninstallStickerPacksRequested", before, state(vm.uiState.value), leafEffects(), mapOf("selectionEstablishedBy" to "StickerManagementViewModel.toggleSelection"))
  }

  run {
    reset("sm-009", listOf(record("a", true), record("b", true), record("c", true)))
    val vm = StickerManagementViewModel()
    waitUntil { vm.uiState.value.installedPacks.size == 3 }
    vm.toggleSelection(vm.uiState.value.installedPacks[0])
    vm.toggleSelection(vm.uiState.value.installedPacks[2])
    val ids = setOf(StickerPackId("a"), StickerPackId("c"))
    vm.onUninstallStickerPacksRequested(ids)
    val before = state(vm.uiState.value)
    vm.onUninstallStickerPacksCanceled()
    emit("sm_state_009_cancel_multi_delete", "StickerManagementViewModel.onUninstallStickerPacksCanceled", before, state(vm.uiState.value), leafEffects(), mapOf("promptEstablishedBy" to "StickerManagementViewModel.onUninstallStickerPacksRequested"))
  }

  run {
    reset("sm-010", listOf(record("a", true), record("b", true), record("c", true)), linkedDevices = true)
    val vm = StickerManagementViewModel()
    waitUntil { vm.uiState.value.installedPacks.size == 3 }
    vm.toggleSelection(vm.uiState.value.installedPacks[0])
    vm.toggleSelection(vm.uiState.value.installedPacks[2])
    val ids = setOf(StickerPackId("a"), StickerPackId("c"))
    vm.onUninstallStickerPacksRequested(ids)
    val before = state(vm.uiState.value)
    vm.onUninstallStickerPacksConfirmed(ids)
    waitUntil { vm.uiState.value.actionConfirmation is StickerManagementConfirmation.UninstalledPacks }
    emit("sm_state_010_confirm_multi_delete", "StickerManagementViewModel.onUninstallStickerPacksConfirmed/StickerManagementRepository.uninstallStickerPacks", before, state(vm.uiState.value), leafEffects(), mapOf("promptEstablishedBy" to "StickerManagementViewModel.onUninstallStickerPacksRequested", "linkedDevices" to true))
  }
}
