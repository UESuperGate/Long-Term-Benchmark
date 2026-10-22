"""Raw Android candidate input snapshots, independent of Git clean/smudge filters."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import tarfile
import time

VERSION = 'android-raw-working-tree.v1'
INIT_RELATIVE = '_benchmark_inputs/android_maven_mirror.init.gradle'
INIT_ENV = 'LTB_ANDROID_PUBLIC_INIT_RECEIPT'


class InputIntegrityError(ValueError):
    pass


def check_deadline(deadline, storage_check=None):
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError('Overall deadline exhausted during Android input snapshot/validation')
    if storage_check is not None:
        storage_check()


def require(value, message):
    if not value:
        raise InputIntegrityError(message)


def digest_file(path, deadline=None, storage_check=None):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            check_deadline(deadline, storage_check)
            digest.update(block)
    return digest.hexdigest()


def record(path, deadline=None, storage_check=None):
    return {'path': str(path.resolve()), 'bytes': path.stat().st_size,
            'sha256': digest_file(path, deadline, storage_check)}


def read_record(value, deadline=None):
    path = Path(value['path'])
    require(record(path, deadline) == value, 'Retained Android input artifact changed')
    return path.read_bytes()


def _file_entry(path, relative, deadline, storage_check=None):
    check_deadline(deadline, storage_check)
    before = path.lstat()
    mode = stat.S_IMODE(before.st_mode)
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
            'Unsupported nonregular/hardlinked input: ' + relative)
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    digest = hashlib.sha256()
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        require((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), 'Input replaced during open')
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            check_deadline(deadline, storage_check)
            digest.update(block)
    after = path.lstat()
    require((before.st_dev, before.st_ino, before.st_mode, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_dev, after.st_ino, after.st_mode, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
            'Input changed during raw hashing: ' + relative)
    return {'path': relative, 'kind': 'file', 'mode': mode, 'bytes': before.st_size, 'sha256': digest.hexdigest()}


def inventory(candidate, deadline=None, storage_check=None):
    """All filesystem entries except root Git metadata; do not apply .gitignore."""
    candidate = Path(candidate).resolve()
    entries = []

    def visit(path):
        check_deadline(deadline, storage_check)
        relative = path.relative_to(candidate).as_posix() if path != candidate else '.'
        value = path.lstat()
        if stat.S_ISLNK(value.st_mode):
            target = os.readlink(path)
            require(not Path(target).is_absolute(), 'Absolute symlink cannot be a self-contained input: ' + relative)
            resolved = path.resolve(strict=False)
            require(resolved == candidate or candidate in resolved.parents,
                    'Symlink escapes the captured candidate: ' + relative)
            raw = os.fsencode(target)
            entries.append({'path': relative, 'kind': 'symlink', 'mode': stat.S_IMODE(value.st_mode),
                            'target': target, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        elif stat.S_ISDIR(value.st_mode):
            entries.append({'path': relative, 'kind': 'directory', 'mode': stat.S_IMODE(value.st_mode)})
            for child in sorted(path.iterdir()):
                if path == candidate and child.name == '.git':
                    continue
                visit(child)
        else:
            entries.append(_file_entry(path, relative, deadline, storage_check))

    visit(candidate)
    return {'version': VERSION, 'candidate': str(candidate),
            'scope': 'all raw working-tree bytes, POSIX modes and literal symlink targets; root .git excluded',
            'excluded': ['.git'], 'entries': sorted(entries, key=lambda item: item['path'])}


def verify_archive(archive, expected, deadline=None, storage_check=None):
    actual = []
    with tarfile.open(archive, 'r:gz') as stream:
        for member in stream:
            check_deadline(deadline, storage_check)
            path = Path(member.name)
            require(not path.is_absolute() and '..' not in path.parts, 'Unsafe raw snapshot archive path')
            item = {'path': member.name, 'mode': member.mode}
            if member.isdir():
                item['kind'] = 'directory'
            elif member.issym():
                raw = os.fsencode(member.linkname)
                item.update(kind='symlink', target=member.linkname, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            elif member.isfile():
                digest = hashlib.sha256()
                with stream.extractfile(member) as source:
                    for block in iter(lambda: source.read(1024 * 1024), b''):
                        check_deadline(deadline, storage_check)
                        digest.update(block)
                item.update(kind='file', bytes=member.size, sha256=digest.hexdigest())
            else:
                raise InputIntegrityError('Unsupported raw archive entry type')
            actual.append(item)
    require(len({item['path'] for item in actual}) == len(actual), 'Duplicate raw archive entries')
    require(sorted(actual, key=lambda item: item['path']) == expected,
            'Raw archive differs in actual bytes, exact POSIX mode, type or link target')
    return {'verified': True, 'entries': len(actual), 'exactModes': True,
            'gitFiltersApplied': False, 'symlinkTargetsFollowed': False}


def _write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def capture(candidate, destination, deadline=None, storage_check=None):
    candidate, destination = Path(candidate).resolve(), Path(destination).resolve()
    require(destination != candidate and candidate not in destination.parents, 'Snapshot must be outside candidate')
    destination.mkdir(parents=True, exist_ok=False)
    before = inventory(candidate, deadline, storage_check)
    _write_json(destination / 'before.json', before)
    archive = destination / 'working-tree.tar.gz'
    with tarfile.open(archive, 'x:gz') as stream:
        for item in before['entries']:
            check_deadline(deadline, storage_check)
            info = tarfile.TarInfo(item['path'])
            info.mode = item['mode']
            if item['kind'] == 'directory':
                info.type = tarfile.DIRTYPE
                stream.addfile(info)
            elif item['kind'] == 'symlink':
                info.type, info.linkname = tarfile.SYMTYPE, item['target']
                stream.addfile(info)
            else:
                info.size = item['bytes']
                flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                with os.fdopen(os.open(candidate / item['path'], flags), 'rb') as source:
                    class BudgetReader:
                        def read(self, size=-1):
                            check_deadline(deadline, storage_check)
                            return source.read(size)
                    stream.addfile(info, BudgetReader())
    validation = verify_archive(archive, before['entries'], deadline, storage_check)
    after = inventory(candidate, deadline, storage_check)
    _write_json(destination / 'after.json', after)
    require(before == after, 'Working tree changed while raw snapshot was captured')
    receipt = {'version': VERSION, 'kind': 'raw_working_tree_snapshot',
        'before': record(destination / 'before.json', deadline, storage_check),
        'after': record(destination / 'after.json', deadline, storage_check),
        'archive': record(archive, deadline, storage_check),
        'sourceUnchangedDuringCapture': True, 'archiveValidation': validation,
        'notCaptured': ['root .git metadata', 'external process environment', 'SDK/dependency caches',
                        'timestamps, ownership, ACLs and extended attributes']}
    _write_json(destination / 'receipt.json', receipt)
    return receipt


def verify_current(candidate, receipt, deadline=None):
    require(receipt.get('version') == VERSION, 'Unknown raw working-tree snapshot version')
    before = json.loads(read_record(receipt['before'], deadline))
    after = json.loads(read_record(receipt['after'], deadline))
    require(before == after, 'Raw before/after inventory differs')
    read_record(receipt['archive'], deadline)
    verify_archive(receipt['archive']['path'], before['entries'], deadline)
    require(inventory(candidate, deadline) == before, 'Actual working tree differs from raw snapshot before execution')


def seal_init(candidate, deadline=None):
    candidate = Path(candidate).resolve()
    directory, path = candidate / '_benchmark_inputs', candidate / INIT_RELATIVE
    require(directory.is_dir() and not directory.is_symlink(), 'Public init directory absent or symlinked')
    require(path.exists() and not path.is_symlink(), 'Candidate-local public init absent or symlinked')
    return _file_entry(path, INIT_RELATIVE, deadline)


def verify_init(candidate, environment, deadline=None):
    require(INIT_ENV in environment, 'Android build requires the pre-agent public init seal from environment()')
    expected = json.loads(environment[INIT_ENV])
    require(expected == seal_init(candidate, deadline), 'Protected Android public init bytes/mode/type changed')
    return expected
