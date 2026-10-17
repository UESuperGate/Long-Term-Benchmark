import { MediaAsyncState, MediaPreferences, MediaQualityGateway, MediaQualityPresenter, MediaType, VideoPreset, VideoUploadEstimation } from '../features/MediaQualityFeature';

@Entry
@Component
struct Index {
  private presenter: MediaQualityPresenter = new MediaQualityPresenter(new MediaQualityGateway(), new MediaPreferences());
  @State private mediaType: MediaType = MediaType.Video;
  @State private maxUploadSize: number = 0;
  @State private estimations: VideoUploadEstimation[] = [];
  @State private optimizeImages: boolean = true;
  @State private selectedPreset: VideoPreset | undefined = undefined;
  @State private selectorOpen: boolean = false;
  @State private fileTooLargeError: boolean = false;
  @State private caption: string = '';
  @State private sendState: MediaAsyncState = MediaAsyncState.Idle;
  @State private statusText: string = 'Loading media information';

  aboutToAppear(): void {
    this.presenter.openPreview(MediaType.Video);
    this.statusText = 'Quality options ready';
    this.refresh();
  }

  build() {
    Column() {
      this.Header()
      Scroll() {
        Column({ space: 12 }) {
          Row({ space: 8 }) {
            Button('Video')
              .enabled(this.mediaType !== MediaType.Video)
              .onClick(() => this.openMedia(MediaType.Video))
            Button('Image')
              .enabled(this.mediaType !== MediaType.Image)
              .onClick(() => this.openMedia(MediaType.Image))
            Button('Limit failure')
              .onClick(() => {
                this.presenter.gateway.failLimitRequest = true;
                this.openMedia(this.mediaType);
              })
          }
          Text(`Upload limit: ${this.maxUploadSize} bytes`)
            .id('media_upload_limit')
            .width('100%')
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
                  .enabled(item.canUpload)
                  .width('100%')
                  .onClick(() => {
                    this.presenter.selectVideoPreset(item.preset);
                    this.refresh();
                  })
              })
              Button('Dismiss quality chooser')
                .onClick(() => {
                  this.presenter.dismissSelector();
                  this.refresh();
                })
            }
          }
          if (this.fileTooLargeError) {
            Text('This media is too large for every available quality.')
              .id('media_too_large_error')
              .fontColor('#B42318')
              .width('100%')
          }
          TextInput({ text: this.caption, placeholder: 'Caption' })
            .id('media_caption')
            .onChange((value: string) => {
              this.presenter.setCaption(value);
              this.caption = value;
            })
          Row({ space: 8 }) {
            Button('Send')
              .id('media_send')
              .enabled(!this.fileTooLargeError)
              .onClick(() => {
                this.statusText = this.presenter.send() ? 'Media sent' : 'Media send failed';
                this.refresh();
              })
            Button('Fail upload')
              .onClick(() => {
                this.presenter.gateway.failNextUpload = true;
              })
            Button('Clear / retry')
              .enabled(this.sendState === MediaAsyncState.Failure)
              .onClick(() => {
                this.presenter.clearFailure();
                this.presenter.send();
                this.refresh();
              })
            Button('Cancel')
              .onClick(() => {
                this.presenter.cancel();
                this.refresh();
              })
          }
          Text(`${this.statusText}; state ${this.sendState}`)
            .id('media_status')
            .fontColor('#475569')
            .width('100%')
        }
        .padding(20)
        .width('100%')
      }
      .layoutWeight(1)
    }
    .height('100%')
    .width('100%')
    .backgroundColor('#F4F6F8')
  }

  private openMedia(mediaType: MediaType): void {
    this.presenter.openPreview(mediaType);
    this.refresh();
  }

  private refresh(): void {
    this.mediaType = this.presenter.mediaType;
    this.maxUploadSize = this.presenter.maxUploadSize;
    this.estimations = this.presenter.estimations.slice();
    this.optimizeImages = this.presenter.optimizeImages;
    this.selectedPreset = this.presenter.selectedPreset;
    this.selectorOpen = this.presenter.selectorOpen;
    this.fileTooLargeError = this.presenter.fileTooLargeError;
    this.caption = this.presenter.caption;
    this.sendState = this.presenter.sendState;
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
