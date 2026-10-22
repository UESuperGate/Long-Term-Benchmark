"""Collect bounded test logs, task-owned file hashes and actual proof references."""

import argparse
from pathlib import Path
import subprocess

from . import task12_13_formal_core as core

FILES = (
    'scripts/runtime_semantics/Task12ReplayFacts.cjs',
    'scripts/runtime_semantics/Task12ReplayDevice.cjs',
    'scripts/runtime_semantics/task12_arkts_replay_v2.py',
    'scripts/runtime_semantics/task12_replay_review.py',
    'scripts/runtime_semantics/Task12ActualUiFacts.cjs',
    'scripts/runtime_semantics/Task12ActualUiDevice.cjs',
    'scripts/runtime_semantics/task12_actual_ui_protocol.py',
    'scripts/runtime_semantics/task12_actual_ui_continue.py',
    'scripts/runtime_semantics/verify_task12_actual_ui_protocol.py',
    'scripts/runtime_semantics/task12_arkts_runtime_admission.py',
    'scripts/runtime_semantics/task12_protection_diff_audit.py',
    'scripts/runtime_semantics/task13_detached_domain_audit.py',
    'scripts/runtime_semantics/task13_wiring_review_plan.py',
    'scripts/runtime_semantics/task12_current_delivery_audit.py',
    'scripts/test_task12_replay_facts.cjs',
    'scripts/test_task12_arkts_replay_v2.py',
    'scripts/test_task12_replay_review.py',
    'scripts/test_task12_actual_ui_facts.cjs',
    'scripts/test_task12_arkts_runtime_admission.py',
    'scripts/test_task12_live_entry_validation.py',
)
TESTS = ('test_task12_13_android_slice', 'test_task12_13_control', 'test_task12_runtime_closure',
    'test_tasks12_13_formal_scorer', 'test_task13_formal_evidence', 'test_task12_live_entry_validation',
    'test_task13_contract_revision5', 'test_task13_revision5_runtime',
    'test_task13_arkts_revision5_assembly', 'test_task13_arkts_revision5_production_fix',
    'test_task12_arkts_runtime_admission', 'test_task12_arkts_replay_v2', 'test_task12_replay_review')


def audit(output):
    if output.exists():
        raise ValueError('Refusing existing delivery audit')
    output.mkdir(parents=True)
    commands = [['python3', '-B', '-m', 'unittest', *('scripts.' + name for name in TESTS)],
                ['node', 'scripts/test_task12_actual_ui_facts.cjs'],
                ['node', 'scripts/test_task12_replay_facts.cjs']]
    tests = []
    for index, command in enumerate(commands):
        log = output / f'test-{index}.log'
        with log.open('w') as stream:
            result = subprocess.run(command, cwd=core.ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=120)
        tests.append({'command': command, 'exitCode': result.returncode, 'log': core.file_record(log)})
    batch = core.ROOT / 'experiment_results/runtime_transition_20261020/task12_actual_ui_protocol_v3'
    roots = [batch, batch / 'admitted']
    cleanup = [core.file_record(path) for path in batch.rglob('cleanup.json')]
    transient = [str(path) for path in batch.rglob('*') if path.is_dir() and path.name in {'build', '.gradle', '.hvigor'}]
    binaries = [str(path) for path in batch.rglob('*') if path.is_file() and path.suffix.lower() in core.BINARY_SUFFIXES]
    result = {'readyCandidate': False, 'reason': 'Pending new entry-policy and aggregate-version review; no readiness/central edits',
        'implementationAndTestFiles': [core.file_record(core.ROOT / path) for path in FILES],
        'fileCount': len(FILES), 'testCommands': tests,
        'allTestsPassed': all(row['exitCode'] == 0 for row in tests),
        'runtimeProtocol': core.file_record(batch / 'protocol.json'),
        'continuation': core.file_record(batch / 'admitted/continuation.json'),
        'publicProof': core.file_record(batch.parent / 'task12_actual_ui_v3_public_review_v1.json'),
        'protectedVersions': core.file_record(batch.parent / 'task12_actual_ui_v3_protected_versions_v1.json'),
        'currentCleanupReceipts': cleanup, 'sourceCleanupReceipts': [core.file_record(root / 'source-cleanup.json') for root in roots],
        'remainingBinaries': binaries, 'remainingBuildDirectories': transient,
        'historicalMissingHapPolicy': 'Fail closed; no relaxed historical binary checks or fake cleanup receipts',
        'task13ProductionEdited': False,
        'task13ReviewPlan': core.file_record(batch.parent / 'task13_production_wiring_review_v2/REVIEW_PLAN.md')}
    core.write(output / 'manifest.json', result)
    print({'allTestsPassed': result['allTestsPassed'], 'files': len(FILES),
           'remainingBinaries': len(binaries), 'remainingBuildDirectories': len(transient)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    audit(**vars(parser.parse_args()))
