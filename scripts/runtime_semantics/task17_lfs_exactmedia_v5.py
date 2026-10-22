"""Exact immutable non-consumer media preparation, not semantic scoring."""
import base64
import hashlib
import json
import os
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / 'experiment_results/runtime_transition_20261020/task17_android_connected_roomflow_v3/lfs-exactmedia-v5/policy.json'
POLICY_SHA256 = 'ce348292f43701fe2235bbc7fd41132148f31835437f5b75e7ccb3ee836af41c'
RAW_TREE = POLICY.with_name('immutable-raw-tree.json')
GUARD = ROOT / 'scripts/runtime_semantics/task17_lfs_input_guard_v5.init.gradle'
GUARD_SHA256 = '66fab3ea282e74b16a5289909f2de08fc0a7d69b2a385af7d631b5686ee9db6d'


def require(value, reason):
    if not value:
        raise ValueError('Task17 exact-media LFS: ' + reason)


def load_policy():
    require(hashlib.sha256(GUARD.read_bytes()).hexdigest() == GUARD_SHA256, 'task-input guard changed')
    raw = POLICY.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == POLICY_SHA256, 'policy SHA mismatch')
    policy = json.loads(raw)
    require(policy['protocol'] == 'task17.exact-nonconsumer-lfs.v5', 'policy identity')
    exclusions = policy['exclusions']
    require(len(exclusions) == len({row['path'] for row in exclusions}) == 123 and
            len({row['lfsOidSha256'] for row in exclusions}) == 114, 'exact inventory cardinality')
    require(all(row['category'] in {'immutable-release-screenshot', 'separate-paparazzi-reference-image'}
                and row['gitMode'] == '100644' and '/src/main/' not in row['path'] for row in exclusions),
            'unknown category or production resource')
    raw_tree = RAW_TREE.read_bytes()
    require(hashlib.sha256(raw_tree).hexdigest() == policy['rawTree']['sha256'] and
            len(raw_tree) == policy['rawTree']['bytes'], 'raw tree manifest changed')
    tree = json.loads(raw_tree)
    require(tree['commit'] == policy['commit'] and tree['tree'] == policy['tree'], 'immutable tree mismatch')
    return policy, tree


def verify_raw_consumers(source, policy, tree, remaining, deadline):
    """Task11-style RAW Git blob verification, never clean-filter equality.

    The exception is allowed only with this complete immutable source and these
    exact original runtime fixtures. Modified/additional consumers cannot inherit
    it merely because a missing pointer has a familiar filename/extension.
    """
    source = Path(source)
    seen, expected, gitlinks = set(), {}, set()
    for row in tree['entries']:
        path = row['path']
        require(not Path(path).is_absolute() and '..' not in Path(path).parts, 'unsafe manifest path')
        if row['kind'] == 'commit' and row['gitMode'] == '160000':
            gitlinks.add(path)
        else:
            require(row['kind'] == 'blob' and row['gitMode'] in {'100644', '100755', '120000'}, 'unsupported raw input')
            expected[path] = row
    for directory, dirs, files in os.walk(source, followlinks=False):
        remaining(deadline)
        relative_dir = Path(directory).relative_to(source)
        if relative_dir.as_posix() in gitlinks:
            require(not dirs and not files, 'unexpected materialized Gitlink consumer')
            continue
        if relative_dir == Path('.'):
            dirs[:] = [name for name in dirs if name != '.git']
            files = [name for name in files if name != '.git']
        symlink_dirs = [name for name in dirs if (Path(directory) / name).is_symlink()]
        dirs[:] = [name for name in dirs if name not in symlink_dirs]
        for name in sorted(files + symlink_dirs):
            remaining(deadline)
            path = Path(directory) / name
            relative = path.relative_to(source).as_posix()
            require(relative in expected and relative not in seen, 'unknown source consumer: ' + relative)
            entry = expected[relative]
            info = path.lstat()
            if entry['gitMode'] == '120000':
                require(stat.S_ISLNK(info.st_mode) and (path.parent / os.readlink(path)).resolve().is_relative_to(source.resolve()),
                        'unsafe source link')
                raw = os.fsencode(os.readlink(path))
                digest = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
                size = len(raw)
            else:
                require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) ==
                        (0o755 if entry['gitMode'] == '100755' else 0o644), 'raw source mode/type mismatch: ' + relative)
                digest = hashlib.sha1(b'blob ' + str(info.st_size).encode() + b'\0')
                with path.open('rb') as stream:
                    while chunk := stream.read(1024 * 1024):
                        remaining(deadline)
                        digest.update(chunk)
                digest, size = digest.hexdigest(), info.st_size
            require(digest == entry['gitBlob'] and size == entry['bytes'], 'raw Git blob mismatch: ' + relative)
            seen.add(relative)
    require(seen == set(expected), 'incomplete immutable raw source')
    for entry in policy['originalFixturePins']:
        remaining(deadline)
        path = Path(entry['path'])
        require(not path.is_symlink() and stat.S_IMODE(path.stat().st_mode) == entry['mode'], 'fixture mode/type changed')
        raw = path.read_bytes()
        require(len(raw) == entry['bytes'] and hashlib.sha256(raw).hexdigest() == entry['sha256'],
                'runtime fixture consumer changed: ' + path.name)
    return {'rawGitBlobCount': len(seen), 'exactImmutableConsumersVerified': True,
            'fixturePinsVerified': len(policy['originalFixturePins']), 'commit': policy['commit'],
            'tree': policy['tree'], 'gitCleanFiltersUsedForEquality': False, 'externalGitlinksMaterialized': False}


def match_pointer(row, policy):
    matches = [entry for entry in policy['exclusions'] if entry['path'] == row['relativePath']]
    if not matches:
        return None
    entry = matches[0]
    raw = base64.b64decode(row['pointerRawBase64'], validate=True)
    require(row['oidSha256'] == entry['lfsOidSha256'] and row['payloadBytes'] == entry['payloadBytes'] and
            raw == base64.b64decode(entry['pointerRawBase64'], validate=True) and
            hashlib.sha256(raw).hexdigest() == entry['pointerSha256'] and
            hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == entry['gitBlob'] and
            row['pointerRecord']['mode'] == 0o644 and row['pointerRecord']['bytes'] == len(raw),
            'whitelisted path has changed pointer/blob/mode')
    return entry
