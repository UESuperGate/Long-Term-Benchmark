#!/usr/bin/env python3
"""Compatibility entrypoint for runtime-only scoring from existing agent runners."""

import argparse
from contextlib import contextmanager
import hashlib
import importlib
import json
import math
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from pathlib import Path

from run_runtime_transition_matrix import ROOT, NODE, unavailable, validate_report, write, load
from runtime_semantics.task09_formal_agent import score as task09_formal_score
from runtime_semantics.task16_android_strict_agent import score as task16_android_strict_score
from runtime_semantics.task16_arkts_strict_agent import score as task16_arkts_strict_score
from runtime_semantics.task17_android_strict_agent import score as task17_android_strict_score
from runtime_semantics.task17_arkts_strict_agent import score as task17_arkts_strict_score


FORMAL_AGENT_TASKS = {f'{number:02d}' for number in range(10, 18)}
FORMAL_AGENT_READINESS = ROOT / 'scripts/runtime_semantics/formal_agent_readiness.json'
CALIBRATED_AGENT_MODULES = {
    f'task{number}_formal_agent_v1': f'runtime_semantics.task{number}_formal_agent'
    for number in range(10, 16)
}


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _retain_task08_evidence(temporary_root, evidence_root, platform='arkts'):
    if evidence_root.exists():
        raise RuntimeError(f'Refusing existing Task08 strict evidence: {evidence_root}')
    evidence_root.parent.mkdir(parents=True, exist_ok=True)
    relocations = None
    if platform == 'arkts':
        binary_suffixes = {'.hap', '.har', '.app', '.apk', '.abc', '.so'}
        inventory, binaries = [], []
        for file in sorted(item for item in temporary_root.rglob('*') if item.is_file()):
            item = {'path': str(file.resolve()), 'bytes': file.stat().st_size, 'sha256': _sha256(file)}
            if file.suffix.lower() in binary_suffixes:
                binaries.append(item)
            else:
                inventory.append((file.relative_to(temporary_root), item))
        shutil.copytree(temporary_root, evidence_root, ignore=lambda directory, names: [
            name for name in names if (Path(directory) / name).is_file() and
            Path(name).suffix.lower() in binary_suffixes])
        mapping = []
        for relative, original in inventory:
            retained = evidence_root / relative
            if retained.stat().st_size != original['bytes'] or _sha256(retained) != original['sha256']:
                raise ValueError('Task08 evidence changed during byte-preserving relocation')
            mapping.append({'originalPath': original['path'], 'retained': {
                **original, 'path': str(retained.resolve())}})
        relocation_path = evidence_root / 'path-relocations.json'
        write(relocation_path, {'schemaVersion': 1, 'taskId': '08_threads',
                               'originalRoot': str(temporary_root.resolve()),
                               'retainedRoot': str(evidence_root.resolve()),
                               'files': mapping, 'removedBinaryArtifacts': binaries})
        relocations = {'path': str(relocation_path.resolve()), 'bytes': relocation_path.stat().st_size,
                       'sha256': _sha256(relocation_path)}
    else:
        shutil.copytree(temporary_root, evidence_root, ignore=shutil.ignore_patterns('*.hap'))
    files = []
    for file in sorted(item for item in evidence_root.rglob('*') if item.is_file()):
        files.append({'path': str(file.relative_to(evidence_root)), 'bytes': file.stat().st_size,
                      'sha256': _sha256(file)})
    manifest = {'schemaVersion': 1, 'taskId': '08_threads', 'platform': platform,
                'hapsRetained': False,
                'temporaryBuildRemoved': True, 'files': files}
    write(evidence_root / 'evidence-manifest.json', manifest)
    retained = {'path': str(evidence_root), 'manifest': str(evidence_root / 'evidence-manifest.json'),
                'manifestSha256': _sha256(evidence_root / 'evidence-manifest.json')}
    if relocations:
        retained['relocations'] = relocations
    return retained


def _retain_task17_evidence(temporary_root, evidence_root):
    if evidence_root.exists():
        raise RuntimeError(f'Refusing existing Task17 strict evidence: {evidence_root}')
    evidence_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(temporary_root, evidence_root, ignore=shutil.ignore_patterns('*.hap'))
    files = []
    for file in sorted(item for item in evidence_root.rglob('*') if item.is_file()):
        files.append({'path': str(file.relative_to(evidence_root)), 'bytes': file.stat().st_size,
                      'sha256': _sha256(file)})
    manifest = {'schemaVersion': 1, 'taskId': '17_pinned_messages', 'hapsRetained': False,
                'temporaryBuildRemoved': True, 'files': files}
    write(evidence_root / 'evidence-manifest.json', manifest)
    return {'path': str(evidence_root), 'manifest': str(evidence_root / 'evidence-manifest.json'),
            'manifestSha256': _sha256(evidence_root / 'evidence-manifest.json')}


def _remaining(deadline, phase):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise subprocess.TimeoutExpired(phase, 0)
    return remaining


def _task08_device_serial(requested, deadline):
    if requested:
        return requested
    hdc = Path.home() / 'Library/OpenHarmony/Sdk/23/toolchains/hdc'
    remaining = _remaining(deadline, 'Task08 API23 device discovery')
    completed = subprocess.run([str(hdc), 'list', 'targets'], capture_output=True, text=True,
                               timeout=min(remaining, 30), check=False)
    targets = [line.strip() for line in completed.stdout.splitlines()
               if line.strip() and line.strip() != '[Empty]']
    if completed.returncode or len(targets) != 1:
        raise RuntimeError(f'Expected one API23 device, found {targets!r}')
    return targets[0]


def _task17_device_serial(requested, deadline):
    if requested:
        return requested
    hdc = Path.home() / 'Library/OpenHarmony/Sdk/23/toolchains/hdc'
    remaining = _remaining(deadline, 'Task17 API23 device discovery')
    completed = subprocess.run([str(hdc), 'list', 'targets'], capture_output=True, text=True,
                               timeout=min(remaining, 30), check=False)
    targets = [line.strip() for line in completed.stdout.splitlines()
               if line.strip() and line.strip() != '[Empty]']
    if completed.returncode or len(targets) != 1:
        raise RuntimeError(f'Expected one API23 device, found {targets!r}')
    return targets[0]


def _task17_device_locks(serial):
    name = 'ltb-arkts-device-' + hashlib.sha256(serial.encode()).hexdigest()[:16]
    return Path('/tmp') / name, Path(tempfile.gettempdir()) / name


def _acquire_task17_device_lock(serial, deadline):
    coordination, transport = _task17_device_locks(serial)
    while True:
        _remaining(deadline, 'Task17 shared device lock')
        if coordination.exists() or transport.exists():
            time.sleep(min(2, _remaining(deadline, 'Task17 shared device lock')))
            continue
        try:
            coordination.mkdir()
            return coordination
        except FileExistsError:
            time.sleep(min(2, _remaining(deadline, 'Task17 shared device lock')))


def _benchmark_compile(args):
    return {'passed': None if args.compile_passed is None else args.compile_passed == 'true',
            'command': args.compile_command, 'scope': 'candidate_application_build'}


def _formal_agent_cell(task_id, platform):
    if task_id[:2] not in FORMAL_AGENT_TASKS:
        return None
    audit = load(FORMAL_AGENT_READINESS)
    return next((cell for cell in audit['cells']
                 if cell['taskId'] == task_id and cell['platform'] == platform), None)


def _unready_formal_agent(args, cell):
    reason = ('Formal agent scorer is not publishable for this task/platform: ' +
              cell['adapterGap'])
    report = unavailable(args.task, args.platform, args.role, reason)
    report['compile'] = _benchmark_compile(args)
    report['runtimeCompile'] = {
        'passed': None,
        'status': 'not_run',
        'scope': 'strict_evaluator_packaging_and_runtime',
        'reason': 'Strict source-parameterized evaluator was not started.',
    }
    report['diagnostics'].update({
        'adapter': 'not_ready',
        'transport': 'not_run',
        'publishable': False,
        'benchmarkCompilePreserved': True,
        'formalAgentReadiness': cell,
        'readinessManifest': str(FORMAL_AGENT_READINESS),
    })
    return report


def _task08_arkts_agent(args, deadline):
    from runtime_semantics.task08_arkts_entry_evidence import validate_report_evidence

    contract = load(ROOT / 'benchmark_tasks/08_threads/transitions.json')
    evidence_root = args.output.resolve().parent / (args.output.stem + '_task08_strict_evidence')
    compile_passed = False
    failure = None
    build_data = None
    execution = None
    with tempfile.TemporaryDirectory(prefix='ltb-task08-agent-') as temporary:
        temporary_root = Path(temporary)
        build_root = temporary_root / 'build'
        execute_root = temporary_root / 'execute'
        build_remaining = _remaining(deadline, 'Task08 strict runtime build')
        if build_remaining <= 6:
            raise subprocess.TimeoutExpired('Task08 strict runtime build', build_remaining)
        build_budget = min(3600, max(1, int(build_remaining) - 5))
        build_command = [NODE, str(ROOT / 'scripts/runtime_semantics/task08_arkts_strict_build.cjs'),
                         '--source', str(args.source.resolve()), '--role', 'agent', '--case', 'all',
                         '--output-dir', str(build_root), '--timeout-seconds', str(build_budget)]
        completed = subprocess.run(build_command, cwd=ROOT, timeout=build_remaining, check=False)
        build_report = build_root / 'device-build-report.json'
        if completed.returncode or not build_report.exists():
            failure = f'Task08 candidate application/ohosTest build failed with exit {completed.returncode}'
        else:
            build_data = load(build_report)
            compile_passed = bool(build_data.get('standaloneAppCompile', {}).get('passed') and
                                  build_data.get('ohosTestCompile', {}).get('passed'))
            if Path(build_data.get('source', '')).resolve() != args.source.resolve():
                failure = 'Task08 packaged source differs from the supplied standalone candidate'
            elif not compile_passed:
                failure = 'Task08 candidate application/ohosTest compile provenance is incomplete'
            else:
                try:
                    serial = _task08_device_serial(args.device_serial, deadline)
                    execute_remaining = _remaining(deadline, 'Task08 strict device execution')
                    if execute_remaining <= 6:
                        raise subprocess.TimeoutExpired('Task08 strict device execution', execute_remaining)
                    execute_budget = min(3600, max(1, int(execute_remaining) - 5))
                    execute_command = [NODE, str(ROOT / 'scripts/runtime_semantics/task08_arkts_strict_execute.cjs'),
                                       str(build_report), serial, str(execute_root),
                                       '--timeout-seconds', str(execute_budget)]
                    completed = subprocess.run(execute_command, cwd=ROOT, timeout=execute_remaining, check=False)
                    execution_report = execute_root / 'device-execution.json'
                    if completed.returncode or not execution_report.exists():
                        failure = f'Task08 strict device execution failed with exit {completed.returncode}'
                    else:
                        execution = load(execution_report)
                        if execution.get('status') != 'transport_completed' or not execution.get('transportCompleted'):
                            failure = f"Task08 strict device transport incomplete: {execution.get('error', execution.get('status'))}"
                except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                    failure = f'Task08 strict device environment failed: {error}'
        retained = _retain_task08_evidence(temporary_root, evidence_root)

    if failure:
        report = unavailable('08_threads', 'arkts', 'agent', failure)
        report['compile'] = _benchmark_compile(args)
        report['runtimeCompile'] = {'passed': compile_passed,
                                    'scope': 'strict evaluator temporary application and ohosTest packaging'}
        report['diagnostics'].update({'publishable': False, 'strictEvidence': retained,
                                      'benchmarkCompilePreserved': True})
        return report

    rows = execution.get('rows', [])
    report = {
        'schemaVersion': 2, 'taskId': '08_threads', 'platform': 'arkts', 'role': 'agent',
        'observationMode': 'runtime_state_transition',
        'compile': _benchmark_compile(args),
        'runtimeCompile': {'passed': True,
                           'scope': 'strict evaluator temporary application and ohosTest packaging',
                           'standaloneApp': build_data['standaloneAppCompile'],
                           'ohosTest': build_data['ohosTestCompile'], 'artifactsRetained': False},
        'semantic': {'cases': rows},
        'provenance': {'candidateMode': 'standalone_directory',
                       'candidateSource': str(args.source.resolve()),
                       'productionSources': build_data['nativeUIObserver']['sources'],
                       'canonicalContractSha256': _sha256(ROOT / 'benchmark_tasks/08_threads/transitions.json'),
                       'strictEvidence': retained,
                       'task08Runtime': {
                           'build': {'path': str(evidence_root / 'build/device-build-report.json'),
                                     'sha256': _sha256(evidence_root / 'build/device-build-report.json')},
                           'execution': {'path': str(evidence_root / 'execute/device-execution.json'),
                                         'sha256': _sha256(evidence_root / 'execute/device-execution.json')}}},
        'diagnostics': {'adapter': 'ready', 'transport': execution['status'],
                        'publishable': _benchmark_compile(args)['passed'] is True and
                        len(rows) == len(contract['cases']) and
                        all(row.get('status') in {'pass', 'fail'} for row in rows),
                        'sharedEvaluator': 'state_tests/runtime/arkts/tasks08_11.cjs',
                        'temporaryHapsRemoved': True, 'benchmarkCompilePreserved': True},
    }
    validate_report_evidence(report, contract)
    return report


def _task08_android_agent(args, deadline):
    contract = load(ROOT / 'benchmark_tasks/08_threads/transitions.json')
    evidence_root = args.output.resolve().parent / (args.output.stem + '_task08_strict_evidence')
    strict_report = None
    failure = None
    with tempfile.TemporaryDirectory(prefix='ltb-task08-android-agent-') as temporary:
        temporary_root = Path(temporary)
        report_path = temporary_root / 'task08-android-strict.json'
        remaining = _remaining(deadline, 'Task08 Android strict runtime score')
        if remaining <= 6:
            raise subprocess.TimeoutExpired('Task08 Android strict runtime score', remaining)
        budget = min(3600, max(1, int(remaining) - 5))
        command = [
            'python3', str(ROOT / 'scripts/runtime_semantics/task08_android_strict.py'),
            '--source', str(args.source.resolve()), '--role', 'agent',
            '--output', str(report_path), '--timeout-seconds', str(budget),
        ]
        completed = subprocess.run(command, cwd=ROOT, timeout=remaining, check=False)
        if completed.returncode or not report_path.is_file():
            failure = f'Task08 Android strict evaluator failed with exit {completed.returncode}'
        else:
            strict_report = load(report_path)
            diagnostics = strict_report.get('diagnostics', {})
            rows = strict_report.get('semantic', {}).get('cases', [])
            if (diagnostics.get('strictReady') is not True or
                    diagnostics.get('adapter') != 'ready' or
                    diagnostics.get('transport') != 'transport_completed' or
                    strict_report.get('runtimeCompile', {}).get('passed') is not True or
                    len(rows) != len(contract['cases']) or
                    any(row.get('status') not in {'pass', 'fail'} for row in rows)):
                failure = diagnostics.get('reason') or 'Task08 Android strict evaluator was not score-ready'
        retained = _retain_task08_evidence(temporary_root, evidence_root, platform='android')

    if failure:
        report = unavailable('08_threads', 'android', 'agent', failure)
        report['compile'] = _benchmark_compile(args)
        report['runtimeCompile'] = ((strict_report or {}).get('runtimeCompile') or {
            'passed': False,
            'status': 'not_run',
            'scope': 'task08_strict_production_state_transition',
        })
        report['diagnostics'].update({
            'adapter': (strict_report or {}).get('diagnostics', {}).get('adapter', 'failed'),
            'transport': (strict_report or {}).get('diagnostics', {}).get('transport', 'failed'),
            'publishable': False,
            'strictEvidence': retained,
            'benchmarkCompilePreserved': True,
            'environmentFailureIsNotSemanticFailure': True,
        })
        return report

    rows = strict_report['semantic']['cases']
    strict_provenance = strict_report.get('provenance', {})
    runtime_provenance = strict_provenance.get('runtimeAdapter', {})
    return {
        'schemaVersion': 2,
        'taskId': '08_threads',
        'platform': 'android',
        'role': 'agent',
        'observationMode': 'runtime_state_transition',
        'compile': _benchmark_compile(args),
        'runtimeCompile': strict_report['runtimeCompile'],
        'semantic': {'cases': rows},
        'provenance': {
            **strict_provenance,
            'productionSources': runtime_provenance.get('productionSources', []),
            'evaluatorSources': runtime_provenance.get('evaluatorSources', []),
            'strictEvidence': retained,
        },
        'diagnostics': {
            'adapter': 'ready',
            'transport': 'transport_completed',
            'strictReady': True,
            'publishable': (_benchmark_compile(args)['passed'] is True and
                            len(rows) == len(contract['cases']) and
                            all(row.get('status') in {'pass', 'fail'} for row in rows)),
            'sharedEvaluator': 'state_tests/runtime/android/08_threads/adapter.json',
            'benchmarkCompilePreserved': True,
            'environmentFailureIsNotSemanticFailure': True,
        },
    }


def _task09_agent(args, deadline):
    remaining = _remaining(deadline, 'Task09 formal agent score')
    report = task09_formal_score(
        platform=args.platform,
        source=args.source,
        output=args.output.resolve(),
        timeout=remaining,
        compile_passed=args.compile_passed == 'true',
        compile_command=args.compile_command,
    )
    report.setdefault('diagnostics', {}).update({
        'publishable': report.get('publication', {}).get('eligible') is True,
        'benchmarkCompilePreserved': True,
        'centralDispatch': 'task09_formal_agent',
        'centralRemainingBudgetSeconds': remaining,
    })
    return report


def _strict_module_agent(args, deadline, scorer, handler, *, device=False):
    benchmark_compile = _benchmark_compile(args)
    if benchmark_compile['passed'] is not True:
        report = unavailable(args.task, args.platform, args.role,
                             'Standalone candidate application build did not pass')
        report['compile'] = benchmark_compile
        report['runtimeCompile'] = {'passed': None, 'status': 'not_run',
                                    'scope': 'strict evaluator packaging and runtime'}
        report['diagnostics'].update(publishable=False, benchmarkCompilePreserved=True,
                                     centralDispatch=handler)
        return report
    if device:
        report = scorer(args.source, args.output.resolve(), deadline, args.device_serial)
    else:
        report = scorer(args.source, args.output.resolve(), deadline)
    report['compile'] = benchmark_compile
    diagnostics = report.setdefault('diagnostics', {})
    diagnostics.update({
        'publishable': (report['compile']['passed'] is True and
                        diagnostics.get('publishableWithoutApplicationCompile') is True),
        'benchmarkCompilePreserved': True,
        'centralDispatch': handler,
    })
    return report


@contextmanager
def _calibration_sources(args, deadline):
    task = load(ROOT / 'benchmark_tasks' / args.task / 'task.json')
    if args.task == '12_report_room' and args.platform == 'arkts':
        sources = {role: (ROOT / task['arkts'][role + 'Path']).resolve() for role in ('base', 'final')}
        for source in sources.values():
            _remaining(deadline, 'Task12 receipt-bound original input verification')
            if not source.is_dir() or not source.is_relative_to(ROOT):
                raise ValueError('Task12 receipt-bound original source is unavailable')
        # The receipt binds these exact paths; the scorer checks their bytes itself.
        yield sources
        return
    with tempfile.TemporaryDirectory(prefix=f'ltb-{args.task}-calibration-') as raw:
        directory = Path(raw)
        sources = {}
        for role in ('base', 'final'):
            destination = directory / role
            if args.platform == 'android':
                archive = directory / (role + '.tar')
                environment = dict(os.environ, GIT_LFS_SKIP_SMUDGE='1')
                subprocess.run([
                    'git', '-C', str(ROOT / '_sources/element-x-android'), 'archive',
                    '--format=tar', '--output=' + str(archive), task['android'][role + 'Commit'],
                ], env=environment, timeout=_remaining(deadline, 'immutable calibration archive'),
                   check=True, capture_output=True)
                destination.mkdir()
                with tarfile.open(archive) as stream:
                    stream.extractall(destination)
                archive.unlink()
            else:
                shutil.copytree(ROOT / task['arkts'][role + 'Path'], destination,
                                ignore=shutil.ignore_patterns(
                                    '.git', '.gradle', '.hvigor', '.idea', 'build', 'node_modules', 'oh_modules'))
            _remaining(deadline, role + ' calibration source preparation')
            sources[role] = destination
        yield sources


def _calibrated_module_agent(args, deadline, handler, scorer=None):
    benchmark_compile = _benchmark_compile(args)
    if benchmark_compile['passed'] is not True:
        report = unavailable(args.task, args.platform, args.role,
                             'Standalone candidate application build did not pass')
        report['compile'] = benchmark_compile
        report['runtimeCompile'] = {'passed': None, 'status': 'not_run',
                                    'scope': 'strict evaluator packaging and runtime'}
        report['diagnostics'].update(publishable=False, benchmarkCompilePreserved=True,
                                     centralDispatch=handler)
        return report
    runtime_path = str(ROOT / 'scripts/runtime_semantics')
    sys.path.insert(0, runtime_path)
    try:
        if scorer is None:
            scorer = importlib.import_module(CALIBRATED_AGENT_MODULES[handler]).score
        with _calibration_sources(args, deadline) as sources:
            receipt = None
            kwargs = {
                'platform': args.platform, 'source': args.source,
                'base_source': sources['base'], 'final_source': sources['final'],
                'output': args.output.resolve(),
                'timeout': _remaining(deadline, 'strict calibrated candidate score'),
                'compile_passed': True, 'compile_command': args.compile_command,
            }
            if args.task[:2] in {'12', '13', '14', '15'}:
                kwargs['device_serial'] = args.device_serial
            if args.task == '12_report_room' and args.platform == 'arkts':
                receipt = _task12_parent_control_receipt(args, sources, deadline)
                if receipt is not None:
                    kwargs['control_receipt'] = Path(receipt['path'])
                kwargs['timeout'] = _remaining(deadline, 'Task12 candidate score after private receipt verification')
            report = scorer(**kwargs)
            if receipt is not None:
                actual = report.get('provenance', {}).get('runtimeEvidence', {}).get('reviewedControlReceipt')
                scored = any(row.get('status') in {'pass', 'fail'}
                             for row in report.get('semantic', {}).get('cases', []))
                if ((actual is not None and actual != receipt) or
                        (actual is None and (scored or report.get('publication', {}).get('eligible') is True))):
                    _reject_task12_receipt_output(args.output.resolve())
                    raise ValueError('Task12 scorer result is not bound to the exact parent-verified control receipt')
    finally:
        sys.path.remove(runtime_path)
    report['compile'] = benchmark_compile
    report.setdefault('diagnostics', {}).update(
        publishable=report.get('publication', {}).get('eligible') is True,
        benchmarkCompilePreserved=True, centralDispatch=handler,
        calibrationTemporarySourcesRemoved=not (args.task == '12_report_room' and args.platform == 'arkts'),
    )
    if args.task == '12_report_room' and args.platform == 'arkts':
        report['diagnostics']['calibrationInputMode'] = 'receipt_bound_read_only_original_paths'
    return report


_TASK12_RECEIPT_MAX_BYTES = 16 * 1024 * 1024
_TASK12_RECEIPT_HASH_PROGRAM = '''import hashlib,json,os,stat,sys
fd=os.open(sys.argv[1],os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
with os.fdopen(fd,"rb") as stream:
 info=os.fstat(stream.fileno())
 if not stat.S_ISREG(info.st_mode) or not 0<info.st_size<=int(sys.argv[2]):
  raise ValueError("Invalid bounded receipt file")
 digest=hashlib.sha256(); size=0
 for block in iter(lambda:stream.read(65536),b""):
  size+=len(block)
  if size>int(sys.argv[2]): raise ValueError("Receipt size limit exceeded")
  digest.update(block)
 print(json.dumps({"bytes":size,"sha256":digest.hexdigest()}))
'''


def _reject_task12_receipt_output(output):
    retained = output.with_name(output.name + '.receipt-rejected-' + uuid.uuid4().hex + '.raw')
    if output.exists():
        os.replace(output, retained)
    # Original raw evidence is retained; the caller writes a separate NS result.


def _task12_parent_control_receipt(args, sources, deadline):
    cell = _formal_agent_cell(args.task, args.platform) or {}
    record = cell.get('reviewedControlReceipt')
    if record is None:
        # The actual Task12 scorer rejects absent receipts without fresh fallback.
        return None
    if (not isinstance(record, dict) or set(record) != {'path', 'bytes', 'sha256'} or
            not isinstance(record['path'], str) or type(record['bytes']) is not int or
            record['bytes'] <= 0 or not isinstance(record['sha256'], str) or
            len(record['sha256']) != 64 or any(char not in '0123456789abcdef' for char in record['sha256'])):
        raise ValueError('Invalid parent-only Task12 control receipt record')
    raw = Path(record['path'])
    path = raw if raw.is_absolute() else ROOT / raw
    path = Path(os.path.abspath(path))
    audit_root = ROOT / 'experiment_results'
    if not path.is_relative_to(audit_root):
        raise ValueError('Task12 control receipt must remain in the private evaluator audit root')
    current = ROOT
    for part in path.relative_to(ROOT).parts:
        current /= part
        if current.is_symlink():
            raise ValueError('Symlink in parent-only Task12 control receipt path')
    path = path.resolve(strict=True)
    if any(path.is_relative_to(Path(source).resolve()) for source in (args.source, *sources.values())):
        raise ValueError('Task12 control receipt must not be supplied inside candidate inputs')
    if record['bytes'] > _TASK12_RECEIPT_MAX_BYTES:
        raise ValueError('Task12 control receipt exceeds the private configuration size limit')
    result = subprocess.run([sys.executable, '-I', '-S', '-c', _TASK12_RECEIPT_HASH_PROGRAM,
                             str(path), str(_TASK12_RECEIPT_MAX_BYTES)],
                            cwd=ROOT, capture_output=True, text=True, check=True,
                            timeout=_remaining(deadline, 'Task12 private control receipt verification'))
    observed = json.loads(result.stdout)
    if observed != {key: record[key] for key in ('bytes', 'sha256')}:
        raise ValueError('Parent-only Task12 control receipt bytes changed')
    _remaining(deadline, 'Task12 private control receipt verification')
    return {**record, 'path': str(path)}


def _task17_arkts_agent(args, deadline, owner_bound=False):
    contract_path = ROOT / 'benchmark_tasks/17_pinned_messages/transitions.json'
    contract = load(contract_path)
    evidence_root = args.output.resolve().parent / (args.output.stem + '_task17_strict_evidence')
    failure = None
    runtime_compile_passed = False
    retained = None
    rows = []
    build_reports = []
    executions = []
    with tempfile.TemporaryDirectory(prefix='ltb-task17-agent-') as temporary:
        temporary_root = Path(temporary)
        try:
            for spec in contract['cases']:
                remaining = _remaining(deadline, f"Task17 strict build {spec['caseId']}")
                case_root = temporary_root / spec['caseId']
                builder = ('task17_arkts_owner_build.cjs' if owner_bound else
                           'task17_arkts_strict_build.cjs')
                command = [NODE, str(ROOT / 'scripts/runtime_semantics' / builder),
                           '--source', str(args.source.resolve()), '--role', 'agent',
                           '--case', spec['caseId'], '--output-dir', str(case_root)]
                completed = subprocess.run(command, cwd=ROOT, timeout=remaining, check=False)
                report_path = case_root / 'device-build-report.json'
                if completed.returncode or not report_path.exists():
                    raise RuntimeError(f"Task17 strict build failed for {spec['caseId']} with exit {completed.returncode}")
                build = load(report_path)
                if (build.get('runtimeCompile', {}).get('passed') is not True or
                        build.get('compile', {}).get('passed') is not True or
                        build.get('role') != 'agent' or build.get('caseId') != spec['caseId']):
                    raise RuntimeError(f"Task17 strict build provenance incomplete for {spec['caseId']}")
                build_reports.append((spec, report_path, build))
            runtime_compile_passed = True
            serial = _task17_device_serial(args.device_serial, deadline)
            for spec, report_path, build in build_reports:
                execution = None
                execution_path = None
                for attempt in range(1, 21):
                    coordination = _acquire_task17_device_lock(serial, deadline)
                    try:
                        remaining = _remaining(deadline, f"Task17 strict execute {spec['caseId']}")
                        execution_root = report_path.parent / f'execute-attempt-{attempt}'
                        command = [NODE, str(ROOT / 'scripts/runtime_semantics/arkts_device_execute.cjs'),
                                   str(report_path), serial, str(execution_root)]
                        environment = dict(os.environ)
                        environment['LTB_DEVICE_LOCK_PREACQUIRED'] = '1'
                        completed = subprocess.run(command, cwd=ROOT, env=environment,
                                                   timeout=remaining, check=False)
                        candidate_path = execution_root / 'device-execution.json'
                        candidate = load(candidate_path) if candidate_path.exists() else {}
                    finally:
                        if coordination.exists():
                            coordination.rmdir()
                    if completed.returncode == 0 and candidate_path.exists():
                        execution, execution_path = candidate, candidate_path
                        break
                    if 'EEXIST' in str(candidate.get('error', '')) and attempt < 20:
                        continue
                    raise RuntimeError(f"Task17 strict execution failed for {spec['caseId']} with exit "
                                       f"{completed.returncode}: {candidate.get('error', 'missing report')}")
                if execution is None or execution_path is None:
                    raise RuntimeError(f"Task17 strict execution exhausted lock retries for {spec['caseId']}")
                if (execution.get('status') != 'transport_completed' or
                        execution.get('transportCompleted') is not True or
                        execution.get('candidateAbsentBeforeInstall') is not True or
                        execution.get('cleanup', {}).get('ownedAppUninstalled') is not True):
                    raise RuntimeError(f"Task17 strict transport incomplete for {spec['caseId']}: " +
                                       str(execution.get('error', execution.get('status'))))
                matches = [row for row in execution.get('rows', [])
                           if row.get('caseId') == spec['caseId'] and
                           row.get('traceDigest') == spec['traceDigest']]
                if len(matches) != 1 or matches[0].get('status') not in {'pass', 'fail', 'not_scored'}:
                    raise RuntimeError(f"Task17 strict row identity incomplete for {spec['caseId']}")
                rows.append(matches[0])
                executions.append({'caseId': spec['caseId'], 'report': str(execution_path)})
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            failure = str(error)
        finally:
            retained = _retain_task17_evidence(temporary_root, evidence_root)

    if failure:
        report = unavailable('17_pinned_messages', 'arkts', 'agent', failure)
        report['compile'] = _benchmark_compile(args)
        report['runtimeCompile'] = {
            'passed': runtime_compile_passed,
            'status': 'passed' if runtime_compile_passed else 'failed',
            'scope': 'strict evaluator temporary candidate application and ohosTest packaging',
        }
        report['diagnostics'].update({'adapter': 'failed', 'transport': 'failed',
                                      'publishable': False, 'strictEvidence': retained,
                                      'benchmarkCompilePreserved': True,
                                      'environmentFailureIsNotSemanticFailure': True})
        return report

    report = {
        'schemaVersion': 2,
        'taskId': '17_pinned_messages',
        'platform': 'arkts',
        'role': 'agent',
        'observationMode': 'runtime_state_transition',
        'compile': _benchmark_compile(args),
        'runtimeCompile': {
            'passed': True,
            'status': 'passed',
            'scope': 'nine isolated strict evaluator candidate application and ohosTest packages',
            'builds': len(build_reports),
            'artifactsRetained': False,
        },
        'semantic': {'cases': rows},
        'provenance': {
            'candidateMode': 'standalone_directory',
            'candidateSource': str(args.source.resolve()),
            'canonicalContractSha256': _sha256(contract_path),
            'strictEvidence': retained,
            'executions': executions,
        },
        'diagnostics': {
            'adapter': 'ready',
            'transport': 'transport_completed',
            'publishable': (_benchmark_compile(args)['passed'] is True and
                            len(rows) == len(contract['cases']) and
                            all(row.get('status') in {'pass', 'fail'} for row in rows)),
            'sharedEvaluator': ('state_tests/runtime/arkts/native/Task17OwnerNativeUi.adapter.cjs'
                                if owner_bound else
                                'state_tests/runtime/arkts/native/Task17StrictNativeUi.adapter.cjs'),
            'ownerBoundCandidatePage': owner_bound,
            'temporaryHapsRemoved': True,
            'benchmarkCompilePreserved': True,
        },
    }
    return report


def _effective_task_deadline(args, started, parser):
    deadline = started + args.timeout
    internal = args.internal_deadline_monotonic
    if internal is not None:
        trusted = os.environ.get('LTB_TRUSTED_INTERNAL_DEADLINE')
        clock = os.environ.get('LTB_TRUSTED_INTERNAL_DEADLINE_CLOCK')
        if trusted is None or trusted != repr(internal) or not math.isfinite(internal) or clock != 'CLOCK_MONOTONIC':
            parser.error('Invalid or untrusted internal overall task deadline')
        local_now = time.monotonic()
        host_now = time.clock_gettime(time.CLOCK_MONOTONIC)
        remaining = internal - host_now
        if remaining <= 0 or remaining > args.timeout:
            parser.error('Internal overall task deadline expired or exceeds public budget')
        # Python 3.9 on macOS gives each process its own monotonic origin.
        # Translate the system-wide clock into this process without renewing it.
        deadline = min(deadline, local_now + remaining)
    return deadline


def main():
    score_started = time.monotonic()
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', required=True)
    parser.add_argument('--platform', required=True, choices=('android', 'arkts'))
    parser.add_argument('--role', required=True, choices=('base', 'final', 'agent'))
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--code-generated', default='false')
    parser.add_argument('--changed-production-file', action='append', default=[])
    parser.add_argument('--compile-passed', choices=('true', 'false'))
    parser.add_argument('--compile-command', default='not recorded')
    parser.add_argument('--timeout', type=int, default=3600)
    parser.add_argument('--internal-deadline-monotonic', type=float, help=argparse.SUPPRESS)
    parser.add_argument('--arkts-runtime', choices=('native', 'host'), default='native')
    parser.add_argument('--device-serial', help='Task08 ArkTS strict scorer device; unique API23 target is auto-detected')
    args = parser.parse_args()
    if args.role == 'agent' and args.timeout != 3600:
        parser.error('--timeout must be exactly 3600 seconds for a formal agent score')
    score_deadline = _effective_task_deadline(args, score_started, parser)
    strict_task08_agent = args.task == '08_threads' and args.role == 'agent'
    strict_task09_agent = args.task == '09_spaces_lifecycle' and args.role == 'agent'
    cell = _formal_agent_cell(args.task, args.platform)
    if args.role != 'agent' and cell is not None and not cell['ready']:
        report = _unready_formal_agent(args, cell)
        report['diagnostics']['publicCalibrationDispatch'] = 'disabled_without_legacy_fallback'
        write(args.output, report)
        print(json.dumps({'output': str(args.output), 'mode': report['observationMode'], 'publishable': False}))
        return 0
    formal_agent_cell = cell if args.role == 'agent' else None
    if (strict_task08_agent or strict_task09_agent) and args.source is None:
        parser.error('--source is required for an agent')
    if strict_task08_agent:
        try:
            handler = _task08_arkts_agent if args.platform == 'arkts' else _task08_android_agent
            report = handler(args, score_deadline)
            validate_report(report, load(ROOT / 'benchmark_tasks/08_threads/transitions.json'))
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            report = unavailable(args.task, args.platform, args.role, str(error))
            report['compile'] = _benchmark_compile(args)
            report['runtimeCompile'] = {'passed': False,
                                        'scope': ('strict evaluator temporary application and ohosTest packaging'
                                                  if args.platform == 'arkts' else
                                                  'task08_strict_production_state_transition')}
            report['diagnostics']['publishable'] = False
            report['diagnostics']['benchmarkCompilePreserved'] = True
        report['codeGeneration'] = {'passed': args.code_generated == 'true',
                                    'changedProductionFiles': args.changed_production_file}
        write(args.output, report)
        print(json.dumps({'output': str(args.output), 'mode': report['observationMode']}))
        return 0
    if strict_task09_agent:
        if args.compile_passed is None:
            parser.error('--compile-passed is required for a Task09 formal agent score')
        try:
            report = _task09_agent(args, score_deadline)
            validate_report(report, load(ROOT / 'benchmark_tasks/09_spaces_lifecycle/transitions.json'))
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, TimeoutError) as error:
            report = unavailable(args.task, args.platform, args.role, str(error))
            report['compile'] = _benchmark_compile(args)
            report['runtimeCompile'] = {
                'passed': False,
                'status': 'failed',
                'scope': 'evaluator_test_packaging_and_runtime_build',
            }
            report['diagnostics'].update({'publishable': False,
                                          'benchmarkCompilePreserved': True,
                                          'centralDispatch': 'task09_formal_agent'})
        report['codeGeneration'] = {'passed': args.code_generated == 'true',
                                    'changedProductionFiles': args.changed_production_file}
        write(args.output, report)
        print(json.dumps({'output': str(args.output), 'mode': report['observationMode'],
                          'publishable': report.get('publication', {}).get('eligible', False)}))
        return 0
    if formal_agent_cell is not None:
        if args.source is None:
            parser.error('--source is required for an agent')
        if formal_agent_cell['ready']:
            handler = formal_agent_cell.get('handler')
            try:
                if handler == 'task17_arkts_strict_agent_v1':
                    report = _task17_arkts_agent(args, score_deadline)
                elif handler == 'task17_arkts_owner_agent_v3':
                    report = _task17_arkts_agent(args, score_deadline, owner_bound=True)
                elif handler == 'task17_arkts_strict_agent_v2':
                    report = _strict_module_agent(
                        args, score_deadline, task17_arkts_strict_score, handler,
                        device=True)
                elif handler == 'task16_android_strict_agent_v1':
                    report = _strict_module_agent(
                        args, score_deadline, task16_android_strict_score, handler)
                elif handler == 'task16_arkts_strict_agent_v1':
                    report = _strict_module_agent(
                        args, score_deadline, task16_arkts_strict_score, handler,
                        device=True)
                elif handler == 'task17_android_strict_agent_v1':
                    report = _strict_module_agent(
                        args, score_deadline, task17_android_strict_score, handler)
                elif handler in CALIBRATED_AGENT_MODULES:
                    report = _calibrated_module_agent(args, score_deadline, handler)
                else:
                    raise RuntimeError(f'No formal agent handler implemented for {handler!r}')
                validate_report(report, load(ROOT / 'benchmark_tasks' / args.task / 'transitions.json'))
                report.setdefault('diagnostics', {})['centralDispatch'] = handler
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                report = unavailable(args.task, args.platform, args.role, str(error))
                report['compile'] = _benchmark_compile(args)
                report['runtimeCompile'] = {
                    'passed': False,
                    'status': 'failed',
                    'scope': 'strict evaluator packaging and runtime',
                }
                report['diagnostics'].update({'publishable': False,
                                              'benchmarkCompilePreserved': True})
            report['codeGeneration'] = {'passed': args.code_generated == 'true',
                                        'changedProductionFiles': args.changed_production_file}
            write(args.output, report)
            print(json.dumps({'output': str(args.output), 'mode': report['observationMode'],
                              'publishable': report.get('diagnostics', {}).get('publishable', False)}))
            return 0
        else:
            report = _unready_formal_agent(args, formal_agent_cell)
            report['codeGeneration'] = {'passed': args.code_generated == 'true',
                                        'changedProductionFiles': args.changed_production_file}
            validate_report(report, load(ROOT / 'benchmark_tasks' / args.task / 'transitions.json'))
            write(args.output, report)
            print(json.dumps({'output': str(args.output), 'mode': report['observationMode'],
                              'publishable': False}))
            return 0
    command = ([NODE, str(ROOT / 'scripts/runtime_semantics/arkts_runtime.cjs')]
               if args.platform == 'arkts' else ['python3', str(ROOT / 'scripts/runtime_semantics/android_runner.py')])
    command += ['--task', args.task, '--role', args.role, '--output', str(args.output.resolve())]
    if args.platform == 'android':
        command += ['--timeout', str(max(1, int(_remaining(score_deadline, 'runtime dispatch'))))]
    source = args.source
    if args.platform == 'arkts' and source is None:
        task = load(ROOT / 'benchmark_tasks' / args.task / 'task.json')
        if args.role == 'agent':
            parser.error('--source is required for an agent')
        source = ROOT / task['arkts']['basePath' if args.role == 'base' else 'finalPath']
    if source:
        command += ['--source', str(source.resolve())]
    native_report = None
    if args.platform == 'arkts' and args.arkts_runtime == 'native':
        evidence_root = args.output.resolve().parent / (args.output.stem + '_native')
        command = [NODE, str(ROOT / 'scripts/runtime_semantics/arkts_native_smoke.cjs'),
                   '--bundle', args.task, '--role', args.role, '--source', str(source.resolve()),
                   '--output-dir', str(evidence_root)]
        native_report = evidence_root / 'reports' / f'arkts_{args.task}_{args.role}.json'
    try:
        completed = subprocess.run(command, timeout=_remaining(score_deadline, 'runtime dispatch'), check=False)
        if native_report and native_report.exists() and completed.returncode == 0:
            write(args.output, load(native_report))
        if completed.returncode or not args.output.exists():
            raise RuntimeError(f'Runtime executor failed with exit {completed.returncode}')
        report = load(args.output)
        validate_report(report, load(ROOT / 'benchmark_tasks' / args.task / 'transitions.json'))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        report = unavailable(args.task, args.platform, args.role, str(error))
    report['codeGeneration'] = {'passed': args.code_generated == 'true', 'changedProductionFiles': args.changed_production_file}
    if args.compile_passed is not None:
        report['compile'] = {'passed': args.compile_passed == 'true', 'command': args.compile_command, 'scope': 'candidate_application_build'}
    write(args.output, report)
    print(json.dumps({'output': str(args.output), 'mode': report['observationMode']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
