"""Independently bind Task11 replay rows to exact retained device output."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

from . import tasks10_11_runtime_evidence as shared


def require(value, reason):
    if not value:
        raise ValueError('Task11 retained integrity: ' + reason)


def read(item):
    return shared.read_record(item)


def object_bytes(manifest, original):
    matches = [item for item in manifest['files'] if item['original'] == original]
    require(len(matches) == 1 and matches[0].get('originalBytesRestorable') is True,
            'original artifact missing or ambiguous in retention manifest')
    result = gzip.decompress(read(matches[0]['gzip']))
    require(len(result) == original['bytes'] and hashlib.sha256(result).hexdigest() == original['sha256'],
            'retained bytes differ from original artifact')
    return result


def candidate_files(reconstruction):
    """Rebuild only from the actual pre-agent archive and immutable model patch."""
    receipt = json.loads(read(reconstruction['baselineReceipt']))
    require(receipt['capturePhase'] == 'before_agent' and
            all(receipt[key] == reconstruction['baselineArchive'][key] for key in ('path', 'bytes', 'sha256')),
            'missing actual pre-agent baseline')
    read(reconstruction['baselineArchive'])
    read(reconstruction['patch'])
    with tempfile.TemporaryDirectory(prefix='ltb-task11-independent-input-') as temporary:
        root = Path(temporary).resolve()
        with tarfile.open(receipt['path'], 'r:gz') as archive:
            for item in archive.getmembers():
                require((root / item.name).resolve().is_relative_to(root) and
                        (item.isfile() or item.isdir()), 'unsafe baseline archive member')
            archive.extractall(root)

        def git(*args):
            return subprocess.check_output(['git', '-C', str(root), *args], timeout=30).decode().strip()

        git('init', '--quiet')
        git('add', '--force', '--all')
        require(git('write-tree') == receipt['tree'] == reconstruction['baselineTree'],
                'reconstructed pre-agent tree differs')
        git('apply', '--index', '--binary', reconstruction['patch']['path'])
        require(git('write-tree') == reconstruction['candidateTree'], 'actual model candidate tree differs')
        ignored = {'.git', '.hvigor', 'build', 'oh_modules', 'node_modules'}
        result = {}
        for path in sorted(root.rglob('*')):
            if ignored.intersection(path.relative_to(root).parts):
                continue
            require(not path.is_symlink(), 'candidate input symlink is unsupported')
            if path.is_file():
                result[path.relative_to(root).as_posix()] = path.read_bytes()
        return result


def input_digest(files):
    digest = hashlib.sha256()
    for name, data in sorted(files.items()):
        key = name.encode()
        digest.update(str(len(key)).encode() + b':' + key)
        digest.update(str(len(data)).encode() + b':' + data)
    return digest.hexdigest()


def verify_report(path, contract, *, reconstruction=None):
    report = json.loads(Path(path).read_text())
    shared.validate_report(report, contract)
    require(report['taskId'] == '11_room_upgrade_navigation' and report['platform'] == 'arkts',
            'wrong runtime task/platform')
    provenance = report['provenance']
    manifest = json.loads(read(provenance['retainedNativeEvidence']))
    specs = {item['caseId']: item for item in contract['cases']}
    inputs = candidate_files(reconstruction) if reconstruction else None
    if inputs is not None:
        require(report['role'] == 'agent' and
                provenance['productionSourceRoot'] == reconstruction['candidate'] and
                provenance['sourceInventory']['sha256'] == input_digest(inputs) and
                provenance['sourceInventory']['files'] == len(inputs),
                'executed candidate differs from exact pre-agent baseline plus model patch')
    seen, statuses = set(), []
    for row in report['semantic']['cases']:
        execution = json.loads(object_bytes(manifest, row['execution']))
        build = json.loads(object_bytes(manifest, row['build']))
        native = json.loads(object_bytes(manifest, row['nativeResult']))
        require(execution.get('transportCompleted') is True and
                execution.get('candidateAbsentBeforeInstall') is True and
                execution.get('cleanup', {}).get('ownedAppUninstalled') is True and
                execution.get('rows') == [native], 'fresh device execution incomplete')
        require(execution['buildReport']['sha256'] == row['build']['sha256'] and
                execution['rowArtifact']['sha256'] == row['nativeResult']['sha256'] and
                execution['rowArtifact']['bytes'] == row['nativeResult']['bytes'], 'raw build/result binding differs')
        identity = (execution.get('executionNonce'), execution.get('pid'))
        require(isinstance(identity[0], str) and len(identity[0]) == 32 and
                all(char in '0123456789abcdef' for char in identity[0]) and
                isinstance(identity[1], str) and identity[1].isascii() and identity[1].isdecimal() and
                str(int(identity[1])) == identity[1] and int(identity[1]) > 0 and identity not in seen,
                'device execution identity missing, invalid or reused')
        seen.add(identity)
        require(build['source'] == provenance['productionSourceRoot'] and
                build['runtimeCompile'].get('passed') is True and
                all(build.get(key) is True for key in
                    ('productionUnchanged', 'copiedProductionUnchanged', 'temporaryProjectRemoved')),
                'production packaging or cleanup differs')
        if inputs is not None:
            expected = {name: hashlib.sha256(data).hexdigest() for name, data in inputs.items()
                        if name.startswith('entry/src/main/')}
            require({item['path']: item['sha256'] for item in build['production']} == expected,
                    'native package consumed different production input files')
        for key in ('taskId', 'role', 'caseId', 'traceDigest', 'status', 'observed', 'invariantChecks'):
            require(row.get(key) == native.get(key), 'normalized ' + key + ' differs from actual native output')
        require(row['key'] == specs[row['caseId']]['key'] and row['status'] in {'pass', 'fail'} and
                not row.get('entryFailureEvidence'), 'candidate row has incomplete or unsupported semantics')
        points = {item.get('label', item.get('name')): item for item in native['checkpoints']}
        require(len(points) == len(native['checkpoints']), 'duplicate original checkpoint label')
        for point in row['checkpoints']:
            label = point.get('sourceLabel', point['name'])
            require(label in points and json.loads(read(point['actualSnapshot'])) == points[label],
                    'retained checkpoint differs from original native frame')
            actual = points[label]['state']
            production = actual.get('state') if isinstance(actual.get('state'), dict) else actual.get('stateAfter')
            expected = {'production': production, 'controls': actual['controls'],
                        'routeName': actual.get('routeName'), 'windowId': actual.get('windowId'),
                        'viewport': actual.get('viewport')}
            require(point['state'] == expected, 'normalized checkpoint invented production or UI state')
        for command in execution['commands']:
            log_path = Path(row['execution']['path']).parent / command['log']
            matches = [item['original'] for item in manifest['files']
                       if Path(item['original']['path']) == log_path and
                       item['original']['sha256'] == command['sha256']]
            require(len(matches) == 1, 'original device command log unavailable')
            object_bytes(manifest, matches[0])
        statuses.append(row['status'])
    require(len(statuses) == len(contract['cases']) and set(specs) ==
            {row['caseId'] for row in report['semantic']['cases']}, 'incomplete canonical case coverage')
    return {'validated': True, 'passed': statuses.count('pass'), 'failed': statuses.count('fail'),
            'notScored': 0, 'nativeExecutions': len(seen),
            'candidateReconstructedFromPreAgentCapture': inputs is not None,
            'newModelOrDeviceRun': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--contract', required=True, type=Path)
    parser.add_argument('--reconstruction', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Refusing to overwrite an integrity receipt')
    proof = verify_report(args.report, json.loads(args.contract.read_text()),
        reconstruction=json.loads(args.reconstruction.read_text()) if args.reconstruction else None)
    receipt = {'assessment': proof, 'report': shared.record(args.report),
        'contract': shared.record(args.contract), 'verifier': shared.record(Path(__file__)),
        'reconstruction': shared.record(args.reconstruction) if args.reconstruction else None}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(json.dumps(proof))
