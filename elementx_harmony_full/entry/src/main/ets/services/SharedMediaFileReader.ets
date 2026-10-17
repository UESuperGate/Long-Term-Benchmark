import fs from '@ohos.file.fs';

export interface SharedMediaReadResult {
  ok: boolean;
  data: ArrayBuffer;
  size: number;
  filename: string;
  errorMessage: string;
}

export class SharedMediaFileReader {
  readFileUri(uri: string): SharedMediaReadResult {
    if (uri.indexOf('fd://') === 0) {
      return this.readFdUri(uri);
    }
    if (this.isGrantableFileUri(uri)) {
      return this.readOpenedUri(uri);
    }
    const path = this.pathFromFileUri(uri);
    if (path.length === 0) {
      return this.createResult(false, new ArrayBuffer(0), 0, '', 'Only file://, content://, datashare:// or shared fd media upload is currently supported');
    }
    let file: fs.File | null = null;
    try {
      const stat = fs.statSync(path);
      if (stat.size <= 0) {
        return this.createResult(false, new ArrayBuffer(0), 0, this.filenameFromPath(path), 'Shared file is empty');
      }
      const data = new ArrayBuffer(stat.size);
      file = fs.openSync(path, fs.OpenMode.READ_ONLY);
      const bytesRead = fs.readSync(file.fd, data);
      if (bytesRead !== stat.size) {
        return this.createResult(false, data, bytesRead, this.filenameFromPath(path), 'Shared file could not be read completely');
      }
      return this.createResult(true, data, stat.size, this.filenameFromPath(path), '');
    } catch (error) {
      return this.createResult(false, new ArrayBuffer(0), 0, this.filenameFromPath(path), `${error}`);
    } finally {
      if (file !== null) {
        try {
          fs.closeSync(file);
        } catch (error) {
        }
      }
    }
  }

  private readOpenedUri(uri: string): SharedMediaReadResult {
    let file: fs.File | null = null;
    const filename = this.filenameFromUri(uri);
    try {
      file = fs.openSync(uri, fs.OpenMode.READ_ONLY);
      const stat = fs.statSync(file.fd);
      if (stat.size <= 0) {
        return this.createResult(false, new ArrayBuffer(0), 0, filename, 'Shared URI is empty');
      }
      const data = new ArrayBuffer(stat.size);
      const bytesRead = fs.readSync(file.fd, data, { offset: 0, length: stat.size });
      if (bytesRead !== stat.size) {
        return this.createResult(false, data, bytesRead, filename, 'Shared URI could not be read completely');
      }
      return this.createResult(true, data, stat.size, filename, '');
    } catch (error) {
      return this.createResult(false, new ArrayBuffer(0), 0, filename, `${error}`);
    } finally {
      if (file !== null) {
        try {
          fs.closeSync(file);
        } catch (error) {
        }
      }
    }
  }

  private readFdUri(uri: string): SharedMediaReadResult {
    const fd = this.fdFromUri(uri);
    const filename = this.filenameFromFdUri(uri);
    if (fd < 0) {
      return this.createResult(false, new ArrayBuffer(0), 0, filename, 'Shared file descriptor is invalid');
    }
    try {
      const stat = fs.statSync(fd);
      if (stat.size <= 0) {
        return this.createResult(false, new ArrayBuffer(0), 0, filename, 'Shared file descriptor is empty');
      }
      const data = new ArrayBuffer(stat.size);
      const bytesRead = fs.readSync(fd, data, { offset: 0, length: stat.size });
      if (bytesRead !== stat.size) {
        return this.createResult(false, data, bytesRead, filename, 'Shared file descriptor could not be read completely');
      }
      return this.createResult(true, data, stat.size, filename, '');
    } catch (error) {
      return this.createResult(false, new ArrayBuffer(0), 0, filename, `${error}`);
    } finally {
      try {
        fs.closeSync(fd);
      } catch (error) {
      }
    }
  }

  private pathFromFileUri(uri: string): string {
    if (uri.indexOf('file://') !== 0) {
      return '';
    }
    const encodedPath = uri.substring(7);
    try {
      return decodeURIComponent(encodedPath);
    } catch (error) {
      return encodedPath;
    }
  }

  private isGrantableFileUri(uri: string): boolean {
    return uri.indexOf('content://') === 0 || uri.indexOf('datashare://') === 0;
  }

  private filenameFromPath(path: string): string {
    const slashIndex = path.lastIndexOf('/');
    if (slashIndex >= 0 && slashIndex < path.length - 1) {
      return path.substring(slashIndex + 1);
    }
    return 'shared-media';
  }

  private filenameFromUri(uri: string): string {
    const stableUri = uri.split('#')[0].split('?')[0];
    const slashIndex = stableUri.lastIndexOf('/');
    const encodedName = slashIndex >= 0 && slashIndex < stableUri.length - 1
      ? stableUri.substring(slashIndex + 1)
      : 'shared-media';
    try {
      const name = decodeURIComponent(encodedName);
      return name.length > 0 ? name : 'shared-media';
    } catch (error) {
      return encodedName.length > 0 ? encodedName : 'shared-media';
    }
  }

  private fdFromUri(uri: string): number {
    const fdKey = '?fd=';
    const fdIndex = uri.indexOf(fdKey);
    if (fdIndex < 0) {
      return -1;
    }
    const fdText = uri.substring(fdIndex + fdKey.length);
    if (!/^[0-9]+$/.test(fdText)) {
      return -1;
    }
    return parseInt(fdText, 10);
  }

  private filenameFromFdUri(uri: string): string {
    const prefix = 'fd://';
    const fdKey = '?fd=';
    const fdIndex = uri.indexOf(fdKey);
    const encodedName = fdIndex >= 0 ? uri.substring(prefix.length, fdIndex) : uri.substring(prefix.length);
    if (encodedName.length === 0) {
      return 'shared-media';
    }
    try {
      const name = decodeURIComponent(encodedName);
      return name.length > 0 ? name : 'shared-media';
    } catch (error) {
      return encodedName;
    }
  }

  private createResult(ok: boolean, data: ArrayBuffer, size: number, filename: string, errorMessage: string): SharedMediaReadResult {
    return {
      ok: ok,
      data: data,
      size: size,
      filename: filename,
      errorMessage: errorMessage
    };
  }
}
