"""Independent reader repair; never rewrites retained native or formal reports."""

import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import time

from . import task12_arkts_merged_runtime_v4 as controller
from . import task12_arkts_merged_protocol_v3 as proof

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


def retained_inputs(root, deadline):
    root = Path(root).resolve()
    request = proof.load(root / 'request.json')
    require(request['output'] == str(root), 'original execution root differs')
    require(request['implementation'] == controller.implementation(deadline),
            'original execution source/policy no longer exact')
    raw = proof.load(root / 'native/runtime.native.json')
    config = proof.load(root / 'native-config.json')
    source = Path(request['source'])
    require(raw['source'] == config['source'] == str(source) and raw['bundle'] == config['bundle'] and
            config['contract'] == str(proof.CONTRACT) and raw['nativeProtocol'] == proof.PROTOCOL,
            'source/config/native protocol differs')
    require(proof.file_record(proof.CONTRACT, deadline)['sha256'] == proof.CONTRACT_SHA,
            'canonical contract changed')
    for key, path, sha in (('facts', proof.FACTS, ORIGINAL_FACTS_SHA),
                           ('runner', proof.RUNNER, ORIGINAL_RUNNER_SHA)):
        record = proof.file_record(path, deadline)
        require(record['sha256'] == sha and raw['provenance'][key] == record,
                'original producer identity differs: ' + key)
    for key, path in (('contract', proof.CONTRACT), ('config', root / 'native-config.json')):
        require(raw['provenance'][key] == proof.file_record(path, deadline), 'original provenance changed')
    require(proof.inventory(source, deadline) == request['inventory'], 'actual production source changed')
    verify_archive(request['sourceInputArchive'], request['inventory'], deadline)
    build_path = root / 'application-build/application-build.json'
    build = proof.load(build_path)
    require(raw['compile']['build'] == proof.file_record(build_path, deadline) and
            raw['compile']['hap'] == build['hap'] and build['sourceInventory'] == request['inventory'] and
            build['source'] == str(source) and all(build.get(k) is True for k in
            ('passed', 'productionUnchanged', 'copiedProductionUnchanged', 'temporaryProjectRemoved')),
            'original actual build/source continuity incomplete')
    builder_cleanup = proof.load(proof.checked(build['ownedBuildCleanup'], deadline))
    require(builder_cleanup.get('complete') is True and not Path(build['temporary']).exists(),
            'original compiler cleanup incomplete')
    proof.checked(builder_cleanup['hashLedger'], deadline)
    local = proof.load(root / 'cleanup.json')
    require(local.get('complete') is True and local.get('localOnly') is True and
            build['hap'] in local['binaryHashes'] and build['hap']['path'] in local['removed'] and
            not Path(build['hap']['path']).exists(), 'actual HAP hash-delete receipt missing')
    with Path(local['ledger']).open() as journal:
        ledger = [json.loads(line) for line in journal]
    require(build['hap'] in ledger, 'HAP hash missing from actual cleanup ledger')
    for name in ('worker', 'independent-validation'):
        status = proof.load(root / (name + '.process.json'))
        require(status.get('leaderReaped') is True and status.get('groupGone') is True and
                status.get('unsafe') is False, 'original owned process cleanup incomplete')
    return {'raw': proof.file_record(root / 'native/runtime.native.json', deadline),
            'request': proof.file_record(root / 'request.json', deadline),
            'build': proof.file_record(build_path, deadline), 'archive': request['sourceInputArchive'],
            'source': str(source), 'inputInventory': request['inventory'], 'bundle': config['bundle'],
            'sourceModesProven': False, 'binaryValidation': 'original real hash-before-delete receipt; no recreated binary'}


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
        return {'protocol': 'task12.independent-retained-reader.v1', 'counts': checked['counts'],
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
