"""Freeze the detached Task13 observer limitation without rewriting old runs."""

import argparse
from pathlib import Path
import shutil

from . import task12_13_formal_core as core


def audit(output):
    output = output.resolve()
    if output.exists():
        raise ValueError('Refusing existing withdrawal audit')
    output.mkdir(parents=True)
    native = core.ROOT / 'state_tests/runtime/arkts/native'
    files = [native / name for name in ('Task13Revision5NativeUi.adapter.cjs',
             'Task13Revision5NativeUi.js', 'Task13Revision5NativeUi.install.cjs')]
    sources = []
    for source in files:
        snapshot = output / 'producer-snapshot' / source.relative_to(core.ROOT)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, snapshot)
        sources.append({'original': core.file_record(source), 'snapshot': core.file_record(snapshot)})
    base = core.ROOT / 'experiment_results/runtime_transition_20261020/formal_task12_13_runtime_20261020'
    reports = [base / 'task13-arkts-current-control-protocol-v5' / name for name in
               ('formal.json', 'protocol.json', 'random-base-agent.json')]
    result = {'schemaVersion': 1, 'taskId': '13_user_verification', 'platform': 'arkts',
        'readyCandidate': False, 'semanticAdmissionWithdrawn': True,
        'reason': 'Detached domain instances do not prove original production page entry/wiring.',
        'producerSnapshot': sources, 'retainedReports': [core.file_record(path) for path in reports if path.exists()],
        'affectedCanonicalCases': [row['caseId'] for row in core.load(
            core.ROOT / 'benchmark_tasks/13_user_verification/transitions.json')['cases'][1:9]],
        'findings': [
            {'file': str(files[0]), 'function': 'actionPrefix/runFinalDomain',
             'detail': 'New IdentityStateStore, VerificationGateway, request and presenter are separate from the page-owned instance.'},
            {'file': str(files[1]), 'function': 'runTask13Revision5NativeUi generic final branch',
             'detail': 'Observing the profile boundary does not execute the downstream transition through its page-owned presenter.'}],
        'requiredRepair': 'Capture original production UI method receivers and original gateway/SDK callbacks; recompute state and all invariants from the same source-bound device execution.',
        'oldRawRewritten': False, 'centralOrReadinessEdited': False,
        'domainOnlyDiagnosticsMayBeRetained': True}
    core.write(output / 'withdrawal.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    audit(**vars(parser.parse_args()))
