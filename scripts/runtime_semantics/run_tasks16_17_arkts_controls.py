#!/usr/bin/env python3
"""Run real base/final-copy controls through the same candidate-only device scorer."""
from __future__ import annotations

import argparse
from collections import Counter
import importlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.run_runtime_transition_matrix import validate_report
from scripts.runtime_semantics.tasks16_17_arkts_entry_evidence import record, require


def verify_control_report(report_path, input_path):
    report = json.loads(report_path.read_text())
    inputs = json.loads(input_path.read_text())
    contract = json.loads((ROOT / 'benchmark_tasks' / report['taskId'] / 'transitions.json').read_text())
    validate_report(report, contract)
    provenance = report['provenance']
    require(provenance['candidateSource'] == inputs['source'], 'control input directory differs')
    root = Path(provenance['strictEvidence']['path']).resolve()
    manifest_path = root / 'evidence-manifest.json'
    require(record(manifest_path)['sha256'] == provenance['strictEvidence']['manifestSha256'],
            'retained evidence manifest changed')
    for item in json.loads(manifest_path.read_text())['files']:
        path = (root / item['path']).resolve()
        require(path.is_relative_to(root) and record(path)['sha256'] == item['sha256'] and
                path.stat().st_size == item['bytes'], 'retained runtime artifact changed')
    inventory = {item['path']: item for item in inputs['files']}
    case_rows = {row['caseId']: row for row in report['semantic']['cases']}
    executions = provenance['executions']
    require([item['caseId'] for item in executions] == [spec['caseId'] for spec in contract['cases']],
            'control execution cases missing or reordered')
    identities = set()
    for item in executions:
        execution_path = (root / item['report']).resolve()
        require(execution_path.is_relative_to(root), 'execution path outside retained evidence')
        build_path = execution_path.parent.parent / 'device-build-report.json'
        raw_path = execution_path.parent / 'native-result.json'
        build, execution, raw = (json.loads(path.read_text()) for path in (build_path, execution_path, raw_path))
        require(execution.get('status') == 'transport_completed' and execution.get('transportCompleted') is True and
                execution.get('candidateAbsentBeforeInstall') is True and
                execution.get('cleanup', {}).get('ownedAppUninstalled') is True, 'incomplete fresh device execution')
        require(execution['rows'] == [raw] and execution['buildReport']['sha256'] == record(build_path)['sha256'] and
                execution['rowArtifact']['sha256'] == record(raw_path)['sha256'] and
                execution['rowArtifact']['bytes'] == raw_path.stat().st_size, 'raw execution identity changed')
        require(build['source'] == inputs['source'] and build['runtimeCompile']['passed'] is True and
                all(build.get(field) is True for field in
                    ('productionUnchanged', 'copiedProductionUnchanged', 'temporaryProjectRemoved')),
                'original application packaging incomplete')
        for source in build['production']:
            require(inventory.get(source['path'], {}).get('sha256') == source['sha256'],
                    'packaged source not in original standalone input')
            origin = Path(inputs['copiedFrom']) / source['path']
            require(record(origin)['sha256'] == source['sha256'], 'control origin changed since packaging')
        for fixture in build['nativeUIObserver']['fixtures']:
            path = Path(fixture['file']).resolve()
            require(path.is_relative_to(ROOT / 'state_tests/runtime/arkts') and
                    record(path)['sha256'] == fixture.get('sourceSha256', fixture['sha256']),
                    'executed evaluator differs from current reviewed module')
        for command in execution['commands']:
            path = (execution_path.parent / command['log']).resolve()
            require(path.is_relative_to(execution_path.parent) and record(path)['sha256'] == command['sha256'],
                    'device command log changed')
        identity = (execution.get('executionNonce'), execution.get('pid'))
        require(bool(identity[0]) and bool(identity[1]) and identity not in identities,
                'control reuses a device execution')
        identities.add(identity)
        row = case_rows[item['caseId']]
        if not row.get('entryFailureEvidence'):
            require(row == raw, 'final semantic row differs from actual native execution')
    return {'verified': True, 'report': record(report_path), 'input': record(input_path),
            'caseCount': len(identities), 'modelAgentResult': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', required=True, choices=('16_identity_reset', '17_pinned_messages'))
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--controls', nargs='+', choices=('base', 'final'), default=['base', 'final'])
    parser.add_argument('--device-serial')
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    task_file = ROOT / 'benchmark_tasks' / args.task / 'task.json'
    contract_file = task_file.with_name('transitions.json')
    task, contract = (json.loads(path.read_text()) for path in (task_file, contract_file))
    scorer = importlib.import_module('scripts.runtime_semantics.task' + args.task[:2] + '_arkts_strict_agent')
    started = time.monotonic()
    deadline = started + 3600
    summary = {'taskId': args.task, 'platform': 'arkts', 'modelAgentResult': False,
               'applicationCompile': 'not_credited_by_runtime_control',
               'canonicalContract': record(contract_file), 'controls': [], 'allReady': False}
    for original_role in args.controls:
        if shutil.disk_usage(output).free < 8 * 1024 ** 3:
            raise RuntimeError('Storage protection: need at least 8 GiB before device packaging')
        with tempfile.TemporaryDirectory(prefix='ltb-ui-control-') as raw:
            source = Path(raw).resolve() / 'candidate'
            origin = ROOT / task['arkts'][original_role + 'Path']
            shutil.copytree(origin, source, ignore=shutil.ignore_patterns(
                '.git', 'build', '.hvigor', '.gradle', '.idea', 'node_modules', 'oh_modules'))
            inventory = [record(path) for path in sorted(source.rglob('*')) if path.is_file()]
            for item in inventory:
                item['path'] = Path(item['path']).relative_to(source).as_posix()
            input_path = output / (original_role + '-input.json')
            input_path.write_text(json.dumps({'source': str(source), 'copiedFrom': str(origin),
                                             'role': 'agent', 'files': inventory}, indent=2) + '\n')
            report_path = output / (original_role + '-as-agent.json')
            report = scorer.score(source, report_path, deadline, args.device_serial)
            entry = {'copiedFrom': original_role, 'role': 'agent', 'source': str(source),
                     'report': record(report_path), 'input': record(input_path), 'validated': False}
            try:
                validate_report(report, contract)
                counts = Counter(row['status'] for row in report['semantic']['cases'])
                entry['counts'] = {key: counts[key] for key in ('pass', 'fail', 'not_scored')}
                expected = 'fail' if original_role == 'base' else 'pass'
                entry['validated'] = (counts[expected] == len(contract['cases']) and
                                      report['diagnostics']['publishableWithoutApplicationCompile'] is True)
            except (KeyError, OSError, ValueError) as error:
                entry['error'] = str(error)
            for item in inventory:
                current = record(source / item['path'])
                if any(current[key] != item[key] for key in ('sha256', 'bytes')):
                    raise ValueError('Runtime modified candidate source: ' + item['path'])
        entry['temporaryCandidateRemoved'] = not source.exists()
        summary['controls'].append(entry)
        summary['elapsedSeconds'] = round(time.monotonic() - started, 3)
        summary['requestedControlsValid'] = all(item['validated'] for item in summary['controls'])
        summary['allReady'] = (summary['requestedControlsValid'] and
                               {item['copiedFrom'] for item in summary['controls']} == {'base', 'final'})
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(json.dumps(entry), flush=True)
    return 0 if summary['requestedControlsValid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
