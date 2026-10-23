# Production integration contract

This document defines the stable production integration surface required for this task to build and be testable. It is not an evaluator API. Implement these declarations in production source files; do not add production dependencies on `benchmark.evaluator`, `RuntimeObserver`, benchmark log formats, or generated evaluator sources.

The contract intentionally omits all evaluator-owned fixtures, observations, verdict data, and evaluator-only entrypoints.

## Stable production source paths

Android production sources:

- `core-util/src/main/java/org/signal/core/util/CollectionsExtensions.kt`
- `app/src/main/java/org/thoughtcrime/securesms/database/model/StickerPackRecord.kt`
- `app/src/main/java/org/thoughtcrime/securesms/database/model/StickerRecord.kt`
- `app/src/main/java/org/thoughtcrime/securesms/stickers/BlessedPacks.java`
- `app/src/main/java/org/thoughtcrime/securesms/stickers/StickerManagementRepository.kt`
- `app/src/main/java/org/thoughtcrime/securesms/stickers/StickerManagementViewModel.kt`

ArkTS production source:

- `entry/src/main/ets/feature/StickerManagementStore.ts`

## Android production API

### Shared collection support

Package `org.signal.core.util`:

```kotlin
fun <E> List<E>.swap(i: Int, j: Int): List<E>
```

### Sticker record types

Package `org.thoughtcrime.securesms.database.model`:

```kotlin
data class StickerRecord(
  @JvmField val rowId: Long,
  @JvmField val packId: String,
  @JvmField val packKey: String,
  @JvmField val stickerId: Int,
  @JvmField val emoji: String,
  @JvmField val contentType: String,
  @JvmField val size: Long,
  @JvmField val isCover: Boolean
) {
  @JvmField val uri: Uri
}

data class StickerPackRecord(
  @JvmField val packId: String,
  @JvmField val packKey: String,
  @JvmField val title: String,
  @JvmField val author: String,
  @JvmField val cover: StickerRecord,
  @JvmField val isInstalled: Boolean
) {
  @JvmField val titleOptional: Optional<String>
  @JvmField val authorOptional: Optional<String>
}

@JvmInline
value class StickerPackId(val value: String)

@JvmInline
value class StickerPackKey(val value: String)
```

### Official-pack lookup

Package `org.thoughtcrime.securesms.stickers`:

```java
public final class BlessedPacks {
  public static boolean contains(@NonNull String packId);

  public static class Pack {
    public Pack(@NonNull String packId, @NonNull String packKey);
    public @NonNull String getPackId();
    public @NonNull String getPackKey();
    public @NonNull String toJson();
    public static @NonNull Pack fromJson(@NonNull String json);
  }
}
```

Existing production pack constants remain part of `BlessedPacks`; their data values are deliberately not reproduced here.

### Repository API

Package `org.thoughtcrime.securesms.stickers`:

```kotlin
object StickerManagementRepository {
  fun getStickerPacks(): Flow<StickerPacksResult>
  suspend fun deleteOrphanedStickerPacks(): Unit
  fun fetchUnretrievedReferencePacks(): Unit
  fun installStickerPackAsync(packId: String, packKey: String, notify: Boolean): Unit
  suspend fun installStickerPack(
    packId: StickerPackId,
    packKey: StickerPackKey,
    notify: Boolean
  ): Unit
  fun uninstallStickerPackAsync(packId: String, packKey: String): Unit
  suspend fun uninstallStickerPacks(
    packKeysById: Map<StickerPackId, StickerPackKey>
  ): Unit
  suspend fun setStickerPacksOrder(
    packsInOrder: List<StickerPackRecord>
  ): Unit

  interface Callback<T> {
    fun onComplete(result: T): Unit
  }
}

data class StickerPacksResult(
  val installedPacks: List<StickerPackRecord>,
  val availablePacks: List<StickerPackRecord>,
  val blessedPacks: List<StickerPackRecord>,
  val sortOrderByPackId: Map<StickerPackId, Int>
)
```

The repository above is application-owned production code. Its public methods must continue through the real production repository body; testability is provided by the existing leaf dependencies, not by replacing this object with an evaluator-only facade.

### View-model state, events, and entrypoints

Package `org.thoughtcrime.securesms.stickers`:

```kotlin
class StickerManagementViewModel() : ViewModel() {
  val uiState: StateFlow<StickerManagementUiState>

  fun onScreenVisible(): Unit
  fun installStickerPack(pack: AvailableStickerPack): Unit
  fun onUninstallStickerPacksRequested(packIds: Set<StickerPackId>): Unit
  fun onUninstallStickerPacksConfirmed(packIds: Set<StickerPackId>): Unit
  fun onUninstallStickerPacksCanceled(): Unit
  fun updatePosition(fromIndex: Int, toIndex: Int): Unit
  fun saveInstalledPacksSortOrder(): Unit
  fun toggleSelection(pack: InstalledStickerPack): Unit
  fun toggleSelectAll(): Unit
  fun setMultiSelectEnabled(isEnabled: Boolean): Unit
  fun onSnackbarDismiss(): Unit
}

data class StickerManagementUiState(
  val availableBlessedPacks: List<AvailableStickerPack>,
  val availableNotBlessedPacks: List<AvailableStickerPack>,
  val installedPacks: List<InstalledStickerPack>,
  val multiSelectEnabled: Boolean,
  val selectedPackIds: Set<StickerPackId>,
  val userPrompt: ConfirmRemoveStickerPacksPrompt?,
  val actionConfirmation: StickerManagementConfirmation?
)

data class ConfirmRemoveStickerPacksPrompt(
  val numItemsToDelete: Int
)

sealed interface StickerManagementConfirmation {
  data class InstalledPack(val packTitle: String) : StickerManagementConfirmation
  data class UninstalledPack(val packTitle: String) : StickerManagementConfirmation
  data class UninstalledPacks(val numPacksUninstalled: Int) : StickerManagementConfirmation
}

data class AvailableStickerPack(
  val record: StickerPackRecord,
  val isBlessed: Boolean,
  val downloadStatus: DownloadStatus
) {
  val id: StickerPackId
  val key: StickerPackKey

  sealed class DownloadStatus {
    data object NotDownloaded : DownloadStatus()
    data object InProgress : DownloadStatus()
    data object Downloaded : DownloadStatus()
  }
}

data class InstalledStickerPack(
  val record: StickerPackRecord,
  val isBlessed: Boolean,
  val sortOrder: Int
) {
  val id: StickerPackId
  val key: StickerPackKey
}
```

The `StickerManagementUiState` constructor parameters retain their production defaults so `StickerManagementUiState()` remains valid.

## ArkTS production store API

Module `entry/src/main/ets/feature/StickerManagementStore.ts` exports the following production declarations:

```typescript
export interface StickerPack {
  id: string;
  key: string;
  title: string;
  installed: boolean;
  official: boolean;
  order: number;
}

export interface StickerLeaf {
  enqueueDownload(id: string, key: string, notify: boolean): void;
  uninstall(ids: string[]): void;
  persistOrder(ids: string[]): void;
  markReferenceInstalled(id: string, notify: boolean): void;
  enqueueLinked(id: string, key: string, operation: string): void;
}

export interface StickerConfirmation {
  type: string;
  title?: string;
  count?: number;
}

export interface StickerManagementState {
  installedPackIds: string[];
  availableOfficialIds: string[];
  availableOtherIds: string[];
  selectedPackIds: string[];
  multiSelectEnabled: boolean;
  prompt: number | null;
  confirmation: StickerConfirmation | null;
}

export class StickerManagementRepository {
  constructor(leaf: StickerLeaf);
  install(pack: StickerPack, notify: boolean, linked: boolean, reference: boolean): void;
  uninstall(keys: Map<string, string>, linked: boolean): void;
  persistOrder(ids: string[]): void;
}

export class StickerManagementStore {
  installed: StickerPack[];
  official: StickerPack[];
  other: StickerPack[];
  selected: string[];
  statuses: Map<string, string>;
  effects: string[];
  orderedStates: string[];
  prompt: number | null;
  confirmation: StickerConfirmation | null;
  multiSelectEnabled: boolean;

  constructor(repository: StickerManagementRepository);
  onPacksUpdated(records: StickerPack[]): void;
  seedInstalled(packs: StickerPack[]): void;
  seedSelection(ids: string[], enabled: boolean, prompt: number | null): void;
  seedSettled(id: string): void;
  install(pack: StickerPack, linked: boolean, reference: boolean): void;
  installationLingerElapsed(id: string): void;
  move(from: number, to: number): void;
  saveOrder(): void;
  toggleSelection(id: string): void;
  setMultiSelectEnabled(enabled: boolean): void;
  toggleSelectAll(): void;
  requestUninstall(ids: string[]): void;
  cancelUninstall(): void;
  confirmUninstall(ids: string[], linked: boolean): void;
  state(): StickerManagementState;
}
```

These ArkTS declarations must remain in the production feature module imported by the ArkUI page. `runStickerSemanticObserver`, observer logging, and any benchmark transport symbols are outside this contract.
