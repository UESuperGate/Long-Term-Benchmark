#!/usr/bin/env python3
"""Task13-only retained page-owner validation; never invokes a model or central dispatcher."""
import argparse
import json
from pathlib import Path
import time
import traceback

try:
    from . import task13_arkts_strict_runtime as runtime
    from . import task12_13_formal_core as core
    from .task13_formal_agent import SPEC
except ImportError:
    import task13_arkts_strict_runtime as runtime
    import task12_13_formal_core as core
    from task13_formal_agent import SPEC


def deadline_for_budget(budget, *, epoch=None, monotonic=None):
    epoch = time.time() if epoch is None else epoch
    monotonic = time.monotonic() if monotonic is None else monotonic
    return monotonic + max(0, budget['startedEpoch'] + 3600 - epoch)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--role', choices=['base', 'final', 'agent'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--budget', type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.output.exists():
        raise FileExistsError('Never overwrite prior evidence')
    if not args.budget.exists():
        core.write(args.budget, {'startedMonotonic': time.monotonic(), 'startedEpoch': time.time(),
                                 'overallTimeoutSeconds': 3600, 'scope': 'all Task13 controls including shared-lock wait/build/runtime/cleanup'})
    budget = core.load(args.budget)
    deadline = deadline_for_budget(budget)
    started = time.monotonic()
    try:
        report = runtime.evaluate(task=SPEC, platform='arkts', source=args.source, role=args.role,
                                  output=args.output, deadline=deadline)
        report['readiness'] = False
        report['publication'] = 'pending independent fullraw page-owner verification and main public routing review'
    except (Exception, KeyboardInterrupt) as error:
        report = {'taskId': SPEC.task_id, 'platform': 'arkts', 'role': args.role,
                  'source': str(args.source.resolve()), 'status': 'failed_closed',
                  'error': str(error), 'traceback': traceback.format_exc(),
                  'semantic': {'total': 10, 'passed': 0, 'failed': 0, 'notScored': 10},
                  'compile': {'status': 'not_run', 'passed': None}, 'readiness': False}
    finally:
        evidence = args.output.with_suffix('.arkts-evidence')
        execution_path = evidence / 'device-execution-attempt-1/device-execution.json'
        runtime_evidence = report.get('provenance', {}).get('runtimeEvidence', {})
        if runtime_evidence.get('execution'):
            execution_path = Path(runtime_evidence['execution']['path'])
        if execution_path.exists() and report.get('semantic', {}).get('cases'):
            execution = core.load(execution_path)
            build_path = evidence / 'device-build/device-build-report.json'
            execution_record, build_record = core.file_record(execution_path), core.file_record(build_path)
            native_by_id = {}
            for artifact in execution.get('rowArtifacts', []):
                path = Path(artifact['local'])
                native_by_id[core.load(path)['caseId']] = core.file_record(path)
            logs = [core.file_record(execution_path.parent / command['log']) for command in execution.get('commands', [])]
            for row in report['semantic']['cases']:
                native_record = native_by_id[row['caseId']]
                row['nativeArtifacts'] = {
                    'execution': {'original': execution_record, 'retained': execution_record},
                    'build': {'original': build_record, 'retained': build_record},
                    'nativeResult': {'original': native_record, 'retained': native_record},
                    'commandLogs': [{'original': item, 'retained': item} for item in logs]}
        application_path = evidence / 'common-application-build/application-build.json'
        if application_path.exists():
            application = core.load(application_path)
            report['compile'] = {'passed': application.get('passed'),
                                 'status': 'passed' if application.get('passed') else 'failed',
                                 'scope': 'standalone production application HAP; no ohosTest injection',
                                 'report': core.file_record(application_path),
                                 'artifact': application.get('hap'), 'log': application.get('log'),
                                 'exitCode': application.get('exitCode')}
        else:
            report['compile'] = {'status': 'not_run', 'passed': None}
        cleanup = core.cleanup_artifacts(evidence)
        for path in sorted(evidence.rglob('*')):
            if path.is_file() and path.suffix.lower() in {'.har', '.app', '.abc', '.so', '.jar', '.o', '.dex', '.class'}:
                cleanup['binaryHashes'].append(core.file_record(path))
                path.unlink()
        cleanup['binariesRetained'] = any(path.suffix.lower() in core.BINARY_SUFFIXES | {'.har', '.app', '.abc', '.so', '.jar', '.o', '.dex', '.class'}
                                         for path in evidence.rglob('*') if path.is_file())
        core.write(evidence / 'cleanup.json', cleanup)
    report.setdefault('diagnostics', {})['cleanup'] = cleanup
    report['timing'] = {'overallElapsedSeconds': time.time() - budget['startedEpoch'],
                        'controlElapsedSeconds': time.monotonic() - started,
                        'overallTimeoutSeconds': 3600, 'deadlineShared': True}
    core.write(args.output, report)
    print(json.dumps({'output': str(args.output), 'semantic': {key: value for key, value in report['semantic'].items() if key != 'cases'},
                      'error': report.get('error'), 'timing': report['timing']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
