"""Independent retained compiler-input checks; never assigns a semantic verdict."""
import base64
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath

from . import task12_13_formal_core as core

MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
PRODUCERS = {
    'scripts/runtime_semantics/task13_arkts_revision5_build.cjs': 'a2339484424ca7f22a1f2c2f86dd4f9b4b4c4c92834600bcbcfa7e653c6aa7b4',
    'scripts/runtime_semantics/arkts_native_device.cjs': '8afa43499654517010a22b8d28629566cec07f4bcf158e3f80a08c78de156473',
    'scripts/runtime_semantics/arkts_native_smoke.cjs': 'a51b119c16b047eb31713b6affffce9d05b9c8e88386df1dc2062c69c0798a59',
    'scripts/runtime_semantics/arkts_native_bundle.cjs': '1dec8dfcbb89b43ff610c2426a10745e229fc3ee46da35d4e87f2b8e15e174da',
    'state_tests/runtime/arkts/native/Task13Revision5NativeUi.install.cjs': '024201ac74ca0d0f1cba017d728be376870ade4d3f78671bfb2a42c4764b5d3b',
    'state_tests/runtime/arkts/native/DeviceTestRunner.ets': '8236528fdefedaa4a2ea45ced1c8d61c17e03947cb688c76d27f7fc2b5808228',
    'state_tests/runtime/arkts/native/Task13Revision5NativeUi.adapter.cjs': '54decbf1f84a01ef5b95bbdfa579b2b01d79e0efadd5279d3c59fb4c42341ce7',
    'state_tests/runtime/arkts/native/Task13Revision5NativeUi.js': '53f7c3ba06f6fb8d4c0b4490ce8c22b17e0aa484590e9009847d0d69972e8841',
    'state_tests/runtime/arkts/native/Task13PageOwnerSdk.js': '499721bb0624774d91a870751dc3bdecae6dcb83aa4217639c37a0697e654945',
}
HELPER = 'scripts/runtime_semantics/Task13CompiledInputs.cjs'
HELPER_SHA = '714a4099569371b3adf6a1ffaac5dc4774d788244f57f5cb6d55911c2a2005b4'
FIXTURES = {
    'Task13Revision5NativeUi.js': '53f7c3ba06f6fb8d4c0b4490ce8c22b17e0aa484590e9009847d0d69972e8841',
    'Task13Revision5NativeUi.d.ts': '4faaa876c51773012aca0897980f986e33242b1300f87697a4f40329cd22e506',
    'Task13Revision5NativeUiSuite.ets': '89e3b8e8eb84f790f04dcd4a42744d8abcf3c24c293c7b9a29cb7e93a435760e',
    'Task13Revision5NativeUiBridge.js': '90569f9cb6ae5fd16e3c529bf2a58105625dfe87de8264c8822f99f2e73e6508',
    'Task13Revision5NativeUiBridge.d.ts': 'e9c911e0c16439e448f3553575d76a03512abf1aaebeb76e450878d8304fbc99',
    'Task16Launch.js': 'ac4c4efea9a23472aed691fe9b7fd98dcb669307e463ce7bf81bb30b9f851c15',
    'Task13LaunchNative.js': '4bf10963a604adf374231d494b82b00a05b0c06264f04b92ada86713061586a1',
    'Task13LaunchNative.d.ts': '3c4f3c68216dae54246af8732e010773546a96fc2e676c1421b868245793f988',
    'Task13PageOwnerSdk.js': '499721bb0624774d91a870751dc3bdecae6dcb83aa4217639c37a0697e654945',
    'Task13UiClosure.js': '21221d7a2f240539c8edfa1fd9ccdbb14c6d4e2938f5f5881078542cbfd1b7c2',
    'Task13Revision5NativeUiAdapter.js': '6dba0497b95ad7feb293c2974da6eceb1cf1aa25951b171369a7e6a3ff895086',
}


def require(value, reason):
    if not value:
        raise ValueError('Task13 compiler-input evidence: ' + reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def checked(record):
    path = Path(record['path'])
    if not path.is_absolute():
        path = core.ROOT / path
    require(not path.is_symlink() and path.resolve().is_relative_to(core.ROOT),
            'artifact outside repository or symlink')
    require(type(record['bytes']) is int and 0 <= record['bytes'] <= MAX_ARCHIVE_BYTES,
            'artifact size outside bound')
    with path.open('rb') as stream:
        data = stream.read(MAX_ARCHIVE_BYTES + 1)
    require(len(data) == record['bytes'] and sha(data) == record['sha256'], 'artifact bytes changed')
    return path, data


def member_path(value):
    require(isinstance(value, str) and value and '\\' not in value, 'invalid archive member')
    path = PurePosixPath(value)
    require(not path.is_absolute() and '..' not in path.parts and
            path.as_posix() == value, 'noncanonical or escaping archive member')
    return path


def validate_snapshot(value):
    require(set(value) == {'root', 'entries', 'payloads'} and
            isinstance(value['root'], str) and Path(value['root']).is_absolute(), 'snapshot structure/root missing')
    require(isinstance(value['entries'], list) and isinstance(value['payloads'], dict), 'snapshot members missing')
    entries, files = {}, {}
    for item in value['entries']:
        path = member_path(item['path'])
        require(item['path'] not in entries, 'duplicate archive member')
        require(type(item['mode']) is int and 0 <= item['mode'] <= 0o7777, 'invalid exact POSIX mode')
        kind = item['kind']
        require(kind in {'file', 'directory', 'symlink'}, 'unsupported input type')
        fields = {'path', 'kind', 'mode'}
        if kind == 'file':
            require(type(item['bytes']) is int and 0 <= item['bytes'] <= MAX_ARCHIVE_BYTES, 'invalid file size')
            data = base64.b64decode(value['payloads'][item['path']], validate=True)
            require(len(data) == item['bytes'] and sha(data) == item['sha256'], 'payload bytes differ')
            files[item['path']] = data
            fields |= {'bytes', 'sha256'}
        elif kind == 'symlink':
            target = item['target']
            require(isinstance(target, str) and target and not target.startswith('/') and '\\' not in target,
                    'absolute/invalid dependency link')
            resolved = posixpath.normpath(posixpath.join(str(path.parent), target))
            require(resolved != '..' and not resolved.startswith('../'), 'dependency link escapes snapshot')
            fields.add('target')
        require(set(item) == fields, 'unbound archive member attributes')
        entries[item['path']] = item
    require(entries.get('.', {}).get('kind') == 'directory', 'snapshot root directory missing')
    for name in entries:
        if name != '.':
            require(entries.get(str(PurePosixPath(name).parent), {}).get('kind') == 'directory',
                    'incomplete parent directory inventory')
    require(set(files) == set(value['payloads']), 'missing/extra payload')
    return entries, files


def load_snapshot(record):
    path, _ = checked(record)
    require(record.get('encoding') == 'gzip-json-with-base64-original-bytes' and
            type(record['uncompressedBytes']) is int and 0 <= record['uncompressedBytes'] <= MAX_ARCHIVE_BYTES,
            'snapshot encoding/decoded bound missing')
    with gzip.open(path, 'rb') as stream:
        data = stream.read(MAX_ARCHIVE_BYTES + 1)
    require(len(data) == record['uncompressedBytes'] and sha(data) == record['uncompressedSha256'],
            'decoded snapshot differs')
    value = json.loads(data, object_pairs_hook=no_duplicate_keys)
    entries, files = validate_snapshot(value)
    require(type(record['entries']) is int and len(entries) == record['entries'], 'snapshot count differs')
    return value, entries, files


def verify(build, inventory):
    """Check v8 retained inputs separately from native assertions and public admission."""
    copy = build['task13InputCopy']
    original, entries, _ = load_snapshot(copy['source'])
    copied, copy_entries, _ = load_snapshot(copy['copied'])
    require(original['root'] == build['source'] == inventory['source'], 'candidate source identity differs')
    require(copy.get('exactNonRootEntries') is True and copy.get('rootDirectoryModeIsNotClaimedEqual') is True and
            copy['rootModes'] == {'source': entries['.']['mode'], 'copied': copy_entries['.']['mode']},
            'copy/root mode attribution differs')
    require({k: v for k, v in entries.items() if k != '.'} ==
            {k: v for k, v in copy_entries.items() if k != '.'}, 'source/copy bytes, type or mode differ')
    require(not any(item['kind'] == 'symlink' for item in entries.values()), 'candidate source link unsupported')
    files = sorted(({'path': name, 'bytes': item['bytes'], 'sha256': item['sha256']}
                    for name, item in entries.items() if item['kind'] == 'file'), key=lambda item: item['path'])
    digest = sha(json.dumps(files, sort_keys=True, separators=(',', ':')).encode())
    require(inventory['files'] == files and inventory['fileCount'] == len(files) and inventory['sha256'] == digest,
            'complete source inventory/digest differs')
    production = [{'path': item['path'], 'sha256': item['sha256']} for item in files
                  if item['path'].startswith('entry/src/main/')]
    require(sorted(build['production'], key=lambda item: item['path']) == production ==
            sorted(build['nativeUIObserver']['production'], key=lambda item: item['path']),
            'complete compiled production set differs')
    targets = build['task13CompilerInputs']
    require([item['target'] for item in targets] == ['default', 'ohosTest'], 'compiler target coverage differs')
    previous, dependency = None, None
    for target in targets:
        require(target['capturedBeforeCompilerInvocation'] is True, 'not a prospective compiler input capture')
        before, compiler_entries, compiler_files = load_snapshot(target['projectInputs'])
        after, _, _ = load_snapshot(target['projectInputsAfter'])
        require(before == after and before['root'] == copied['root'], 'compiler project changed or wrong work root')
        require(previous is None or previous == before, 'different project inputs across compiler targets')
        previous = before
        deps, _, _ = load_snapshot(target['dependencies'])
        require(deps['root'] == str(Path(copied['root']) / 'oh_modules') and
                (dependency is None or dependency == deps), 'dependency snapshots differ across targets')
        dependency = deps
        for item in production:
            require(compiler_entries[item['path']] == entries[item['path']], 'compiler production bytes/mode changed')
        producers = target['producerSources']
        require(producers == target['producerSourcesAfter'] and len(producers) == len(PRODUCERS),
                'producer set changed during compilation')
        actual = {}
        for item in producers + [target['helper']]:
            path, data = checked(item)
            relative = path.resolve().relative_to(core.ROOT).as_posix()
            require(relative not in actual, 'duplicate compiler producer')
            actual[relative] = sha(data)
        require(actual == {**PRODUCERS, HELPER: HELPER_SHA}, 'unreviewed compiler/assertion producer version')
        observer = build['nativeUIObserver']
        require(len(observer['fixtures']) == len(FIXTURES) and
                {item['installedPath']: item['sha256'] for item in observer['fixtures']} ==
                {'entry/src/test/' + name: digest for name, digest in FIXTURES.items()},
                'complete reviewed fixture set differs')
        for fixture in observer['fixtures']:
            require(sha(compiler_files[fixture['installedPath']]) == fixture['sha256'], 'installed fixture differs')
            source = Path(fixture['file']).relative_to(core.ROOT).as_posix()
            if source in PRODUCERS:
                require(fixture.get('sourceSha256', fixture['sha256']) == PRODUCERS[source], 'fixture producer differs')
        for path_key, hash_key in (('bundleFile', 'bundleSha256'), ('suiteFile', 'suiteSha256')):
            relative = Path(observer[path_key]).resolve().relative_to(Path(before['root']).resolve()).as_posix()
            require(sha(compiler_files[relative]) == observer[hash_key], 'generated native bundle/suite differs')
    require(len(build['commands']) == 2 and
            [next(arg for arg in cmd if arg.startswith('module=entry@')) for cmd in build['commands']] ==
            ['module=entry@default', 'module=entry@ohosTest'], 'actual compiler command targets differ')
    return {'verified': True, 'sourceFiles': len(files), 'productionFiles': len(production),
            'compilerTargets': ['default', 'ohosTest'], 'exactProductionModes': True,
            'dependenciesScope': 'before each compiler target; no post-ohosTest dependency immutability claim',
            'sdkToolchainBinaryClosureClaimed': False, 'semanticVerdictAssigned': False, 'readyClaim': False}


def verify_report(path):
    from . import task13_page_owner_verify as runtime
    report = core.load(path)
    retained = report['provenance']['runtimeEvidence']
    build_path, build_bytes = checked(retained['build'])
    _, inventory_bytes = checked(retained['sourceInventory'])
    closure = verify(json.loads(build_bytes), json.loads(inventory_bytes))
    native = runtime.verify(path)
    return {'protocol': 'task13.independent-native-and-compiler-review.v1',
            'report': core.file_record(path), 'build': core.file_record(build_path),
            'reviewer': core.file_record(Path(__file__)),
            'runtimeReviewer': core.file_record(Path(runtime.__file__)),
            'compilerInputs': closure, 'native': native,
            'publicAdmissionChanged': False, 'readyClaim': False}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'refusing to overwrite a review receipt')
    result = verify_report(args.report.resolve())
    core.write(args.output, result)
    print(json.dumps({'output': str(args.output), 'counts': result['native']['counts'],
                      'compilerInputs': result['compilerInputs'], 'readyClaim': False}))
