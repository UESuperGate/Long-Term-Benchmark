"""Task11-only fallback retention before shared-core failed-child cleanup."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil

IGNORED = {'.git', '.hvigor', 'build', 'oh_modules', 'node_modules'}
BINARY = {'.apk', '.hap', '.aab', '.apks', '.abc', '.dex', '.so', '.jar', '.class', '.har'}


def record(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def retain_failed_artifacts(source, target):
    source, target = Path(source).resolve(), Path(target).resolve()
    if target == source or target.is_relative_to(source) or target.exists():
        raise ValueError('Task11 failure archive must be a new location outside temporary artifacts')
    (target / 'objects').mkdir(parents=True)
    manifest = {'schemaVersion': 1, 'taskId': '11_room_upgrade_navigation',
                'originalRoot': str(source), 'retentionRoot': str(target),
                'compression': 'gzip_lossless_original_bytes', 'files': [], 'binaryHashes': [],
                'reason': 'Failed or timed-out child: preserve actual available bytes before shared cleanup, never infer missing state'}
    for path in sorted(source.rglob('*')):
        if any(part in IGNORED for part in path.relative_to(source).parts):
            continue
        if path.is_symlink():
            raise ValueError('Task11 artifact symlink unsupported')
        if not path.is_file():
            continue
        original = record(path)
        if path.suffix.lower() in BINARY:
            manifest['binaryHashes'].append(original)
            continue
        compressed = target / 'objects' / (original['sha256'] + '.gz')
        if not compressed.exists():
            with path.open('rb') as raw, gzip.open(compressed, 'xb') as output:
                shutil.copyfileobj(raw, output, length=1024 * 1024)
        digest, length = hashlib.sha256(), 0
        with gzip.open(compressed, 'rb') as restored:
            for chunk in iter(lambda: restored.read(1024 * 1024), b''):
                length += len(chunk)
                digest.update(chunk)
        if length != original['bytes'] or digest.hexdigest() != original['sha256']:
            raise ValueError('Task11 failure evidence is not losslessly restorable')
        manifest['files'].append({'original': original, 'relativePath': path.relative_to(source).as_posix(),
                                  'gzip': record(compressed), 'originalBytesRestorable': True})
    manifest_path = target / 'manifest.json'
    with manifest_path.open('x') as stream:
        json.dump(manifest, stream, indent=2)
        stream.write('\n')
    return record(manifest_path)
