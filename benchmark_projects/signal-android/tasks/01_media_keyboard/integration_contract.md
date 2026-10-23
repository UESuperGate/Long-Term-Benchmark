# Production integration contract

This document defines the stable production integration surface required for this task to build and be testable. It is not an evaluator API. Implement these declarations in production source files; do not add production dependencies on `benchmark.evaluator`, `RuntimeObserver`, benchmark log formats, or generated evaluator sources.

The contract intentionally omits all evaluator-owned fixtures, observations, verdict data, and evaluator-only entrypoints.

## Stable production source paths

Android production sources:

- `core/ui/src/main/java/org/signal/core/ui/compose/EventDrivenViewModel.kt`
- `core/util/src/main/java/org/signal/core/util/Result.kt`
- `feature/media-keyboard/src/main/java/org/signal/mediakeyboard/MediaKeyboardTab.kt`
- `feature/media-keyboard/src/main/java/org/signal/mediakeyboard/MediaKeyboardAction.kt`
- `feature/media-keyboard/src/main/java/org/signal/mediakeyboard/MediaKeyboardState.kt`
- `feature/media-keyboard/src/main/java/org/signal/mediakeyboard/MediaKeyboardScreenEvents.kt`
- `feature/media-keyboard/src/main/java/org/signal/mediakeyboard/MediaKeyboardViewModel.kt`
- `feature/media-keyboard/src/main/java/org/signal/mediakeyboard/data/EmojiKeyboardRepository.kt`
- `feature/media-keyboard/src/main/java/org/signal/mediakeyboard/data/GifKeyboardRepository.kt`
- `feature/media-keyboard/src/main/java/org/signal/mediakeyboard/data/MediaKeyboardRepository.kt`
- `feature/media-keyboard/src/main/java/org/signal/mediakeyboard/data/StickerKeyboardRepository.kt`
- `feature/media-keyboard/src/main/java/org/signal/mediakeyboard/screens/MediaKeyboardPageViewModel.kt`
- `feature/media-keyboard/src/main/java/org/signal/mediakeyboard/screens/gif/GifPageScreenEvents.kt`
- `feature/media-keyboard/src/main/java/org/signal/mediakeyboard/screens/gif/GifPageState.kt`
- `feature/media-keyboard/src/main/java/org/signal/mediakeyboard/screens/gif/GifPageViewModel.kt`
- `feature/media-keyboard/src/main/java/org/signal/mediakeyboard/screens/gif/GifQuickSearchOption.kt`
- `app/src/main/java/org/thoughtcrime/securesms/conversation/v2/ChatStickerConfirmationController.kt`

ArkTS production source:

- `entry/src/main/ets/feature/MediaKeyboardStore.ts`

## Android production API

### Shared support types

Package `org.signal.core.ui.compose`:

```kotlin
abstract class EventDrivenViewModel<E : Any>(
  tag: String,
  shouldLogEvents: Boolean = false
) : ViewModel() {
  fun onEvent(event: E): Unit
  protected abstract suspend fun processEvent(event: E): Unit
}
```

Package `org.signal.core.util`:

```kotlin
sealed class Result<out S, out F> {
  data class Failure<out F>(val failure: F) : Result<Nothing, F>
  data class Success<out S>(val success: S) : Result<S, Nothing>

  companion object {
    fun <S> success(value: S): Result<S, Nothing>
    fun <F> failure(value: F): Result<Nothing, F>
  }
}
```

### Keyboard state and events

Package `org.signal.mediakeyboard`:

```kotlin
enum class MediaKeyboardTab { EMOJI, STICKER, GIF }

sealed interface MediaKeyboardAction {
  data class EmojiSelected(val emoji: String) : MediaKeyboardAction
  data object Backspace : MediaKeyboardAction
  data class StickerSelected(val sticker: KeyboardSticker) : MediaKeyboardAction
  data class StickerSendClicked(val sticker: KeyboardSticker) : MediaKeyboardAction
  data class GifSelected(val gif: KeyboardGif) : MediaKeyboardAction
  data class TabSelected(val tab: MediaKeyboardTab) : MediaKeyboardAction
  data object StickerManagementClicked : MediaKeyboardAction
  data object StickerSearchClicked : MediaKeyboardAction
  data object GifSearchClicked : MediaKeyboardAction
  data class ViewStickerPackClicked(val packId: String, val packKey: String) : MediaKeyboardAction
  data class SendStickerPackClicked(val packId: String, val packKey: String) : MediaKeyboardAction
  data class RemoveStickerPackConfirmed(val packId: String, val packKey: String) : MediaKeyboardAction
}

data class MediaKeyboardState(
  val offeredTabs: List<MediaKeyboardTab>,
  val restrictedTo: Set<MediaKeyboardTab>?,
  val preferredTab: MediaKeyboardTab,
  val searchActive: Boolean,
  val searchQuery: String,
  val initialized: Boolean
) {
  val availableTabs: List<MediaKeyboardTab>
  val selectedTab: MediaKeyboardTab
}

sealed interface MediaKeyboardScreenEvents {
  data object Initialize : MediaKeyboardScreenEvents
  data class TabSelected(val tab: MediaKeyboardTab) : MediaKeyboardScreenEvents
  data class SearchQueryChanged(val query: String) : MediaKeyboardScreenEvents
}

class MediaKeyboardViewModel(
  repository: MediaKeyboardRepository,
  isEnteringText: StateFlow<Boolean>,
  initialTab: MediaKeyboardTab? = null
) : EventDrivenViewModel<MediaKeyboardScreenEvents> {
  val state: StateFlow<MediaKeyboardState>
  fun restrictTabs(tabs: Set<MediaKeyboardTab>?): Unit
  suspend fun applyEvent(
    state: MediaKeyboardState,
    event: MediaKeyboardScreenEvents,
    stateEmitter: (MediaKeyboardState) -> Unit
  ): Unit
}
```

The `MediaKeyboardState` constructor parameters retain their production defaults so `MediaKeyboardState()` remains valid.

### Repository and media model types

Package `org.signal.mediakeyboard.data`:

```kotlin
interface MediaKeyboardRepository {
  val emoji: EmojiKeyboardRepository
  val stickers: StickerKeyboardRepository
  val gifs: GifKeyboardRepository
  suspend fun getAvailableTabs(): Set<MediaKeyboardTab>
}

interface EmojiKeyboardRepository {
  suspend fun getEmojiPages(): List<EmojiCategoryPage>
  suspend fun getRecentEmoji(): List<KeyboardEmoji>
  suspend fun search(query: String): List<KeyboardEmoji>
  suspend fun getPreferredVariations(): Map<String, String>
  fun setPreferredVariation(canonical: String, variation: String): Unit
  suspend fun onEmojiUsed(emoji: String): Unit
  fun getEmojiDrawable(emoji: String): Drawable?
}

data class KeyboardEmoji(
  val canonical: String,
  val variations: List<String>
) {
  val hasVariations: Boolean
}

data class EmojiCategoryPage(
  val category: EmojiKeyboardCategory,
  val emoji: List<KeyboardEmoji>
)

enum class EmojiKeyboardCategory

interface GifKeyboardRepository {
  suspend fun getGifs(
    query: String,
    offset: Int,
    limit: Int
  ): Result<GifPage, GifFetchError>
}

data class GifPage(
  val gifs: List<KeyboardGif>,
  val hasMore: Boolean
)

sealed interface GifFetchError {
  data object Network : GifFetchError
  data class Unknown(val cause: Throwable? = null) : GifFetchError
}

data class KeyboardGif(
  val id: String,
  val still: Any?,
  val mp4PreviewUri: Uri?,
  val width: Int,
  val height: Int
) {
  val aspectRatio: Float
}

interface StickerKeyboardRepository {
  val allowStickerAnimation: Boolean
  fun observeStickerPacks(): Flow<List<KeyboardStickerPack>>
  fun onStickerUsed(sticker: KeyboardSticker): Unit
  fun clearRecentStickers(): Unit
}

data class KeyboardSticker(
  val packId: String,
  val packKey: String,
  val stickerId: Long,
  val emoji: String?,
  val image: Any
)

data class KeyboardStickerPack(
  val id: String,
  val packKey: String?,
  val title: String?,
  val cover: Any?,
  val stickers: List<KeyboardSticker>
)
```

Production default implementations on repository members remain part of the source API where present.

### GIF page API

Package `org.signal.mediakeyboard.screens`:

```kotlin
abstract class MediaKeyboardPageViewModel<E : Any>(
  tag: String,
  shouldLogEvents: Boolean = false
) : EventDrivenViewModel<E> {
  val actions: Flow<MediaKeyboardAction>
  protected fun emitAction(action: MediaKeyboardAction): Unit
}
```

Package `org.signal.mediakeyboard.screens.gif`:

```kotlin
enum class GifQuickSearchOption(val query: String, @field:StringRes val label: Int)

data class GifPageState(
  val selectedQuickSearch: GifQuickSearchOption,
  val gifs: List<KeyboardGif>,
  val isLoading: Boolean,
  val isLoadingMore: Boolean,
  val hasMore: Boolean,
  val loadFailed: Boolean
)

sealed interface GifPageScreenEvents {
  data object Initialize : GifPageScreenEvents
  data class QuickSearchSelected(val option: GifQuickSearchOption) : GifPageScreenEvents
  data object LoadMoreRequested : GifPageScreenEvents
  data object RetryClicked : GifPageScreenEvents
  data class GifClicked(val gif: KeyboardGif) : GifPageScreenEvents
  data object SearchClicked : GifPageScreenEvents
}

class GifPageViewModel(
  repository: GifKeyboardRepository
) : MediaKeyboardPageViewModel<GifPageScreenEvents> {
  val state: StateFlow<GifPageState>
  suspend fun applyEvent(
    state: GifPageState,
    event: GifPageScreenEvents,
    stateEmitter: (GifPageState) -> Unit
  ): Unit
}
```

The `GifPageState` constructor parameters retain their production defaults so `GifPageState()` remains valid.

### Conversation sticker confirmation API

Package `org.thoughtcrime.securesms.conversation.v2`:

```kotlin
class ChatStickerConfirmationController(
  onSend: (KeyboardSticker) -> Unit,
  onShowingChanged: (Boolean) -> Unit
) {
  var confirmation: StickerConfirmation?
    private set
  var sendColor: Color
  val isShowing: Boolean

  fun show(sticker: KeyboardSticker, replyTo: String?): Unit
  fun dismiss(): Unit
  fun send(): Unit
}

data class StickerConfirmation(
  val sticker: KeyboardSticker,
  val replyTo: String?
)
```

## ArkTS production store API

Module `entry/src/main/ets/feature/MediaKeyboardStore.ts` exports the following production declarations:

```typescript
export interface GifPageResult {
  failed: boolean;
  ids: string[];
  hasMore: boolean;
}

export interface KeyboardSticker {
  packId: string;
  packKey: string;
  stickerId: number;
}

export interface ConversationEffects {
  visibility(value: boolean): void;
  onSend(sticker: KeyboardSticker): void;
}

export interface MediaKeyboardState {
  initialized: boolean;
  availableTabs: string[];
  selectedTab: string;
  preferredTab: string;
  searchActive: boolean;
  searchQuery: string;
}

export interface GifState {
  gifs: string[];
  isLoading: boolean;
  isLoadingMore: boolean;
  hasMore: boolean;
  loadFailed: boolean;
}

export class MediaKeyboardStore {
  offeredTabs: string[];
  preferredTab: string;
  restrictedTo: string[] | null;
  initialized: boolean;
  searchActive: boolean;
  searchQuery: string;

  constructor(getAvailableTabs: () => string[]);
  initialize(): void;
  seed(tabs: string[], preferred: string, restricted: string[] | null, active: boolean, query: string): void;
  restrictTabs(tabs: string[] | null): void;
  selectTab(tab: string): void;
  keyboardState(): MediaKeyboardState;
}

export class GifStore {
  gifs: string[];
  isLoading: boolean;
  isLoadingMore: boolean;
  hasMore: boolean;
  loadFailed: boolean;

  constructor(getGifs: (query: string, offset: number, limit: number) => GifPageResult);
  seed(ids: string[], more: boolean, failed: boolean): void;
  loadFirstPage(): void;
  retry(): void;
  loadMore(): void;
  state(): GifState;
}

export class ConversationMediaStore {
  pending: KeyboardSticker | null;

  constructor(effects: ConversationEffects);
  seed(sticker: KeyboardSticker): void;
  tapSticker(sticker: KeyboardSticker): void;
  cancelConfirmation(): void;
  confirmSend(): void;
  confirmation(): KeyboardSticker | null;
}
```

These ArkTS declarations must remain in the production feature module imported by the ArkUI page. `runMediaSemanticObserver`, observer logging, and any benchmark transport symbols are outside this contract.
