import fs from '@ohos.file.fs';
import { MediaPreprocessConfig, PreparedMediaArtifactStore, VideoPreset } from '../features/MediaQualityFeature';

export class FilePreparedMediaArtifactStore implements PreparedMediaArtifactStore {
  private readonly artifactPath: string;

  constructor(cacheDir: string) {
    this.artifactPath = cacheDir + '/elementx-media-upload-prepared.tmp';
  }

  prepare(preset: VideoPreset, config: MediaPreprocessConfig): boolean {
    this.cleanUp();
    let file: fs.File | undefined = undefined;
    let written: boolean = false;
    try {
      file = fs.openSync(this.artifactPath,
        fs.OpenMode.CREATE | fs.OpenMode.WRITE_ONLY | fs.OpenMode.TRUNC);
      const payload: string = JSON.stringify({
        preset: preset,
        compressImages: config.compressImages,
        videoCompressionPreset: config.videoCompressionPreset
      });
      fs.writeSync(file.fd, payload);
      written = true;
    } catch (_) {
    } finally {
      if (file !== undefined) fs.closeSync(file);
    }
    if (!written || !this.exists()) {
      this.cleanUp();
      return false;
    }
    return true;
  }

  exists(): boolean {
    let file: fs.File | undefined = undefined;
    try {
      file = fs.openSync(this.artifactPath, fs.OpenMode.READ_ONLY);
      return true;
    } catch (_) {
      return false;
    } finally {
      if (file !== undefined) fs.closeSync(file);
    }
  }

  cleanUp(): void {
    try {
      fs.unlinkSync(this.artifactPath);
    } catch (_) {
    }
  }
}
