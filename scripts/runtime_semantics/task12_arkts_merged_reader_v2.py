"""Independent reader repair; never rewrites retained native or formal reports."""

import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import time

from . import task12_arkts_merged_runtime_v4 as controller
from . import task12_arkts_merged_protocol_v3 as proof
from . import task12_arkts_merged_reader_v1 as previous

READER = Path(__file__).with_name('Task12MergedNativeReader.v1.cjs')
ORIGINAL_FACTS_SHA = 'f2b3247160b4c2c376ac4fee2be82c2a437081a4735d4d71d3d0d1b8491e8bfb'
ORIGINAL_RUNNER_SHA = '37378135689d6f077bee4d266ea0cfc1359d58a284abf252b2f87e6504103cd1'


def require(value, reason):
    if not value:
        raise ValueError('Task12 independent retained reader: ' + reason)


def verify_archive(record, inventory, deadline):
    path = proof.checked(record, deadline)
    expected = {item['path']: item for item in inventory['files']}
    seen = set()
    with tarfile.open(path, 'r:gz') as stream:
        for member in stream:
            proof.check(deadline)
            require(member.isfile() and member.name in expected and member.name not in seen,
                    'unexpected/duplicate/non-regular archived source')
            seen.add(member.name)
            digest, size = hashlib.sha256(), 0
            with stream.extractfile(member) as incoming:
                for block in iter(lambda: incoming.read(1024 * 1024), b''):
                    proof.check(deadline)
                    digest.update(block)
                    size += len(block)
            item = expected[member.name]
            require(size == item['bytes'] == member.size and digest.hexdigest() == item['sha256'],
                    'archived source bytes differ')
    require(seen == set(expected), 'archived source set incomplete')


def binary_free_history(root, raw, build, config, deadline):
    hap = build['hap']
    require(raw['compile']['hap'] == hap and config['hap'] == hap['path'] and
            config['buildReport'] == str(root / 'application-build/application-build.json') and
            config['output'] == str(root / 'native'), 'build/native/config HAP path/bytes/hash differ')
    require(not Path(hap['path']).exists() and not Path(hap['path']).is_symlink(),
            'hashed-deleted binary is present or substituted')
    local = proof.load(root / 'cleanup.json')
    ledger_path = Path(local['ledger'])
    require(ledger_path.resolve() == root / 'cleanup.hashes.jsonl', 'binary deletion ledger path differs')
    with ledger_path.open() as stream:
        ledger = []
        for line in stream:
            proof.check(deadline)
            item = json.loads(line)
            require(root in Path(item['path']).parents, 'unowned deletion ledger entry')
            ledger.append(item)
    require(local.get('complete') is True and local.get('localOnly') is True and
            local['removed'] == [item['path'] for item in ledger] and
            ledger.count(hap) == 1 and local['binaryHashes'].count(hap) == 1,
            'actual HAP deletion path/size/SHA is not exact in both receipts')
    compiler_cleanup = proof.load(proof.checked(build['ownedBuildCleanup'], deadline))
    compiler_ledger = proof.checked(compiler_cleanup['hashLedger'], deadline)
    work = Path(build['temporary'])
    require(work.parent == root / 'owned-temporary' and compiler_cleanup['root'] == str(work) and
            compiler_cleanup.get('complete') is True and not work.exists(), 'compiler ownership/removal differs')
    entries = []
    with compiler_ledger.open() as stream:
        for line in stream:
            proof.check(deadline)
            item = json.loads(line)
            require(work in Path(item['path']).parents, 'compiler ledger escaped owned tree')
            if 'retained' in item:
                proof.checked(item['retained'], deadline)
            entries.append(item)
    require(len(entries) == compiler_cleanup['filesRemoved'] and
            compiler_cleanup['binaryHashes'] == [item for item in entries if
                Path(item['path']).suffix.lower() in proof.BINARIES and 'sha256' in item] and
            any(item.get('bytes') == hap['bytes'] and item.get('sha256') == hap['sha256'] and
                Path(item['path']).suffix == '.hap' for item in compiler_cleanup['binaryHashes']),
            'compiler actual HAP hash ledger differs')
    installs = [item for item in raw['diagnostics']['commands'] if item['args'][0] == 'install']
    ids = {row['caseRunId'] for row in raw['semantic']['cases']}
    require(len(installs) == 10 and len(ids) == 10 and
            {item['caseRunId'] for item in installs} == ids, 'ten independent actual installs missing')
    for item in installs:
        proof.check(deadline)
        require(item['args'] == ['install', '-r', hap['path']] and item['exitCode'] == 0,
                'actual install did not consume the bound binary')
        log = proof.checked(item['log'], deadline).read_text()
        require('App install path:' + hap['path'] in log and 'install bundle successfully' in log,
                'actual install log does not confirm the same binary path')
    return {'binaryBytesReverifiedNow': False, 'executionTimePreinstallDriverHashChecked': True,
            'basis': 'frozen actual driver hashes HAP before install; original actual HDC logs; exact deletion ledgers',
            'hap': hap, 'installCount': len(installs), 'cleanupLedger': proof.file_record(ledger_path, deadline)}


def retained_inputs(root, deadline):
    result = previous.retained_inputs(root, deadline)
    root = Path(root).resolve()
    raw = proof.load(root / 'native/runtime.native.json')
    config = proof.load(root / 'native-config.json')
    build = proof.load(root / 'application-build/application-build.json')
    result['binaryFreeHistory'] = binary_free_history(root, raw, build, config, deadline)
    result['readerDependency'] = proof.file_record(Path(previous.__file__), deadline)
    return result


def recompute(*, retained_root, output, deadline):
    def prepare(root, clock):
        bound = retained_inputs(retained_root, clock.work_deadline)
        return {'bound': bound, 'reader': proof.file_record(READER, clock.work_deadline),
                'readerModule': proof.file_record(Path(__file__), clock.work_deadline)}

    def command(request_path):
        request = proof.load(request_path)
        return [controller.NODE, '-e', proof.NODE_VERIFY, str(READER), request['bound']['raw']['path'],
                str(proof.CONTRACT), request['bound']['bundle'], str(Path(retained_root).resolve() / 'native')]

    def finalize(root, request, clock, launch):
        checked = proof.load(root / 'worker.log')
        require(checked.get('validated') is True and checked['counts']['notScored'] == 0,
                'independent native recomputation incomplete')
        require(retained_inputs(retained_root, clock.work_deadline) == request['bound'] and
                proof.file_record(READER, clock.work_deadline) == request['reader'] and
                proof.file_record(Path(__file__), clock.work_deadline) == request['readerModule'],
                'reader or retained input changed during recomputation')
        return {'protocol': 'task12.independent-retained-reader.v2', 'counts': checked['counts'],
                'assessment': checked, 'original': request['bound'], 'reader': request['reader'],
                'oldFormalEnvelopeUnmodified': True, 'freshNativeRun': False,
                'publicAdmitted': False, 'publicationEligible': False}

    return controller._supervise(Path(output).with_suffix('.reader-evidence'), deadline,
            prepare, command, finalize, report_path=output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retained-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--original-deadline-epoch-ms', type=int, required=True)
    args = parser.parse_args()
    deadline = time.monotonic() + max(0, args.original_deadline_epoch_ms / 1000 - time.time())
    recompute(retained_root=args.retained_root, output=args.output, deadline=deadline)


if __name__ == '__main__':
    main()
