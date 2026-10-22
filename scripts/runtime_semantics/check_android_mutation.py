#!/usr/bin/env python3
"""Opt-in production mutation check; temporary source copies never alter goldens."""

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from android_runner import ROOT, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    task_id = '12_report_room'
    task = json.loads((ROOT / 'benchmark_tasks' / task_id / 'task.json').read_text())
    config = json.loads((ROOT / 'state_tests/runtime/android' / task_id / 'adapter.json').read_text())
    repo = ROOT / '_sources/element-x-android'
    target = 'features/reportroom/impl/src/main/kotlin/io/element/android/features/reportroom/impl/ReportRoom.kt'
    with tempfile.TemporaryDirectory(prefix='ltb-mutation-') as directory:
        candidate = Path(directory) / 'candidate'
        candidate.mkdir()
        (candidate / 'gradlew').touch()
        for relative in config['sources']:
            source = subprocess.check_output(['git', '-C', str(repo), 'show', f"{task['android']['finalCommit']}:{relative}"])
            path = candidate / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source)
        baseline = run(task_id, 'final', candidate, Path(directory) / 'baseline.json', 180)
        path = candidate / target
        original = path.read_text()
        marker = 'if (shouldLeave) {'
        if original.count(marker) != 1:
            raise RuntimeError('Production mutation site is no longer unique')
        mutated = original.replace(marker, 'if (false) {')
        path.write_text(mutated)
        mutant = run(task_id, 'final', candidate, Path(directory) / 'mutant.json', 180)
        case_id = 'rr_state_005_report_then_leave'
        before = next(row for row in baseline['semantic']['cases'] if row['caseId'] == case_id)
        after = next(row for row in mutant['semantic']['cases'] if row['caseId'] == case_id)
        result = {
            'taskId': task_id, 'caseId': case_id,
            'mutation': 'Disable the production leave branch after successful reporting',
            'source': target, 'sourceCommit': task['android']['finalCommit'],
            'originalSha256': hashlib.sha256(original.encode()).hexdigest(),
            'mutatedSha256': hashlib.sha256(mutated.encode()).hexdigest(),
            'baseline': before, 'mutant': after,
            'detected': before['status'] == 'pass' and after['status'] != 'pass',
            'scope': 'runtime mutation sensitivity, not benchmark calibration; incomplete mutant evidence remains not_scored',
            'temporaryCandidateRemoved': True,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'detected': result['detected'], 'baseline': before['status'], 'mutant': after['status']}))
    return 0 if result['detected'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
