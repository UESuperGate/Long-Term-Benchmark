import {
  DomainError,
  DomainErrorCode,
  DomainFailure,
  DomainResult,
  unexpectedFailure
} from '../core/DomainResult';
import {
  CachedMedia,
  MediaProgressUpdate,
  MediaTransferDirection,
  MediaTransferSnapshot,
  MediaTransferState,
  UploadedMedia
} from '../matrix/api/MediaModels';
import {
  DownloadRequest,
  MediaProgressObserver,
  MediaRepositoryDataSource,
  ThumbnailRequest,
  UploadRequest
} from '../matrix/api/MediaRepository';

class ControllerProgressObserver implements MediaProgressObserver {
  private readonly update: (progress: MediaProgressUpdate) => void;

  constructor(update: (progress: MediaProgressUpdate) => void) {
    this.update = update;
  }

  onProgress(progress: MediaProgressUpdate): void {
    this.update(progress);
  }
}

function progressValue(transferred: number, total: number | null): number | null {
  if (total === null || total <= 0) {
    return null;
  }
  return Math.max(0, Math.min(1, transferred / total));
}

export class MediaRepositoryController {
  private readonly source: MediaRepositoryDataSource;
  private readonly operations: Map<string, MediaTransferSnapshot> = new Map<string, MediaTransferSnapshot>();
  private readonly generations: Map<string, number> = new Map<string, number>();
  private readonly thumbnails: Map<string, ThumbnailRequest> = new Map<string, ThumbnailRequest>();
  private readonly downloads: Map<string, DownloadRequest> = new Map<string, DownloadRequest>();
  private readonly uploads: Map<string, UploadRequest> = new Map<string, UploadRequest>();

  constructor(source: MediaRepositoryDataSource) {
    this.source = source;
  }

  getOperations(): MediaTransferSnapshot[] {
    const values: MediaTransferSnapshot[] = [];
    this.operations.forEach((operation: MediaTransferSnapshot) => values.push(this.copy(operation)));
    return values.sort((left: MediaTransferSnapshot, right: MediaTransferSnapshot) =>
      left.operationId.localeCompare(right.operationId));
  }

  getOperation(operationId: string): MediaTransferSnapshot | null {
    const operation = this.operations.get(operationId);
    return operation === undefined ? null : this.copy(operation);
  }

  async loadThumbnail(request: ThumbnailRequest): Promise<DomainResult<MediaTransferSnapshot>> {
    const validation = this.validateOperation(request.operationId, request.media.mediaId);
    if (validation !== null) {
      return DomainResult.fail<MediaTransferSnapshot>(validation);
    }
    if (request.requestedWidth <= 0 || request.requestedHeight <= 0) {
      return DomainResult.fail<MediaTransferSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Thumbnail dimensions must be positive',
        true
      ));
    }
    this.thumbnails.set(request.operationId, request);
    this.begin(request.operationId, request.media.mediaId, MediaTransferDirection.Thumbnail);
    const generation = this.generation(request.operationId);
    return this.completeCached(
      request.operationId,
      generation,
      await this.source.loadThumbnail(request, this.progressObserver(request.operationId, generation))
    );
  }

  async download(request: DownloadRequest): Promise<DomainResult<MediaTransferSnapshot>> {
    const validation = this.validateOperation(request.operationId, request.media.mediaId);
    if (validation !== null) {
      return DomainResult.fail<MediaTransferSnapshot>(validation);
    }
    this.downloads.set(request.operationId, request);
    this.begin(request.operationId, request.media.mediaId, MediaTransferDirection.Download);
    const generation = this.generation(request.operationId);
    return this.completeCached(
      request.operationId,
      generation,
      await this.source.download(request, this.progressObserver(request.operationId, generation))
    );
  }

  async upload(request: UploadRequest): Promise<DomainResult<MediaTransferSnapshot>> {
    const validation = this.validateOperation(request.operationId, request.operationId);
    if (validation !== null) {
      return DomainResult.fail<MediaTransferSnapshot>(validation);
    }
    if (request.sourceHandle.length === 0 || request.roomId.length === 0 || request.fileName.length === 0) {
      return DomainResult.fail<MediaTransferSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Upload source, room, and file name are required',
        true
      ));
    }
    this.uploads.set(request.operationId, request);
    this.begin(request.operationId, request.operationId, MediaTransferDirection.Upload);
    const generation = this.generation(request.operationId);
    return this.completeUpload(
      request.operationId,
      generation,
      await this.source.upload(request, this.progressObserver(request.operationId, generation))
    );
  }

  receiveProgress(update: MediaProgressUpdate): DomainResult<MediaTransferSnapshot> {
    const operation = this.operations.get(update.operationId);
    if (operation === undefined || operation.state !== MediaTransferState.Running) {
      return DomainResult.fail<MediaTransferSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Progress does not belong to an active media operation',
        false
      ));
    }
    if (update.transferredBytes < operation.transferredBytes ||
      (update.totalBytes !== null && update.transferredBytes > update.totalBytes)) {
      return DomainResult.fail<MediaTransferSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Media progress is not monotonic',
        false
      ));
    }
    operation.transferredBytes = update.transferredBytes;
    operation.totalBytes = update.totalBytes;
    operation.progress = progressValue(update.transferredBytes, update.totalBytes);
    return DomainResult.succeed<MediaTransferSnapshot>(this.copy(operation));
  }

  async cancel(operationId: string): Promise<DomainResult<MediaTransferSnapshot>> {
    const operation = this.operations.get(operationId);
    if (operation === undefined) {
      return this.missing(operationId);
    }
    if (operation.state !== MediaTransferState.Running && operation.state !== MediaTransferState.Queued) {
      return DomainResult.succeed<MediaTransferSnapshot>(this.copy(operation));
    }
    this.generations.set(operationId, this.generation(operationId) + 1);
    const result = await this.source.cancel(operationId);
    if (!result.success) {
      return this.failOperation(operationId, result.error, 'media cancel');
    }
    operation.state = MediaTransferState.Cancelled;
    operation.error = null;
    return DomainResult.succeed<MediaTransferSnapshot>(this.copy(operation));
  }

  async retry(operationId: string): Promise<DomainResult<MediaTransferSnapshot>> {
    const operation = this.operations.get(operationId);
    if (operation === undefined) {
      return this.missing(operationId);
    }
    if (operation.state !== MediaTransferState.Failed && operation.state !== MediaTransferState.Cancelled) {
      return DomainResult.fail<MediaTransferSnapshot>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Only failed or cancelled media operations can retry',
        true
      ));
    }
    operation.state = MediaTransferState.Running;
    operation.transferredBytes = 0;
    operation.totalBytes = null;
    operation.progress = null;
    operation.error = null;
    const generation = this.generation(operationId) + 1;
    this.generations.set(operationId, generation);
    if (operation.direction === MediaTransferDirection.Thumbnail) {
      const request = this.thumbnails.get(operationId);
      if (request !== undefined) {
        return this.completeCached(
          operationId,
          generation,
          await this.source.loadThumbnail(request, this.progressObserver(operationId, generation))
        );
      }
    } else if (operation.direction === MediaTransferDirection.Download) {
      const request = this.downloads.get(operationId);
      if (request !== undefined) {
        return this.completeCached(
          operationId,
          generation,
          await this.source.download(request, this.progressObserver(operationId, generation))
        );
      }
    } else {
      const request = this.uploads.get(operationId);
      if (request !== undefined) {
        return this.completeUpload(
          operationId,
          generation,
          await this.source.upload(request, this.progressObserver(operationId, generation))
        );
      }
    }
    return this.failOperation(operationId, new DomainFailure(
      DomainErrorCode.InvalidInput,
      'Media retry request is unavailable',
      false
    ), 'media retry');
  }

  async evict(operationId: string): Promise<DomainResult<boolean>> {
    const operation = this.operations.get(operationId);
    if (operation === undefined || operation.cacheEntryId === null) {
      return DomainResult.fail<boolean>(new DomainFailure(
        DomainErrorCode.InvalidInput,
        'Completed cached media is required',
        true
      ));
    }
    const result = await this.source.evict(operation.cacheEntryId);
    if (result.success) {
      operation.cacheEntryId = null;
    }
    return result;
  }

  private validateOperation(operationId: string, mediaId: string): DomainFailure | null {
    if (operationId.length === 0 || mediaId.length === 0) {
      return new DomainFailure(DomainErrorCode.InvalidInput, 'Media operation and media IDs are required', true);
    }
    if (this.operations.has(operationId)) {
      return new DomainFailure(DomainErrorCode.InvalidInput, 'Media operation ID already exists', true);
    }
    return null;
  }

  private begin(operationId: string, mediaId: string, direction: MediaTransferDirection): void {
    this.operations.set(operationId, {
      operationId: operationId,
      mediaId: mediaId,
      direction: direction,
      state: MediaTransferState.Running,
      transferredBytes: 0,
      totalBytes: null,
      progress: null,
      cacheEntryId: null,
      uploadedContentUri: null,
      encryptedMetadataReference: null,
      error: null
    });
    this.generations.set(operationId, 1);
  }

  private progressObserver(operationId: string, generation: number): MediaProgressObserver {
    return new ControllerProgressObserver((progress: MediaProgressUpdate) => {
      if (progress.operationId === operationId && this.generation(operationId) === generation) {
        this.receiveProgress(progress);
      }
    });
  }

  private completeCached(
    operationId: string,
    generation: number,
    result: DomainResult<CachedMedia>
  ): DomainResult<MediaTransferSnapshot> {
    if (this.generation(operationId) !== generation) {
      return this.stale(operationId);
    }
    if (!result.success || result.value === null) {
      return this.failOperation(operationId, result.error, 'media download');
    }
    const operation = this.operations.get(operationId);
    if (operation === undefined) {
      return this.missing(operationId);
    }
    if (operation.state === MediaTransferState.Cancelled) {
      return DomainResult.succeed<MediaTransferSnapshot>(this.copy(operation));
    }
    operation.state = MediaTransferState.Completed;
    operation.transferredBytes = result.value.sizeBytes;
    operation.totalBytes = result.value.sizeBytes;
    operation.progress = 1;
    operation.cacheEntryId = result.value.cacheEntryId;
    operation.error = null;
    return DomainResult.succeed<MediaTransferSnapshot>(this.copy(operation));
  }

  private completeUpload(
    operationId: string,
    generation: number,
    result: DomainResult<UploadedMedia>
  ): DomainResult<MediaTransferSnapshot> {
    if (this.generation(operationId) !== generation) {
      return this.stale(operationId);
    }
    if (!result.success || result.value === null) {
      return this.failOperation(operationId, result.error, 'media upload');
    }
    const operation = this.operations.get(operationId);
    if (operation === undefined) {
      return this.missing(operationId);
    }
    if (operation.state === MediaTransferState.Cancelled) {
      return DomainResult.succeed<MediaTransferSnapshot>(this.copy(operation));
    }
    operation.state = MediaTransferState.Completed;
    operation.progress = 1;
    operation.uploadedContentUri = result.value.contentUri;
    operation.encryptedMetadataReference = result.value.encryptedMetadataReference;
    operation.error = null;
    return DomainResult.succeed<MediaTransferSnapshot>(this.copy(operation));
  }

  private failOperation(
    operationId: string,
    error: DomainError | null,
    operationName: string
  ): DomainResult<MediaTransferSnapshot> {
    const failure = error === null ? unexpectedFailure(operationName) : error;
    const operation = this.operations.get(operationId);
    if (operation !== undefined && operation.state !== MediaTransferState.Cancelled) {
      operation.state = failure.code === DomainErrorCode.Cancelled ?
        MediaTransferState.Cancelled : MediaTransferState.Failed;
      operation.error = failure;
    }
    return DomainResult.fail<MediaTransferSnapshot>(failure);
  }

  private missing(operationId: string): DomainResult<MediaTransferSnapshot> {
    return DomainResult.fail<MediaTransferSnapshot>(new DomainFailure(
      DomainErrorCode.InvalidInput,
      `Unknown media operation ${operationId}`,
      false
    ));
  }

  private generation(operationId: string): number {
    const generation = this.generations.get(operationId);
    return generation === undefined ? 0 : generation;
  }

  private stale(operationId: string): DomainResult<MediaTransferSnapshot> {
    return DomainResult.fail<MediaTransferSnapshot>(new DomainFailure(
      DomainErrorCode.Cancelled,
      `Stale media operation result ignored for ${operationId}`,
      false
    ));
  }

  private copy(operation: MediaTransferSnapshot): MediaTransferSnapshot {
    return {
      operationId: operation.operationId,
      mediaId: operation.mediaId,
      direction: operation.direction,
      state: operation.state,
      transferredBytes: operation.transferredBytes,
      totalBytes: operation.totalBytes,
      progress: operation.progress,
      cacheEntryId: operation.cacheEntryId,
      uploadedContentUri: operation.uploadedContentUri,
      encryptedMetadataReference: operation.encryptedMetadataReference,
      error: operation.error
    };
  }
}
