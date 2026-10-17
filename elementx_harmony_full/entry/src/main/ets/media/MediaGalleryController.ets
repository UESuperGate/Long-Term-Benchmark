import {
  DomainError,
  DomainErrorCode,
  DomainFailure,
  DomainResult,
  unexpectedFailure
} from '../core/DomainResult';
import {
  GalleryMode,
  GalleryPage,
  GalleryPhase,
  GallerySnapshot,
  MediaItem,
  MediaKind
} from '../matrix/api/MediaModels';
import { MediaGalleryDataSource } from '../matrix/api/MediaRepository';

function modeMatches(item: MediaItem, mode: GalleryMode): boolean {
  if (mode === GalleryMode.All) {
    return true;
  }
  const visual = item.kind === MediaKind.Image || item.kind === MediaKind.Video;
  return mode === GalleryMode.Images ? visual : !visual;
}
function validItem(item: MediaItem): boolean {
  if (item.redacted || item.mediaId.length === 0 || item.roomId.length === 0 || item.source.contentUri.length === 0) {
    return false;
  }
  if (item.sizeBytes !== null && item.sizeBytes < 0) {
    return false;
  }
  if (item.source.encrypted !== null) {
    return item.source.encrypted.algorithm.length > 0 &&
      item.source.encrypted.metadataReference.length > 0 &&
      item.source.encrypted.sha256.length > 0;
  }
  return true;
}

export class MediaGalleryController {
  private readonly roomId: string;
  private readonly source: MediaGalleryDataSource;
  private allItems: MediaItem[] = [];
  private hasMore: boolean = false;
  private snapshot: GallerySnapshot;

  constructor(roomId: string, source: MediaGalleryDataSource, mode: GalleryMode = GalleryMode.All) {
    this.roomId = roomId;
    this.source = source;
    this.snapshot = {
      roomId: roomId,
      phase: GalleryPhase.Loading,
      mode: mode,
      items: [],
      selectedMediaId: null,
      selectedIndex: -1,
      canMovePrevious: false,
      canMoveNext: false,
      shareableMediaIds: [],
      omittedInvalidCount: 0,
      error: null
    };
  }

  getSnapshot(): GallerySnapshot {
    return {
      roomId: this.snapshot.roomId,
      phase: this.snapshot.phase,
      mode: this.snapshot.mode,
      items: this.snapshot.items.slice(),
      selectedMediaId: this.snapshot.selectedMediaId,
      selectedIndex: this.snapshot.selectedIndex,
      canMovePrevious: this.snapshot.canMovePrevious,
      canMoveNext: this.snapshot.canMoveNext,
      shareableMediaIds: this.snapshot.shareableMediaIds.slice(),
      omittedInvalidCount: this.snapshot.omittedInvalidCount,
      error: this.snapshot.error
    };
  }

  async start(initialMediaId: string | null = null): Promise<DomainResult<GallerySnapshot>> {
    this.snapshot.phase = GalleryPhase.Loading;
    this.snapshot.error = null;
    const result = await this.source.load(this.roomId);
    return this.applyPage(result, false, initialMediaId);
  }

  async loadMore(): Promise<DomainResult<GallerySnapshot>> {
    if (!this.hasMore) {
      return DomainResult.succeed<GallerySnapshot>(this.getSnapshot());
    }
    return this.applyPage(await this.source.loadMore(this.roomId), true, this.snapshot.selectedMediaId);
  }

  setMode(mode: GalleryMode): GallerySnapshot {
    this.snapshot.mode = mode;
    this.rebuild(this.snapshot.selectedMediaId);
    return this.getSnapshot();
  }

  select(mediaId: string): DomainResult<GallerySnapshot> {
    const index = this.snapshot.items.findIndex((item: MediaItem) => item.mediaId === mediaId);
    if (index < 0) {
      return DomainResult.fail<GallerySnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Selected media is not available in this gallery',
        true
      ));
    }
    this.setSelection(index);
    return DomainResult.succeed<GallerySnapshot>(this.getSnapshot());
  }

  movePrevious(): DomainResult<GallerySnapshot> {
    if (!this.snapshot.canMovePrevious) {
      return DomainResult.fail<GallerySnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'No previous media item',
        true
      ));
    }
    this.setSelection(this.snapshot.selectedIndex - 1);
    return DomainResult.succeed<GallerySnapshot>(this.getSnapshot());
  }

  moveNext(): DomainResult<GallerySnapshot> {
    if (!this.snapshot.canMoveNext) {
      return DomainResult.fail<GallerySnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'No next media item',
        true
      ));
    }
    this.setSelection(this.snapshot.selectedIndex + 1);
    return DomainResult.succeed<GallerySnapshot>(this.getSnapshot());
  }

  redact(eventId: string): GallerySnapshot {
    this.allItems = this.allItems.filter((item: MediaItem) => item.eventId !== eventId);
    this.rebuild(this.snapshot.selectedMediaId);
    return this.getSnapshot();
  }

  shareSelection(): string[] {
    const selected = this.snapshot.items[this.snapshot.selectedIndex];
    if (selected === undefined || !selected.shareAllowed) {
      return [];
    }
    return [selected.mediaId];
  }

  private applyPage(
    result: DomainResult<GalleryPage>,
    append: boolean,
    requestedSelection: string | null
  ): DomainResult<GallerySnapshot> {
    if (!result.success || result.value === null) {
      const error: DomainError = result.error === null ? unexpectedFailure('media gallery load') : result.error;
      this.snapshot.phase = error.code === DomainErrorCode.NetworkUnavailable ? GalleryPhase.Offline : GalleryPhase.Error;
      this.snapshot.error = error;
      return DomainResult.fail<GallerySnapshot>(error);
    }
    const merged = append ? this.allItems.slice() : [];
    result.value.items.forEach((item: MediaItem) => {
      const index = merged.findIndex((candidate: MediaItem) => candidate.mediaId === item.mediaId);
      if (index >= 0) {
        merged[index] = item;
      } else {
        merged.push(item);
      }
    });
    this.allItems = merged.sort((left: MediaItem, right: MediaItem) => {
      const timestamp = right.timestampMs - left.timestampMs;
      return timestamp === 0 ? left.mediaId.localeCompare(right.mediaId) : timestamp;
    });
    this.hasMore = result.value.hasMore;
    this.snapshot.error = null;
    this.rebuild(requestedSelection);
    return DomainResult.succeed<GallerySnapshot>(this.getSnapshot());
  }

  private rebuild(requestedSelection: string | null): void {
    let omitted = 0;
    const items: MediaItem[] = [];
    this.allItems.forEach((item: MediaItem) => {
      if (!validItem(item)) {
        omitted++;
      } else if (modeMatches(item, this.snapshot.mode)) {
        items.push(item);
      }
    });
    this.snapshot.items = items;
    this.snapshot.omittedInvalidCount = omitted;
    this.snapshot.shareableMediaIds = items
      .filter((item: MediaItem) => item.shareAllowed)
      .map((item: MediaItem) => item.mediaId);
    this.snapshot.phase = items.length === 0 ? GalleryPhase.Empty : GalleryPhase.Ready;
    let selectedIndex = requestedSelection === null ? -1 :
      items.findIndex((item: MediaItem) => item.mediaId === requestedSelection);
    if (selectedIndex < 0 && items.length > 0) {
      selectedIndex = 0;
    }
    this.setSelection(selectedIndex);
  }

  private setSelection(index: number): void {
    if (index < 0 || index >= this.snapshot.items.length) {
      this.snapshot.selectedIndex = -1;
      this.snapshot.selectedMediaId = null;
      this.snapshot.canMovePrevious = false;
      this.snapshot.canMoveNext = false;
      return;
    }
    this.snapshot.selectedIndex = index;
    this.snapshot.selectedMediaId = this.snapshot.items[index].mediaId;
    this.snapshot.canMovePrevious = index > 0;
    this.snapshot.canMoveNext = index < this.snapshot.items.length - 1;
  }
}
