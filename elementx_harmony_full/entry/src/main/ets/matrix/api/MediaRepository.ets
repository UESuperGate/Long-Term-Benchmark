import { DomainResult } from '../../core/DomainResult';
import {
  CachedMedia,
  GalleryPage,
  MediaItem,
  MediaProgressUpdate,
  UploadedMedia
} from './MediaModels';

export interface ThumbnailRequest {
  operationId: string;
  media: MediaItem;
  requestedWidth: number;
  requestedHeight: number;
}

export interface DownloadRequest {
  operationId: string;
  media: MediaItem;
}

export interface UploadRequest {
  operationId: string;
  roomId: string;
  sourceHandle: string;
  fileName: string;
  mimeType: string;
  encrypt: boolean;
}

export interface MediaProgressObserver {
  onProgress(update: MediaProgressUpdate): void;
}

/** Platform/Rust boundary. Handles resolve to protected storage and never expose file paths or keys. */
export interface MediaRepositoryDataSource {
  loadThumbnail(request: ThumbnailRequest, observer: MediaProgressObserver): Promise<DomainResult<CachedMedia>>;
  download(request: DownloadRequest, observer: MediaProgressObserver): Promise<DomainResult<CachedMedia>>;
  upload(request: UploadRequest, observer: MediaProgressObserver): Promise<DomainResult<UploadedMedia>>;
  cancel(operationId: string): Promise<DomainResult<boolean>>;
  evict(cacheEntryId: string): Promise<DomainResult<boolean>>;
}

/** Rust timeline boundary used to aggregate real room media. */
export interface MediaGalleryDataSource {
  load(roomId: string): Promise<DomainResult<GalleryPage>>;
  loadMore(roomId: string): Promise<DomainResult<GalleryPage>>;
}
