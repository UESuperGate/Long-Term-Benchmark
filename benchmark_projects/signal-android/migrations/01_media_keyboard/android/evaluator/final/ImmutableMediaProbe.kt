package benchmark.evaluator

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.signal.core.util.Result
import org.signal.mediakeyboard.MediaKeyboardScreenEvents
import org.signal.mediakeyboard.MediaKeyboardState
import org.signal.mediakeyboard.MediaKeyboardTab
import org.signal.mediakeyboard.MediaKeyboardViewModel
import org.signal.mediakeyboard.data.EmojiCategoryPage
import org.signal.mediakeyboard.data.EmojiKeyboardRepository
import org.signal.mediakeyboard.data.GifFetchError
import org.signal.mediakeyboard.data.GifKeyboardRepository
import org.signal.mediakeyboard.data.GifPage
import org.signal.mediakeyboard.data.KeyboardEmoji
import org.signal.mediakeyboard.data.KeyboardGif
import org.signal.mediakeyboard.data.KeyboardSticker
import org.signal.mediakeyboard.data.KeyboardStickerPack
import org.signal.mediakeyboard.data.MediaKeyboardRepository
import org.signal.mediakeyboard.data.StickerKeyboardRepository
import org.signal.mediakeyboard.screens.gif.GifPageScreenEvents
import org.signal.mediakeyboard.screens.gif.GifPageState
import org.signal.mediakeyboard.screens.gif.GifPageViewModel
import org.thoughtcrime.securesms.conversation.v2.ChatStickerConfirmationController

private fun json(value: Any?): String = when (value) {
  null -> "null"
  is String -> "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""
  is Number, is Boolean -> value.toString()
  is Map<*, *> -> value.entries.joinToString(prefix = "{", postfix = "}") { (key, item) -> "${json(key.toString())}:${json(item)}" }
  is Iterable<*> -> value.joinToString(prefix = "[", postfix = "]") { json(it) }
  else -> json(value.toString())
}

private class EmojiLeaf : EmojiKeyboardRepository {
  override suspend fun getEmojiPages(): List<EmojiCategoryPage> = emptyList()
  override suspend fun getRecentEmoji(): List<KeyboardEmoji> = emptyList()
  override suspend fun search(query: String): List<KeyboardEmoji> = emptyList()
  override suspend fun getPreferredVariations(): Map<String, String> = emptyMap()
  override fun setPreferredVariation(canonical: String, variation: String) = Unit
  override suspend fun onEmojiUsed(emoji: String) = Unit
}

private class StickerLeaf : StickerKeyboardRepository {
  override val allowStickerAnimation: Boolean = false
  override fun observeStickerPacks(): Flow<List<KeyboardStickerPack>> = flowOf(emptyList())
}

private class GifLeaf(
  private var heldResult: CompletableDeferred<Result<GifPage, GifFetchError>>? = null
) : GifKeyboardRepository {
  val calls = mutableListOf<Map<String, Any?>>()
  private val results = ArrayDeque<Result<GifPage, GifFetchError>>()

  fun enqueue(result: Result<GifPage, GifFetchError>) {
    results.addLast(result)
  }

  override suspend fun getGifs(query: String, offset: Int, limit: Int): Result<GifPage, GifFetchError> {
    calls += mapOf("name" to "getGifs", "query" to query, "offset" to offset, "limit" to limit)
    val held = heldResult
    if (held != null) {
      heldResult = null
      return held.await()
    }
    return results.removeFirst()
  }
}

private class MediaRepository(
  private val tabs: Set<MediaKeyboardTab>,
  private val tabsGate: CompletableDeferred<Unit>? = null,
  override val gifs: GifLeaf = GifLeaf()
) : MediaKeyboardRepository {
  override val emoji: EmojiKeyboardRepository = EmojiLeaf()
  override val stickers: StickerKeyboardRepository = StickerLeaf()
  val calls = mutableListOf<Map<String, Any?>>()

  override suspend fun getAvailableTabs(): Set<MediaKeyboardTab> {
    calls += mapOf("name" to "getAvailableTabs", "count" to 1)
    tabsGate?.await()
    return tabs
  }
}

private class ConfirmationLeaf {
  val calls = mutableListOf<Map<String, Any?>>()

  fun controller(): ChatStickerConfirmationController = ChatStickerConfirmationController(
    onSend = { sticker -> calls += mapOf("name" to "onSend", "stickerId" to sticker.stickerId, "count" to 1) },
    onShowingChanged = { showing -> calls += mapOf("name" to "confirmationVisibility", "value" to showing) }
  )
}

private fun keyboardState(state: MediaKeyboardState): Map<String, Any?> = mapOf(
  "initialized" to state.initialized,
  "availableTabs" to state.availableTabs.map { it.name },
  "selectedTab" to state.selectedTab.name,
  "preferredTab" to state.preferredTab.name,
  "restrictedTo" to state.restrictedTo?.map { it.name },
  "searchActive" to state.searchActive,
  "searchQuery" to state.searchQuery
)

private fun gifState(state: GifPageState): Map<String, Any?> = mapOf(
  "gifs" to state.gifs.map { it.id },
  "isLoading" to state.isLoading,
  "isLoadingMore" to state.isLoadingMore,
  "hasMore" to state.hasMore,
  "loadFailed" to state.loadFailed
)

private fun confirmationState(controller: ChatStickerConfirmationController): Map<String, Any?> = mapOf(
  "confirmation" to controller.confirmation?.let {
    mapOf("packId" to it.sticker.packId, "packKey" to it.sticker.packKey, "stickerId" to it.sticker.stickerId)
  }
)

private fun gif(id: String) = KeyboardGif(id, null, null, 1, 1)

private suspend fun waitUntil(predicate: () -> Boolean) {
  withTimeout(5_000) {
    while (!predicate()) delay(10)
  }
}

private fun emit(
  caseId: String,
  entrypoint: String,
  before: Map<String, Any?>,
  after: Map<String, Any?>,
  effects: List<Map<String, Any?>>,
  setup: Map<String, Any?>
) {
  println(json(mapOf(
    "caseId" to caseId,
    "productionEntrypoint" to entrypoint,
    "before" to before,
    "after" to after,
    "effects" to effects,
    "setup" to setup,
    "givenEstablished" to true,
    "availability" to "executed_production_owner"
  )))
}

fun main() = runBlocking {
  run {
    val gate = CompletableDeferred<Unit>()
    val repositoryTabs = setOf(MediaKeyboardTab.GIF, MediaKeyboardTab.EMOJI, MediaKeyboardTab.STICKER)
    val repository = MediaRepository(repositoryTabs, gate)
    val vm = MediaKeyboardViewModel(repository, MutableStateFlow(false))
    val before = keyboardState(vm.state.value)
    gate.complete(Unit)
    waitUntil { vm.state.value.initialized }
    emit(
      "mk_state_001_initialize_tabs",
      "MediaKeyboardViewModel.init/onEvent(Initialize)",
      before,
      keyboardState(vm.state.value),
      repository.calls.toList(),
      mapOf("repositoryTabs" to repositoryTabs.map { it.name }, "initialTab" to null)
    )
  }

  run {
    val repository = MediaRepository(MediaKeyboardTab.entries.toSet())
    val vm = MediaKeyboardViewModel(repository, MutableStateFlow(false), MediaKeyboardTab.GIF)
    waitUntil { vm.state.value.initialized }
    val before = keyboardState(vm.state.value)
    vm.restrictTabs(setOf(MediaKeyboardTab.EMOJI))
    emit("mk_state_002_restrict_fallback", "MediaKeyboardViewModel.restrictTabs", before, keyboardState(vm.state.value), emptyList(), mapOf("offeredTabs" to before["availableTabs"], "preferredTab" to before["preferredTab"], "restrictedTo" to null))
  }

  run {
    val repository = MediaRepository(MediaKeyboardTab.entries.toSet())
    val vm = MediaKeyboardViewModel(repository, MutableStateFlow(false), MediaKeyboardTab.GIF)
    waitUntil { vm.state.value.initialized }
    vm.restrictTabs(setOf(MediaKeyboardTab.EMOJI))
    val before = keyboardState(vm.state.value)
    vm.restrictTabs(null)
    emit("mk_state_003_lift_restriction", "MediaKeyboardViewModel.restrictTabs", before, keyboardState(vm.state.value), emptyList(), mapOf("offeredTabs" to listOf("EMOJI", "STICKER", "GIF"), "preferredTab" to "GIF", "restrictedTo" to listOf("EMOJI")))
  }

  run {
    val repository = MediaRepository(MediaKeyboardTab.entries.toSet())
    val vm = MediaKeyboardViewModel(repository, MutableStateFlow(true), MediaKeyboardTab.EMOJI)
    waitUntil { vm.state.value.initialized && vm.state.value.searchActive }
    vm.onEvent(MediaKeyboardScreenEvents.SearchQueryChanged("cats"))
    waitUntil { vm.state.value.searchQuery == "cats" }
    val before = keyboardState(vm.state.value)
    vm.onEvent(MediaKeyboardScreenEvents.TabSelected(MediaKeyboardTab.GIF))
    waitUntil { vm.state.value.preferredTab == MediaKeyboardTab.GIF && vm.state.value.searchQuery.isEmpty() }
    emit("mk_state_004_tab_clears_query", "MediaKeyboardViewModel.onEvent(TabSelected)", before, keyboardState(vm.state.value), emptyList(), mapOf("queryEstablishedBy" to "MediaKeyboardViewModel.onEvent(SearchQueryChanged)", "searchActiveInput" to true))
  }

  run {
    val completion = CompletableDeferred<Result<GifPage, GifFetchError>>()
    val leaf = GifLeaf(completion)
    val vm = GifPageViewModel(leaf)
    waitUntil { leaf.calls.size == 1 && vm.state.value.isLoading }
    val before = gifState(vm.state.value)
    completion.complete(Result.failure(GifFetchError.Network))
    waitUntil { vm.state.value.loadFailed && !vm.state.value.isLoading }
    emit("mk_state_005_gif_initial_failure", "GifPageViewModel.init/onEvent(Initialize)", before, gifState(vm.state.value), leaf.calls.toList(), mapOf("repositoryFirstPage" to mapOf("result" to "network_failure")))
  }

  run {
    val leaf = GifLeaf()
    leaf.enqueue(Result.failure(GifFetchError.Network))
    val vm = GifPageViewModel(leaf)
    waitUntil { vm.state.value.loadFailed && !vm.state.value.isLoading }
    leaf.calls.clear()
    leaf.enqueue(Result.success(GifPage(listOf(gif("g1"), gif("g2")), true)))
    val before = gifState(vm.state.value)
    vm.onEvent(GifPageScreenEvents.RetryClicked)
    waitUntil { vm.state.value.gifs.map { it.id } == listOf("g1", "g2") && !vm.state.value.loadFailed }
    emit("mk_state_006_gif_retry_recovery", "GifPageViewModel.onEvent(RetryClicked)", before, gifState(vm.state.value), leaf.calls.toList(), mapOf("failedStateEstablishedBy" to "GifPageViewModel.init/onEvent(Initialize)", "repositoryFirstPage" to mapOf("result" to "success", "gifIds" to listOf("g1", "g2"), "hasMore" to true)))
  }

  run {
    val leaf = GifLeaf()
    leaf.enqueue(Result.success(GifPage(listOf(gif("g1"), gif("g2")), true)))
    val vm = GifPageViewModel(leaf)
    waitUntil { vm.state.value.gifs.map { it.id } == listOf("g1", "g2") && vm.state.value.hasMore }
    leaf.calls.clear()
    leaf.enqueue(Result.success(GifPage(listOf(gif("g3")), false)))
    val before = gifState(vm.state.value)
    vm.onEvent(GifPageScreenEvents.LoadMoreRequested)
    waitUntil { vm.state.value.gifs.map { it.id } == listOf("g1", "g2", "g3") && !vm.state.value.isLoadingMore }
    emit("mk_state_007_gif_pagination", "GifPageViewModel.onEvent(LoadMoreRequested)", before, gifState(vm.state.value), leaf.calls.toList(), mapOf("firstPageEstablishedBy" to "GifPageViewModel.init/onEvent(Initialize)", "repositoryNextPage" to mapOf("result" to "success", "gifIds" to listOf("g3"), "hasMore" to false)))
  }

  val sticker = KeyboardSticker("pack-1", "key-1", 7, null, "fixture-image")

  run {
    val leaf = ConfirmationLeaf()
    val controller = leaf.controller()
    val before = confirmationState(controller)
    controller.show(sticker, null)
    emit("mk_state_008_sticker_tap_defers_send", "ChatStickerConfirmationController.show", before, confirmationState(controller), leaf.calls.toList(), mapOf("sticker" to mapOf("packId" to sticker.packId, "packKey" to sticker.packKey, "stickerId" to sticker.stickerId), "confirmation" to null))
  }

  run {
    val leaf = ConfirmationLeaf()
    val controller = leaf.controller()
    controller.show(sticker, null)
    leaf.calls.clear()
    val before = confirmationState(controller)
    controller.dismiss()
    emit("mk_state_009_confirmation_cancel", "ChatStickerConfirmationController.dismiss", before, confirmationState(controller), leaf.calls.toList(), mapOf("confirmationEstablishedBy" to "ChatStickerConfirmationController.show"))
  }

  run {
    val leaf = ConfirmationLeaf()
    val controller = leaf.controller()
    controller.show(sticker, null)
    leaf.calls.clear()
    val before = confirmationState(controller)
    controller.send()
    emit("mk_state_010_confirmation_send_once", "ChatStickerConfirmationController.send", before, confirmationState(controller), leaf.calls.toList(), mapOf("confirmationEstablishedBy" to "ChatStickerConfirmationController.show"))
  }
}
