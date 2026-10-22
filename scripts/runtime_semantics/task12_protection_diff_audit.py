"""Separate frozen Task12 input integrity from shared manifest/code revisions."""

import argparse
from pathlib import Path

from . import task12_13_formal_core as core


def audit(batch, output):
    if output.exists():
        raise ValueError('Refusing existing version audit')
    before = core.load(batch / 'protected-inputs.json')
    changed = []
    for item in before:
        path = Path(item['path'])
        now = core.file_record(path) if path.is_file() else None
        if now != item:
            kind = ('shared_aggregate_manifest' if path.name in {'eval_manifest.json', 'eval_manifest.partial.json'}
                    else 'public_validator_code_version' if path.name in
                    {'run_runtime_transition_matrix.py', 'run_task_runtime_tests.py'} else 'other_protected_file')
            changed.append({'classification': kind, 'before': item, 'current': now})
    run_root = core.ROOT / 'eval_runs/runtime_minimax_m3_20261020_fresh_v2'
    old = core.ROOT / 'experiment_results/runtime_transition_20261020/task12_fresh_v2_evaluator_repair_v1/original/arkts_12_report_room_agent.json'
    current = run_root / 'reports/arkts_12_report_room_agent.json'
    original = core.load(current)
    protected_by_path = {item['path']: item for item in before}
    task_records = []
    for relative in ('reports/arkts_12_report_room_agent.json',
                     'reports/arkts_12_report_room_execution-budget.json',
                     'reports/arkts_12_report_room_isolation-audit.json',
                     'inputs/arkts_12_report_room/af582be814dc85b3e8d288dc0970868cd616115f.tar.gz',
                     'patches/arkts_12_report_room.patch'):
        path = run_root / relative
        now = core.file_record(path)
        task_records.append({'before': protected_by_path[str(path)], 'current': now,
                             'unchanged': now == protected_by_path[str(path)]})
    core.write(output, {'taskId': '12_report_room', 'platform': 'arkts',
        'scope': 'Hash/size version comparison, not a reconstructed JSON textual diff where before bytes were not archived',
        'originalBroadProtectionResult': core.load(batch / 'protocol.json')['protectedOriginalsUnchanged'],
        'changedProtectedFiles': changed, 'taskSpecificFrozenInputVersions': task_records,
        'taskSpecificFrozenInputsUnchanged': all(row['unchanged'] for row in task_records),
        'originalTask12ReportBytesMatchArchivedOriginal': current.read_bytes() == old.read_bytes(),
        'originalTask12ReportSnapshot': core.file_record(old),
        'originalTask12Metrics': {key: original.get(key) for key in ('codeGeneration', 'compile', 'calibration')},
        'originalTask12SemanticCounts': {key: original['semantic'][key] for key in ('passed', 'failed', 'notScored')},
        'allOtherProtectedFilesUnchanged': all(row['classification'] == 'shared_aggregate_manifest' for row in changed),
        'wholeRunUnchangedClaimed': False, 'readinessChanged': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    audit(**vars(parser.parse_args()))
