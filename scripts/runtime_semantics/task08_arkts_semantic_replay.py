#!/usr/bin/env python3
"""Replay the archived Task08 candidate without a model call or score feedback."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import verify_task08_arkts_strict as verifier
import test_verify_task08_arkts_strict as verifier_tests

NODE = '/Applications/DevEco-Studio.app/Contents/tools/node/bin/node'
ORIGINAL = ROOT / 'eval_runs/runtime_minimax_m3_20261020_fresh_v1'
OLD_REPORT = ORIGINAL / 'reports/arkts_08_threads_agent.json'
OLD_EVIDENCE = ORIGINAL / 'reports/arkts_08_threads_agent_task08_strict_evidence'
PATCH = ORIGINAL / 'patches/arkts_08_threads.patch'
BINARY_SUFFIXES = {'.hap', '.har', '.app', '.apk', '.abc', '.so'}


def load(path):
    return json.loads(path.read_text())


def record(path):
    data = path.read_bytes()
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def guard():
    free = shutil.disk_usage(ROOT).free
    if free < 8 * 1024**3:
        raise RuntimeError(f'8 GiB disk guard: {free / 1024**3:.3f} GiB available')
    return free


def run(command, output, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('Task08 semantic replay exhausted overall 3600s budget')
    with output.open('x') as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                timeout=remaining, check=False)
    if result.returncode:
        raise RuntimeError(f'Command failed ({result.returncode}); see {output}')


def cleanup(directory):
    removed = []
    for file in sorted(directory.rglob('*')):
        if file.is_file() and file.suffix.lower() in BINARY_SUFFIXES:
            removed.append(record(file))
            file.unlink()
    write(directory / 'binary-cleanup.json', {'hashesRecordedBeforeRemoval': True,
          'removed': removed, 'binariesRetained': False,
          'remaining': [str(p) for p in directory.rglob('*') if p.is_file() and p.suffix.lower() in BINARY_SUFFIXES]})


def replay(output, serial, roles=('base', 'final', 'agent'), selected_case='all'):
    guard()
    output.mkdir(parents=True, exist_ok=False)
    old = load(OLD_REPORT)
    contract = load(ROOT / 'benchmark_tasks/08_threads/transitions.json')
    cases = [case for case in contract['cases'] if selected_case == 'all' or case['caseId'] == selected_case]
    if not cases:
        raise ValueError('Unknown Task08 case selection')
    archived_build = load(OLD_EVIDENCE / 'build/device-build-report.json')
    protected = [OLD_REPORT, PATCH, ORIGINAL / 'eval_manifest.json', ORIGINAL / 'eval_manifest.partial.json',
                 ROOT / 'benchmark_tasks/08_threads/transitions.json']
    before = [record(p) for p in protected]
    for file in [OLD_REPORT, PATCH, ORIGINAL / 'eval_manifest.json', ORIGINAL / 'eval_manifest.partial.json']:
        target = output / 'original' / file.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, target)
    shutil.copytree(OLD_EVIDENCE, output / 'original/strict-evidence')
    write(output / 'original/source-hashes.json', before)
    task = load(ROOT / 'benchmark_tasks/08_threads/task.json')
    reports = {}
    errors = {}
    with tempfile.TemporaryDirectory(prefix='ltb-task08-archived-replay-') as temporary:
        candidate = Path(temporary) / 'candidate'
        shutil.copytree(ROOT / task['arkts']['basePath'], candidate,
                        ignore=shutil.ignore_patterns('.git', '.hvigor', 'build', 'oh_modules', 'node_modules'))
        subprocess.run(['git', 'init', '-q', str(candidate)], check=True)
        subprocess.run(['git', '-C', str(candidate), 'apply', '--check', str(PATCH)], check=True)
        subprocess.run(['git', '-C', str(candidate), 'apply', str(PATCH)], check=True)
        inventory = archived_build['nativeUIObserver']['production']
        actual = {str(p.relative_to(candidate)): record(p)['sha256']
                  for p in (candidate / 'entry/src/main').rglob('*') if p.is_file()}
        expected = {item['path']: item['sha256'] for item in inventory}
        if actual != expected:
            raise ValueError('Reconstructed production differs from archived evaluator candidate')
        write(output / 'candidate-reconstruction.json', {'exactArchivedProduction': True,
              'archivedBuildReport': record(OLD_EVIDENCE / 'build/device-build-report.json'),
              'patch': record(PATCH), 'production': inventory, 'newModelCall': False})
        sources = {'base': ROOT / task['arkts']['basePath'], 'final': ROOT / task['arkts']['finalPath'], 'agent': candidate}
        for role, source in sources.items():
            if role not in roles:
                continue
            deadline = time.monotonic() + 3600
            role_output = output / role
            role_output.mkdir()
            try:
                guard()
                run([NODE, str(ROOT / 'scripts/runtime_semantics/task08_arkts_strict_build.cjs'),
                     '--source', str(source), '--role', role, '--output-dir', str(role_output / 'build'),
                     '--case', selected_case,
                     '--timeout-seconds', '3600'], role_output / 'build.log', deadline)
                budget = max(1, math.floor(deadline - time.monotonic()) - 5)
                run([NODE, str(ROOT / 'scripts/runtime_semantics/task08_arkts_strict_execute.cjs'),
                     str(role_output / 'build/device-build-report.json'), serial, str(role_output / 'execute'),
                     '--timeout-seconds', str(budget)], role_output / 'execute.log', deadline)
                execution = load(role_output / 'execute/device-execution.json')
                if (execution.get('status') != 'transport_completed' or not execution.get('transportCompleted') or
                        not execution.get('candidateAbsentBeforeInstall') or not execution.get('cleanup', {}).get('ownedAppUninstalled')):
                    raise RuntimeError('Device transport/cleanup incomplete: ' + str(execution.get('error')))
                by_id = {row['caseId']: row for row in execution['rows']}
                if len(by_id) != len(cases) or any(by_id[c['caseId']]['traceDigest'] != c['traceDigest'] for c in cases):
                    raise RuntimeError('Canonical runtime case identity/digest mismatch')
                reports[role] = execution
                print(json.dumps({'role': role, 'counts': {status: sum(r['status'] == status for r in by_id.values())
                      for status in ('pass', 'fail', 'not_scored')}}), flush=True)
            except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
                errors[role] = str(error)
                print(json.dumps({'role': role, 'error': str(error)}), flush=True)
        if selected_case == 'all' and 'base' in reports and 'final' in reports:
            try:
                result = verifier.verify_matrix(output / 'base/build/device-build-report.json',
                         output / 'base/execute/device-execution.json', output / 'final/build/device-build-report.json',
                         output / 'final/execute/device-execution.json')
                write(output / 'independent-base-final-verifier.json', result)
                verifier_tests.BASE_BUILD = output / 'base/build/device-build-report.json'
                verifier_tests.BASE_EXECUTION = output / 'base/execute/device-execution.json'
                verifier_tests.FINAL_BUILD = output / 'final/build/device-build-report.json'
                verifier_tests.FINAL_EXECUTION = output / 'final/execute/device-execution.json'
                suite = unittest.defaultTestLoader.loadTestsFromTestCase(verifier_tests.VerifyTask08ArktsStrictTest)
                with (output / 'independent-verifier-tests.log').open('x') as log:
                    tested = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
                write(output / 'independent-verifier-tests.json', {
                    'testsRun': tested.testsRun, 'successful': tested.wasSuccessful(),
                    'mutationsRejected': 8 if tested.wasSuccessful() else None,
                    'failures': len(tested.failures), 'errors': len(tested.errors),
                    'verifiedBeforeBinaryCleanup': True})
                if not tested.wasSuccessful():
                    errors['calibration'] = 'Independent verifier regression/mutation tests failed'
            except ValueError as error:
                errors['calibration'] = str(error)
        rows = reports.get('agent', {}).get('rows')
        if rows is None:
            rows = [{'caseId': c['caseId'], 'traceDigest': c['traceDigest'], 'status': 'not_scored',
                     'reason': errors.get('agent', 'Runtime execution unavailable')} for c in cases]
        build_path = output / 'agent/build/device-build-report.json'
        build = load(build_path) if build_path.exists() else {}
        report = {'schemaVersion': 2, 'taskId': '08_threads', 'platform': 'arkts', 'role': 'agent',
                  'observationMode': 'runtime_state_transition', 'compile': old['compile'], 'codeGeneration': old['codeGeneration'],
                  'runtimeCompile': {'passed': build.get('runtimeCompile', {}).get('passed') is True,
                                     'scope': 'evaluator application and ohosTest packaging', 'artifactsRetained': False},
                  'semantic': {'cases': rows}, 'provenance': {'originalReport': before[0], 'archivedPatch': record(PATCH),
                    'exactCandidateProduction': inventory, 'newModelCall': False},
                  'diagnostics': {'errors': errors, 'caseSelection': selected_case, 'roles': list(roles),
                     'publishable': selected_case == 'all' and 'calibration' not in errors and
                     'base' in reports and 'final' in reports and all(r['status'] in ('pass', 'fail') for r in rows),
                     'benchmarkCompilePreserved': True}}
        write(output / 'arkts_08_threads_agent.semantic-replay.json', report)
    # Task09 legitimately updates shared run manifests while this replay is active.
    immutable = [p for p in protected if p.name not in {'eval_manifest.json', 'eval_manifest.partial.json'}]
    if [record(p) for p in immutable] != [r for r in before if Path(r['path']) in immutable]:
        raise ValueError('Protected old Task08 evidence, patch or contract changed')
    cleanup(output)
    write(output / 'completion.json', {'oldEvidenceUnchanged': True, 'modelRun': False,
          'candidateRemoved': True, 'errors': errors, 'semantic': {
              role: {s: sum(r['status'] == s for r in execution['rows']) for s in ('pass', 'fail', 'not_scored')}
              for role, execution in reports.items()}, 'freeBytes': shutil.disk_usage(ROOT).free})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--serial', default='127.0.0.1:5555')
    parser.add_argument('--roles', nargs='+', choices=('base', 'final', 'agent'), default=['base', 'final', 'agent'])
    parser.add_argument('--case', default='all')
    args = parser.parse_args()
    replay(args.output.resolve(), args.serial, args.roles, args.case)
