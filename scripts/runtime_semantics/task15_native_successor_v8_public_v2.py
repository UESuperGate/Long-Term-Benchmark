"""OFFLINE public-compatibility successor. No native/semantic policy change."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import time
import types

from . import task15_native_successor_runner_v8 as previous

ROOT, TASK, core, artifacts = previous.ROOT, previous.TASK, previous.core, previous.artifacts
PUBLIC = ROOT / 'scripts/run_runtime_transition_matrix.py'
PUBLIC_SHA = '25525fe1713d3194bbd8c2bf694800967b54fb4e5acf318e763dba82bfa4c7cc'
OLD_PUBLIC_SHA = '6ceed2ee265a4eaeb59f13f4c8a4befbbc27f5c04cd2b9277cff0ab2f0a9d626'
ARCHIVE = ROOT / ('experiment_results/runtime_transition_20261021/'
    'task12_merged_public_registration_v1/before-public-registration-source.tar.gz')
PROTOCOL = 'task15.native-v8.current-public-compatibility.v2'


def archived_sources():
    expected = {'scripts/run_runtime_transition_matrix.py', 'scripts/runtime_semantics/task12_arkts_runtime_admission.py'}
    with tarfile.open(ARCHIVE, 'r:gz') as archive:
        members = archive.getmembers()
        metadata = {str(Path(name).with_name('._'+Path(name).name)) for name in expected}
        artifacts.require({item.name for item in members} == expected | metadata and len(members) == len(expected | metadata) and
            all(item.isfile() for item in members), 'Unknown public lineage archive members')
        result = {item.name: archive.extractfile(item).read() for item in members if item.name in expected}
    artifacts.require(hashlib.sha256(result['scripts/run_runtime_transition_matrix.py']).hexdigest() == OLD_PUBLIC_SHA,
        'Archived public bytes do not match the old freeze')
    return result


def require_current_public():
    artifacts.require(core.sha256(PUBLIC) == PUBLIC_SHA, 'New public revision requires a new compatibility suffix')
    for name, expected in previous.old.PUBLIC_DEPS.items():
        artifacts.require(core.sha256(Path(__file__).with_name(name)) == expected, 'Task15 public boundary dependency changed')


def historical_freeze(record):
    """Historical snapshot verification, never rebind/relabel the old proof."""
    value = json.loads(artifacts.bound(record))
    artifacts.require(value['publicSha256'] == OLD_PUBLIC_SHA, 'Not the predecessor public freeze')
    archived = archived_sources()
    for item in value['files']:
        snapshot = artifacts.bound(item['snapshot'])
        artifacts.require(len(snapshot) == item['bytes'] and hashlib.sha256(snapshot).hexdigest() == item['sha256'],
            'Historical source snapshot/hash changed')
        path = Path(item['path'])
        if path == PUBLIC:
            artifacts.require(snapshot == archived['scripts/run_runtime_transition_matrix.py'], 'Historical public source mismatch')
        else:
            artifacts.require(path.is_file() and not path.is_symlink() and path.read_bytes() == snapshot,
                'Unexpected non-public predecessor source drift: '+str(path))
    return value


def verify_historical_preparation(root):
    # Scoped function derivation; neither the frozen module nor any globals are
    # mutated. This function is explicitly NOT current-runtime readiness proof.
    namespace = types.SimpleNamespace(**{**vars(previous.old), 'check_freeze': historical_freeze})
    return previous.producer.clone(previous.verify_preparation, old=namespace)(root)


def freeze(root):
    require_current_public()
    archived_sources()
    upstream = previous.producer.clone(previous.old.freeze, PUBLIC_SHA=PUBLIC_SHA)
    scoped = types.SimpleNamespace(**{**vars(previous.old), 'freeze': upstream})
    record = previous.producer.clone(previous.freeze, old=scoped)(root)
    value = json.loads(artifacts.bound(record))
    records = {item['path']: item for item in value['files']}
    for path in (Path(__file__), ROOT / 'scripts/audit_task15_native_v8_public_v2.py',
                 ROOT / 'scripts/runtime_semantics/test_task15_native_v8_public_v2.py',
                 ROOT / 'scripts/runtime_semantics/task12_arkts_runtime_admission.py',
                 ROOT / 'scripts/runtime_semantics/task12_merged_pipeline_v1.py'):
        target = Path(root) / 'frozen-sources' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        records[str(path)] = {'path':str(path),'bytes':path.stat().st_size,'sha256':core.sha256(path),
            'snapshot':artifacts.artifact(target)}
    value.update(compatibilityProtocol=PROTOCOL, files=[records[key] for key in sorted(records)],
        publicLineage={'beforeSha256':OLD_PUBLIC_SHA,'afterSha256':PUBLIC_SHA,
            'beforeSourceArchive':artifacts.artifact(ARCHIVE),'nativeSemanticsChanged':False})
    core.write(Path(root) / 'source-freeze.json',value)
    return artifacts.artifact(Path(root) / 'source-freeze.json')


def prepare(**kwargs):
    require_current_public()
    return previous.producer.clone(previous.prepare, freeze=freeze)(**kwargs)


def verify_preparation(root):
    require_current_public()
    result = previous.verify_preparation(root)
    index = core.load(Path(root) / 'full-native-index.json')
    value = json.loads(artifacts.bound(index['freeze']))
    artifacts.require(value['compatibilityProtocol'] == PROTOCOL and value['publicSha256'] == PUBLIC_SHA and
        value['publicLineage']['beforeSha256'] == OLD_PUBLIC_SHA and
        value['publicLineage']['afterSha256'] == PUBLIC_SHA, 'Wrong compatibility source freeze')
    artifacts.bound(value['publicLineage']['beforeSourceArchive'])
    return {**result,'compatibilityProtocol':PROTOCOL,'currentPublicSha256':PUBLIC_SHA}


def assemble(root):
    verify_preparation(root)
    return previous.assemble(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--verify-preparation',type=Path)
    args = parser.parse_args()
    if args.verify_preparation:
        result = verify_preparation(args.verify_preparation)
    else:
        if not (args.source and args.output): parser.error('--source/--output required')
        # File generation only. This is not a reset of any scoring/repair epoch.
        prepare(source=args.source,output=args.output,deadline=time.monotonic()+300)
        result = verify_preparation(args.output)
        report = assemble(args.output)
        core.write(args.output / 'unexecuted-report.json',report)
    print(json.dumps(result,indent=2))


if __name__ == '__main__':main()
