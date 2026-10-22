"""Prospective production source bytes, types and POSIX modes; no SDK cache inputs."""

import hashlib
import json
import os
from pathlib import Path
import stat
import tarfile

from . import task12_arkts_merged_protocol_v3 as proof

POLICY = 'task12.production-inputs.bytes-type-mode.no-symlinks.v1'


def require(value, reason):
    if not value:
        raise ValueError('Task12 production inputs: ' + reason)


def digest_stream(stream, deadline):
    digest, size = hashlib.sha256(), 0
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        proof.check(deadline)
        digest.update(block)
        size += len(block)
    proof.check(deadline)
    return {'bytes': size, 'sha256': digest.hexdigest()}


def regular(path):
    # O_NONBLOCK prevents a raced FIFO from blocking before its fstat check.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'non-regular production file')
        return os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise


def inventory(source, deadline):
    source = Path(source).absolute()
    require(not source.is_symlink() and source.is_dir(), 'source root must be a real directory')
    source = source.resolve()
    records = []
    pending = [source]
    while pending:
        proof.check(deadline)
        path = pending.pop()
        st = path.lstat()
        relative = path.relative_to(source).as_posix()
        item = {'path': relative, 'mode': stat.S_IMODE(st.st_mode)}
        require(not stat.S_ISLNK(st.st_mode), 'source symlinks unsupported: ' + relative)
        if stat.S_ISDIR(st.st_mode):
            item['type'] = 'directory'
            pending.extend(sorted((p for p in path.iterdir() if p.name not in proof.EXCLUDES), reverse=True))
        else:
            require(stat.S_ISREG(st.st_mode), 'non-regular production input: ' + relative)
            item['type'] = 'file'
            with regular(path) as stream:
                item.update(digest_stream(stream, deadline))
                require(stat.S_IMODE(os.fstat(stream.fileno()).st_mode) == item['mode'], 'source mode raced')
        records.append(item)
    records.sort(key=lambda item: item['path'])
    encoded = json.dumps(records, sort_keys=True, separators=(',', ':')).encode()
    return {'source': str(source), 'policy': POLICY, 'entries': records,
            'sha256': hashlib.sha256(encoded).hexdigest(),
            'scope': 'production tree only; generated/cache directories excluded by explicit policy',
            'excludedDirectoryNames': sorted(proof.EXCLUDES), 'symlinkPolicy': 'reject, never follow'}


def copy(source, target, expected, deadline):
    source, target = Path(source).resolve(), Path(target)
    require(inventory(source, deadline) == expected, 'source changed before materialization')
    target.mkdir(parents=True, exist_ok=False)
    for item in expected['entries']:
        proof.check(deadline)
        if item['path'] == '.':
            continue
        path = target / item['path']
        if item['type'] == 'directory':
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            with regular(source / item['path']) as incoming, path.open('xb') as outgoing:
                for block in iter(lambda: incoming.read(1024 * 1024), b''):
                    proof.check(deadline)
                    outgoing.write(block)
            path.chmod(item['mode'])
    for item in reversed(expected['entries']):
        if item['type'] == 'directory':
            (target / item['path']).chmod(item['mode'])
    result = inventory(target, deadline)
    require(result['entries'] == expected['entries'] and inventory(source, deadline) == expected,
            'source copy bytes/type/modes differ')
    return result


def archive(source, output, expected, deadline):
    require(inventory(source, deadline) == expected, 'source changed before archive')
    with tarfile.open(output, 'x:gz') as stream:
        for item in expected['entries']:
            proof.check(deadline)
            info = tarfile.TarInfo(item['path'])
            info.mode = item['mode']
            info.uid = info.gid = info.mtime = 0
            if item['type'] == 'directory':
                info.type = tarfile.DIRTYPE
                stream.addfile(info)
            else:
                info.size = item['bytes']
                with regular(Path(source) / item['path']) as incoming:
                    stream.addfile(info, incoming)
    require(inventory(source, deadline) == expected, 'source changed while archiving')
    record = proof.file_record(output, deadline)
    verify_archive(record, expected, deadline)
    return record


def verify_archive(record, expected, deadline):
    path = proof.checked(record, deadline)
    entries = {item['path']: item for item in expected['entries']}
    seen = set()
    with tarfile.open(path, 'r:gz') as stream:
        for member in stream:
            proof.check(deadline)
            require(member.name in entries and member.name not in seen, 'archive member duplicate/extra')
            seen.add(member.name)
            item = entries[member.name]
            require(member.mode == item['mode'] and (member.isdir() if item['type'] == 'directory' else member.isfile()),
                    'archive type/mode differs; links unsupported')
            if item['type'] == 'file':
                with stream.extractfile(member) as incoming:
                    value = digest_stream(incoming, deadline)
                require(value == {k: item[k] for k in ('bytes', 'sha256')}, 'archive source bytes differ')
    require(seen == set(entries), 'archive missing production inputs')
    return True
