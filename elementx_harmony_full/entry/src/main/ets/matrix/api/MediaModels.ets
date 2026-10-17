import { DomainError } from '../../core/DomainResult';

export const MEDIA_CONTRACT_VERSION: string = '1';

export enum MediaKind {
  Image = 'image',
  Video = 'video',
  Audio = 'audio',
  Voice = 'voice',
  File = 'file'
}

export interface EncryptedMediaMetadata {
  algorithm: string;
  metadataReference: string;
  sha256: string;
  version: string;
}

export interface MatrixMediaSource {
  contentUri: string;
  thumbnailUri: string | null;
  encrypted: EncryptedMediaMetadata | null;
}

export interface MediaItem {
  mediaId: string;
  eventId: string | null;
  roomId: string;
  senderId: string;
  timestampMs: number;
  kind: MediaKind;
  fileName: string;
  mimeType: string;
  sizeBytes: number | null;
  width: number | null;
  height: number | null;
  durationMs: number | null;
  source: MatrixMediaSource;
  caption: string | null;
  redacted: boolean;
  shareAllowed: boolean;
}

export enum MediaTransferDirection {
  Thumbnail = 'thumbnail',
  Download = 'download',
  Upload = 'upload'
}

export enum MediaTransferState {
  Idle = 'idle',
  Queued = 'queued',
  Running = 'running',
  Completed = 'completed',
  Failed = 'failed',
  Cancelled = 'cancelled'
}

export interface MediaTransferSnapshot {
  operationId: string;
  mediaId: string;
  direction: MediaTransferDirection;
  state: MediaTransferState;
  transferredBytes: number;
  totalBytes: number | null;
  progress: number | null;
  cacheEntryId: string | null;
  uploadedContentUri: string | null;
  encryptedMetadataReference: string | null;
  error: DomainError | null;
}

export interface MediaProgressUpdate {
  operationId: string;
  transferredBytes: number;
  totalBytes: number | null;
}

export interface CachedMedia {
  cacheEntryId: string;
  validatedMimeType: string;
  sizeBytes: number;
}

export interface UploadedMedia {
  contentUri: string;
  encryptedMetadataReference: string | null;
}

export enum GalleryPhase {
  Loading = 'loading',
  Ready = 'ready',
  Empty = 'empty',
  Offline = 'offline',
  Error = 'error'
}

export enum GalleryMode {
  Images = 'images',
  Files = 'files',
  All = 'all'
}

export interface GallerySnapshot {
  roomId: string;
  phase: GalleryPhase;
  mode: GalleryMode;
  items: MediaItem[];
  selectedMediaId: string | null;
  selectedIndex: number;
  canMovePrevious: boolean;
  canMoveNext: boolean;
  shareableMediaIds: string[];
  omittedInvalidCount: number;
  error: DomainError | null;
}

export interface GalleryPage {
  items: MediaItem[];
  hasMore: boolean;
}
