"""Independent admission primitives for the unregistered merged Task12 protocol.

No historical report, candidate role, or known implementation hash is an oracle.
This module does not register a public policy or promote readiness.
"""

import hashlib
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / 'benchmark_tasks/12_report_room/transitions.json'
CONTRACT_SHA = '365670eba603c9762842a836b3b5385c37f925abdf3e88cc1d3d355b3f64531e'
PROTOCOL = 'task12.merged-native.v4'
RUNNER = Path(__file__).with_name('Task12MergedNativeDevice.hint-profile-v4.cjs')
FACTS = Path(__file__).with_name('Task12MergedNativeFacts.hint-profile-v4.cjs')
JSON5 = Path('/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin/node_modules/json5/lib/index.js')
EXCLUDES = {'.git', 'node_modules', 'oh_modules', 'build', '.hvigor', '.gradle'}
BINARIES = {'.hap', '.apk', '.aab', '.apks', '.har', '.app', '.abc', '.so'}


def check(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError('Task12 merged original deadline exhausted')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True)
        stream.write('\n')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def file_record(path, deadline):
    check(deadline)
    digest, size = hashlib.sha256(), 0
    with path.open('rb') as stream:
        while True:
            check(deadline)
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
            size += len(block)
    check(deadline)
    return {'path': str(path.resolve()), 'bytes': size, 'sha256': digest.hexdigest()}


def checked(record, deadline):
    path = Path(record['path'])
    if path.is_symlink() or file_record(path, deadline) != record:
        raise ValueError('Task12 merged bound artifact differs: ' + str(path))
    return path


def inventory(source, deadline):
    source = source.resolve()
    if not source.is_dir():
        raise ValueError('Candidate source is not a directory')
    files = []
    # Walk with pruning: never recurse through excluded caches or source symlinks.
    import os
    for directory, directories, names in os.walk(source, followlinks=False):
        check(deadline)
        directories[:] = sorted(name for name in directories if name not in EXCLUDES)
        for name in directories + sorted(names):
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError('Candidate source symlink unsupported: ' + str(path))
            if path.is_file() and path.suffix.lower() not in {'.hap', '.apk', '.aab', '.apks'}:
                files.append({**file_record(path, deadline), 'path': path.relative_to(source).as_posix()})
    files.sort(key=lambda item: item['path'])
    encoded = json.dumps(files, sort_keys=True, separators=(',', ':')).encode()
    return {'source': str(source), 'fileCount': len(files), 'sha256': hashlib.sha256(encoded).hexdigest(), 'files': files}


def producer_records(deadline):
    paths = [RUNNER, FACTS, Path(__file__), Path(__file__).with_name('task12_arkts_merged_protocol_v4.py'), Path(__file__).with_name('task12_arkts_merged_protocol_v1.py'),
             Path(__file__).with_name('task12_arkts_merged_runtime_v1.py'),
             Path(__file__).with_name('task12_arkts_merged_build_v2.py'),
             Path(__file__).with_name('task12_merged_inputs_v1.py'),
             Path(__file__).with_name('task12_arkts_merged_protocol_v3.py')]
    paths.extend(Path(__file__).with_name(name) for name in (
        'task12_13_runtime_support.py', 'task12_13_formal_core.py', 'task14_15_formal_core.py'))
    paths.extend(sorted(JSON5.parent.glob('*.js')))
    paths.append(JSON5.parent.parent / 'package.json')
    return [file_record(path, deadline) for path in paths]


def validate_envelope(raw, *, source, source_inventory, build_path, config_path, deadline):
    """Bind new raw to this invocation before bounded independent Node recomputation."""
    check(deadline)
    if raw.get('nativeProtocol') != PROTOCOL or raw.get('source') != str(source.resolve()):
        raise ValueError('Wrong merged protocol/source; legacy reports cannot be relabeled')
    config = load(config_path)
    if config['source'] != str(source.resolve()) or raw['bundle'] != config['bundle'] or \
            raw['executionConfig']['port'] != config['port'] or raw['compile']['hap']['path'] != config['hap'] or \
            config['contract'] != str(CONTRACT):
        raise ValueError('Raw app/service/source config binding differs')
    if file_record(CONTRACT, deadline)['sha256'] != CONTRACT_SHA:
        raise ValueError('Canonical Task12 contract differs')
    for name, path in (('runner', RUNNER), ('facts', FACTS), ('contract', CONTRACT), ('config', config_path)):
        if raw['provenance'][name] != file_record(path, deadline):
            raise ValueError('Raw producer/config/contract binding differs: ' + name)
    if raw['compile']['build'] != file_record(build_path, deadline):
        raise ValueError('Raw build binding differs')
    build = load(build_path)
    if build.get('source') != str(source.resolve()) or any(build.get(key) is not True for key in
            ('passed', 'productionUnchanged', 'copiedProductionUnchanged', 'temporaryProjectRemoved')):
        raise ValueError('Production HAP build/source continuity incomplete')
    if raw['compile']['hap'] != build['hap']:
        raise ValueError('Raw installed binary differs from build')
    cleanup = load(checked(build['ownedBuildCleanup'], deadline))
    work = Path(build['temporary'])
    if not work.is_absolute() or work.parent.resolve() != (build_path.parent.parent / 'owned-temporary').resolve() or \
            cleanup['root'] != str(work) or cleanup.get('complete') is not True or work.exists():
        raise ValueError('Owned compiler temporary cleanup incomplete or wrong root')
    ledger = checked(cleanup['hashLedger'], deadline)
    removed, binaries = 0, []
    with ledger.open() as stream:
        for line in stream:
            check(deadline)
            item = json.loads(line)
            removed += 1
            if work not in Path(item['path']).parents:
                raise ValueError('Cleanup ledger contains an unowned path')
            if 'retained' in item:
                checked(item['retained'], deadline)
            if Path(item['path']).suffix.lower() in BINARIES and 'sha256' in item:
                binaries.append(item)
    if cleanup['filesRemoved'] != removed or cleanup['binaryHashes'] != binaries:
        raise ValueError('Owned compiler cleanup ledger/aggregate differs')
    # Before hash-cleanup, prove the exact actual HAP bytes still match.
    checked(build['hap'], deadline)
    if inventory(source, deadline) != source_inventory:
        raise ValueError('Candidate changed during build/runtime')
    return {'protocol': PROTOCOL, 'sourceInventory': source_inventory, 'build': file_record(build_path, deadline)}


NODE_VERIFY = r"""
const fs=require('node:fs'),crypto=require('node:crypto');
const F=require(process.argv[1]);
const root=process.argv[5];
const path=require('node:path');
const bytes=r=>{
  const resolved=fs.realpathSync(r.path);
  if(!resolved.startsWith(root+path.sep))throw Error('Raw artifact escapes this execution root');
  const b=fs.readFileSync(resolved);
  if(b.length!==r.bytes||crypto.createHash('sha256').update(b).digest('hex')!==r.sha256)throw Error('Raw artifact hash differs');
  return b;
};
const raw=JSON.parse(fs.readFileSync(process.argv[2]));
const result=F.verifyNative(raw,JSON.parse(fs.readFileSync(process.argv[3])),
  r=>JSON.parse(bytes(r)),process.argv[4],r=>bytes(r).toString('utf8'));
process.stdout.write(JSON.stringify(result));
"""
