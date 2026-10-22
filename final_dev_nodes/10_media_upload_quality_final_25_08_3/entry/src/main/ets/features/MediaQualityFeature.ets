export const DEFAULT_MAX_UPLOAD_SIZE: number = 100 * 1024 * 1024;
export const MEDIA_ESTIMATION_SAFETY_OVERHEAD: number = 1.1;

export enum MediaType {
  Image = 'image',
  Video = 'video',
  File = 'file'
}

export enum VideoPreset {
  High = 'high',
  Standard = 'standard',
  Low = 'low'
}

export enum MediaAsyncState {
  Idle = 'idle',
  Loading = 'loading',
  Success = 'success',
  Failure = 'failure',
  Uninitialized = 'uninitialized',
  ReadyToUpload = 'ready_to_upload',
  Done = 'done'
}

export class VideoUploadEstimation {
  preset: VideoPreset;
  sizeInBytes: number;
  canUpload: boolean;
  bitrateKbps: number;

  constructor(preset: VideoPreset, sizeInBytes: number, canUpload: boolean, bitrateKbps: number = 0) {
    this.preset = preset;
    this.sizeInBytes = sizeInBytes;
    this.canUpload = canUpload;
    this.bitrateKbps = bitrateKbps;
  }
}

export class VideoDimensions {
  width: number;
  height: number;

  constructor(width: number, height: number) {
    this.width = width;
    this.height = height;
  }
}

// Android v25.08.3 VideoCompressorHelper: retain Float arithmetic and integer kbps truncation.
export class VideoCompressorHelper {
  private maxSize: number;

  constructor(maxSize: number) {
    this.maxSize = maxSize;
  }

  getOutputSize(inputSize: VideoDimensions): VideoDimensions {
    const major = Math.max(inputSize.width, inputSize.height);
    const minor = Math.min(inputSize.width, inputSize.height);
    const resultMajor = Math.min(major, this.maxSize);
    const aspectRatio = Math.fround(Math.fround(major) / Math.fround(minor));
    return new VideoDimensions(resultMajor, Math.round(Math.fround(resultMajor / aspectRatio)));
  }

  calculateOptimalBitrate(inputSize: VideoDimensions, frameRate: number): number {
    const outputSize = this.getOutputSize(inputSize);
    const pixelsPerFrame = outputSize.width * outputSize.height;
    const bitsPerSecond = Math.fround(Math.fround(pixelsPerFrame * Math.fround(0.1)) * frameRate);
    return Math.trunc(Math.trunc(bitsPerSecond) / 1000);
  }
}

export class MediaPreferences {
  optimizeImages: boolean = true;
  videoPreset: VideoPreset = VideoPreset.High;

  saveImageOptimization(enabled: boolean): void {
    this.optimizeImages = enabled;
  }

  saveVideoPreset(preset: VideoPreset): void {
    this.videoPreset = preset;
  }
}

export class MediaMetadata {
  mediaType: MediaType;
  durationSeconds: number;
  originalSize: number;
  width: number;
  height: number;

  constructor(mediaType: MediaType, durationSeconds: number, originalSize: number = 0,
    width: number = 0, height: number = 0) {
    this.mediaType = mediaType;
    this.durationSeconds = durationSeconds;
    this.originalSize = originalSize;
    this.width = width;
    this.height = height;
  }
}

export class MediaPreprocessConfig {
  compressImages: boolean;
  videoCompressionPreset: VideoPreset;

  constructor(compressImages: boolean, videoCompressionPreset: VideoPreset) {
    this.compressImages = compressImages;
    this.videoCompressionPreset = videoCompressionPreset;
  }
}

export interface PreparedMediaArtifactStore {
  prepare(preset: VideoPreset, config: MediaPreprocessConfig): boolean;
  exists(): boolean;
  cleanUp(): void;
}

export class MemoryPreparedMediaArtifactStore implements PreparedMediaArtifactStore {
  private present: boolean = false;

  prepare(_preset: VideoPreset, _config: MediaPreprocessConfig): boolean {
    this.present = true;
    return true;
  }

  exists(): boolean {
    return this.present;
  }

  cleanUp(): void {
    this.present = false;
  }
}

export interface MediaInformationSource {
  requestUploadLimit(): Promise<number>;
  requestMetadata(mediaType: MediaType): Promise<MediaMetadata>;
}

export class MediaQualityGateway {
  private informationSource?: MediaInformationSource;
  private artifactStore: PreparedMediaArtifactStore;

  constructor(informationSource?: MediaInformationSource,
    artifactStore: PreparedMediaArtifactStore = new MemoryPreparedMediaArtifactStore()) {
    this.informationSource = informationSource;
    this.artifactStore = artifactStore;
  }

  maxUploadSize: number = 35_000_000;
  informationDelayMs: number = 0;
  failLimitRequest: boolean = false;
  failNextPreprocess: boolean = false;
  failNextUpload: boolean = false;
  lastPreset: VideoPreset = VideoPreset.Standard;
  lastCaption: string = '';
  attempts: number = 0;
  lastPreprocessConfig: MediaPreprocessConfig | undefined = undefined;

  setArtifactStore(artifactStore: PreparedMediaArtifactStore): void {
    this.artifactStore.cleanUp();
    this.artifactStore = artifactStore;
  }

  async requestUploadLimit(): Promise<number> {
    await this.delayInformation();
    if (this.informationSource !== undefined) return this.informationSource.requestUploadLimit();
    return this.getMaxUploadSize();
  }

  async requestMetadata(mediaType: MediaType): Promise<MediaMetadata> {
    await this.delayInformation();
    if (this.informationSource !== undefined) return this.informationSource.requestMetadata(mediaType);
    // Metadata for the standalone sample; session/file integrations supply the source.
    return new MediaMetadata(mediaType, mediaType === MediaType.Video ? 60 : 0, 0,
      mediaType === MediaType.Video ? 1920 : 0, mediaType === MediaType.Video ? 1080 : 0);
  }

  getMaxUploadSize(): number {
    return this.failLimitRequest ? -1 : this.maxUploadSize;
  }

  preprocess(preset: VideoPreset, config: MediaPreprocessConfig): boolean {
    if (this.failNextPreprocess) {
      this.failNextPreprocess = false;
      return false;
    }
    this.lastPreset = preset;
    this.lastPreprocessConfig = config;
    return this.artifactStore.prepare(preset, config);
  }

  upload(caption: string): boolean {
    this.attempts += 1;
    this.lastCaption = caption;
    if (this.failNextUpload) {
      this.failNextUpload = false;
      return false;
    }
    return true;
  }

  preparedMediaExists(): boolean {
    return this.artifactStore.exists();
  }

  cleanUpPreparedMedia(): void {
    this.artifactStore.cleanUp();
  }

  private async delayInformation(): Promise<void> {
    if (this.informationDelayMs <= 0) return;
    await new Promise<void>((resolve: () => void) => setTimeout(resolve, this.informationDelayMs));
  }
}

export class MediaQualityPresenter {
  readonly gateway: MediaQualityGateway;
  readonly preferences: MediaPreferences;
  mediaType: MediaType = MediaType.Video;
  limitState: MediaAsyncState = MediaAsyncState.Idle;
  estimationState: MediaAsyncState = MediaAsyncState.Idle;
  sendState: MediaAsyncState = MediaAsyncState.Idle;
  maxUploadSize: number = 0;
  fallbackUsed: boolean = false;
  estimations: VideoUploadEstimation[] = [];
  optimizeImages: boolean = true;
  selectedPreset: VideoPreset | undefined = undefined;
  selectorOpen: boolean = false;
  fileTooLargeError: boolean = false;
  preparedMedia: boolean = false;
  previewVisible: boolean = true;
  sendControlsVisible: boolean = true;
  caption: string = '';
  metadata: MediaMetadata | undefined = undefined;
  private previewGeneration: number = 0;

  constructor(gateway: MediaQualityGateway, preferences: MediaPreferences) {
    this.gateway = gateway;
    this.preferences = preferences;
  }

  async openPreview(mediaType: MediaType): Promise<void> {
    const generation = ++this.previewGeneration;
    this.discardPreparedMedia();
    this.mediaType = mediaType;
    this.limitState = MediaAsyncState.Loading;
    this.estimationState = MediaAsyncState.Loading;
    this.sendState = MediaAsyncState.Idle;
    this.metadata = undefined;
    this.maxUploadSize = 0;
    this.fallbackUsed = false;
    this.estimations = [];
    this.selectedPreset = undefined;
    this.fileTooLargeError = false;
    this.selectorOpen = false;
    this.preparedMedia = false;
    this.previewVisible = true;
    this.sendControlsVisible = true;
    this.optimizeImages = this.preferences.optimizeImages;
    // Start both I/O operations without blocking the caption editor or cancel action.
    const limitRequest = this.loadUploadLimit(generation);
    const metadataRequest = this.loadMetadata(mediaType, generation);
    await Promise.all([limitRequest, metadataRequest]);
    this.completePreview(generation);
  }

  private completePreview(generation: number): void {
    if (generation !== this.previewGeneration || this.metadata === undefined) return;
    if (this.metadata.mediaType === MediaType.Video) {
      this.calculateVideoEstimations(this.metadata.durationSeconds);
      this.chooseBestPreset(this.preferences.videoPreset);
    } else {
      this.estimationState = MediaAsyncState.Uninitialized;
    }
  }

  private async loadUploadLimit(generation: number): Promise<void> {
    let limit: number;
    try {
      limit = await this.gateway.requestUploadLimit();
    } catch {
      limit = -1;
    }
    if (generation !== this.previewGeneration) return;
    this.fallbackUsed = !Number.isFinite(limit) || limit < 0;
    this.maxUploadSize = this.fallbackUsed ? DEFAULT_MAX_UPLOAD_SIZE : limit;
    this.limitState = MediaAsyncState.Success;
  }

  private async loadMetadata(mediaType: MediaType, generation: number): Promise<void> {
    try {
      const metadata = await this.gateway.requestMetadata(mediaType);
      if (generation !== this.previewGeneration) return;
      if (metadata.mediaType !== mediaType || (mediaType === MediaType.Video &&
        (!Number.isFinite(metadata.durationSeconds) || metadata.durationSeconds < 0 ||
          !Number.isInteger(metadata.width) || metadata.width <= 0 ||
          !Number.isInteger(metadata.height) || metadata.height <= 0))) {
        this.estimationState = MediaAsyncState.Failure;
        return;
      }
      this.metadata = metadata;
    } catch {
      if (generation === this.previewGeneration) this.estimationState = MediaAsyncState.Failure;
    }
  }

  selectImageOptimization(enabled: boolean): void {
    if (this.optimizeImages !== enabled) this.discardPreparedMedia();
    this.optimizeImages = enabled;
    this.preferences.saveImageOptimization(enabled);
  }

  calculateVideoEstimations(durationSeconds: number): void {
    if (this.metadata?.mediaType !== MediaType.Video || this.limitState !== MediaAsyncState.Success) return;
    this.estimationState = MediaAsyncState.Loading;
    this.estimations = [
      this.estimate(VideoPreset.High, 1920, durationSeconds),
      this.estimate(VideoPreset.Standard, 1280, durationSeconds),
      this.estimate(VideoPreset.Low, 640, durationSeconds)
    ];
    this.estimationState = MediaAsyncState.Success;
    this.fileTooLargeError = this.estimations.every((item: VideoUploadEstimation) => !item.canUpload);
  }

  chooseBestPreset(defaultPreset: VideoPreset): void {
    const ordered: VideoPreset[] = [VideoPreset.High, VideoPreset.Standard, VideoPreset.Low];
    const start = ordered.indexOf(defaultPreset);
    this.selectedPreset = undefined;
    for (let index = start; index < ordered.length; index += 1) {
      const candidate = this.estimations.find((item: VideoUploadEstimation) => item.preset === ordered[index]);
      if (candidate !== undefined && candidate.canUpload) {
        this.selectedPreset = candidate.preset;
        this.preferences.saveVideoPreset(candidate.preset);
        break;
      }
    }
    this.fileTooLargeError = this.selectedPreset === undefined;
  }

  openSelector(): void {
    this.selectorOpen = true;
  }

  dismissSelector(): void {
    this.selectorOpen = false;
  }

  selectVideoPreset(preset: VideoPreset): boolean {
    const estimation = this.estimations.find((item: VideoUploadEstimation) => item.preset === preset);
    if (estimation === undefined || !estimation.canUpload) {
      return false;
    }
    if (this.selectedPreset !== preset) this.discardPreparedMedia();
    this.selectedPreset = preset;
    this.preferences.saveVideoPreset(preset);
    this.selectorOpen = false;
    return true;
  }

  setCaption(caption: string): void {
    this.caption = caption;
  }

  send(): boolean {
    if (this.limitState !== MediaAsyncState.Success || this.metadata === undefined ||
      this.estimationState === MediaAsyncState.Loading || this.estimationState === MediaAsyncState.Failure ||
      this.sendState === MediaAsyncState.Done) return false;
    if (this.fileTooLargeError || (this.mediaType === MediaType.Video && this.selectedPreset === undefined)) {
      this.sendState = MediaAsyncState.Failure;
      return false;
    }
    if (!this.preparedMedia) {
      this.sendState = MediaAsyncState.Loading;
      if (!this.prepareSelectedMedia()) {
        this.sendState = MediaAsyncState.Failure;
        return false;
      }
    }
    this.previewVisible = false;
    this.sendControlsVisible = false;
    const succeeded = this.gateway.upload(this.caption);
    this.sendState = succeeded ? MediaAsyncState.Done : MediaAsyncState.Failure;
    this.discardPreparedMedia();
    return succeeded;
  }

  clearFailure(): void {
    if (this.previewVisible && this.sendState === MediaAsyncState.Failure) {
      this.sendState = this.preparedMedia ? MediaAsyncState.ReadyToUpload : MediaAsyncState.Idle;
    }
  }

  cancel(): void {
    this.previewGeneration += 1;
    this.previewVisible = false;
    this.sendControlsVisible = false;
    this.discardPreparedMedia();
    this.sendState = MediaAsyncState.Done;
  }

  preparedMediaExists(): boolean {
    return this.gateway.preparedMediaExists();
  }

  prepareSelectedMediaForSend(): boolean {
    if (this.sendState === MediaAsyncState.Done || this.fileTooLargeError) return false;
    return this.prepareSelectedMedia();
  }

  private prepareSelectedMedia(): boolean {
    if (this.mediaType === MediaType.Video && this.selectedPreset === undefined) return false;
    const preset = this.selectedPreset === undefined ? VideoPreset.Standard : this.selectedPreset;
    const prepared = this.gateway.preprocess(preset, new MediaPreprocessConfig(this.optimizeImages, preset));
    this.preparedMedia = prepared && this.gateway.preparedMediaExists();
    this.sendState = this.preparedMedia ? MediaAsyncState.ReadyToUpload : MediaAsyncState.Failure;
    return this.preparedMedia;
  }

  private discardPreparedMedia(): void {
    this.gateway.cleanUpPreparedMedia();
    this.preparedMedia = false;
  }

  private estimate(preset: VideoPreset, maxSize: number, durationSeconds: number): VideoUploadEstimation {
    const dimensions = new VideoDimensions(this.metadata!.width, this.metadata!.height);
    const bitrate = new VideoCompressorHelper(maxSize).calculateOptimalBitrate(dimensions, 30);
    const durationMilliseconds = Math.trunc(durationSeconds * 1000);
    const calculatedSize = Math.round(Math.trunc(bitrate * durationMilliseconds / 8) * MEDIA_ESTIMATION_SAFETY_OVERHEAD);
    return new VideoUploadEstimation(preset, calculatedSize, calculatedSize <= this.maxUploadSize, bitrate);
  }
}
