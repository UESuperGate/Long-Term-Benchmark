import fs from '@ohos.file.fs';
import { DomainErrorCode, DomainResult } from '../../core/DomainResult';
import {
  PlatformFailure,
  PlatformFailureKind,
  platformCodeOf,
  platformSdkError
} from '../errors/PlatformFailure';

export interface MediaDescriptorBackend {
  openReadOnly(uri: string): Promise<number>;
  duplicate(fd: number): Promise<number>;
  close(fd: number): Promise<void>;
}

export class OpenHarmonyMediaDescriptorBackend implements MediaDescriptorBackend {
  async openReadOnly(uri: string): Promise<number> {
    try {
      const file = await fs.open(uri, fs.OpenMode.READ_ONLY);
      return file.fd;
    } catch (error) {
      throw platformSdkError('media.open', error as Error);
    }
  }

  async duplicate(fd: number): Promise<number> {
    try {
      return fs.dup(fd).fd;
    } catch (error) {
      throw platformSdkError('media.duplicate', error as Error);
    }
  }

  async close(fd: number): Promise<void> {
    try {
      await fs.close(fd);
    } catch (error) {
      throw platformSdkError('media.close', error as Error);
    }
  }
}

/** Explicit ownership wrapper. The original or duplicated FD is closed exactly once. */
export class OwnedMediaDescriptor {
  private readonly backend: MediaDescriptorBackend;
  private descriptor: number;
  private closed: boolean = false;

  private constructor(descriptor: number, backend: MediaDescriptorBackend) {
    this.descriptor = descriptor;
    this.backend = backend;
  }

  static async open(
    uri: string,
    backend: MediaDescriptorBackend = new OpenHarmonyMediaDescriptorBackend()
  ): Promise<DomainResult<OwnedMediaDescriptor>> {
    if (!OwnedMediaDescriptor.isSupportedUri(uri)) {
      return DomainResult.fail<OwnedMediaDescriptor>(new PlatformFailure(
        DomainErrorCode.InvalidInput,
        PlatformFailureKind.InvalidData,
        'media_descriptor.open',
        'Media URI must use a supported local or provider-backed scheme',
        false
      ));
    }
    try {
      const fd = await backend.openReadOnly(uri);
      if (fd < 0) {
        throw new Error('Platform returned an invalid file descriptor');
      }
      return DomainResult.succeed<OwnedMediaDescriptor>(new OwnedMediaDescriptor(fd, backend));
    } catch (error) {
      return DomainResult.fail<OwnedMediaDescriptor>(OwnedMediaDescriptor.ioFailure(
        'media_descriptor.open',
        'Unable to open media URI for reading',
        error as Error
      ));
    }
  }

  borrow(): DomainResult<number> {
    if (this.closed) {
      return DomainResult.fail<number>(new PlatformFailure(
        DomainErrorCode.ServiceUnavailable,
        PlatformFailureKind.ResourceClosed,
        'media_descriptor.borrow',
        'Media descriptor is already closed',
        false
      ));
    }
    return DomainResult.succeed<number>(this.descriptor);
  }

  async duplicate(): Promise<DomainResult<OwnedMediaDescriptor>> {
    if (this.closed) {
      return DomainResult.fail<OwnedMediaDescriptor>(new PlatformFailure(
        DomainErrorCode.ServiceUnavailable,
        PlatformFailureKind.ResourceClosed,
        'media_descriptor.duplicate',
        'Media descriptor is already closed',
        false
      ));
    }
    try {
      const duplicate = await this.backend.duplicate(this.descriptor);
      return DomainResult.succeed<OwnedMediaDescriptor>(
        new OwnedMediaDescriptor(duplicate, this.backend)
      );
    } catch (error) {
      return DomainResult.fail<OwnedMediaDescriptor>(OwnedMediaDescriptor.ioFailure(
        'media_descriptor.duplicate',
        'Unable to duplicate media descriptor',
        error as Error
      ));
    }
  }

  async close(): Promise<DomainResult<boolean>> {
    if (this.closed) {
      return DomainResult.succeed<boolean>(false);
    }
    const descriptor = this.descriptor;
    this.closed = true;
    this.descriptor = -1;
    try {
      await this.backend.close(descriptor);
      return DomainResult.succeed<boolean>(true);
    } catch (error) {
      return DomainResult.fail<boolean>(OwnedMediaDescriptor.ioFailure(
        'media_descriptor.close',
        'Unable to close media descriptor',
        error as Error
      ));
    }
  }

  private static isSupportedUri(value: string): boolean {
    return value.startsWith('file://') || value.startsWith('datashare://') ||
      value.startsWith('content://') || value.startsWith('/');
  }

  private static ioFailure(operation: string, message: string, error: Error): PlatformFailure {
    return new PlatformFailure(
      DomainErrorCode.ServiceUnavailable,
      PlatformFailureKind.ReadFailed,
      operation,
      message,
      true,
      platformCodeOf(error)
    );
  }
}
