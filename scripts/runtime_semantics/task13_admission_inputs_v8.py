"""Fail-closed, versioned verification of original archived compiler inputs."""
import base64
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath

from . import task12_13_formal_core as core
from . import task13_page_owner_entry_audit_v8 as policy
from scripts.android_candidate_inputs import verify_archive


def require(value, message):
    if not value:
        raise ValueError('Task13 v8 admission inputs: ' + message)


def record_path(record):
    path = Path(record['path'])
    if not path.is_absolute():
        path = core.ROOT / path
    actual = core.file_record(path)
    require(actual['bytes'] == record['bytes'] and actual['sha256'] == record['sha256'], 'artifact bytes/hash differ')
    return path


def normalized_files(entries):
    seen, files = set(), []
    for item in entries:
        relative = item['path']
        path = PurePosixPath(relative)
        require(isinstance(relative, str) and not path.is_absolute() and '..' not in path.parts and relative not in seen,
                'unsafe/duplicate input path')
        seen.add(relative)
        require(type(item['mode']) is int and 0 <= item['mode'] <= 0o7777 and
                item['kind'] in {'file', 'directory', 'symlink'}, 'mode/link type missing')
        if any(part in core.INVENTORY_EXCLUDES for part in path.parts):
            continue
        require(item['kind'] != 'symlink', 'candidate source contains unsupported symlink')
        if item['kind'] == 'file' and path.suffix.lower() not in core.BINARY_SUFFIXES:
            require(type(item['bytes']) is int and item['bytes'] >= 0, 'byte length invalid')
            files.append({key: item[key] for key in ['path', 'bytes', 'sha256']})
    files.sort(key=lambda item: item['path'])
    return files


def frozen_adapter():
    relative = 'state_tests/runtime/arkts/native/Task13Revision5NativeUi.adapter.cjs'
    manifest = core.load(policy.POLICY)
    require(core.sha256(policy.POLICY) == policy.POLICY_SHA256, 'policy changed')
    expected = next(item for item in manifest['producerHashes'] if item['relativePath'] == relative)
    path = policy.POLICY.parent / 'frozen' / relative
    actual = core.file_record(path)
    require(actual['sha256'] == expected['sha256'] and actual['bytes'] == expected['bytes'], 'frozen adapter changed')
    return path


def unpack(record):
    path = record_path(record)
    plain = gzip.decompress(path.read_bytes())
    require(len(plain) == record['uncompressedBytes'] and hashlib.sha256(plain).hexdigest() == record['uncompressedSha256'],
            'lossless compiler input payload differs')
    data = json.loads(plain)
    require(len(data['entries']) == record['entries'], 'compiler input cardinality differs')
    files = {item['path']: item for item in data['entries'] if item['kind'] == 'file'}
    require(set(files) == set(data['payloads']), 'complete original byte payload set differs')
    require(len({item['path'] for item in data['entries']}) == len(data['entries']), 'duplicate compiled input')
    for name, item in files.items():
        value = base64.b64decode(data['payloads'][name], validate=True)
        require(len(value) == item['bytes'] and hashlib.sha256(value).hexdigest() == item['sha256'], 'compiled original file payload differs')
    return data


def verify_inventory(report_path, declared):
    root = report_path.parent.parent
    summary = core.load(root / 'summary.json')
    phases = [item for item in summary['phases'] if item.get('reportPath') == str(report_path)]
    require(len(phases) == 1 and phases[0]['role'] == core.load(report_path)['role'], 'standalone source/caller identity differs')
    phase = phases[0]
    receipt = phase['rawInput']
    before = core.load(record_path(receipt['before']))
    after = core.load(record_path(receipt['after']))
    require(before == after, 'raw source changed during archive capture')
    verify_archive(record_path(receipt['archive']), before['entries'])
    files = normalized_files(before['entries'])
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    normalized = {'source': phase['source'], 'files': files, 'fileCount': len(files), 'sha256': digest}
    require(normalized == declared and before['candidate'] == declared['source'],
            'normalized actual archive filelist does not equal claimed inventory/digest')
    return normalized, before['entries']


def verify_compilation(build, execution, input_entries):
    expected = {item['path']: item for item in input_entries if item['kind'] == 'file' and item['path'].startswith('entry/src/main/')}
    produced = build['production']
    require(len(produced) == len(expected) and {item['path']: item['sha256'] for item in produced} ==
            {name: item['sha256'] for name, item in expected.items()}, 'compiled production input set is not exact/complete')
    copied = build.get('task13InputCopy')
    require(copied is not None, 'missing actual copied-input modes/link receipt; historical hash-only copy is not admitted')
    original, destination = unpack(copied['source']), unpack(copied['copied'])
    require(original['entries'] == input_entries, 'build original raw inputs differ from archived candidate')
    require([item for item in original['entries'] if item['path'] != '.'] ==
            [item for item in destination['entries'] if item['path'] != '.'],
            'actual copied file/directory/link modes or bytes differ')
    require(copied['rootDirectoryModeIsNotClaimedEqual'] is True, 'temporary root mode difference hidden')
    receipts = build.get('task13CompilerInputs', [])
    require([item['target'] for item in receipts] == ['default', 'ohosTest'], 'missing separate actual compiler input snapshots')
    frozen = core.load(policy.POLICY)
    reviewed = {item['path']: item['sha256'] for item in frozen['producerHashes']}
    adapter = frozen_adapter()
    for receipt in receipts:
        require(receipt['capturedBeforeCompilerInvocation'] is True, 'compiler input receipt is not an execution binding')
        inputs, after = unpack(receipt['projectInputs']), unpack(receipt['projectInputsAfter'])
        left = {item['path']: item for item in inputs['entries']}
        right = {item['path']: item for item in after['entries']}
        for name, item in expected.items():
            require(left.get(name) == item and right.get(name) == item, 'production bytes/mode/type changed inside compilation')
        generated = {item['path']: item['sha256'] for item in build['generatedEvaluator']}
        actual_generated = {item['path']: item['sha256'] for item in inputs['entries'] if item['kind'] == 'file' and
                            item['path'].startswith(('entry/src/test/', 'entry/src/ohosTest/'))}
        require(generated == actual_generated, 'generated evaluator closure is incomplete')
        for fixture in build['nativeUIObserver']['fixtures']:
            require(left[fixture['installedPath']]['sha256'] == fixture['sha256'], 'installed test byte payload differs')
            if fixture['file'] in reviewed:
                require(fixture.get('sourceSha256', fixture['sha256']) == reviewed[fixture['file']], 'test producer differs from reviewed freeze')
        require(receipt['producerSources'] == receipt['producerSourcesAfter'], 'producer changed during compile')
        for source in receipt['producerSources']:
            if source['path'] in reviewed:
                require(source['sha256'] == reviewed[source['path']], 'compiler executed an unreviewed task producer')
        require(any(item['sha256'] == core.sha256(adapter) for item in receipt['producerSources']), 'actual adapter compile binding absent')
        unpack(receipt['dependencies'])
    bindings = execution.get('task13ExecutionSources')
    require(isinstance(bindings, list) and len(bindings) == 3, 'actual runner/package source execution SHA binding missing')
    for item in bindings:
        retained = record_path(item['retained'])
        require(item['original']['sha256'] == core.sha256(retained) and
                item['original']['bytes'] == retained.stat().st_size, 'runner original/retained source binding differs')
        if item['original']['path'] in reviewed:
            require(item['original']['sha256'] == reviewed[item['original']['path']], 'actual runner differs from reviewed producer')
    return {'completeCompiledInputSet': True, 'copiedModesAndLinkTypesVerified': True,
            'frozenAdapter': core.file_record(adapter), 'runnerSources': bindings,
            'originalCanonicalAndProductionUnchanged': True}
