export const DEFAULT_MAX_UPLOAD_SIZE: number = 100 * 1024 * 1024;

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

  constructor(preset: VideoPreset, sizeInBytes: number, canUpload: boolean) {
    this.preset = preset;
    this.sizeInBytes = sizeInBytes;
    this.canUpload = canUpload;
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

export class MediaQualityGateway {
  maxUploadSize: number = 35_000_000;
  failLimitRequest: boolean = false;
  failNextPreprocess: boolean = false;
  failNextUpload: boolean = false;
  lastPreset: VideoPreset = VideoPreset.Standard;
  lastCaption: string = '';
  attempts: number = 0;

  getMaxUploadSize(): number {
    return this.failLimitRequest ? -1 : this.maxUploadSize;
  }

  preprocess(preset: VideoPreset): boolean {
    if (this.failNextPreprocess) {
      this.failNextPreprocess = false;
      return false;
    }
    this.lastPreset = preset;
    return true;
  }

  upload(caption: string): boolean {
    this.attempts += 1;
    if (this.failNextUpload) {
      this.failNextUpload = false;
      return false;
    }
    this.lastCaption = caption;
    return true;
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
  caption: string = '';

  constructor(gateway: MediaQualityGateway, preferences: MediaPreferences) {
    this.gateway = gateway;
    this.preferences = preferences;
  }

  openPreview(mediaType: MediaType): void {
    this.mediaType = mediaType;
    this.limitState = MediaAsyncState.Loading;
    this.estimationState = MediaAsyncState.Loading;
    this.sendState = MediaAsyncState.Idle;
    const serverLimit = this.gateway.getMaxUploadSize();
    this.fallbackUsed = serverLimit < 0;
    this.maxUploadSize = this.fallbackUsed ? DEFAULT_MAX_UPLOAD_SIZE : serverLimit;
    this.limitState = MediaAsyncState.Success;
    this.optimizeImages = this.preferences.optimizeImages;
    if (mediaType === MediaType.Video) {
      this.calculateVideoEstimations(60);
      this.chooseBestPreset(this.preferences.videoPreset);
    } else {
      this.estimations = [];
      this.estimationState = MediaAsyncState.Uninitialized;
      this.selectedPreset = undefined;
    }
  }

  selectImageOptimization(enabled: boolean): void {
    this.optimizeImages = enabled;
    this.preferences.saveImageOptimization(enabled);
  }

  calculateVideoEstimations(durationSeconds: number): void {
    this.estimationState = MediaAsyncState.Loading;
    this.estimations = [
      this.estimate(VideoPreset.High, 8_000_000, durationSeconds),
      this.estimate(VideoPreset.Standard, 4_000_000, durationSeconds),
      this.estimate(VideoPreset.Low, 1_000_000, durationSeconds)
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
    this.selectedPreset = preset;
    this.preferences.saveVideoPreset(preset);
    this.selectorOpen = false;
    return true;
  }

  setCaption(caption: string): void {
    this.caption = caption;
  }

  send(): boolean {
    if (this.fileTooLargeError || (this.mediaType === MediaType.Video && this.selectedPreset === undefined)) {
      this.sendState = MediaAsyncState.Failure;
      return false;
    }
    const preset = this.selectedPreset === undefined ? VideoPreset.Standard : this.selectedPreset;
    if (!this.preparedMedia) {
      this.sendState = MediaAsyncState.Loading;
      if (!this.gateway.preprocess(preset)) {
        this.sendState = MediaAsyncState.Failure;
        return false;
      }
      this.preparedMedia = true;
      this.sendState = MediaAsyncState.ReadyToUpload;
    }
    const succeeded = this.gateway.upload(this.caption);
    this.sendState = succeeded ? MediaAsyncState.Done : MediaAsyncState.Failure;
    if (succeeded) {
      this.preparedMedia = false;
    }
    return succeeded;
  }

  clearFailure(): void {
    if (this.sendState === MediaAsyncState.Failure) {
      this.sendState = this.preparedMedia ? MediaAsyncState.ReadyToUpload : MediaAsyncState.Idle;
    }
  }

  cancel(): void {
    this.preparedMedia = false;
    this.sendState = MediaAsyncState.Done;
  }

  private estimate(preset: VideoPreset, bitRate: number, durationSeconds: number): VideoUploadEstimation {
    const calculatedSize = Math.round(bitRate * durationSeconds / 8 * 1.1);
    return new VideoUploadEstimation(preset, calculatedSize, calculatedSize <= this.maxUploadSize);
  }
}
