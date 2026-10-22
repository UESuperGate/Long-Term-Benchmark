import common from '@ohos.app.ability.common';
import fs from '@ohos.file.fs';
import fileUri from '@ohos.file.fileuri';
import { BusinessError } from '@ohos.base';

interface TransportError {
  name: string;
  message: string;
  code: number;
}

interface TransportAttempt {
  sourceKind: string;
  source: string;
  destination: string;
  completed: boolean;
  bytes?: number[];
  sameBytes?: boolean;
  error?: TransportError;
}

interface TransportDirectory {
  path: string;
  exists: boolean;
  isDirectory: boolean;
  error?: TransportError;
}

export interface Tasks16_18CopyTransportResult {
  observationLevel: string;
  scope: string;
  sourcePath: string;
  sourceUri: string;
  sourceBytes: number[];
  directories: TransportDirectory[];
  attempts: TransportAttempt[];
  cleanupErrors: TransportError[];
  error?: TransportError;
}

function failure(error: Error): TransportError {
  const native = error as BusinessError;
  return { name: error.name, message: error.message || String(error), code: native.code };
}

async function directory(path: string): Promise<TransportDirectory> {
  try {
    const stat = await fs.stat(path);
    return { path, exists: true, isDirectory: stat.isDirectory() };
  } catch (error) {
    return { path, exists: false, isDirectory: false, error: failure(error as Error) };
  }
}

async function bytesAt(path: string): Promise<number[]> {
  const file = await fs.open(path, fs.OpenMode.READ_ONLY);
  try {
    const size = (await fs.stat(file.fd)).size;
    if (size > 65536) throw new Error('Diagnostic file exceeds 64 KiB.');
    const bytes = new ArrayBuffer(size);
    if (await fs.read(file.fd, bytes) !== size) throw new Error('Diagnostic read was incomplete.');
    return Array.from(new Uint8Array(bytes));
  } finally { await fs.close(file); }
}

// Standalone SDK transport diagnostic. Never calls or replaces a production
// copier and never contributes a canonical semantic pass. The same real file
// is addressed three ways; URI rejection is retained, not normalized away.
export async function probeTasks16To18CopyTransport(context: common.Context): Promise<Tasks16_18CopyTransportResult> {
  const root = context.cacheDir + '/Tasks16_18_copy_' + Date.now();
  const sourcePath = root + '/42';
  const result: Tasks16_18CopyTransportResult = {
    observationLevel: 'native_sdk_transport_diagnostic',
    scope: 'Real SDK path/URI/FD copies of one file; no production semantic outcome inferred.',
    sourcePath, sourceUri: '', sourceBytes: [], directories: [], attempts: [], cleanupErrors: []
  };
  const ownedFiles: string[] = [];
  let created = false;
  try {
    // Observe the production destination parent before creating any probe data.
    result.directories.push(await directory(context.filesDir));
    result.directories.push(await directory(context.cacheDir));
    fs.mkdirSync(root);
    created = true;
    result.directories.push(await directory(root));
    result.sourceUri = fileUri.getUriFromPath(sourcePath);
    const source = await fs.open(sourcePath, fs.OpenMode.CREATE | fs.OpenMode.WRITE_ONLY | fs.OpenMode.TRUNC);
    ownedFiles.push(sourcePath);
    const payload = new Uint8Array([82, 73, 70, 70, 16, 0, 0, 0, 87, 65, 86, 69, 42, 7, 18, 16]);
    try {
      if (await fs.write(source.fd, payload.buffer) !== payload.byteLength) throw new Error('Source write was incomplete.');
    } finally { await fs.close(source); }
    result.sourceBytes = await bytesAt(sourcePath);
    // fs.open URI success is observed independently of fs.copyFile URI support.
    const uriBytes = await bytesAt(result.sourceUri);
    if (JSON.stringify(uriBytes) !== JSON.stringify(result.sourceBytes)) throw new Error('Path and URI did not address identical source bytes.');
    for (const kind of ['path', 'uri', 'fd']) {
      const destination = root + '/copy_' + kind;
      const attempt: TransportAttempt = { sourceKind: kind,
        source: kind === 'uri' ? result.sourceUri : sourcePath, destination, completed: false };
      result.attempts.push(attempt);
      ownedFiles.push(destination);
      let descriptor: fs.File | undefined = undefined;
      try {
        if (kind === 'fd') descriptor = await fs.open(sourcePath, fs.OpenMode.READ_ONLY);
        await fs.copyFile(descriptor !== undefined ? descriptor.fd : attempt.source, destination);
        attempt.completed = true;
        attempt.bytes = await bytesAt(destination);
        attempt.sameBytes = JSON.stringify(attempt.bytes) === JSON.stringify(result.sourceBytes);
      } catch (error) {
        attempt.error = failure(error as Error);
      } finally {
        if (descriptor !== undefined) {
          try { await fs.close(descriptor); } catch (error) { result.cleanupErrors.push(failure(error as Error)); }
        }
      }
    }
  } catch (error) {
    result.error = failure(error as Error);
  } finally {
    for (const path of ownedFiles) {
      try { await fs.unlink(path); }
      catch (error) {
        const detail = failure(error as Error);
        if (detail.code !== 13900002) result.cleanupErrors.push(detail);
      }
    }
    if (created) {
      try { fs.rmdirSync(root); } catch (error) { result.cleanupErrors.push(failure(error as Error)); }
    }
  }
  console.info('ARKTS_16_18_COPY_TRANSPORT ' + JSON.stringify(result));
  return result;
}
