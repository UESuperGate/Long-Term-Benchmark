import { MEDIA_ESTIMATION_SAFETY_OVERHEAD, MediaAsyncState, MediaPreferences, MediaQualityGateway, MediaQualityPresenter, MediaType, VideoPreset, VideoUploadEstimation } from '../features/MediaQualityFeature';
import { FilePreparedMediaArtifactStore } from '../services/FilePreparedMediaArtifactStore';

@Entry
@Component
struct Index {
  private gateway: MediaQualityGateway = new MediaQualityGateway();
  private presenter: MediaQualityPresenter = new MediaQualityPresenter(this.gateway, new MediaPreferences());
  private previewGeneration: number = 0;
  @State private mediaType: MediaType = MediaType.Video;
  @State private maxUploadSize: number = 0;
  @State private fallbackUsed: boolean = false;
  @State private estimations: VideoUploadEstimation[] = [];
  @State private optimizeImages: boolean = true;
  @State private selectedPreset: VideoPreset | undefined = undefined;
  @State private selectorOpen: boolean = false;
  @State private fileTooLargeError: boolean = false;
  @State private caption: string = '';
  @State private sendState: MediaAsyncState = MediaAsyncState.Idle;
  @State private limitState: MediaAsyncState = MediaAsyncState.Idle;
  @State private estimationState: MediaAsyncState = MediaAsyncState.Idle;
  @State private statusText: string = 'Loading media information';
  @State private previewVisible: boolean = true;
  @State private preparedMediaExists: boolean = false;

  aboutToAppear(): void {
    this.gateway.setArtifactStore(new FilePreparedMediaArtifactStore(getContext(this).getApplicationContext().cacheDir));
    this.openMedia(MediaType.Video);
  }

  aboutToDisappear(): void {
    this.previewGeneration += 1;
    this.presenter.cancel();
  }

  build() {
    Stack({ alignContent: Alignment.Center }) {
      Column() {
      this.Header()
      if (this.previewVisible) {
        Scroll() {
        Column({ space: 12 }) {
          Row({ space: 8 }) {
            Button('Video')
              .id('media_open_video')
              .enabled(this.mediaType !== MediaType.Video)
              .onClick(() => this.openMedia(MediaType.Video))
            Button('Image')
              .id('media_open_image')
              .enabled(this.mediaType !== MediaType.Image)
              .onClick(() => this.openMedia(MediaType.Image))
          }
          Row({ space: 8 }) {
            Button('Limit failure')
              .id('media_limit_failure')
              .onClick(() => {
                this.presenter.gateway.failLimitRequest = true;
                this.openMedia(this.mediaType);
              })
            Button('Slow info')
              .id('media_slow_info')
              .onClick(() => {
                this.presenter.gateway.informationDelayMs = 5000;
                this.openMedia(this.mediaType);
              })
            Button('Tiny limit')
              .id('media_tiny_limit')
              .onClick(() => {
                this.presenter.gateway.maxUploadSize = 1;
                this.openMedia(MediaType.Video);
              })
          }
          Text(`Upload limit: ${this.maxUploadSize} bytes`)
            .id('media_upload_limit')
            .width('100%')
          Text(`Fallback used: ${this.fallbackUsed}`)
            .id('media_fallback_status')
          Text(`Estimation state: ${this.estimationState}`)
            .id('media_estimation_state')
          Text(`Safety overhead: ${MEDIA_ESTIMATION_SAFETY_OVERHEAD}`)
            .id('media_safety_overhead')
          if (this.limitState === MediaAsyncState.Loading || this.estimationState === MediaAsyncState.Loading) {
            LoadingProgress()
              .id('media_information_loading')
              .width(24)
              .height(24)
          }
          if (this.mediaType === MediaType.Image) {
            Row({ space: 8 }) {
              Toggle({ type: ToggleType.Switch, isOn: this.optimizeImages })
                .id('image_optimization_toggle')
                .onChange((enabled: boolean) => {
                  this.presenter.selectImageOptimization(enabled);
                  this.refresh();
                })
              Text('Optimize image before upload')
            }
          } else {
            Button(`Quality: ${this.selectedPreset === undefined ? 'unavailable' : this.selectedPreset}`)
              .id('video_quality_selector')
              .width('100%')
              .onClick(() => {
                this.presenter.openSelector();
                this.refresh();
              })
            if (this.selectorOpen) {
              ForEach(this.estimations, (item: VideoUploadEstimation) => {
                Button(`${item.preset}: ${item.sizeInBytes} bytes${item.canUpload ? '' : ' (too large)'}`)
                  .id(`video_preset_${item.preset}`)
                  .enabled(item.canUpload)
                  .width('100%')
                  .onClick(() => {
                    this.presenter.selectVideoPreset(item.preset);
                    this.refresh();
                  })
              })
              Button('Dismiss quality chooser')
                .id('video_quality_dismiss')
                .onClick(() => {
                  this.presenter.dismissSelector();
                  this.refresh();
                })
            }
          }
          TextInput({ text: this.caption, placeholder: 'Caption' })
            .id('media_caption')
            .onChange((value: string) => {
              this.presenter.setCaption(value);
              this.caption = value;
            })
          Row({ space: 8 }) {
            Button('Prepare media')
              .id('media_prepare')
              .enabled(!this.fileTooLargeError && this.limitState === MediaAsyncState.Success &&
                this.estimationState !== MediaAsyncState.Loading && this.estimationState !== MediaAsyncState.Failure)
              .onClick(() => {
                this.presenter.prepareSelectedMediaForSend();
                this.refresh();
              })
            Button('Send')
              .id('media_send')
              .enabled(this.limitState === MediaAsyncState.Success &&
                this.estimationState !== MediaAsyncState.Loading && this.estimationState !== MediaAsyncState.Failure &&
                this.sendState !== MediaAsyncState.Done)
              .onClick(() => {
                this.statusText = this.presenter.send() ? 'Media sent' : 'Media send failed';
                this.refresh();
              })
            Button('Fail upload')
              .id('media_fail_upload')
              .onClick(() => {
                this.presenter.gateway.failNextUpload = true;
              })
            Button('Cancel')
              .id('media_cancel')
              .onClick(() => {
                this.presenter.cancel();
                this.refresh();
              })
          }
          Text(`${this.statusText}; state ${this.sendState}`)
            .id('media_status')
            .fontColor('#475569')
            .width('100%')
          Text(`Attempts: ${this.presenter.gateway.attempts}`)
            .id('media_attempt_count')
          Text(this.preparedMediaExists ? 'Prepared media ready' : 'Prepared media absent')
            .id('media_prepared_status')
        }
        .padding(20)
        .width('100%')
        }
        .layoutWeight(1)
      } else {
        Column({ space: 10 }) {
          Text(this.sendState === MediaAsyncState.Failure ?
            'The preview closed. Background upload failed.' : 'The preview closed after sending.')
            .id('media_background_result')
            .fontSize(18)
          Text(this.preparedMediaExists ? 'Temporary media remains' : 'Temporary media removed')
            .id('media_cleanup_status')
            .fontColor(this.preparedMediaExists ? '#B42318' : '#067647')
          Text(`Attempts: ${this.presenter.gateway.attempts}; preset: ${this.presenter.gateway.lastPreset}; caption: ${this.presenter.gateway.lastCaption}`)
            .id('media_background_effect')
          Text(`compressImages: ${this.presenter.gateway.lastPreprocessConfig?.compressImages ?? true}`)
            .id('media_preprocess_effect')
        }
        .padding(20)
        .alignItems(HorizontalAlign.Start)
        .width('100%')
        .layoutWeight(1)
      }
      }
      .height('100%')
      .width('100%')
      .backgroundColor('#F4F6F8')
      if (this.fileTooLargeError) {
        Stack({ alignContent: Alignment.Center }) {
          Column()
            .width('100%')
            .height('100%')
            .backgroundColor('#55000000')
            .onClick(() => {})
          Column({ space: 12 }) {
            Text('This media is too large for every available quality.')
              .id('media_too_large_error')
              .fontColor('#B42318')
              .fontSize(18)
            Text('Choose another attachment or cancel this preview.')
          }
          .padding(24)
          .width('88%')
          .backgroundColor('#FFFFFF')
          .borderRadius(8)
          .shadow({ radius: 20, color: '#66000000', offsetX: 0, offsetY: 8 })
        }
        .id('media_too_large_modal')
        .width('100%')
        .height('100%')
        .zIndex(10)
      }
    }
    .height('100%')
    .width('100%')
  }

  private openMedia(mediaType: MediaType): void {
    const generation = ++this.previewGeneration;
    const loading = this.presenter.openPreview(mediaType);
    this.statusText = 'Loading media information';
    this.refresh();
    loading.then(() => {
      if (generation !== this.previewGeneration || this.presenter.sendState === MediaAsyncState.Done) return;
      this.statusText = this.presenter.estimationState === MediaAsyncState.Failure ?
        'Unable to read media information' : 'Quality options ready';
      this.refresh();
    });
  }

  private refresh(): void {
    this.mediaType = this.presenter.mediaType;
    this.maxUploadSize = this.presenter.maxUploadSize;
    this.fallbackUsed = this.presenter.fallbackUsed;
    this.estimations = this.presenter.estimations.slice();
    this.optimizeImages = this.presenter.optimizeImages;
    this.selectedPreset = this.presenter.selectedPreset;
    this.selectorOpen = this.presenter.selectorOpen;
    this.fileTooLargeError = this.presenter.fileTooLargeError;
    this.caption = this.presenter.caption;
    this.sendState = this.presenter.sendState;
    this.limitState = this.presenter.limitState;
    this.estimationState = this.presenter.estimationState;
    this.previewVisible = this.presenter.previewVisible;
    this.preparedMediaExists = this.presenter.preparedMediaExists();
  }

  @Builder
  Header() {
    Column({ space: 4 }) {
      Text('Element X Media Quality')
        .fontSize(24)
        .fontWeight(FontWeight.Bold)
      Text('Android v25.08.3 behavior: quality selection within the server limit')
        .fontSize(13)
        .fontColor('#64748B')
    }
    .alignItems(HorizontalAlign.Start)
    .padding(20)
    .width('100%')
    .backgroundColor('#FFFFFF')
  }
}
